"""Live: pop the mouse icon at the cursor and REALLY click it via
SendInput -- the exact path the operator's click takes."""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
import qtranslate.qt.app as appmod
appmod.HISTORY_PATH = os.path.join(os.environ.get("TEMP", "/tmp"),
                                   "dbg_hist.json")
try:
    os.remove(os.path.join(os.environ.get("TEMP", "/tmp"),
                           "qt_mouse_debug.log"))
except OSError:
    pass

from qtranslate.qt.app import QtApp
from qtranslate.qt.main_window import MainWindow

app = QtApp([])
app._load_session()
app.source, app.target = "en", "vi"
app.win = MainWindow(app)
app.win.show()
app.qapp.processEvents()

u = ctypes.windll.user32


class _PT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


# pop the icon ABOVE-LEFT of the cursor, exactly as the drag-release does
pt = _PT()
u.GetCursorPos(ctypes.byref(pt))
print("cursor:", pt.x, pt.y)
app._show_mouse_icon(pt.x, pt.y, "good morning my friend")
app.qapp.processEvents()
icon = app._mouse_icon
print("icon visible:", icon.isVisible(),
      "geom:", icon.geometry().getRect())
g = icon.geometry()
cx, cy = g.x() + g.width() // 2, g.y() + g.height() // 2
print("clicking at", cx, cy)

u.SetCursorPos(cx, cy)
time.sleep(0.3)
for down, up in ((0x0002, 0x0004),):      # LEFTDOWN, LEFTUP
    u.mouse_event(down, cx, cy, 0, 0)
    time.sleep(0.05)
    u.mouse_event(up, cx, cy, 0, 0)

for _ in range(60):                        # 6s of pumping
    app.qapp.processEvents()
    time.sleep(0.1)
pop = getattr(app, "_popup", None)
print("popup:", pop, "visible:", pop.isVisible() if pop else "-")
log = os.path.join(os.environ.get("TEMP", "/tmp"), "qt_mouse_debug.log")
print("--- log ---")
print(open(log, encoding="utf-8").read() if os.path.exists(log)
      else "(no log -- the click never reached the handler)")
