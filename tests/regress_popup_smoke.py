"""Regression: the press-Q popup surface (user-reported path).

The user's point: QTranslate is not only a translate table -- pressing the
hotkey (Q by default) shows a borderless popup NEXT TO THE CURSOR, plus an
Options panel that carries hotkeys, and more. This suite pins the
non-translate surfaces the port must keep working:

  1. hotkey -> popup chain: hotkey_popup ends at show_translation, which
     opens the popup
  2. popup placement comes from Appearance.PopupAutoPos (near pointer)
     and Transparency (the native 217 default)
  3. Options panel exposes a Hotkeys page with the hotkey list
  4. PopupIcons renders as a passive indicator row, not clickable buttons
  5. one main window (the app reuses it; a popup never opens a second one)

Reads the view's source (structural -- the tkinter view is gone,
2026-10-22) plus constructs the popup headlessly. No provider calls: the
popup path is UI-only, so nothing here touches the network.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from tests._view_src import view_source  # noqa: E402

SRC = view_source()

# 1. the hotkey path reaches the popup (a popup, not just a table render)
ck("the hotkey path opens the popup",
   "def hotkey_popup" in SRC
   and SRC.count("PopupWindow(") >= 1,
   "the press-Q popup must be in the hotkey chain")
ck("show_translation drives the popup",
   "self._popup.set_text(" in SRC and "self._popup.place()" in SRC,
   "set_text + place before show")

# 2. popup placement honours Appearance.PopupAutoPos (cursor-adjacent)
ck("popup reads Appearance.PopupAutoPos", "PopupAutoPos" in SRC,
   "_ap.get(\"PopupAutoPos\", True)")
ck("popup positions near the pointer when auto-pos is on",
   "QCursor.pos()" in SRC,
   "the popup must appear beside the cursor")
ck("popup restores a saved placement when auto-pos is off",
   "decode_placement" in SRC and "WindowPopupPlacement" in SRC,
   "the remembered-geometry path")
ck("popup applies Transparency (native 217 default)",
   "Transparency" in SRC and "setWindowOpacity" in SRC,
   "0..255 mapped to 0.0..1.0")
ck("popup honours PopupAutoFocus (off by default)",
   "PopupAutoFocus" in SRC)

# 3. Options panel / Hotkeys page exist
ck("Options panel exists", "def open_options" in SRC)
ck("Hotkeys page is one of the 9 options pages",
   "HotkeysPage" in SRC or "hotkeys" in open(
       os.path.join(ROOT, "qtranslate", "qt", "options",
                    "__init__.py"), encoding="utf-8").read(),
   "the options package must expose the Hotkeys page")
ck("Hotkey actions list is populated",
   "hotkey-names-17" in open("tests/ui_match.py",
                             encoding="utf-8").read(),
   "ui_match pins 17 hotkey action names")

# 4. PopupIcons must stay passive (native popup is button-less)
if "popup-no-buttons" in open("tests/ui_match.py",
                              encoding="utf-8").read():
    ck("ui_match still pins popup-no-buttons", True)
else:
    ck("ui_match still pins popup-no-buttons", False, "the guard was removed")
_pop_src = open(os.path.join(ROOT, "qtranslate", "qt", "popup.py"),
                encoding="utf-8").read()
ck("popup icons render as Labels, not Buttons",
   "QPushButton" not in _pop_src,
   "Button glyphs would regress popup-no-buttons")

# 5. one main window per app (no second top-level per popup)
ck("the app keeps one main window it reuses",
   "app.win = MainWindow" in SRC,
   "the popups must be children, not new rooted windows")

# 6. popup option defaults must match native (DAT_005494A4 = 217)
import io  # noqa: E402
_c = io.open(os.path.join(ROOT, "qtranslate", "config.py"),
             encoding="utf-8").read()
ck("Transparency default is the native 217, not 255",
   '"Transparency": 217' in _c,
   "native default Transparency is 217 (NATIVE_ARCH.md:1200)")
ck("PopupAutoPos defaults True (cursor-adjacent)",
   '"PopupAutoPos": True' in _c,
   "native shows the popup beside the pointer")
ck("PopupAutoFocus defaults off (do not steal focus)",
   '"PopupAutoFocus": False' in _c)

# 7. the popup, constructed, is the native's 200x68 frameless window
try:
    from qtranslate.qt import app as _qa
    _app = _qa.QtApp([])
    from PySide6.QtCore import Qt as _Qt
    from qtranslate.qt.popup import PopupWindow
    p = PopupWindow(None)
    ck("the popup is the native's size", (p.width(), p.height())
       == (200, 68), "%dx%d" % (p.width(), p.height()))
    ck("the popup is frameless",
       (_Qt.FramelessWindowHint & p.windowFlags()) != 0,
       str(p.windowFlags()))
except Exception as e:
    print("FAIL: live popup construction -- %r" % (e,))
    raise SystemExit(1)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_popup_smoke: all checks ok (%d assertions)" % n[0])
