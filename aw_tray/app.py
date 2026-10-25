"""Tray icon entry point: left click opens the panel, right click shows the menu."""
import ctypes
import queue
import sys
import threading
import tkinter as tk
import winreg

import pystray
from PIL import Image, ImageDraw

from .controller import Controller
from .modes import DARK_STABILIZER_LEVELS, HDR_MODES, MODEL, SDR_MODES
from .panel import Panel

APP_NAME = "AW Monitor Tray"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _single_instance():
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\AWMonitorTray")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def _icon_image():
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    outline, fill = (20, 20, 20, 255), (235, 235, 235, 255)
    # Curved-ultrawide screen with a stand, outlined so it reads on light and dark taskbars.
    d.rounded_rectangle((4, 12, 60, 44), radius=6, fill=fill, outline=outline, width=3)
    d.rectangle((11, 19, 53, 37), fill=(76, 194, 255, 255))
    d.rectangle((28, 44, 36, 52), fill=fill, outline=outline, width=2)
    d.rounded_rectangle((18, 51, 46, 58), radius=3, fill=fill, outline=outline, width=2)
    return img


# --- autostart (only meaningful for the packaged .exe) -------------------------------

def _autostart_command():
    return f'"{sys.executable}"' if getattr(sys, "frozen", False) else None


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, APP_NAME)[0] == _autostart_command()
    except OSError:
        return False


def set_autostart(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled and _autostart_command():
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


class App:
    def __init__(self):
        # Sharp text on high-DPI screens; must happen before any window exists.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        self.root = tk.Tk()
        self.root.withdraw()
        self._ui_calls = queue.Queue()  # tray and worker threads hand work to the Tk thread here
        self.controller = Controller(on_change=self._state_changed)
        self.panel = Panel(self.root, self.controller)
        self.icon = pystray.Icon(APP_NAME, _icon_image(), f"{MODEL}", menu=self._menu())

    def _state_changed(self, state):
        self._call(self.panel.render, state)
        self.icon.title = f"{MODEL}: {state.mode_name}" if state.mode_name else MODEL
        self.icon.update_menu()  # re-evaluates the radio checks

    def _call(self, fn, *args):
        self._ui_calls.put((fn, args))

    def _pump(self):
        while True:
            try:
                fn, args = self._ui_calls.get_nowait()
            except queue.Empty:
                break
            fn(*args)
        self.root.after(50, self._pump)

    def _menu(self):
        def mode_item(mode):
            return pystray.MenuItem(
                mode.name, lambda: self.controller.apply_mode(mode),
                checked=lambda _: self.controller.state.mode_e2 == mode.e2, radio=True)

        # pystray picks the call signature from the argument count, so actions take none.
        def stabilizer_item(level):
            return pystray.MenuItem(
                f"Level {level}", lambda: self.controller.set_dark_stabilizer(level),
                checked=lambda _: self.controller.state.dark_stabilizer == level, radio=True)

        return pystray.Menu(
            pystray.MenuItem("Open panel", lambda: self._call(self.panel.toggle), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Mode", pystray.Menu(*[mode_item(m) for m in SDR_MODES])),
            pystray.MenuItem("HDR mode", pystray.Menu(*[mode_item(m) for m in HDR_MODES])),
            pystray.MenuItem("Dark Stabilizer", pystray.Menu(
                *[stabilizer_item(lv) for lv in DARK_STABILIZER_LEVELS])),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start with Windows",
                             lambda: set_autostart(not autostart_enabled()),
                             checked=lambda _: autostart_enabled(),
                             enabled=_autostart_command() is not None),
            pystray.MenuItem("Quit", self._quit),
        )

    def _quit(self):
        self.icon.stop()
        self._call(self.root.destroy)

    def run(self):
        threading.Thread(target=self.icon.run, name="tray", daemon=True).start()
        self.controller.refresh()
        self.root.after(50, self._pump)
        self.root.mainloop()


def main():
    if not _single_instance():
        return
    App().run()


if __name__ == "__main__":
    main()
