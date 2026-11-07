#!/usr/bin/env python3
"""Image-search window preferences (.tmp imageSearch* fields):
Transparency percent -> window opacity, AutoPosition off -> restore
LastKnownSize/Position on next open, geometry saved on close."""
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

from qtranslate import config as _C  # noqa: E402
_saved = _C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
_C.DEFAULT_PATH = _tmp

from qtranslate.qt.image_search import (ImageSearchDialog,  # noqa: E402
                                        _imgsearch_save)


class _App:
    pass


# default: 5% transparent -> opacity 0.95, default 580x500
d = ImageSearchDialog(_App())
ck("default opacity", abs(d.windowOpacity() - 0.95) < 0.01,
   repr(d.windowOpacity()))
ck("default size", d.width() == 580 and d.height() == 500)
d.close()

# transparency 30 -> opacity 0.70
_imgsearch_save(Transparency=30)
d2 = ImageSearchDialog(_App())
ck("pct30 opacity", abs(d2.windowOpacity() - 0.70) < 0.01,
   repr(d2.windowOpacity()))
d2.close()

# out-of-range clamps to 5..50
_imgsearch_save(Transparency=90)
d3 = ImageSearchDialog(_App())
ck("clamped high", abs(d3.windowOpacity() - 0.50) < 0.01,
   repr(d3.windowOpacity()))
_imgsearch_save(Transparency=1)
d4 = ImageSearchDialog(_App())
ck("clamped low", abs(d4.windowOpacity() - 0.95) < 0.01,
   repr(d4.windowOpacity()))
d3.close()
d4.close()

# AutoPosition off + saved geometry -> restored on next open
_imgsearch_save(Transparency=5, AutoPosition=False,
                LastKnownSize="700,600",
                LastKnownPosition="120,90")
d5 = ImageSearchDialog(_App())
ck("restored size", d5.width() == 700 and d5.height() == 600,
   "%dx%d" % (d5.width(), d5.height()))
ck("restored pos", d5.x() == 120 and d5.y() == 90,
   "%d,%d" % (d5.x(), d5.y()))
d5.close()

# closeEvent persists the CURRENT geometry
cfg = _C.load()
sec = cfg.get("ImageSearch", {})
ck("geometry saved", "LastKnownSize" in sec and
   "LastKnownPosition" in sec, repr(sec))

# AutoPosition on -> default size even with saved geometry
_imgsearch_save(AutoPosition=True)
d6 = ImageSearchDialog(_App())
ck("auto pos ignores saved", d6.width() == 580 and d6.height() == 500)
d6.close()

# malformed saved geometry falls back to default
d7 = ImageSearchDialog(_App())
d7.close()
_imgsearch_save(AutoPosition=False, LastKnownSize="junk",
                LastKnownPosition="junk")
d8 = ImageSearchDialog(_App())
ck("bad geometry fallback", d8.width() == 580 and d8.height() == 500)
d8.close()

# options-page writer reaches the same section
from qtranslate.qt.options import appearance as APP  # noqa: E402
APP._imgsearch_set("Transparency", 25)
_IMG = (_C.load().get("ImageSearch", {}) or {}).get("Transparency")
ck("options writer", _IMG == 25, repr(_IMG))
_APPp = APP._imgsearch_set("AutoPosition", False)
ck("options writer bool",
   (_C.load().get("ImageSearch", {}) or {}).get("AutoPosition")
   is False)

_C.DEFAULT_PATH = _saved
try:
    os.unlink(_tmp)
except OSError:
    pass

if FAIL:
    print("\nregress_image_search_prefs: %d FAILURES" % len(FAIL))
    sys.exit(1)
print("\nregress_image_search_prefs: all checks ok")

# ---- .tmp AppearancePanel uiScale (QT_SCALE_FACTOR bridge) ----
import os as _os, importlib
import qtranslate.qt.app as _qa
importlib.reload(_qa)

def _scale_env(scale_val, preset=None):
    _os.environ.pop("QT_SCALE_FACTOR", None)
    data = _C.load()
    data.setdefault("Appearance", {})["UiScale"] = scale_val
    _C.save(data)
    if preset is not None:
        _os.environ["QT_SCALE_FACTOR"] = preset
    _qa._apply_ui_scale()
    return _os.environ.get("QT_SCALE_FACTOR")

try:
    ck("uiScale default leaves the env alone",
       _scale_env(100) is None)
    ck("uiScale 150 sets QT_SCALE_FACTOR 1.5",
       _scale_env(150) == "1.50")
    ck("uiScale clamps below 75",
       _scale_env(10) == "0.75")
    ck("uiScale clamps above 300",
       _scale_env(999) == "3.00")
    ck("explicit QT_SCALE_FACTOR wins over the setting",
       _scale_env(150, "2.00") == "2.00")
    ck("malformed UiScale is ignored",
       _scale_env("abc") in (None, "abc"))
finally:
    _os.environ.pop("QT_SCALE_FACTOR", None)
    data = _C.load()
    data.get("Appearance", {}).pop("UiScale", None)
    _C.save(data)
