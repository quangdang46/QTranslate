"""Pin the UI parity fixes landed 2026-10-15 (headless, AST + logic).

Covers the four fixes that had no dedicated regression test:

1. Languages page per-key defaults (From=1/auto, To=57/vi,
   Dictionary=17/en, Keyboard=17/en) — a single default 17 showed `en`
   for an unset From on first run. The table moved to
   ``qtranslate.config.LANG_DEFAULTS`` (2026-10-22, with the tkinter
   front end gone) and both front ends read it.
2. History-window I6 five-entry right-click menu (Open/Copy text/Copy
   translation/Delete/Listen) — was missing entirely. Now pinned on
   ``qtranslate/qt/history_window.py``.
3. OCR overlay keys (S/C/arrows/Del/Enter via shared `_grab_png`) —
   was Esc-only. Now pinned on ``qtranslate/qt/ocr_pick.py``.
4. win32app `_translate` reads combos 1001/1002 via `_combo_text`
   (was hardcoded `("google", text, "vi")`); dead wrong-font
   `_font_handle` deleted.

All checks read source or exercise headless logic. No window opened on
the host (the offscreen platform builds the Qt widgets it needs).
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


_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from tests._view_src import view_source  # noqa: E402

VIEW = view_source()


def __dict_view(key, root, view):
    """The source that consumes the ``key`` default: the dictionary
    slots' consumer is Core's dictionary_search, the main view reads
    the rest."""
    if key.endswith("Dictionary"):
        return io.open(os.path.join(root, "qtranslate",
                                    "dictionary_search.py"),
                       encoding="utf-8").read()
    return view


CFG = io.open(os.path.join(_REPO, "qtranslate", "config.py"),
              encoding="utf-8").read()
BOTH = CFG + "\n" + VIEW
c_tree = ast.parse(CFG)
v_tree = ast.parse(VIEW)

# --- 1. per-key language defaults ---------------------------------------
# 2026-10-21: the table was named `_defs` and lived in the Options
# "Languages" page -- a page NATIVE DOES NOT HAVE (native's is DLG174,
# the language checklist). The defaults are still real and still
# per-slot, so the table now lives in config.py next to the other
# tables, and the consumers read config.LANG_DEFAULTS.
m = re.search(r"LANG_DEFAULTS = (\{[^}]*\})", CFG)
ck("the per-key language defaults table exists (in config.py)",
   m is not None)
if m:
    import ast as _ast
    defs = _ast.literal_eval(m.group(1))
    ck("From defaults to 1 (auto)", defs.get("LanguageFrom") == 1,
       repr(defs))
    ck("To defaults to 57 (vi)", defs.get("LanguageTo") == 57,
       repr(defs))
    ck("Dictionary defaults to 17 (en)",
       defs.get("LanguageDictionary") == 17, repr(defs))
    ck("Keyboard defaults to 17 (en)",
       defs.get("LanguageKeyboard") == 17, repr(defs))
    for _key in ("LanguageFrom", "LanguageTo", "LanguageDictionary",
                 "LanguageKeyboard"):
        _ds = __dict_view(_key, _REPO, VIEW)
        ck("the %s default is read from the table" % _key,
           ('LANG_DEFAULTS["%s"]' % _key) in _ds
           or ('config.LANG_DEFAULTS["%s"]' % _key) in _ds,
           "the consumer must ask the table, not a literal")
    ck("no single-default-17 for the four slots",
       "_gen.get(key, 17) or 0" not in BOTH)

# --- 2. history I6 five-entry menu --------------------------------------
# The tkinter window implemented it as a tk.Menu on Button-3; the Qt
# window implements the same five entries on a custom context menu.
ROOT = _REPO
HIST = io.open(os.path.join(ROOT, "qtranslate", "qt",
                            "history_window.py"),
               encoding="utf-8").read()
h_tree = ast.parse(HIST)
hm = [x for x in ast.walk(h_tree)
      if isinstance(x, ast.FunctionDef) and x.name == "_entry_menu_requested"]
ck("history window defines the entry-menu handler",
   len(hm) == 1)
menumod = os.path.join(ROOT, "qtranslate", "qt", "history_window.py")
HIST_SRC = HIST
ck("the menu has the five native entries",
   all(op in HIST_SRC for op in
       ("Open", "Copy translation", "Copy text", "Delete",
        "Listen to text")),
   str([op for op in ("Open", "Copy translation", "Copy text", "Delete",
                      "Listen to text") if op not in HIST_SRC]))
ck("...with native's own lang.json ids",
   all(str(mid) in HIST_SRC or ('%d' % mid) in HIST_SRC
       for mid in (10, 20, 30, 50, 40)))
ck("the menu is bound to the entry rows",
   "customContextMenuRequested" in HIST_SRC
   and "CustomContextMenu" in HIST_SRC)
ck("entries disabled without a selection",
   "setEnabled(ent is not None)" in HIST_SRC)
for op in ("_open_entry", "_copy_tr", "_copy_src", "_delete", "_listen"):
    ck("the menu implements %s" % op, op in HIST_SRC, op)
ck("Delete splices the LIVE history list",
   re.search(r"del self\.app\.history\[", HIST_SRC) is not None)
ck("Listen plays through the shared player",
   "play_text" in HIST_SRC)

# --- 3. OCR overlay keys ------------------------------------------------
OV = io.open(os.path.join(ROOT, "qtranslate", "qt", "ocr_pick.py"),
             encoding="utf-8").read()
o_tree = ast.parse(OV)
kpf = [x for x in ast.walk(o_tree)
       if isinstance(x, ast.FunctionDef) and x.name == "keyPressEvent"]
ck("overlay defines the key handler", len(kpf) == 1)
gp = [x for x in ast.walk(o_tree)
      if isinstance(x, ast.FunctionDef) and x.name == "_grab_png"]
ck("overlay shares one _grab_png capture path", len(gp) == 1)
if kpf:
    seg = ast.get_source_segment(OV, kpf[0])
    for k in ("Key_S", "Key_C", "Key_Return", "Key_Delete", "Key_Escape",
              "_grab", "_png_of", "Key_Left", "Key_Right", "Key_Up",
              "Key_Down"):
        ck("overlay handles %s" % k, k in seg, k)
    ck("C copies to the clipboard, not a viewer",
       "setPixmap" in seg or "clipboard" in seg, seg[:60])

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
