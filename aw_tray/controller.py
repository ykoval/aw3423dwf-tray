"""Runs all monitor I/O on one worker thread so the UI never blocks on DDC/CI."""
import queue
import threading
import time
from dataclasses import dataclass, replace

from . import hdr
from .ddc import Monitor
from .modes import (DARK_STABILIZER_BASE, DARK_STABILIZER_LEVELS, DARK_STABILIZER_QUERY, MODEL,
                    VCP_BRIGHTNESS, VCP_CONTRAST, VCP_DELL_COMMAND, VCP_HDR_ACTIVE, VCP_MODE,
                    name_for)


@dataclass(frozen=True)
class State:
    available: bool = False
    brightness: int | None = None
    contrast: int | None = None
    mode_e2: int | None = None
    hdr_on: bool = False
    hdr_supported: bool = False
    dark_stabilizer: int | None = None
    busy: str | None = None    # what is being switched right now
    message: str | None = None  # result of the last switch, e.g. a mismatch warning

    @property
    def mode_name(self):
        return name_for(self.mode_e2)


class Controller:
    def __init__(self, on_change):
        self._on_change = on_change
        self._monitor = Monitor(MODEL)
        self._jobs = queue.Queue()
        self._pending = {}  # latest slider value per VCP code, coalesced
        self._pending_lock = threading.Lock()
        self.state = State()
        threading.Thread(target=self._run, name="monitor-io", daemon=True).start()

    # --- public API, safe to call from any thread -------------------------------------

    def refresh(self):
        self._jobs.put(("refresh",))

    def set_brightness(self, value):
        self._queue_slider(VCP_BRIGHTNESS, value)

    def set_contrast(self, value):
        self._queue_slider(VCP_CONTRAST, value)

    def apply_mode(self, mode):
        self._jobs.put(("mode", mode))

    def set_hdr(self, enabled):
        self._jobs.put(("hdr", enabled))

    def set_dark_stabilizer(self, level):
        self._jobs.put(("dark_stabilizer", level))

    # --- worker -----------------------------------------------------------------------

    def _queue_slider(self, code, value):
        with self._pending_lock:
            first = code not in self._pending
            self._pending[code] = int(value)
        if first:
            self._jobs.put(("slider", code))

    def _publish(self, **changes):
        self.state = replace(self.state, **changes)
        self._on_change(self.state)

    def _run(self):
        while True:
            job = self._jobs.get()
            try:
                getattr(self, "_do_" + job[0])(*job[1:])
            except Exception as exc:  # keep the worker alive whatever happens
                self._publish(busy=None, message=f"Ошибка: {exc}")

    def _do_refresh(self):
        if not self._monitor.available():
            self._publish(available=False, busy=None,
                          message="Монитор не отвечает по DDC/CI (удалённый сеанс или монитор выключен)")
            return
        hdr_state = hdr.get_state(MODEL) or (False, False)
        self._publish(
            available=True,
            brightness=self._monitor.get(VCP_BRIGHTNESS),
            contrast=self._monitor.get(VCP_CONTRAST),
            mode_e2=self._monitor.get(VCP_MODE),
            hdr_supported=hdr_state[0],
            hdr_on=hdr_state[1],
            dark_stabilizer=self._read_dark_stabilizer(),
        )

    def _read_dark_stabilizer(self):
        # DDPM uses the same register, so a reply may belong to its query; only a
        # value in our range counts.
        for _ in range(5):
            self._monitor.set(VCP_DELL_COMMAND, DARK_STABILIZER_QUERY)
            time.sleep(0.2)
            level = (self._monitor.get(VCP_DELL_COMMAND, retries=1) or 0) - DARK_STABILIZER_BASE
            if level in DARK_STABILIZER_LEVELS:
                return level
            time.sleep(0.3)
        return None

    def _do_dark_stabilizer(self, level):
        self._publish(busy=f"Dark Stabilizer {level}", message=None)
        self._monitor.set(VCP_DELL_COMMAND, DARK_STABILIZER_BASE + level)
        time.sleep(0.5)
        got = self._read_dark_stabilizer()
        self._publish(dark_stabilizer=got, busy=None, message=None if got == level else
                      f"Монитор не подтвердил Dark Stabilizer {level}")

    def _do_slider(self, code):
        time.sleep(0.08)  # let a dragging slider settle so only the last value is sent
        with self._pending_lock:
            value = self._pending.pop(code, None)
        if value is None:
            return
        ok = self._monitor.set(code, value)
        field = "brightness" if code == VCP_BRIGHTNESS else "contrast"
        self._publish(**{field: value}, message=None if ok else "Монитор не принял значение")

    def _wait_for(self, code, expected, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._monitor.get(code, retries=1) == expected:
                return True
            time.sleep(0.4)
        return False

    def _switch_hdr(self, enabled):
        if not hdr.set_enabled(enabled, MODEL):
            return False
        # The monitor needs a few seconds to change its signal mode; until VCP 0xF2
        # flips it ignores mode writes and reports stale values.
        ready = self._wait_for(VCP_HDR_ACTIVE, 65 if enabled else 0, timeout=15)
        time.sleep(0.8)
        return ready

    def _do_hdr(self, enabled):
        self._publish(busy="HDR вкл…" if enabled else "HDR выкл…", message=None)
        ok = self._switch_hdr(enabled)
        self._do_refresh()
        self._publish(busy=None, message=None if ok else "Не удалось переключить HDR")

    def _do_mode(self, mode):
        self._publish(busy=mode.name, message=None)
        current_hdr = (hdr.get_state(MODEL) or (False, False))[1]
        if mode.hdr != current_hdr and not self._switch_hdr(mode.hdr):
            self._do_refresh()
            self._publish(busy=None, message="Не удалось переключить HDR")
            return
        self._monitor.set(mode.code, mode.value)
        confirmed = self._wait_for(VCP_MODE, mode.e2, timeout=6)
        self._do_refresh()  # brightness and contrast are stored per mode
        self._publish(busy=None, message=None if confirmed else
                      f"Монитор не подтвердил режим {mode.name}: сейчас {self.state.mode_name}")
