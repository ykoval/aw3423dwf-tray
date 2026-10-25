"""The flyout panel shown next to the tray icon, styled after Windows 11 flyouts."""
import ctypes
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import ttk

from .modes import DARK_STABILIZER_LEVELS, HDR_MODES, MODEL, SDR_MODES

BG = "#202020"
CARD = "#2b2b2b"
FG = "#ffffff"
MUTED = "#a0a0a0"
ACCENT = "#4cc2ff"
ACCENT_FG = "#000000"
WARN = "#ffb454"
FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI Semibold", 11)
COLUMNS = 3
USER_EDIT_GRACE = 1.5  # seconds a slider ignores monitor readings after the user moves it


def _work_area():
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right, rect.bottom


class Slider:
    def __init__(self, parent, label, on_change):
        self._on_change = on_change
        self._last_user_edit = 0.0
        self._setting = False
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(row, text=label, bg=CARD, fg=FG, font=FONT).pack(side="left")
        self._value_label = tk.Label(row, text="—", bg=CARD, fg=MUTED, font=FONT)
        self._value_label.pack(side="right")
        self._var = tk.DoubleVar(value=0)
        self._scale = ttk.Scale(parent, from_=0, to=100, variable=self._var,
                                command=self._moved, style="Panel.Horizontal.TScale")
        self._scale.pack(fill="x", padx=12, pady=(2, 8))

    def _moved(self, _):
        if self._setting:
            return
        value = round(self._var.get())
        self._value_label.config(text=str(value))
        self._last_user_edit = time.time()
        self._on_change(value)

    def show(self, value, enabled):
        self._scale.state(["!disabled"] if enabled else ["disabled"])
        if value is None or time.time() - self._last_user_edit < USER_EDIT_GRACE:
            return
        self._setting = True
        self._var.set(value)
        self._setting = False
        self._value_label.config(text=str(value))


class Panel:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.window = tk.Toplevel(root, bg=BG)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.bind("<Escape>", lambda e: self.hide())
        self.window.bind("<FocusOut>", self._focus_out)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Panel.Horizontal.TScale", background=CARD, troughcolor="#4a4a4a",
                        bordercolor=CARD, lightcolor=ACCENT, darkcolor=ACCENT, sliderthickness=14)

        outer = tk.Frame(self.window, bg=BG, highlightthickness=1, highlightbackground="#3c3c3c")
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(header, text=MODEL, bg=BG, fg=FG, font=FONT_TITLE).pack(side="left")
        self._mode_label = tk.Label(header, text="", bg=BG, fg=MUTED, font=FONT_SMALL)
        self._mode_label.pack(side="right")

        card = tk.Frame(outer, bg=CARD)
        card.pack(fill="x", padx=10, pady=4)
        self._brightness = Slider(card, "Яркость", controller.set_brightness)
        self._contrast = Slider(card, "Контрастность", controller.set_contrast)

        # On the window background, like the mode buttons, so unselected levels stay visible.
        stabilizer = tk.Frame(outer, bg=BG)
        stabilizer.pack(fill="x", padx=14, pady=(8, 0))
        tk.Label(stabilizer, text="Dark Stabilizer", bg=BG, fg=MUTED, font=FONT_SMALL).pack(side="left")
        self._stabilizer_buttons = {}
        for level in reversed(DARK_STABILIZER_LEVELS):
            button = tk.Button(stabilizer, text=str(level), font=FONT_SMALL, relief="flat", bd=0,
                               width=3, pady=2, cursor="hand2",
                               command=lambda lv=level: controller.set_dark_stabilizer(lv))
            button.pack(side="right", padx=(4, 0))
            self._stabilizer_buttons[level] = button

        self._mode_buttons = {}
        self._section(outer, "Режим", SDR_MODES)

        hdr_header = tk.Frame(outer, bg=BG)
        hdr_header.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(hdr_header, text="HDR", bg=BG, fg=MUTED, font=FONT_SMALL).pack(side="left")
        self._hdr_button = tk.Button(hdr_header, text="", font=FONT_SMALL, relief="flat", bd=0,
                                     padx=10, pady=2, cursor="hand2", command=self._toggle_hdr)
        self._hdr_button.pack(side="right")
        self._grid(outer, HDR_MODES)

        self._status = tk.Label(outer, text="", bg=BG, fg=MUTED, font=FONT_SMALL,
                                wraplength=300, justify="left", anchor="w")
        self._status.pack(fill="x", padx=14, pady=(8, 12))
        self._hdr_on = False
        self._hidden_at = 0.0

    def _section(self, parent, title, modes):
        tk.Label(parent, text=title, bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w").pack(
            fill="x", padx=14, pady=(10, 2))
        self._grid(parent, modes)

    def _grid(self, parent, modes):
        grid = tk.Frame(parent, bg=BG)
        grid.pack(fill="x", padx=10)
        for i in range(COLUMNS):
            grid.columnconfigure(i, weight=1, uniform="modes")
        for i, mode in enumerate(modes):
            button = tk.Button(grid, text=mode.name, font=FONT_SMALL, relief="flat", bd=0,
                               padx=4, pady=6, cursor="hand2",
                               command=lambda m=mode: self.controller.apply_mode(m))
            button.grid(row=i // COLUMNS, column=i % COLUMNS, sticky="ew", padx=2, pady=2)
            self._mode_buttons[mode.e2] = button

    def _toggle_hdr(self):
        self.controller.set_hdr(not self._hdr_on)

    def _focus_out(self, _):
        # FocusOut also fires when focus moves between widgets inside the panel.
        self.window.after(150, lambda: None if self.window.focus_get() else self.hide())

    # --- visibility -------------------------------------------------------------------

    def toggle(self):
        # Clicking the tray icon first steals focus and hides the panel; that click
        # should close it, not reopen it.
        if self.window.winfo_viewable():
            self.hide()
        elif time.time() - self._hidden_at > 0.4:
            self.show()

    def show(self):
        self.controller.refresh()
        self.window.update_idletasks()
        w, h = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        left, top, right, bottom = _work_area()
        x, y = right - w - 12, bottom - h - 12
        self.window.geometry(f"+{max(left, x)}+{max(top, y)}")
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def hide(self):
        if self.window.winfo_viewable():
            self._hidden_at = time.time()
        self.window.withdraw()

    # --- state ------------------------------------------------------------------------

    @staticmethod
    def _paint(button, active, enabled):
        button.config(bg=ACCENT if active else CARD, fg=ACCENT_FG if active else FG,
                      activebackground=ACCENT if active else "#3a3a3a",
                      activeforeground=ACCENT_FG if active else FG,
                      state="normal" if enabled else "disabled",
                      disabledforeground="#6a6a6a")

    def render(self, state):
        enabled = state.available and not state.busy
        self._brightness.show(state.brightness, enabled)
        self._contrast.show(state.contrast, enabled)
        selected = [(state.mode_e2, self._mode_buttons),
                    (state.dark_stabilizer, self._stabilizer_buttons)]
        for current, buttons in selected:
            for key, button in buttons.items():
                self._paint(button, key == current, enabled)
        self._hdr_on = state.hdr_on
        self._hdr_button.config(
            text="Вкл" if state.hdr_on else "Выкл",
            bg=ACCENT if state.hdr_on else CARD, fg=ACCENT_FG if state.hdr_on else FG,
            activebackground="#3a3a3a", activeforeground=FG,
            state="normal" if enabled and state.hdr_supported else "disabled")
        self._mode_label.config(text=state.mode_name or "")
        if state.busy:
            self._status.config(text=f"Переключаю: {state.busy}", fg=MUTED)
        elif state.message:
            self._status.config(text=state.message, fg=WARN)
        else:
            self._status.config(text="Режимы HDR сами включают HDR в Windows", fg=MUTED)
