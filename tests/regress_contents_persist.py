"""regress_contents_persist -- Contents.EditSource/EditTranslation/
EditBackTranslation round-trip.

Native keeps the three editor fields as separate Options.json keys,
each truncated to 5000 chars on save (D10 spotcheck). The port maps
them one-to-one onto the main window's src/out/back panes; this suite
pins the write on quit, the restore on boot, the 5000-char clip, and
the separate back-translation field.
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import qtranslate.config as C  # noqa: E402

_tmp = tempfile.mktemp(suffix=".json")
C.DEFAULT_PATH = _tmp

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


try:
    from PySide6.QtWidgets import QApplication
    _qapp = QApplication.instance() or QApplication([])
    from qtranslate.qt.app import QtApp
    from qtranslate.qt.main_window import MainWindow
    app = QtApp([])
    app.win = MainWindow(app)
    win = app.win

    win.src.setPlainText("hello world")
    win.set_result("xin chào\n\n--- back-translation ---\nhello world")
    app._persist_contents()
    cfg = json.load(open(_tmp))
    cont = cfg.get("Contents", {})
    ck("EditSource persisted", cont.get("EditSource") == "hello world",
       repr(cont.get("EditSource")))
    ck("EditTranslation persisted", cont.get("EditTranslation") == "xin chào",
       repr(cont.get("EditTranslation")))
    ck("EditBackTranslation persisted",
       cont.get("EditBackTranslation") == "hello world",
       repr(cont.get("EditBackTranslation")))

    # restore: clear panes, reload from Contents
    win.src.setPlainText("")
    win.set_result("")
    app._restore_contents()
    ck("EditSource restored", win.src.toPlainText() == "hello world")
    ck("EditTranslation restored", win.out.toPlainText() == "xin chào")
    ck("EditBackTranslation restored",
       win.back.toPlainText() == "hello world")

    # the three fields stay separate: no marker leaks into EditTranslation
    ck("no marker in EditTranslation",
       "--- back-translation ---" not in cont.get("EditTranslation", ""))

    # 5000-char clip on each field
    win.src.setPlainText("s" * 6000)
    win.out.setPlainText("t" * 6000)
    win.back.setPlainText("b" * 6000)
    app._persist_contents()
    cfg = json.load(open(_tmp))
    cont = cfg.get("Contents", {})
    ck("EditSource clipped", len(cont.get("EditSource", "")) == 5000)
    ck("EditTranslation clipped", len(cont.get("EditTranslation", "")) == 5000)
    ck("EditBackTranslation clipped",
       len(cont.get("EditBackTranslation", "")) == 5000)

    # empty panes persist empty strings (native writes "" not absent)
    win.src.setPlainText("")
    win.out.setPlainText("")
    win.back.setPlainText("")
    app._persist_contents()
    cfg = json.load(open(_tmp))
    cont = cfg.get("Contents", {})
    ck("empty contents persist", cont.get("EditSource") == ""
       and cont.get("EditTranslation") == ""
       and cont.get("EditBackTranslation") == "")
except Exception as exc:                        # noqa: BLE001
    ck("contents persist suite runs", False,
       "%s: %s" % (type(exc).__name__, exc))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_contents_persist: all checks ok (%d assertions)" % n[0])
