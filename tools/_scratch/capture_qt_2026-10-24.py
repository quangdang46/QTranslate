"""Capture the running Qt app's windows to PNGs, for the operator to view.

One-off (2026-10-24, at the operator's request): main window, the aux
windows, the popup, and every Options page -- each via QWidget.grab(),
which reads the widget's own pixels and needs no screen-recording
permission and no window focus. Written to
docs/review/screenshots_2026-10-24/.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "docs", "review", "screenshots_2026-10-24")
os.makedirs(OUT, exist_ok=True)

from qtranslate.qt.app import QtApp                      # noqa: E402
from qtranslate.qt.main_window import MainWindow         # noqa: E402

app = QtApp([])
app._load_session()
app.win = MainWindow(app)
app.win.show()
app.qapp.processEvents()


def grab(widget, name):
    pix = widget.grab()
    path = os.path.join(OUT, name + ".png")
    pix.save(path)
    print("ok", name, pix.width(), "x", pix.height())
    return path


grab(app.win, "01_main_window")

# the popup: show it with text, then grab
try:
    app.show_translation("Good morning", "Chào buổi sáng", provider="google")
    app.qapp.processEvents()
    if getattr(app, "_popup", None) is not None:
        grab(app._popup, "02_popup")
        app._popup.close()
except Exception as exc:                                 # noqa: BLE001
    print("popup SKIP:", type(exc).__name__, str(exc)[:80])

# aux windows through the app's own openers
for attr, holder, name in (("open_dictionary", "_dict", "03_dictionary"),
                           ("open_history", "_hist", "04_history"),
                           ("open_keyboard", "_kbd", "05_keyboard")):
    try:
        getattr(app, attr)()
        app.qapp.processEvents()
        w = getattr(app, holder, None)
        if w is not None:
            grab(w, name)
            w.close()
            setattr(app, holder, None)
    except Exception as exc:                             # noqa: BLE001
        print(name, "SKIP:", type(exc).__name__, str(exc)[:100])

# every Options page, through the real shell
from qtranslate.qt.options import OptionsDialog          # noqa: E402
from qtranslate.qt.options.base import SIDEBAR            # noqa: E402
dlg = OptionsDialog(app)
dlg.show()
app.qapp.processEvents()
for page in SIDEBAR:
    try:
        dlg._goto(page)
        app.qapp.processEvents()
        grab(dlg, "10_options_" + page.lower())
    except Exception as exc:                             # noqa: BLE001
        print(page, "SKIP:", type(exc).__name__, str(exc)[:80])
dlg.close()

app.win.close()
print("DONE ->", OUT)
