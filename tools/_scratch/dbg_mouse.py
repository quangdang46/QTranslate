"""One-off: prove where the mouse-capture chain breaks, on the real desktop.

Runs the REAL app (no offscreen), enables the mouse capture, prints each
link: hook installed? gate ok? capture returns text? icon shows?
"""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from qtranslate import mouse_capture as mc
from qtranslate.qt.app import QtApp
from qtranslate.qt.main_window import MainWindow

app = QtApp([])
app._load_session()
app.source, app.target = "en", "vi"
app.win = MainWindow(app)
app.win.show()
app.qapp.processEvents()

pt = ctypes.wintypes.POINT() if hasattr(ctypes, "wintypes") else None
u = ctypes.windll.user32
class _PT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
p = _PT()
u.GetCursorPos(ctypes.byref(p))
print("cursor now at", p.x, p.y)

print("mc.available:", mc.available())
app._mouse_enabled = True
app.set_mouse_mode("Show icon")
print("after sync: hook handle =", bool(mc._handle),
      "enabled =", app._mouse_enabled,
      "mode =", app.mouse_mode)
print("gate ok:", app._mouse_gate_ok())

txt = app._capture_selection(p.x, p.y)
print("capture at cursor ->", repr(txt)[:120])

shown = {}
app._show_mouse_icon(p.x, p.y, txt or "DEBUG icon under the cursor")
app.qapp.processEvents()
print("mouse icon visible:", getattr(app._mouse_icon, "isVisible", None))

for _ in range(40):          # keep alive 4s so the icon is on screen
    app.qapp.processEvents()
    time.sleep(0.1)
print("done")
