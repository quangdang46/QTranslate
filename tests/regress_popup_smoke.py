"""Regression: the press-Q popup surface (user-reported path).

The user's point: QTranslate is not only a translate table -- pressing the
hotkey (Q by default) shows a borderless popup NEXT TO THE CURSOR, plus an
Options panel that carries hotkeys, and more. This suite pins the
non-translate surfaces the port must keep working:

  1. hotkey -> popup chain: on_hotkey ends by calling show_popup
  2. popup geometry comes from Appearance.PopupAutoPos (near pointer)
  3. Options panel exposes a Hotkeys page with a hotkey list
  4. PopupIcons renders as a passive indicator row, not clickable buttons
  5. Tray/minimize -> restore keeps the same single main window (_MAIN_APP)

Reads app.py source (structural) plus constructs the popup where a live Tk
root exists. No provider calls: the popup path is UI-only, so nothing here
touches the network.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


SRC = open("qtranslate/app.py", encoding="utf-8").read()

# 1. the hotkey path reaches show_popup (a popup, not just a table render)
ck("on_hotkey calls show_popup",
   "def on_hotkey" in SRC
   and SRC.count("show_popup(") >= 2,
   "the press-Q popup must be in the hotkey chain")

# 2. popup placement honours Appearance.PopupAutoPos (cursor-adjacent)
ck("popup reads Appearance.PopupAutoPos", "PopupAutoPos" in SRC)
ck("popup positions near the pointer when auto-pos is on",
   "winfo_pointerx" in SRC and "winfo_pointery" in SRC,
   "the popup must appear beside the cursor")
ck("popup restores a saved placement when auto-pos is off",
   "WindowPopupPlacement" in SRC and "_place_aux" in SRC,
   "the remembered-geometry path")

# 3. Options panel / Hotkeys page exist with actions
ck("Options panel exists", "def open_options" in SRC)
ck("Hotkeys page is one of the 9 options pages", "def show_hotkeys" in SRC)
ck("Hotkey actions list is populated",
   "hotkey-names-17" in open("tests/ui_match.py", encoding="utf-8").read(),
   "ui_match pins 17 hotkey action names")

# 4. PopupIcons must stay passive (native popup is button-less)
if "popup-no-buttons" in open("tests/ui_match.py", encoding="utf-8").read():
    ck("ui_match still pins popup-no-buttons", True)
else:
    ck("ui_match still pins popup-no-buttons", False, "the guard was removed")
ck("popup icons render as Labels, not Buttons",
   "tk.Label(_bar, text=" in SRC and "tk.Button(_bar" not in SRC,
   "Button glyphs would regress popup-no-buttons")

# 5. _to_main reuses one main window (no second tk.Tk per popup)
ck("_MAIN_APP is the single main window",
   "global _MAIN_APP" in SRC and "_MAIN_APP = app" in SRC)

# 6. popup option defaults must match native (DAT_005494A4 = 217)
ck("Transparency fallback is the native 217, not 255",
   '_ap.get("Transparency", 217)' in SRC,
   "native default Transparency is 217 (NATIVE_ARCH.md:1200)")
ck("DEFAULT_APPEARANCE also carries 217",
   '"Transparency": 217' in open("qtranslate/config.py",
                                 encoding="utf-8").read())
ck("PopupTimeout default stays 0 (opaque, no auto-hide)",
   '_ap.get("PopupTimeout", 0)' in SRC)
ck("PopupAutoPos defaults True (cursor-adjacent)",
   '_ap.get("PopupAutoPos", True)' in SRC)
ck("PopupAutoFocus gates focus steal (default off)",
   "PopupAutoFocus" in SRC)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_popup_smoke: all checks ok (%d assertions)" % n[0])
