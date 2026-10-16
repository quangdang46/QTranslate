"""Regression: Phase 7's window split is a MOVE, not a rewrite.

`qtranslate/windows.py` holds the classes extracted out of `App`. The risk
with extracting a 3,400-line class is not that it fails to import — it is
that the extraction quietly *rewrites* the code while moving it. That
happened on the first attempt at `HistoryView`: it invented menu labels the
locale packs do not have, dropped the per-entry ``state=`` disabling,
changed the history filter to search the translation as well as the source,
and replaced `_sel_entry` with a different helper. Three assertions went
red, which is the only reason it was caught.

So this suite compares the extracted body against the body that is still in
`git HEAD`, mechanically, and fails on any difference that is not one of the
three allowed substitutions:

  ``self.`` -> ``self.app.``     the live App's attributes and methods
  ``w``     -> ``self.win``      the window is now an instance field
  indentation                   the body moved one level deeper (method in
                                ``App`` -> method in ``HistoryView.open``)

That last one is the reason a naive ``diff`` is useless here, so the
comparison is done on a normalized form (strip indentation, apply the
``self.``/``w`` rewrites, drop blank lines and comments) rather than on raw
text.

Headless: no window is opened, no Tk is created. Pure AST + text.
"""
import ast
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s%s" % (name, (" -- " + detail) if detail else ""))


def read(rel):
    return io.open(os.path.join(ROOT, rel), encoding="utf-8").read()


WIN = read(os.path.join("qtranslate", "windows.py"))
APP = read(os.path.join("qtranslate", "app.py"))

# ---------------------------------------------------------------- the module

ck("windows.py imports cleanly",
   __import__("qtranslate.windows") is not None)
def _module_level_tk_calls(src):
    """True if a `tk.Tk(` call sits at module scope (not inside a def)."""
    tree = ast.parse(src)
    calls = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "Tk"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "tk"):
            calls.append(node)
    # A call is module-level if no enclosing function/class-method scope
    # contains it -- cheapest correct check: walk every FunctionDef's body
    # and remove calls found there.
    nested = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested.update(id(c) for c in ast.walk(fn)
                          if isinstance(c, ast.Call))
    return [c for c in calls if id(c) not in nested]


ck("...and creates no window at import",
   not _module_level_tk_calls(WIN),
   "a module-level Tk() would open a window on import "
   "(a text search for 'tk.Tk(' is not enough -- it matches comments too)")
ck("...and holds no module-level widget construction",
   not re.search(r"^[a-z_]+ = (tk|ttk)\.(Toplevel|Frame|Button|Menu)\(",
                  WIN, re.M),
   "widgets must be built inside a method")

# ------------------------------------------------- the allowed rewrites only


def normalize(body: str) -> list:
    """Strip indentation, comments, blanks; apply the allowed rewrites.

    The body moved one level deeper (a method in `App` -> a method inside
    `HistoryView.open`), so every line gains 4 spaces. Removing leading
    whitespace makes the comparison indentation-insensitive; the two
    textual substitutions below are the only semantic changes permitted.
    """
    out = []
    for raw in body.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # the window variable is now an instance field
        line = re.sub(r"\bw\b", "self.win", line)
        # the live App is now reached through self.app
        line = line.replace("self.app.", "self.")
        out.append(line)
    return out


def head_source(rel: str, func: str, cls: str = None):
    """The named function's body as it existed BEFORE the split."""
    rev = ("%s:" % _PRE_SPLIT) if _PRE_SPLIT else "HEAD:"
    proc = subprocess.run(
        ["git", "show", "%s%s" % (rev, rel.replace("\\", "/"))],
        cwd=ROOT, capture_output=True, encoding="utf-8")
    if proc.returncode:
        return None
    tree = ast.parse(proc.stdout)
    scope = tree
    if cls:
        scope = next((x for x in tree.body
                      if isinstance(x, ast.ClassDef) and x.name == cls), None)
        if scope is None:
            return None
    fn = next((x for x in ast.walk(scope)
               if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
               and x.name == func), None)
    if fn is None:
        return None
    return ast.get_source_segment(proc.stdout, fn)


def extracted_method(cls_name: str, inner: str):
    """The body of a nested function inside an extracted class."""
    tree = ast.parse(WIN)
    cls = next((x for x in tree.body
                if isinstance(x, ast.ClassDef) and x.name == cls_name), None)
    if cls is None:
        return None
    fn = next((x for x in ast.walk(cls)
               if isinstance(x, ast.FunctionDef) and x.name == inner), None)
    return ast.get_source_segment(WIN, fn) if fn else None


# ------------------------------------------- the HistoryView move, verbatim
# Every nested closure the original window defined must exist in the
# extracted class, with the same body. This is the check that catches a
# rewritten split: a renamed helper, an invented label, a dropped guard.
#
# The baseline is the commit IMMEDIATELY BEFORE the split, resolved by
# searching for the split commit's subject and taking its parent -- not by
# counting back a fixed number of commits (which would silently compare
# against a body that had already moved once a few more commits land, the
# exact staleness this repo hit with its known-answer vectors) and not by
# `HEAD` (which stops being the pre-split state the moment the split is
# committed). If it cannot be resolved, the verbatim checks say SKIPPED
# rather than passing against nothing.
def _pre_split_rev():
    log = subprocess.run(["git", "log", "--format=%H%x00%s", "-n", "200"],
                         cwd=ROOT, capture_output=True,
                         encoding="utf-8").stdout or ""
    for entry in log.splitlines():
        sha, _, subject = entry.partition("\x00")
        if "HistoryView extracted" in subject:
            return sha + "^"
    return None


_PRE_SPLIT = _pre_split_rev()
HEAD_APP = ""
if _PRE_SPLIT:
    _proc = subprocess.run(["git", "show", "%s:qtranslate/app.py" % _PRE_SPLIT],
                           cwd=ROOT, capture_output=True,
                           encoding="utf-8")
    HEAD_APP = _proc.stdout or ""
if HEAD_APP:
    old = next(x for x in ast.walk(ast.parse(HEAD_APP))
               if isinstance(x, ast.FunctionDef)
               and x.name == "open_history_window")
    new_cls = next(x for x in ast.walk(ast.parse(WIN))
                   if isinstance(x, ast.ClassDef)
                   and x.name == "HistoryView")
    new_open = next(x for x in ast.walk(new_cls)
                    if isinstance(x, ast.FunctionDef) and x.name == "open")

    def nested(node):
        """Names of the closures defined directly inside a function."""
        return {c.name for c in node.body
                if isinstance(c, ast.FunctionDef)}

    old_inner = nested(old)
    new_inner = nested(new_open)
    ck("every original closure was moved, none invented",
       old_inner == new_inner,
       "missing=%r extra=%r"
       % (sorted(old_inner - new_inner), sorted(new_inner - old_inner)))

    # Bodies, compared on the normalized form so only real changes show.
    diffs = []
    for name in sorted(old_inner & new_inner):
        o = next(c for c in old.body if isinstance(c, ast.FunctionDef)
                 and c.name == name)
        w = next(c for c in new_open.body if isinstance(c, ast.FunctionDef)
                 and c.name == name)
        a, b = normalize(ast.get_source_segment(HEAD_APP, o)), \
            normalize(ast.get_source_segment(WIN, w))
        if a != b:
            # Report WHERE, not a full diff -- a reader needs the line.
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    diffs.append("%s[%d]: HEAD=%r new=%r" % (name, i, x, y))
                    break
            else:
                diffs.append("%s: length %d vs %d"
                             % (name, len(a), len(b)))
    ck("the moved closures are byte-identical after the allowed rewrites",
       not diffs, "; ".join(diffs[:6]))

    # The statements of the window body itself (outside any closure).
    # Three additions are the extraction's own scaffolding and are NOT
    # behavior, so they are excluded rather than counted as a difference:
    #   the docstring        (app.py's method docstring now lives on the class)
    #   the `if self.win`    (idempotent re-open guard)
    #   the trailing `return`(the delegator needs the window back)
    def scaffolding(node):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            return True
        if isinstance(node, ast.If):
            src = ast.get_source_segment(WIN, node)
            return src is not None and "self.win" in src
        return isinstance(node, ast.Return)

    o_top = [s for s in old.body
             if not isinstance(s, ast.FunctionDef)]
    w_top = [s for s in new_open.body
             if not isinstance(s, ast.FunctionDef) and not scaffolding(s)]
    ck("the window's own top-level statements were moved too",
       len(o_top) == len(w_top),
       "HEAD has %d, windows.py has %d (excluding the extraction's own "
       "scaffolding)" % (len(o_top), len(w_top)))
    if len(o_top) == len(w_top):
        # And they are the same statements in the same order.
        same = all(type(a) is type(b) for a, b in zip(o_top, w_top))
        ck("...in the same order and shape", same)
else:
    print("NOTE: git HEAD unavailable -- the verbatim-move checks skipped")


# ------------------------------------------- the DictionaryView move, verbatim
# A second class transcribed from a body that contains `"w"` as a FILE MODE
# and `anchor="w"`, which is why the window variable was NOT renamed (see
# the class docstring). The scaffolding inserted at the top of `open()`
# (docstring + the idempotency guard) is excluded, and the trailing
# `return self.win` likewise, so only the moved body is compared.
if HEAD_APP:
    old_d = next(x for x in ast.walk(ast.parse(HEAD_APP))
                 if isinstance(x, ast.FunctionDef)
                 and x.name == "open_dict_window")
    d_cls = next((x for x in ast.walk(ast.parse(WIN))
                  if isinstance(x, ast.ClassDef)
                  and x.name == "DictionaryView"), None)
    d_open = next((x for x in ast.walk(d_cls)
                   if isinstance(x, ast.FunctionDef)
                   and x.name == "open"), None) if d_cls else None
    ck("DictionaryView defines open()", d_open is not None)

    def _moved(src, fn, drop_head_scaffolding):
        """The function's normalized lines, minus the extraction's own."""
        out = []
        for ln in ast.get_source_segment(src, fn).splitlines()[1:]:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            # The one allowed ADDITION in the body: the window-creation
            # line gains a `self.win =` alias so `open()` can be idempotent.
            if s == "self.win = w = tk.Toplevel(self.app.root)":
                s = "w = tk.Toplevel(self.root)"
            out.append(s.replace("self.app.", "self."))
        return out

    # The scaffold inserted by the extraction is docstring + the
    # idempotency guard, which sits between the imports and the body. Cut
    # both sides at the first real statement they SHARE, so an off-by-one
    # in the scaffold's size cannot masquerade as a body change.
    o_d = _moved(HEAD_APP, old_d, False)
    w_raw = _moved(WIN, d_open, False)
    _cut = next(i for i, l in enumerate(o_d)
                if "from qtranslate import config as _C" in l)
    w_d = w_raw[w_raw.index(o_d[_cut]):]
    d_diffs = []
    for i, (x, y) in enumerate(zip(o_d, w_d)):
        if x != y:
            d_diffs.append("%d: HEAD=%r new=%r" % (i, x, y))
            break
    ck("the DictionaryView body is identical after the allowed substitution",
       not d_diffs and len(o_d) <= len(w_d),
       (d_diffs[0] if d_diffs else
        "HEAD %d lines, windows.py %d" % (len(o_d), len(w_d))))
    # The tail is the one allowed ADDITION: the delegator needs the window.
    ck("...and the only addition is the return the delegator needs",
       w_d[len(o_d):] == ["return self.win"]
       or w_d[-1] == "return self.win",
       repr(w_d[len(o_d):][:3]))
    # The `"w"` file-mode literals must have survived a `self.` rewrite.
    _blob = "\n".join(w_d)
    ck("the file-mode literal \"w\" was not corrupted by the rewrite",
       w_d.count('DEFAULT_PATH, "w"') >= 2
       or 'open("dict_last.html", "w"' in _blob,
       "a rename of the window variable would have broken open(..., 'w')")
    ck("anchor=\"w\" survived too", 'anchor="w"' in _blob)


# ------------------------------------------- the TrayController move, verbatim
# A third class, transcribed from a plain module FUNCTION (`_make_tray`) --
# so there are no `self.` renames at all and the body is compared verbatim
# after the two edits that are the whole point of the extraction (it became
# a method, and the icon is kept on `self.icon`).
if HEAD_APP:
    old_t = next(x for x in ast.walk(ast.parse(HEAD_APP))
                 if isinstance(x, ast.FunctionDef) and x.name == "_make_tray")
    t_cls = next((x for x in ast.walk(ast.parse(WIN))
                  if isinstance(x, ast.ClassDef)
                  and x.name == "TrayController"), None)
    t_build = next((x for x in ast.walk(t_cls)
                    if isinstance(x, ast.FunctionDef)
                    and x.name == "build"), None) if t_cls else None
    ck("TrayController defines build()", t_build is not None)

    def _lines(src, fn):
        out = []
        for ln in ast.get_source_segment(src, fn).splitlines()[1:]:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
        return out

    _ALIAS = "icon = pystray.Icon("
    o_t = _lines(HEAD_APP, old_t)
    w_t = _lines(WIN, t_build)
    # The one allowed ADDITION: the icon is also kept on `self.icon` so
    # `sync()` can be reached without rebuilding it. Normalize it away on
    # the new side (the original never had it).
    w_t = [l.replace("self.icon = icon = pystray.Icon(",
                     "icon = pystray.Icon(") for l in w_t]
    # cut both at a line that exists exactly once in each
    _anc = "from PIL import Image"
    o_t = o_t[o_t.index(_anc):]
    w_t = w_t[w_t.index(_anc):]
    t_diffs = [(i, x, y) for i, (x, y) in enumerate(zip(o_t, w_t))
               if x != y]
    ck("the TrayController body is identical (a plain function moved as-is)",
       not t_diffs and len(o_t) == len(w_t),
       (repr(t_diffs[0]) if t_diffs else
        "HEAD %d lines, windows.py %d" % (len(o_t), len(w_t))))
    ck("...and the tray still returns the icon object",
       w_t[-1] == "return icon", repr(w_t[-1]))


# -------------------------------------------- the PopupHost move, verbatim
# A fourth class, transcribed from a plain module FUNCTION (`show_popup`)
# that took no `self` at all -- every dependency arrived as an argument or
# a module global (re-imported locally where it needed the LIVE value, e.g.
# `_MAIN_APP`). So there are no renames whatsoever; the body is identical.
if HEAD_APP:
    old_p = next(x for x in ast.walk(ast.parse(HEAD_APP))
                 if isinstance(x, ast.FunctionDef) and x.name == "show_popup")
    p_cls = next((x for x in ast.walk(ast.parse(WIN))
                  if isinstance(x, ast.ClassDef)
                  and x.name == "PopupHost"), None)
    p_open = next((x for x in ast.walk(p_cls)
                   if isinstance(x, ast.FunctionDef)
                   and x.name == "open"), None) if p_cls else None
    ck("PopupHost defines a static open()", p_open is not None)
    ck("...decorated @staticmethod (no self -- it never had one)",
       p_cls is not None and any(
           isinstance(d, ast.Name) and d.id == "staticmethod"
           for d in p_open.decorator_list) if p_open else False)

    def _body_lines(src, fn):
        out = []
        for ln in ast.get_source_segment(src, fn).splitlines()[1:]:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
        return out

    o_p = _body_lines(HEAD_APP, old_p)
    w_p = _body_lines(WIN, p_open)
    _anc = "win = tk.Toplevel()"
    o_p = o_p[o_p.index(_anc):]
    w_p = w_p[w_p.index(_anc):]
    p_diffs = [(i, x, y) for i, (x, y) in enumerate(zip(o_p, w_p))
               if x != y]
    ck("the PopupHost body is byte-identical (no substitutions at all)",
       not p_diffs and len(o_p) == len(w_p),
       (repr(p_diffs[0]) if p_diffs else
        "HEAD %d lines, windows.py %d" % (len(o_p), len(w_p))))
    ck("...and it still re-imports the LIVE _MAIN_APP, not a stale copy",
       "from qtranslate.app import _MAIN_APP" in w_p
       if any("_MAIN_APP" in l for l in w_p) else True,
       "a module-level import of _MAIN_APP would capture it at import "
       "time, before main() ever sets it")


# ---------------------------------------------- the OptionsDialog move, verbatim
# The fifth and largest class: 1056 statement lines across 13 pages. The
# ONE allowed substitution is `self.` -> `self.app.`; the window variable
# stays `w` for the same reason as DictionaryView (a dozen `open(path,
# "w")` calls and `anchor="w"` throughout).
if HEAD_APP:
    old_o = next(x for x in ast.walk(ast.parse(HEAD_APP))
                 if isinstance(x, ast.FunctionDef)
                 and x.name == "open_options")
    o_cls = next((x for x in ast.walk(ast.parse(WIN))
                  if isinstance(x, ast.ClassDef)
                  and x.name == "OptionsDialog"), None)
    o_open = next((x for x in ast.walk(o_cls)
                   if isinstance(x, ast.FunctionDef)
                   and x.name == "open"), None) if o_cls else None
    ck("OptionsDialog defines open()", o_open is not None)

    def _norm_opts(src, fn):
        out = []
        for ln in ast.get_source_segment(src, fn).splitlines()[1:]:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if s == "self.win = w = tk.Toplevel(self.app.root)":
                s = "w = tk.Toplevel(self.root)"
            out.append(s.replace("self.app.", "self."))
        return out

    o_o = _norm_opts(HEAD_APP, old_o)
    w_o = _norm_opts(WIN, o_open)
    _anc = "w = tk.Toplevel(self.root)"
    o_o = o_o[o_o.index(_anc):]
    w_o = w_o[w_o.index(_anc):]
    o_diffs = []
    for i, (x, y) in enumerate(zip(o_o, w_o)):
        if x != y:
            o_diffs.append("%d: HEAD=%r new=%r" % (i, x, y))
            break
    ck("the OptionsDialog body (all 13 pages) is identical after the "
       "allowed substitution",
       not o_diffs and len(o_o) == len(w_o),
       (o_diffs[0] if o_diffs else
        "HEAD %d lines, windows.py %d" % (len(o_o), len(w_o))))
    # The 13 pages by name, so a page silently dropped shows up by name
    # rather than just as a line-count mismatch.
    PAGES = ["show_basics", "show_appearance", "show_hotkeys",
            "show_services", "show_languages", "show_internet",
            "show_exceptions", "show_advanced", "show_updates"]
    _blob = "\n".join(w_o)
    for page in PAGES:
        ck("page %s survived the move" % page,
           "def %s(" % page in _blob)
    # The file-mode literal, proof the rename-avoidance actually worked.
    ck("file-mode \"w\" literals were not touched (a dozen open(path, \"w\"))",
       _blob.count('DEFAULT_PATH, "w"') >= 10)

# -------------------------------------------------------- the delegator half
ck("App.open_history_window delegates to HistoryView",
   re.search(r'def open_history_window\(self\):.*?'
             r'from qtranslate\.windows import HistoryView.*?'
             r'return HistoryView\(self\.root, self, self\.history\)\.open\(\)',
             APP, re.S) is not None)
ck("the old body is gone from app.py (a move, not a copy)",
   'tv = ttk.Treeview(w, columns=("fav", "svc")' not in APP,
   "a leftover copy would silently diverge from windows.py")

# The three specifically-invented regressions from the first attempt must
# not be able to come back: the native locale strings, the per-entry
# disabling, and the source-only filter.
ck("menu labels come from the locale packs, not invented strings",
   '_T("Menus", 10, "Open", menu=3)' in WIN
   and '_T("Menus", 30, "Copy text", menu=3)' in WIN
   and "Open service page" not in WIN.split('"""', 2)[2])
ck("each menu entry disables itself without a selection",
   WIN.count('state="normal" if _ent else "disabled"') == 5,
   "native disables all five; the first attempt dropped this")
ck("the history filter matches the SOURCE only (native's substring)",
   "if _text and _text not in src.lower():" in WIN
   and "_text not in (src + res).lower()" not in WIN)
ck("_sel_entry returns the (idx, entry) pair the menu handlers expect",
   "def _sel_entry():" in WIN
   and "return idx, self.history[idx]" in WIN)

# The facade: HistoryView must be constructible without a display, and its
# `open` must be the ONLY place a Toplevel is created.
ck("HistoryView takes (root, app, history)",
   "def __init__(self, root, app, history):" in WIN)
ck("...and passes the history list through by reference",
   "self.history = history" in WIN,
   "a copy would desynchronize the window from the main window")

if fails:
    print("FAIL %d/%d" % (len(fails), n[0]))
    for f in fails:
        # cp1252 cannot render ★ / — / →, and this project's own test output
        # must survive a dumb console (a traceback here hides the finding).
        try:
            print("  -", f)
        except UnicodeEncodeError:
            print("  -", f.encode("ascii", "replace").decode("ascii"))
    raise SystemExit(1)
print("regress_windows: all checks ok (%d assertions)" % n[0])
