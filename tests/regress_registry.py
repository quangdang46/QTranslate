"""Registry is the single source of truth for dispatch (Phase 2 slice).

CURRENT_STATE.md §3 names the three-source-of-truth problem:
``app.TRANSLATORS`` / ``app.DICTS`` hardcoded tables plus a dead
``services.REGISTRY``. ``qtranslate/registry.py`` owns the canonical
tables; this suite pins that.

Two halves, deliberately separated (peer finding 2026-10-15: the source
asserts used to sit below a ``if not HAS_TK: exit(2)`` gate, so the most
important checks — "app.py no longer imports providers for dispatch" —
were silently skipped on a headless interpreter):

1. **Static half (always runs, headless).** Reads ``registry.py`` and
   ``app.py`` as text/AST. Never needs tkinter. These are the checks that
   guard the migration, so they must never be conditional.
2. **Live half (skips honestly when tkinter is absent).** Imports the
   modules and compares the live tables. Reported as ``SKIPPED`` with a
   reason, never as PASS.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

n = [0]
skipped = []


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        skipped.append("FAIL: %s -- %s" % (name, detail))


def skip(name, reason):
    n[0] += 1
    skipped.append("SKIP: %s -- %s" % (name, reason))


from qtranslate import registry as _RG  # noqa: E402
REG_SRC = io.open(os.path.join(ROOT, "qtranslate", "registry.py"),
                  encoding="utf-8").read()
# The view is the PySide6 front end now (the tkinter one is gone, and
# with it the file this used to read). The intent of the checks below
# is unchanged: the VIEW must use the registry's tables, never its own.
_QT_DIR = os.path.join(ROOT, "qtranslate", "qt")
APP_SRC = "\n".join(
    io.open(os.path.join(_QT_DIR, _f), encoding="utf-8").read()
    for _f in sorted(os.listdir(_QT_DIR)) if _f.endswith(".py"))

# ===================== half 1: static, always runs =====================

# registry owns the tables itself
ck("registry defines TRANSLATORS",
   re.search(r"^TRANSLATORS = \{", REG_SRC, re.M) is not None)
ck("registry defines DICTS",
   re.search(r"^DICTS = \{", REG_SRC, re.M) is not None)
ck("registry defines the 9 _t_* adapters",
   len(re.findall(r"^def _t_\w+\(", REG_SRC, re.M)) == 9,
   str(len(re.findall(r"^def _t_\w+\(", REG_SRC, re.M))))
ck("registry defines detectors()",
   "def detectors(" in REG_SRC)
ck("registry defines router_order()",
   "def router_order(" in REG_SRC)
ck("registry defines google_suggest()",
   "def google_suggest(" in REG_SRC)
ck("registry owns USES_AUTO_DETECT + uses_auto_detect()",
   "def uses_auto_detect(" in REG_SRC
   and _RG.uses_auto_detect("microsoft") is True
   and _RG.uses_auto_detect("no-such-service") is False)
ck("registry owns call_with_sink + apply_phonetics",
   "def call_with_sink(" in REG_SRC
   and "def apply_phonetics(" in REG_SRC)
ck("the view defines neither of the two helpers",
   re.search(r"^def _t_call\(", APP_SRC, re.M) is None
   and re.search(r"^def _apply_phonetics\(", APP_SRC, re.M) is None)
ck("the view holds no capability table of its own",
   re.search(r"^_?USES_AUTO_DETECT\s*=\s*\{", APP_SRC, re.M) is None)

# app.py must no LONGER define its own dispatch tables or import providers
# for dispatch.SUPPORTED_LANGS constant imports stay allowed: that is the
# shared language-index table, not dispatch.
ck("the view has no TRANSLATORS literal",
   re.search(r"^\s*TRANSLATORS = \{", APP_SRC, re.M) is None,
   "second table = second source of truth")
ck("the view has no DICTS literal",
   re.search(r"^\s*DICTS = \{", APP_SRC, re.M) is None)
ck("the view defines no _t_* adapter",
   re.search(r"^\s*def _t_(google|deepl|yandex|baidu|naver|youdao|bing|babylon|promt)\(",
             APP_SRC, re.M) is None,
   "provider adapters live in registry")
for _mod in ("deepl", "yandex", "baidu", "naver", "youdao", "microsoft",
             "promt", "babylon", "google_translate", "dictionary", "spell"):
    ck("the view does not alias services.%s for dispatch" % _mod,
       ("services import %s as _" % _mod) not in APP_SRC)
ck("the view does not import session for dispatch",
   "from qtranslate.session import" not in APP_SRC)
ck("the view has no second copy of detect_language",
   re.search(r"^\s*def detect_language\(", APP_SRC, re.M) is None)
ck("registry owns SERVICE_LINKS + service_link()",
   re.search(r"^SERVICE_LINKS = \{", REG_SRC, re.M) is not None
   and "def service_link(" in REG_SRC)
ck("the view defines neither of the link helpers",
   re.search(r"^\s*_?SERVICE_LINKS = \{", APP_SRC, re.M) is None
   and re.search(r"^\s*def _?dict_service_link\(", APP_SRC, re.M) is None)
ck("SUPPORTED_LANGS constant import is allowed (not dispatch)",
   "SUPPORTED_LANGS" in APP_SRC)

# registry must be tkinter-free by construction: no import statement for
# it (docstring prose may mention the word, which is why this is anchored
# to import lines, not a substring search).
ck("registry does not import tkinter",
   re.search(r"^\s*(import|from)\s+tkinter\b", REG_SRC, re.M) is None)
ck("registry does not import app at module level",
   not re.search(r"^from qtranslate\.app import|^import qtranslate\.app",
                 REG_SRC, re.M))

# ===================== half 2: live ================================
# The live half used to be gated on tkinter, because it compared the
# registry's tables with the tkinter front end's aliases. That view is
# gone (2026-10-22), so the comparison is with the registry's own
# tables -- which is what the aliases were checked against anyway.

from qtranslate import registry as RG

if True:
    t, d = RG.translators(), RG.dicts()
    ck("translators() == registry.TRANSLATORS", t == RG.TRANSLATORS,
       "%d vs %d keys" % (len(t), len(RG.TRANSLATORS)))
    ck("dicts() == registry.DICTS", d == RG.DICTS,
       "%d vs %d keys" % (len(d), len(RG.DICTS)))
    ck("10 translate entries", len(t) == 10, str(sorted(t)))
    # 11, not 10: youdao (id 26) is the one TRANSLATE|DICTIONARY service, and
    # an earlier version of this table omitted it -- so `_ID2FN`'s "youdao"
    # key had no entry, the lookup returned None, and the service silently
    # never ran. The count going 10 -> 11 was the fix; the old assertion
    # would have flagged it as a regression.
    ck("11 dict entries (10 dictionary + youdao, the TRANSLATE|DICTIONARY "
       "service)", len(d) == 11, str(sorted(d)))
    ck("youdao is one of them", "youdao" in d, str(sorted(d)))
    ck("...and its entry resolves language indices before calling",
       all(k in __import__("inspect").getsource(d["youdao"])
           for k in ("SUPPORTED_LANGS", "code_from_language")),
       repr(__import__("inspect").getsource(d["youdao"]))[:200])

    order = RG.router_order()
    # Slice 1 rule (b): "bing" is an alias of "microsoft" (same
    # callable), not an independent chain entry.
    ck("router_order covers every translator (bing aliased)",
       sorted(order) == sorted(k for k in t if k != "bing"), str(order))
    ck("google is head (ServicesOrder id 1 first)",
       order[0] == "google", str(order))
    r = RG.build_router()
    ck("build_router returns a ProviderRouter",
       type(r).__name__ == "ProviderRouter", repr(type(r)))
    ck("router order == registry order",
       list(r.router.order) == order, str(r.router.order))

    det = RG.detectors()
    ck("detectors() has 6 providers", len(det) == 6, str(len(det)))
    ck("detectors are callables", all(callable(f) for f in det))

bad = [s for s in skipped if s.startswith("FAIL")]
soft = [s for s in skipped if not s.startswith("FAIL")]
for s in skipped:
    print(s)
print("regress_registry: %d checks, %d failed, %d skipped"
      % (n[0], len(bad), len(soft)))
sys.exit(1 if bad else 0)
