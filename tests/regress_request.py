"""Pin the TranslationRequest value object (Phase 2 domain model).

`ARCHITECTURE.md` §3.1 requires the fallback guarantee "preserve the
request across providers" to be STRUCTURAL: one frozen request travels
the chain; `with_src`/`shaped` return derived copies, so a provider that
mutates src (auto-detect) cannot corrupt the original for the next
fallback.

Offline: dataclass semantics only, no window, no network.
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate.core import TranslationRequest as R

# --- frozen -------------------------------------------------------------
r = R(service="google", text="hello", target="vi")
_boom = False
try:
    r.text = "mutated"
except dataclasses.FrozenInstanceError:
    _boom = True
ck("the request is frozen (fallback cannot mutate it)", _boom)

# --- defaults mirror the historical signature --------------------------
ck("defaults match do_translate's", (r.src, r.auto_detect, r.back_translate)
   == ("auto", False, False), repr((r.src, r.auto_detect, r.back_translate)))

# --- with_src returns a copy, original untouched ------------------------
r2 = r.with_src("en")
ck("with_src replaces src", r2.src == "en", r2.src)
ck("original src unchanged", r.src == "auto", r.src)
ck("with_src keeps everything else",
   (r2.service, r2.text, r2.target) == (r.service, r.text, r.target))

# --- shaped returns a copy, text-only ------------------------------------
r3 = r.shaped("  hello world  ")
ck("shaped replaces text", r3.text == "  hello world  ")
ck("original text unchanged", r.text == "hello")
ck("shaped keeps src/tgt", (r3.src, r3.target) == (r.src, r.target),
   repr((r3.src, r3.target)))

# --- the chain returns derived copies in order ---------------------------
r4 = r.shaped("hello").with_src("en")
ck("shaped().with_src() compose", (r4.text, r4.src) == ("hello", "en"))
ck("base request still pristine after the chain",
   (r.text, r.src) == ("hello", "auto"))

# --- engine builds the request from its positional signature -------------
from qtranslate import engine as E
import inspect
ck("engine.translate keeps the historical signature",
   str(inspect.signature(E.translate))
   == "(service, text, target, src='auto', auto_detect=False, "
   "back_translate=False)",
   str(inspect.signature(E.translate)))

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_request: all checks ok (%d assertions)" % n[0])
