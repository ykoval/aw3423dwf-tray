"""Opens the real panel against the monitor, waits for data, saves a screenshot of it."""
import ctypes
import sys
import tkinter as tk

from PIL import ImageGrab

from aw_tray.controller import Controller
from aw_tray.panel import Panel

out = sys.argv[1] if len(sys.argv) > 1 else "panel.png"
ctypes.windll.shcore.SetProcessDpiAwareness(2)
root = tk.Tk()
root.withdraw()
panel = None
controller = Controller(on_change=lambda s: root.after(0, panel.render, s))
panel = Panel(root, controller)
panel.window.unbind("<FocusOut>")  # the shot must not depend on keeping focus
panel.show()


def shoot():
    w = panel.window
    box = (w.winfo_rootx(), w.winfo_rooty(), w.winfo_rootx() + w.winfo_width(), w.winfo_rooty() + w.winfo_height())
    ImageGrab.grab(bbox=box, all_screens=True).save(out)
    print("state:", controller.state)
    root.destroy()


root.after(4000, shoot)
root.mainloop()
