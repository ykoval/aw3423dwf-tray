"""DDC/CI access to one physical monitor through dxva2."""
import ctypes
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
dxva2 = ctypes.windll.dxva2


class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [("hPhysicalMonitor", wintypes.HANDLE),
                ("szPhysicalMonitorDescription", wintypes.WCHAR * 128)]


MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                     ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)


def _enumerate():
    found = []

    def cb(hmon, hdc, rect, lparam):
        count = wintypes.DWORD()
        if dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)) and count.value:
            arr = (PHYSICAL_MONITOR * count.value)()
            if dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, arr):
                found.extend(arr)
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    return found


class Monitor:
    """Thread-safe handle to the monitor whose description contains name_hint.

    The handle is re-acquired after a failed call, which covers sleep, input
    switches and remote desktop sessions taking the display away.
    """

    def __init__(self, name_hint):
        self.name_hint = name_hint
        self.description = ""
        self._handle = None
        self._lock = threading.Lock()

    def _close(self):
        if self._handle:
            dxva2.DestroyPhysicalMonitor(self._handle)
        self._handle = None

    def _open(self):
        self._close()
        monitors = _enumerate()
        chosen = next((m for m in monitors if self.name_hint.lower() in m.szPhysicalMonitorDescription.lower()), None)
        for m in monitors:
            if m is not chosen:
                dxva2.DestroyPhysicalMonitor(m.hPhysicalMonitor)
        if chosen:
            self._handle = chosen.hPhysicalMonitor
            self.description = chosen.szPhysicalMonitorDescription
        return self._handle is not None

    def _read(self, code):
        cur, mx, typ = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
        if dxva2.GetVCPFeatureAndVCPFeatureReply(self._handle, code, ctypes.byref(typ),
                                                 ctypes.byref(cur), ctypes.byref(mx)):
            return cur.value
        return None

    def get(self, code, retries=3):
        with self._lock:
            for attempt in range(retries + 1):
                if not self._handle and not self._open():
                    return None
                value = self._read(code)
                if value is not None:
                    return value
                time.sleep(0.1)
                if attempt == retries - 1:
                    self._open()
            return None

    def set(self, code, value, retries=2):
        with self._lock:
            for _ in range(retries + 1):
                if not self._handle and not self._open():
                    return False
                if dxva2.SetVCPFeature(self._handle, code, value):
                    return True
                time.sleep(0.1)
                self._open()
            return False

    def available(self):
        with self._lock:
            return self._handle is not None or self._open()
