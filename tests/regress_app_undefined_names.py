"""Regression pin for the undefined-name bugs fixed in ``qtranslate/app.py``.

Three latent ``NameError``s, each swallowed by a bare ``except Exception: pass``
so they never crashed the app — they silently disabled a feature:

1. ``_gp`` was *read* (ShowTopPane/ShowMiddlePane) before it was *assigned*,
   so the top/middle panes never hid.
2. ``except Exception as e`` then a deferred ``lambda`` referenced ``e``,
   which Python 3 unbinds at the end of the ``except`` block.
3. ``show_popup(..., res.source_language_code or src)`` passed an undefined
   ``src`` for the popup's ``src_lang``.

The buggy paths are GUI-only, so the pins are structural (read ``app.py`` as
text/AST; no Tk root is created). Offline, no network.

Cross-scope note: the fixes live in ``qtranslate/`` (src scope); this suite is
their regression coverage and therefore lives in ``tests/`` (test scope).
"""
import ast
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "qtranslate", "app.py"),
              encoding="utf-8").read()
TREE = ast.parse(SRC)


def _method(name):
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


# --- 1. _gp is assigned before its first read in _build_main -----------
_build = _method("_build_main")
if _build is None:
    ck("_build_main exists", False)
else:
    stores, loads = [], []
    for node in ast.walk(_build):
        if isinstance(node, ast.Name) and node.id == "_gp":
            (stores if isinstance(node.ctx, ast.Store) else loads).append(
                node.lineno)
    ck("_gp is assigned before it is read (ShowTopPane/ShowMiddlePane)",
       bool(stores) and bool(loads) and min(stores) < min(loads),
       "stores=%s loads=%s" % (stores, loads))

# --- 2. the speech-error lambda must not reference the except var --------
_bad = []
for node in ast.walk(TREE):
    if isinstance(node, ast.ExceptHandler) and node.name == "e":
        for sub in ast.walk(node):
            if isinstance(sub, ast.Lambda):
                for nm in ast.walk(sub):
                    if isinstance(nm, ast.Name) and nm.id == "e":
                        _bad.append(nm.lineno)
ck("no deferred lambda reads the unbound except var 'e'",
   not _bad, str(_bad))
ck("the speech error is captured in a local (_speech_err)",
   "_speech_err" in SRC)

# --- 3. no show_popup call passes an unbound `src` ----------------------
# `src` is a legitimate local at the hotkey/translate sites (bound from
# app.current()); the clipboard `_poll` discarded it with `_` yet still
# referenced it. Resolve `src` through the whole enclosing-scope chain
# (a lambda is a closure over the function that defines it).
_parent = {}
for _p in ast.walk(TREE):
    for _c in ast.iter_child_nodes(_p):
        _parent[_c] = _p


def _enclosing_funcs(node):
    funcs = []
    cur = node
    while cur in _parent:
        cur = _parent[cur]
        if isinstance(cur, (ast.FunctionDef, ast.Lambda)):
            funcs.append(cur)
    return funcs


def _bound_in(func):
    """Names bound in ``func``'s own scope (params + stores), not nested."""
    bound = set(a.arg for a in func.args.args)
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        stack.extend(ast.iter_child_nodes(node))
    return bound


_bad3 = []
for node in ast.walk(TREE):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == "show_popup":
        if not any(isinstance(a, ast.Name) and a.id == "src"
                   for a in ast.walk(node)):
            continue
        if not any("src" in _bound_in(f) for f in _enclosing_funcs(node)):
            _bad3.append(node.lineno)
ck("no show_popup call passes an unbound `src`", not _bad3, str(_bad3))

# --- 4. the file still parses -------------------------------------------
try:
    compile(SRC, "qtranslate/app.py", "exec")
    ck("app.py compiles", True)
except SyntaxError as exc:
    ck("app.py compiles", False, str(exc))

print("regress_app_undefined_names: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    try:
        print("FAIL:", f)
    except UnicodeEncodeError:
        print("FAIL:", f.encode("ascii", "replace").decode("ascii"))
sys.exit(1 if fails else 0)
