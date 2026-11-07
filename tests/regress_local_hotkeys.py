#!/usr/bin/env python3
""".tmp LOCAL hotkeys (HotkeyBinding scope=LOCAL): window-scoped
QShortcuts on the main window -- Ctrl+Enter translate, Ctrl+, options,
Ctrl+Shift+S swap, Ctrl+Shift+H history, Ctrl+Shift+D document,
Ctrl+Shift+C copy result, Ctrl+Shift+X clear input, Alt+1/2/3 focus."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from PySide6.QtWidgets import QApplication  # noqa: E402
_qapp = QApplication.instance() or QApplication([])

from PySide6.QtGui import QShortcut  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402

from qtranslate import config as _C  # noqa: E402
_saved = _C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
_C.DEFAULT_PATH = _tmp

from qtranslate.qt.app import QtApp  # noqa: E402
from qtranslate.qt.main_window import MainWindow  # noqa: E402

app = QtApp([])

# Shortcuts bind app methods at connect time (inside MainWindow.__init__),
# so the stubs must be in place BEFORE the window is built.
fired = []
app.on_go = lambda: fired.append("go")
app.on_swap = lambda: fired.append("swap")
app.open_history = lambda: fired.append("hist")
app.open_document_translation = lambda path=None: fired.append("doc")
app.open_options = lambda page="": fired.append("opts")

win = MainWindow(app)
win.show()
win.activateWindow()
_qapp.processEvents()

scs = {}
for sc in win.findChildren(QShortcut):
    scs[str(sc.key().toString())] = sc

for key in ("Ctrl+Enter", "Ctrl+,", "Ctrl+Shift+S", "Ctrl+Shift+H",
            "Ctrl+Shift+D", "Ctrl+Shift+C", "Ctrl+Shift+X", "Ctrl+L",
            "Alt+1", "Alt+2", "Alt+3", "Alt+Left", "Alt+Right"):
    ck("shortcut %s" % key, key in scs, "keys: %s" % sorted(scs))

# Window-scoped context: must NOT be global (that's the LOCAL contract).
for key in ("Ctrl+Enter", "Ctrl+Shift+S", "Alt+1"):
    ck("%s window-scoped" % key,
       scs[key].context() == Qt.ShortcutContext.WindowShortcut)

# Fire each and check the effect.
scs["Ctrl+Enter"].activated.emit()
scs["Ctrl+,"].activated.emit()
scs["Ctrl+Shift+S"].activated.emit()
scs["Ctrl+Shift+H"].activated.emit()
scs["Ctrl+Shift+D"].activated.emit()
ck("actions fired", fired == ["go", "opts", "swap", "hist", "doc"],
   repr(fired))

# Ctrl+Shift+C copies the whole result, not the selection.
win.out.setPlainText("translated text")
scs["Ctrl+Shift+C"].activated.emit()
from PySide6.QtWidgets import QApplication as _QA
clip = _QA.clipboard().text()
ck("copy result", clip == "translated text", repr(clip))

# Ctrl+Shift+X clears the input.
win.src.setPlainText("hello")
scs["Ctrl+Shift+X"].activated.emit()
ck("clear input", win.src.toPlainText() == "")

# Alt+1/2/3 move focus to the three panes.
for key, pane in (("Alt+1", win.src), ("Alt+2", win.out),
                  ("Alt+3", win.back)):
    win.src.clearFocus()
    win.out.clearFocus()
    win.back.clearFocus()
    scs[key].activated.emit()
    ck("focus %s" % key, _QA.focusWidget() is pane,
       "focus=%r want=%r" % (_QA.focusWidget(), pane))

# Ctrl+L cycles the target combo and wraps.
cmb = win.cmb_tgt
n = cmb.count()
if n >= 2:
    start = cmb.currentIndex()
    scs["Ctrl+L"].activated.emit()
    ck("cycle target", cmb.currentIndex() == (start + 1) % n,
       "%s -> %s" % (start, cmb.currentIndex()))
    cmb.setCurrentIndex(n - 1)
    scs["Ctrl+L"].activated.emit()
    ck("cycle wraps", cmb.currentIndex() == 0,
       "idx=%s" % cmb.currentIndex())

if FAIL:
    print("\nregress_local_hotkeys: %d FAILURES" % len(FAIL))
    _C.DEFAULT_PATH = _saved
    sys.exit(1)
_C.DEFAULT_PATH = _saved
try:
    os.unlink(_tmp)
except OSError:
    pass
print("\nregress_local_hotkeys: all checks ok")
