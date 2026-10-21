"""Regression: the Phase 7 delegators forward their arguments.

`app.py` keeps thin delegators for the bodies that moved to
`qtranslate/windows.py` (`self._main.<name>(...)`). A delegator that
drops an argument, or that is a `@staticmethod` whose body still uses
`self`, is a silent break: the call raises, and the caller swallows it.

That is not hypothetical. `App.tag_links` was a `@staticmethod` whose
body read `self._main.tag_links(text, on_click)` -- so **every** call
raised `NameError: name 'self' is not defined`, `render()` could not
fill the result pane at all, and the port could not show a
translation. Nothing in the suite called `render()`.

The checks here are structural (an AST walk over the delegators) plus
two behavioural ones, so the class of bug cannot come back.
"""

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


APP = os.path.join(ROOT, "qtranslate", "app.py")
WIN = os.path.join(ROOT, "qtranslate", "windows.py")
_app_src = open(APP, encoding="utf-8").read()
_win_src = open(WIN, encoding="utf-8").read()
_app_tree = ast.parse(_app_src)

# --- 1. no delegator drops an argument --------------------------------------
delegators = []
for node in ast.walk(_app_tree):
    if not isinstance(node, ast.ClassDef):
        continue
    for item in node.body:
        if not isinstance(item, ast.FunctionDef):
            continue
        _body = [b for b in item.body
                 if not (isinstance(b, ast.Expr)
                         and isinstance(b.value, ast.Constant))]
        if len(_body) != 1 or not isinstance(_body[0], ast.Return):
            continue
        val = _body[0].value
        if not isinstance(val, ast.Call) or not isinstance(val.func, ast.Attribute):
            continue
        if val.func.attr != item.name:
            continue
        target = ast.unparse(val.func.value)
        if target not in ("self._main", "_MAIN_APP"):
            continue
        delegators.append((node.name, item, val, target))

ck("the delegators were found", len(delegators) > 5, str(len(delegators)))
for cls, item, val, target in delegators:
    sent = [ast.unparse(a) for a in val.args]
    want = [a.arg for a in item.args.args if a.arg != "self"]
    ck("%s.%s forwards every argument" % (cls, item.name), sent == want,
       "declared %r, forwarded %r" % (want, sent))

# --- 2. no delegator is a staticmethod whose body uses `self` ---------------
for node in ast.walk(_app_tree):
    if not isinstance(node, ast.ClassDef):
        continue
    for item in node.body:
        if not isinstance(item, ast.FunctionDef):
            continue
        if "staticmethod" not in [ast.unparse(d) for d in item.decorator_list]:
            continue
        body = ast.get_source_segment(_app_src, item) or ""
        if "self." in body:
            ck("%s.%s (a staticmethod) does not use `self`" % (node.name,
                                                                item.name),
               False, body.splitlines()[0][:70])

# --- 3. the same for windows.py ---------------------------------------------
_win_tree = ast.parse(_win_src)
for node in ast.walk(_win_tree):
    if not isinstance(node, ast.ClassDef):
        continue
    for item in node.body:
        if not isinstance(item, ast.FunctionDef):
            continue
        if "staticmethod" not in [ast.unparse(d) for d in item.decorator_list]:
            continue
        first = item.args.args[0].arg if item.args.args else ""
        if first in ("self", "cls"):
            ck("%s.%s (a staticmethod) does not take `self`" % (node.name,
                                                                 item.name),
               False, first)

# --- 4. behaviour: render() fills the result pane ---------------------------
import tkinter as tk  # noqa: E402
from qtranslate import app as A  # noqa: E402

root = tk.Tk()
root.withdraw()
app = A.App(root)
root.update_idletasks()
root.update()

try:
    app.render("HELLO WORLD")
    ck("render() fills the result pane",
       app.out.get("1.0", "end-1c") == "HELLO WORLD",
       repr(app.out.get("1.0", "end-1c")))
except Exception as exc:
    ck("render() fills the result pane", False, repr(exc))

try:
    app.render("RESULT", "BACK")
    ck("render() fills the back-translation pane",
       app.aux.get("1.0", "end-1c") == "BACK",
       repr(app.aux.get("1.0", "end-1c")))
except Exception as exc:
    ck("render() fills the back-translation pane", False, repr(exc))

# --- 5. behaviour: tag_links tags the WIDGET it is handed -------------------
try:
    app.tag_links(app.out, "see https://example.com now", lambda e: None)
    ranges = app.out.tag_ranges("link")
    ck("tag_links tags the widget it is handed",
       bool(ranges), "no link tag on the result pane")
except Exception as exc:
    ck("tag_links tags the widget it is handed", False, repr(exc))

root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_delegators: all checks ok (%d assertions)" % n[0])
