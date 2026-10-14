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


# main/dict/hist/kbd build at (spec_height - 30): the spec's figure is the
# FULL window including the native title bar, which tkinter draws as real
# OS chrome outside the geometry/client area now that screens.py no longer
# paints a second, fake title bar inside the window (see _titlebar).
EXPECTED = {
    "main": (S.MAIN_WIDTH, S.MAIN_HEIGHT - 30),
    "popup": (S.POPUP_W, S.POPUP_H),
    "options": (S.OPTS_W, S.OPTS_H),
    "dict": (S.DICT_W, S.DICT_H - 30),
    "hist": (S.HIST_W, S.HIST_H - 30),
    "kbd": (S.KBD_W, S.KBD_H - 30),
    "tray": (S.TRAY_W, S.TRAY_H),
}

ck("screens exposes all 7 builders",
   set(EXPECTED) == set(S.SCREENS),
   str(sorted(S.SCREENS)))

ck("all 9 Options pages have a body builder",
   set(S.OPTION_PAGES) == set(S.PAGE_BODIES),
   "missing: %s" % sorted(set(S.OPTION_PAGES) - set(S.PAGE_BODIES)))

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
    # main window: the control band matches the spec's measured band
    # (UI-FULL.html .spl top:212px height:5px, .ctl top:217px, hline 242;
    # control lefts 4/41/67/223/256/438). Probed headlessly from widget
    # placement -- no screenshot needed.
    try:
        win = S.main_window(root)
        root.update_idletasks()
        root.update()

        def _frames():
            out = []

            def walk(w):
                for k in w.winfo_children():
                    try:
                        out.append((k.winfo_x(), k.winfo_y(),
                                    k.winfo_width(), k.winfo_height()))
                    except Exception:
                        pass
                    walk(k)
            walk(win)
            return out
        placed = _frames()
        xs = sorted({x for x, y, w, h in placed if y == 217})
        ck("control row sits at spec y=217", bool(xs), str(xs))
        for sx in (4, 67, 223, 256, 438):
            ck("control at spec left %d" % sx,
               any(x == sx and y == 217 for x, y, w, h in placed),
               "y217 xs=%s" % xs)
        ck("splitter frame at spec y=212..217",
           any(x == 1 and y == 212 and w == 513 and h == 5
               for x, y, w, h in placed))
        ck("splitter double line at 213 and 214",
           any(y == 213 for x, y, w, h in placed)
           and any(y == 214 for x, y, w, h in placed))
        ck("3-dot grip at x 249/254/259",
           all(any(x == gx and y == 213 for x, y, w, h in placed)
               for gx in (249, 254, 259)))
        ck("control-row bottom rule at y=242",
           any(x == 1 and y == 242 for x, y, w, h in placed))
        win.destroy()
    except Exception as e:
        ck("main window control band matches the spec", False, repr(e))
    # every Options page must build too (each is its own measured screen)
    for page in S.OPTION_PAGES:
        try:
            win = S.options_window(root, page=page)
            root.update_idletasks()
            ck("Options/%s builds at %dx%d"
               % (page, S.OPTS_W, S.OPTS_H),
               win.geometry().startswith("%dx%d" % (S.OPTS_W, S.OPTS_H)),
               win.geometry())
            win.destroy()
        except Exception as e:
            ck("Options/%s builds" % page, False, repr(e))
    root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_screens: all checks ok (%d assertions)" % n[0])
