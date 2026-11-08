"""Regression: the cursor-following loading marker
(``qtranslate/qt/loading_indicator.py``, .tmp ``LoadingIndicator``).

The contract pinned here:

  1. window flags mirror the other cursor widgets -- frameless,
     no-focus, always-on-top, transparent for mouse events;
  2. fixed 45x10 size with an indeterminate (0..0) progress bar;
  3. ``_follow`` parks the marker under the pointer (+20px y gap);
  4. ``hide()`` honours the 350 ms minimum-visible window -- a hide
     requested earlier DEFERS instead of flashing the marker away;
  5. once the minimum has elapsed, ``hide()`` hides immediately.

Offscreen; timing is driven by writing ``_shown_at`` directly, so the
suite is deterministic (no real waits).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCursor
    from PySide6.QtWidgets import QApplication, QProgressBar
    qapp = QApplication.instance() or QApplication([])
    from qtranslate.qt.loading_indicator import (
        GAP_Y, H, MIN_VISIBLE_MS, W, LoadingIndicator)
except Exception as exc:                                # noqa: BLE001
    print("SKIP regress_loading_indicator: Qt imports failed (%s)" % exc)
    raise SystemExit(0)

ind = LoadingIndicator()

# -- flags / geometry -------------------------------------------------------
flags = ind.windowFlags()
ck("frameless", bool(flags & Qt.FramelessWindowHint))
ck("does not accept focus", bool(flags & Qt.WindowDoesNotAcceptFocus))
ck("stays on top", bool(flags & Qt.WindowStaysOnTopHint))
ck("transparent for mouse", ind.testAttribute(Qt.WA_TransparentForMouseEvents))
ck("show-without-activating", ind.testAttribute(Qt.WA_ShowWithoutActivating))
ck("fixed size is the .tmp marker", (ind.width(), ind.height()) == (W, H),
   "%sx%s" % (ind.width(), ind.height()))
bar = ind.findChild(QProgressBar)
ck("indeterminate bar", bar is not None and bar.minimum() == 0
   and bar.maximum() == 0)
ck("bar fills the marker", bar is not None
   and bar.geometry().width() == W and bar.geometry().height() == H)

# -- follow -----------------------------------------------------------------
ind._follow()
pos = QCursor.pos()
ck("marker parks under the pointer",
   (ind.x(), ind.y()) == (pos.x(), pos.y() + GAP_Y),
   "%s,%s vs %s,%s" % (ind.x(), ind.y(), pos.x(), pos.y() + GAP_Y))

# -- min-visible deferral ----------------------------------------------------
ind.show_at_cursor()
ck("shown under cursor", ind.isVisible())
ind.hide()                       # requested immediately -> deferred
ck("early hide defers", ind.isVisible() and ind._pending)

# once the minimum elapsed, hide() is immediate
from PySide6.QtCore import QDateTime
ind._shown_at = (QDateTime.currentMSecsSinceEpoch()
                 - MIN_VISIBLE_MS - 1)
ind.hide()
ck("hide after minimum hides now", not ind.isVisible())

# a fresh show resets the clock: another early hide defers again
ind.show_at_cursor()
ind.hide()
ck("second early hide defers too", ind.isVisible() and ind._pending)
ind._shown_at = (QDateTime.currentMSecsSinceEpoch()
                 - MIN_VISIBLE_MS - 1)
ind.hide()
ck("second hide after minimum hides", not ind.isVisible())

# -- failsafe ----------------------------------------------------------------
# show_at_cursor arms a 15 s singleShot failsafe; do not wait it out,
# just pin that _hide_now exists and hides unconditionally.
ind.show_at_cursor()
ind._hide_now()
ck("_hide_now hides unconditionally", not ind.isVisible())

if fail:
    print("FAIL %d" % len(fail))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_loading_indicator: all checks ok (%d assertions)" % n[0])
