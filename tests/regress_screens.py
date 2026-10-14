"""Regression: the UI-FULL.html 1:1 screen port (qtranslate/screens.py).

Each of the 7 builders must construct without error and report the exact
geometry the spec measured. The point is to catch drift early: if a later
edit silently changes a screen's size or drops a builder, this fails before
any screenshot comparison does.

The spec's non-drillable parts (exact icon glyphs, measured text wrapping)
are left out deliberately -- geometry and presence only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk  # noqa: E402

import qtranslate.screens as S  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


EXPECTED = {
    "main": (S.MAIN_WIDTH, S.MAIN_HEIGHT),
    "popup": (S.POPUP_W, S.POPUP_H),
    "options": (S.OPTS_W, S.OPTS_H),
    "dict": (S.DICT_W, S.DICT_H),
    "hist": (S.HIST_W, S.HIST_H),
    "kbd": (S.KBD_W, S.KBD_H),
    "tray": (S.TRAY_W, S.TRAY_H),
}

ck("screens exposes all 7 builders",
   set(EXPECTED) == set(S.SCREENS),
   str(sorted(S.SCREENS)))

ck("option pages are the 9 native pages",
   S.OPTION_PAGES == ["Basics", "Hotkeys", "Internet", "Services",
                      "Languages", "Appearance", "Exceptions", "Advanced",
                      "Updates"])

ck("hotkey table carries the 13 native actions",
   len(S.HOTKEY_ACTIONS) == 13, str(len(S.HOTKEY_ACTIONS)))
ck("Show popup window is bound to Ctrl + Q",
   S.HOTKEY_BINDINGS.get(1) == "Ctrl + Q")
ck("Replace selected text is bound to Alt + W",
   S.HOTKEY_BINDINGS.get(7) == "Alt + W")

# no colour outside the measured token table may appear anywhere in the
# module (the spec's hard rule 4)
import re as _re  # noqa: E402

SRC = open("qtranslate/screens.py", encoding="utf-8").read()
USED = {"#" + m for m in
        _re.findall(r"#([0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?)\b", SRC)}
KNOWN = {
    "#f0f0f0", "#ffffff", "#fff", "#7e7e7e", "#000", "#000000", "#6d6d6d",
    "#0078d7", "#0066cc", "#858585", "#e5e5e5", "#e3e3e3", "#d4d4d4",
    "#cacaca", "#e1e1e1", "#dcdcdc", "#d0d0d0", "#53606c", "#3a3a3a",
    "#040404", "#f9f9f9", "#e5e5e5", "#d7d7d7", "#eff4f9", "#005eb8",
    "#b5c9e0", "#5d6c7a", "#555", "#4b8bf5", "#1b9bb0", "#3aa757",
    "#2d6cdf", "#d33", "#e53", "#3a7bd5", "#0f2b46", "#888",
    "#4285f4", "#d9534f", "#1a73c8", "#999", "#7a3d9e", "#e8890c",
    "#e53935", "#8a8a2a", "#1dc078", "#f5a623", "#2bb673", "#d32f2f",
    "#e6c800",
}
UNKNOWN = {c for c in USED if c.lower() not in {k.lower() for k in KNOWN}}
ck("no colour outside the measured token table", not UNKNOWN,
   "foreign: %s" % sorted(UNKNOWN))

# build every screen, assert exact geometry
try:
    root = tk.Tk()
    root.withdraw()
except Exception as e:
    ck("tk root available for geometry checks", False, repr(e))
    root = None
if root is not None:
    for name, (w, h) in EXPECTED.items():
        try:
            win = S.SCREENS[name](root)
            root.update_idletasks()
            g = win.geometry()
            ck("%s builds at %dx%d" % (name, w, h),
               g.startswith("%dx%d" % (w, h)), g)
            win.destroy()
        except Exception as e:
            ck("%s builds at %dx%d" % (name, w, h), False, repr(e))
    root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_screens: all checks ok (%d assertions)" % n[0])
