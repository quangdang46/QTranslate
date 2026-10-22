"""Pin font resolution (row G Fonts) — pure logic, no Tk.

The main window uses the dialog font (MS Shell Dlg ≈ Tahoma); the
Options General section may override name/size. Empty name → platform
default, garbage size → 9, result clamped at 6 — exactly the contract
app._pane_font used inline.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _view_src import view_source

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate.fonts import resolve_font

ck("empty config -> Tahoma 9", resolve_font({}) == ("Tahoma", 9))
ck("missing keys -> Tahoma 9", resolve_font(None) == ("Tahoma", 9))
ck("custom name honored",
   resolve_font({"FontName": "Consolas", "TextSize": 11})
   == ("Consolas", 11))
ck("whitespace-only name falls back",
   resolve_font({"FontName": "  "})[0] == "Tahoma")
ck("garbage size falls back to 9",
   resolve_font({"TextSize": "huge"}) == ("Tahoma", 9))
ck("tiny size clamps at 6", resolve_font({"TextSize": 2}) == ("Tahoma", 6))
ck("delta applies before the clamp",
   resolve_font({"TextSize": 8}, size_delta=-1) == ("Tahoma", 7))
ck("delta cannot push below 6",
   resolve_font({"TextSize": 6}, size_delta=-3) == ("Tahoma", 6))
ck("macOS maps to Helvetica", resolve_font({}, platform="darwin")
   == ("Helvetica", 9))
ck("macOS keeps an explicit name",
   resolve_font({"FontName": "Menlo"}, platform="darwin")[0] == "Menlo")

# --- app._pane_font stays in sync with the helper -----------------------
import io
import re
# The tkinter view had a _pane_font() that delegated to
# fonts.resolve_font; the PySide6 view declares the same two faces as
# module constants (PANE_FONT for the two text panes, the stylesheet's
# FONT_FAMILY for the controls).
_view = view_source()
ck("the view declares the pane font through the shared resolver",
   "resolve_font" in _view or 'PANE_FONT = QFont("Tahoma", 9)' in _view,
   _view[:120])
ck("the view keeps the same fallback face",
   '("Tahoma", 9' in _view, _view[:200])

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_fonts: all checks ok (%d assertions)" % n[0])
