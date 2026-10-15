"""Pin the UI parity fixes landed 2026-10-15 (headless, AST + logic).

Covers the four fixes that had no dedicated regression test:

1. Languages page per-key defaults (From=1/auto, To=57/vi,
   Dictionary=17/en, Keyboard=17/en) — a single default 17 showed `en`
   for an unset From on first run.
2. History-window I6 five-entry right-click menu (Open/Copy text/Copy
   translation/Delete/Listen) — was missing entirely.
3. OCR overlay keys (S/C/arrows/Del/Enter via shared `_grab_png`) —
   was Esc-only.
4. win32app `_translate` reads combos 1001/1002 via `_combo_text`
   (was hardcoded `("google", text, "vi")`); dead wrong-font
   `_font_handle` deleted.

All checks read source or exercise tkinter-free logic. No window opened.
"""
import ast
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


APP = io.open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "app.py"),
    encoding="utf-8").read()
tree = ast.parse(APP)

# --- 1. per-key language defaults -------------------------------------
m = re.search(r"_defs = (\{[^}]*\})", APP)
ck("per-key _defs table exists", m is not None)
if m:
    defs = eval(m.group(1))
    ck("From defaults to 1 (auto)", defs.get("LanguageFrom") == 1,
       repr(defs))
    ck("To defaults to 57 (vi)", defs.get("LanguageTo") == 57,
       repr(defs))
    ck("Dictionary defaults to 17 (en)",
       defs.get("LanguageDictionary") == 17, repr(defs))
    ck("Keyboard defaults to 17 (en)",
       defs.get("LanguageKeyboard") == 17, repr(defs))
    ck("combos use _defs, not a single 17",
       "_gen.get(key, _defs[key])" in APP)
    ck("no single-default-17 for the four combos",
       "_gen.get(key, 17) or 0" not in APP)

# --- 2. history I6 five-entry menu -------------------------------------
hm = [x for x in ast.walk(tree)
      if isinstance(x, ast.FunctionDef) and x.name == "_hist_menu"]
ck("history window defines _hist_menu", len(hm) == 1)
if hm:
    seg = ast.get_source_segment(APP, hm[0])
    ck("menu has 5 entries", seg.count("add_command") == 5,
       str(seg.count("add_command")))
    for op in ("load_sel", "_pcopy", "_hdel", "_hear"):
        ck("menu references %s" % op, op in seg, op)
    ck("bound to right-click",
       'tv.bind("<Button-3>", _hist_menu)' in APP)
    ck("entries disabled without selection",
       'state="normal" if _ent else "disabled"' in seg)

# --- 3. OCR overlay keys -----------------------------------------------
ov = [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)
      and x.name == "_keys"]
ck("overlay defines _keys handler", len(ov) == 1)
gp = [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)
      and x.name == "_grab_png"]
ck("overlay shares one _grab_png capture path", len(gp) == 1)
ng = [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)
      and x.name == "_nudge"]
ck("overlay defines _nudge for arrows", len(ng) == 1)
if ov:
    seg = ast.get_source_segment(APP, ov[0])
    for k in ('"s"', '"c"', '"return"', '"delete"', '"escape"',
              "_grab_png", "_nudge", "SetClipboardData"):
        ck("overlay handles %s" % k, k in seg, k)
    ck("C copies to clipboard, not a viewer",
       "mspaint" not in seg and "SetClipboardData" in seg)

# --- 4. win32app combo wiring (dead-divergence fix, same day) ------------
WA = io.open(os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))),
    "qtranslate", "win32app.py"), encoding="utf-8").read()
ck("win32app reads combos, not hardcoded vi",
   'do_translate("google", text, "vi")' not in WA)
ck("win32app has _combo_text helper", "_combo_text" in WA)
ck("win32app maps combos to codes",
   "CB_GETLBTEXT" in WA and "Auto-Detect" in WA)
ck("dead _font_handle removed", "_font_handle" not in WA)

print("regress_ui_parity_fixes: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
