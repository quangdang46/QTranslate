"""Regression: DictionaryExactSearch gates XDXF match breadth.

Native evidence (traced 2026-10-09):
  options +0x181 = DictionaryExactSearch (base 0x5492B0; DAT_00549431).
  Menu "Exact search" (id 30) in the Dictionary window: FUN_00423087 reads
  the flag for its check state; FUN_004262f2 toggles/persists it. The only
  behavioral consumer is the XDXF lookup task FUN_004151c3 (from FUN_00414f54):
  the flag gates a substring/entry fanout -- exact is the default (ON),
  OFF broadens the match.

This test covers the port's flag plumbing only (offline). The exact native
index algorithm is INFERRED; only exact-vs-broader is evidence-backed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))

from qtranslate import xdxf  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


X = ("<xdxf><ar><k>hello</k><tr>həˈloʊ</tr></ar>"
     "<ar><k>hello world</k><tr>x</tr></ar>"
     "<ar><k>world</k><tr>y</tr></ar></xdxf>")

import tempfile  # noqa: E402
import os  # noqa: E402

fd, path = tempfile.mkstemp(suffix=".xdxf")
os.close(fd)
try:
    with open(path, "w", encoding="utf-8") as f:
        f.write(X)

    # exact=True: only the article whose <k> equals the query.
    # (render_article() maps <k> -> <div><b>key</b></div>.)
    exact = xdxf.lookup("hello", path, exact=True)
    check("exact match returns the exact 'hello' article",
          "<b>hello</b>" in exact, exact[:120])
    check("exact match does NOT return the substring article",
          "<b>hello world</b>" not in exact, exact[:200])

    # exact=False: broadened -- first article whose key CONTAINS "world"
    # is "hello world" (deterministic file order).
    broad = xdxf.lookup("world", path, exact=False)
    check("broad (exact=False) matches a key containing 'world'",
          "<b>hello world</b>" in broad, broad[:120])
    # exact=True for "world" must match only the exact <k>world</k>.
    ex_world = xdxf.lookup("world", path, exact=True)
    check("exact match for 'world' returns only the exact article",
          "<b>world</b>" in ex_world and "<b>hello world</b>" not in ex_world,
          ex_world[:120])

    # 'hello' is an exact key, so it is found either way.
    check("exact key found under both modes",
          xdxf.lookup("hello", path, exact=False) != "")

    # default is exact (native default DictionaryExactSearch=true).
    default = xdxf.lookup("hello", path)
    check("default lookup is exact (no substring article)",
          "<b>hello</b>" in default and "<b>hello world</b>" not in default)
finally:
    os.remove(path)

# app wiring: the flag is read and threaded into the offline lookup.
# Phase 7 (2026-10-16): the Dictionary window moved to `qtranslate/windows.py`
# as `DictionaryView`. The tkinter view is gone (2026-10-22): the lookup and
# its flag live in `qtranslate/dictionary_search.py` (Core) and the Qt
# window reads the option and passes it in.
import inspect  # noqa: E402

try:
    from qtranslate import dictionary_search as DS  # noqa: E402
    from qtranslate.qt import dictionary as _dic  # noqa: E402
    src = inspect.getsource(DS) + "\n" + inspect.getsource(_dic)
    check("the exact-search flag is threaded into xdxf.lookup "
          "(no dead branch)",
          "_X.lookup(word, path, exact=exact)" in src,
          "search() passes exact into the lookup")
    check("search() carries the exact parameter through",
          'exact: bool = True' in src and 'exact=exact' in src)
    check("the Qt view reads DictionaryExactSearch and passes it",
          '"DictionaryExactSearch"' in inspect.getsource(_dic))
except Exception as e:  # pragma: no cover - headless
    check("source wiring check", False, repr(e))

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: DictionaryExactSearch gates XDXF match breadth")
