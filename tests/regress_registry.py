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
APP_SRC = io.open(os.path.join(ROOT, "qtranslate", "app.py"),
                  encoding="utf-8").read()

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
ck("app.py aliases the two helpers, defines neither",
   "from qtranslate.registry import call_with_sink as _t_call" in APP_SRC
   and "from qtranslate.registry import apply_phonetics as _apply_phonetics"
   in APP_SRC
   and re.search(r"^def _t_call\(", APP_SRC, re.M) is None
   and re.search(r"^def _apply_phonetics\(", APP_SRC, re.M) is None)
ck("app.py holds a capability alias, not a second literal",
   "from qtranslate.registry import USES_AUTO_DETECT" in APP_SRC
   and re.search(r"^_USES_AUTO_DETECT\s*=\s*\{", APP_SRC, re.M) is None)

# app.py must no LONGER define its own dispatch tables or import providers
# for dispatch.SUPPORTED_LANGS constant imports stay allowed: that is the
# shared language-index table, not dispatch.
ck("app.py aliases the registry tables",
   "from qtranslate.registry import TRANSLATORS, DICTS" in APP_SRC,
   "app.py must alias, not re-define")
ck("app.py has no TRANSLATORS literal",
   re.search(r"^TRANSLATORS = \{", APP_SRC, re.M) is None,
   "second table = second source of truth")
ck("app.py has no DICTS literal",
   re.search(r"^DICTS = \{", APP_SRC, re.M) is None)
ck("app.py defines no _t_* adapter",
   re.search(r"^def _t_(google|deepl|yandex|baidu|naver|youdao|bing|babylon|promt)\(",
             APP_SRC, re.M) is None,
   "provider adapters live in registry")
for _mod in ("deepl", "yandex", "baidu", "naver", "youdao", "microsoft",
             "promt", "babylon", "google_translate", "dictionary", "spell"):
    ck("app.py does not alias services.%s for dispatch" % _mod,
       ("services import %s as _" % _mod) not in APP_SRC)
ck("app.py does not import session for dispatch",
   "from qtranslate.session import" not in APP_SRC)
ck("app.py aliases registry.detect_language (no second copy)",
   "from qtranslate.registry import detect_language" in APP_SRC
   and re.search(r"^def detect_language\(", APP_SRC, re.M) is None)
ck("registry owns SERVICE_LINKS + service_link()",
   re.search(r"^SERVICE_LINKS = \{", REG_SRC, re.M) is not None
   and "def service_link(" in REG_SRC)
ck("app.py aliases links, defines neither",
   "from qtranslate.registry import SERVICE_LINKS as _SERVICE_LINKS"
   in APP_SRC
   and "from qtranslate.registry import service_link as _dict_service_link"
   in APP_SRC
   and re.search(r"^_SERVICE_LINKS = \{", APP_SRC, re.M) is None
   and re.search(r"^def _dict_service_link\(", APP_SRC, re.M) is None)
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

# ===================== half 2: live (needs tkinter) =====================

try:
    import tkinter  # noqa: F401
    HAS_TK = True
except ImportError:
    HAS_TK = False

if not HAS_TK:
    skip("live table comparison", "no tkinter; app cannot be imported")
else:
    from qtranslate import registry as RG
    from qtranslate import app as A

    t, d = RG.translators(), RG.dicts()
    ck("translators() == app.TRANSLATORS", t == A.TRANSLATORS,
       "%d vs %d keys" % (len(t), len(A.TRANSLATORS)))
    ck("dicts() == app.DICTS", d == A.DICTS,
       "%d vs %d keys" % (len(d), len(A.DICTS)))
    ck("app.TRANSLATORS IS registry.TRANSLATORS (alias, not copy)",
       A.TRANSLATORS is RG.TRANSLATORS)
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
