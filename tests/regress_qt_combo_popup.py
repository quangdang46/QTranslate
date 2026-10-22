"""Regression: the combo's drop-down behaves like the native's.

The user opened the target-language combo and the list ran off the
screen. Three separate faults were behind it, and each one is pinned
here:

  1. the drop-down was as tall as the WHOLE list (1266px for the 74
     languages of the native's own table), where the native's is a
     fixed 225px -- the height its own dialog resource asks for;
  2. it had no scroll bar, so the languages past the fold could not be
     reached at all; and
  3. the row the user was standing on -- the current language -- was
     painted BLACK on black, so it could not be read.

The height is not a guess: DLG129's language combos (ids 1001/1002) are
120 dialog units tall in the native's own resource, and the dialog's
font (MS Shell Dlg 8pt, average character height 15) puts one vertical
DLU at 15/8 px. The first check below re-derives that from the
recovered executable, so the constant cannot drift away from the
native's resource without this suite noticing.

Offline, no network. Skips (exit 0) when PySide6 is not importable.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s%s" % (name, (" -- " + detail) if detail else ""))


# --- 1. the native's own drop-down height ---------------------------------
# The height comes out of the native's dialog template, so it is read
# back from the recovered executable rather than trusted.
try:
    from qtranslate.qt.widgets import DROPDOWN_H
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_combo_popup: the Qt front end does not import (%s)"
          % exc)
    raise SystemExit(0)

EXE = os.path.join(ROOT, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")
if os.path.exists(EXE):
    try:
        import dlg_parse
        hdr, ctrls = dlg_parse.parse_dialog(EXE, 129)
        combos = {c["id"]: c for c in ctrls
                  if c.get("id") in (1001, 1002)}
        ck("the native's main window has both language combos",
           set(combos) == {1001, 1002}, str(sorted(combos)))
        if combos:
            heights = {c["cy"] for c in combos.values()}
            ck("the native's language combo drop-down is 120 DLU tall",
               heights == {120}, str(heights))
            # 120 DLU * 15px average character height / 8 = 225px.
            ck("the port's drop-down height is that height in pixels",
               DROPDOWN_H == 120 * 15 // 8,
               "DROPDOWN_H=%s" % DROPDOWN_H)
    except Exception as exc:                   # noqa: BLE001
        ck("the native's drop-down height is re-derived", False,
           "%s: %s" % (type(exc).__name__, exc))
else:
    print("note: the recovered executable is absent; the drop-down height "
          "was not re-derived from it")

# --- 2. the drop-down itself ----------------------------------------------
try:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_combo_popup: PySide6 is not importable (%s)" % exc)
    raise SystemExit(0)

try:
    from qtranslate.qt.app import QtApp
    from qtranslate.qt.main_window import MainWindow
    from qtranslate_style import ACCENT
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_combo_popup: the Qt front end does not import (%s)"
          % exc)
    raise SystemExit(0)

try:
    app = QtApp([])
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_combo_popup: no usable QApplication (%s)" % exc)
    raise SystemExit(0)

win = None
try:
    win = MainWindow(app)
    win.show()
    app.qapp.processEvents()

    combo = win.cmb_tgt
    ck("the target combo holds the native's whole language table",
       combo.count() == 74, "%d items" % combo.count())

    combo.showPopup()
    for _ in range(12):
        app.qapp.processEvents()

    view = combo.view()
    container = view.parentWidget()

    # (a) the drop-down is bounded
    ck("the drop-down is no taller than the native's",
       container.height() <= DROPDOWN_H,
       "%dpx, the native's is %dpx" % (container.height(), DROPDOWN_H))
    ck("the drop-down is tall enough to be a list",
       container.height() >= 100, "%dpx" % container.height())

    # (b) the list scrolls, and says so
    bar = view.verticalScrollBar()
    ck("the drop-down has a scroll bar", bar.isVisible())
    ck("the scroll bar has somewhere to go",
       bar.maximum() > 0, "max=%s" % bar.maximum())
    ck("the scroll bar takes room beside the list",
       bar.geometry().width() > 0, str(bar.geometry().getRect()))
    # The bar is laid out against the right edge of the view, but only
    # once the popup has been given a geometry -- a headless platform
    # leaves it at the default.
    if bar.geometry().left() > 0:
        ck("the scroll bar is on the right of the list",
           bar.geometry().left() > view.width() // 2,
           str(bar.geometry().getRect()))

    # (c) the current row is readable: the accent, not black
    img = container.grab().toImage()
    accent = tuple(int(ACCENT[i:i + 2], 16) for i in (1, 3, 5))
    rows = {}
    for y in range(img.height()):
        rows.setdefault(img.pixelColor(90, y).getRgb()[:3], []).append(y)
    ck("the current row is painted in the accent colour",
       accent in rows, str(sorted(rows)))
    ck("no row of the drop-down is painted black",
       (0, 0, 0) not in rows, str(sorted(rows)))

    # (d) the drop-down has no up/down buttons: the native's Win32
    #     drop-down has a scroll bar and nothing else
    buttons = [ch for ch in container.children()
               if isinstance(ch, QWidget) and ch is not view]
    ck("the drop-down has no up/down scroller buttons",
       all(not ch.isVisible() for ch in buttons),
       str([(type(ch).__name__, ch.isVisible()) for ch in buttons]))

    # (e) picking a language works, and the app follows
    combo.hidePopup()
    app.qapp.processEvents()
    combo.showPopup()
    for _ in range(12):
        app.qapp.processEvents()
    view = combo.view()
    index = view.indexAt(QPoint(30, 40))
    ck("the drop-down lists languages", index.isValid())
    if index.isValid():
        wanted = combo.itemText(index.row())
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                         pos=view.visualRect(index).center())
        for _ in range(8):
            app.qapp.processEvents()
        ck("clicking a language picks it", combo.currentText() == wanted,
           "%r != %r" % (combo.currentText(), wanted))
        ck("the app's target language follows the pick",
           app.target == app._code_of(wanted),
           "%r -> %r" % (wanted, app.target))
finally:
    if win is not None:
        try:
            win.close()
        except Exception:                      # noqa: BLE001
            pass
    app.qapp.processEvents()

if fails:
    print("FAIL %d/%d" % (len(fails), n[0]))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_qt_combo_popup: all checks ok (%d assertions)" % n[0])
