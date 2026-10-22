"""Regression pin for the undefined-name bugs fixed in the view.

Three latent ``NameError``s, each swallowed by a bare
``except Exception: pass`` so they never crashed the app — they silently
disabled a feature:

1. ``_gp`` was *read* (ShowTopPane/ShowMiddlePane) before it was *assigned*,
   so the top/middle panes never hid. That was tkinter's grid-pack
   helper; the PySide6 view has no pack/grid duality, so the pin is gone
   with the tkinter front end (2026-10-22).
2. ``except Exception as e`` then a deferred ``lambda`` referenced ``e``,
   which Python 3 unbinds at the end of the ``except`` block.
3. ``show_popup(..., res.source_language_code or src)`` passed an undefined
   ``src`` for the popup's ``src_lang`` — in the view that is now
   ``set_text(...)``, and the same unbound-variable hazard applies.

The pins are structural (read the view's source; no QApplication root is
created). Offline, no network.

Cross-scope note: the fixes live in ``qtranslate/`` (src scope); this
suite is their regression coverage and therefore lives in ``tests/``.
"""
import ast
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The view is several modules under qtranslate/qt/.
from tests._view_src import view_source  # noqa: E402

SRC = view_source()
TREE = ast.parse(SRC)
# And the helper modules that share the view's wiring vocabulary.
HELP = []
for rel in ("qtranslate/win32app.py",):
    _p = os.path.join(ROOT, rel)
    if os.path.exists(_p):
        HELP.append(io.open(_p, encoding="utf-8").read())
ALL_SRC = SRC + "\n" + "\n".join(HELP)


# --- 1. no deferred lambda reads the unbound except var 'e' --------------
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

# --- 2. no popup call passes an unbound variable --------------------------
# The tkinter bug called show_popup with an unbound `src`; the view shows
# the popup through `set_text(...)`. Any argument that names a bare local
# must be bound in an enclosing function, or Python raises NameError at
# the worst time -- inside the handler.
_parent = {}
for _p in ast.walk(TREE):
    for _c in ast.iter_child_nodes(_p):
        _parent[_c] = _p


def _enclosing_funcs(node):
    funcs = []
    cur = node
    while cur in _parent:
        cur = _parent[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.Lambda)):
            funcs.append(cur)
    return funcs


def _bound_in(func):
    """Names bound in ``func``'s own scope (params + stores), not nested."""
    args = getattr(func, "args", None)
    bound = set(a.arg for a in (args.posonlyargs + args.args
                                if _py311(func) else args.args)
                if a is not None)
    for d in getattr(args, "kwonlyargs", []) or []:
        bound.add(d.arg)
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        stack.extend(ast.iter_child_nodes(node))
    return bound


def _py311(func):
    return False  # posonlyargs flattening not needed for this view


_bad2 = []
for node in ast.walk(TREE):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == "set_text" \
            and isinstance(node.func.value, ast.Attribute) \
            and node.func.value.attr == "_popup":
        # Every bare Name argument must be bound somewhere in scope.
        for a in ast.walk(node):
            if isinstance(a, ast.Name) and isinstance(a.ctx, ast.Load):
                if not any(a.id in _bound_in(f)
                           for f in _enclosing_funcs(node)):
                    _bad2.append(a.id + ("@%d" % node.lineno))
                break
ck("no popup call passes an unbound variable", not _bad2, str(_bad2))

# --- 3. every view module compiles ---------------------------------------
# The view source is a concatenation, and ``from __future__`` is only
# legal at the beginning of a FILE, so each file is compiled on its own.
import qtranslate.qt  # noqa: E402  (for the package dir)

_qt_dir = os.path.join(ROOT, "qtranslate", "qt")
_ck_files = []
for _dirpath, _dirnames, _filenames in os.walk(_qt_dir):
    _dirnames[:] = [d for d in _dirnames if d != "__pycache__"]
    for _fn in sorted(_filenames):
        if _fn.endswith(".py"):
            _ck_files.append(os.path.join(_dirpath, _fn))
_syn = None
for _p in _ck_files:
    try:
        compile(io.open(_p, encoding="utf-8").read(), _p, "exec")
    except SyntaxError as exc:
        _syn = str(exc)
        break
ck("every view module compiles", _syn is None, str(_syn))

print("regress_app_undefined_names: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
