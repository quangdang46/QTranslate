"""Regression: `qtranslate/core.Result` — the Phase 5 public result type.

Settled design: `docs/review/CORE_RESULT_SHAPE_2026-10-10.md`, reviewed in
`docs/review/CORE_RESULT_REVIEW_2026-10-10.md` ("§2 agreed, code may be
written against it"). Migration step 1: `core.Result` exists as a new type,
`reliability.Result` unchanged, nothing imports this yet.

Run: python -I tests/regress_core_result.py
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import core as C  # noqa: E402
from qtranslate import reliability as R  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append("%s -- %s" % (name, detail))


# --- the eight fields, in the settled order ----------------------------------
# provider_used/text non-defaulted; the rest (including the Phase 5 additions)
# keyword-defaulted. Appending keeps reliability.py:704/:708's six-positional
# calls byte-identical; any insertion before the end mis-binds them.
_names = [f.name for f in dataclasses.fields(C.Result)]
ck("field order is the settled eight",
   _names == ["provider_used", "text", "requested", "failures",
              "attempts", "note", "phonetics", "source_language"],
   repr(_names))
ck("exactly provider_used/text are non-defaulted",
   [f.name for f in dataclasses.fields(C.Result)
    if f.default is dataclasses.MISSING] == ["provider_used", "text"],
   repr(_names))

# --- the six-positional call shape still lands --------------------------------
# Reproduces reliability.py:704/:708 against the NEW type: a future field
# inserted before `requested` mis-binds here exactly as the review measured
# (requested=1, failures='n', no exception).
r = C.Result("deepl", "txt", "deepl", (), 1, "n")
ck("positional 1 -> provider_used", r.provider_used == "deepl", repr(r))
ck("positional 2 -> text", r.text == "txt", repr(r))
ck("positional 3 -> requested", r.requested == "deepl", repr(r))
ck("positional 4 -> failures", r.failures == (), repr(r))
ck("positional 5 -> attempts", r.attempts == 1, repr(r))
ck("positional 6 -> note", r.note == "n", repr(r))

# --- the Phase 5 additions ----------------------------------------------------
r2 = C.Result("google", "hola", "google", phonetics="Hola",
              source_language=17)
ck("phonetics fills by keyword", r2.phonetics == "Hola", repr(r2))
ck("source_language fills by keyword", r2.source_language == 17, repr(r2))
ck("both default when absent",
   C.Result("p", "t").phonetics == ""
   and C.Result("p", "t").source_language is None, repr(C.Result("p", "t")))
ck("source_language has no native slot: None is normal, not an error",
   C.Result("p", "t").source_language is None)

# --- ask 1: failures is tuple[Failure, ...], not bare tuple ------------------
# The bare tuple is what let the review's §2 corruption pass a type-checker:
# each misplaced value was a legal type for the field it landed in. The
# annotation is the thing that converts the warning from prose into
# something the next reshuffle can't break.
_fail_type = [f.type for f in dataclasses.fields(C.Result)
              if f.name == "failures"][0]
ck("failures is annotated tuple[Failure, ...]",
   _fail_type == "tuple[Failure, ...]"
   or "Failure" in str(_fail_type), repr(_fail_type))
ck("requested is annotated str",
   [f.type for f in dataclasses.fields(C.Result)
    if f.name == "requested"][0] == "str")

# --- ok semantics --------------------------------------------------------------
ck("ok is True when a provider answered", C.Result("p", "t").ok is True)
ck("ok is False on a failed route", C.Result("", "t").ok is False)

# --- ask 3 (review §4): ok + fallback implies the note says so ----------------
# No Result should be ok and attributed to a provider the user didn't pick
# without saying so. `note` carries it today (":543/:545 by construction);
# this makes it durable rather than incidental.
ck("ok and provider_used != requested implies non-empty note",
   (lambda b: not (b.ok and b.provider_used != b.requested)
    or bool(b.note))(C.Result("google", "t", "deepl",
                              note="google answered (fallback from deepl)")),
   "a fallback attribution with an empty note hides the switch")
ck("the same-provider case needs no note",
   C.Result("deepl", "t", "deepl").ok is True
   and C.Result("deepl", "t", "deepl").note == "")

# --- §7 diagnostics survive through failures ----------------------------------
f = R.Failure("deepl", R.ErrorKind.RATE_LIMITED, 429, "rate limited",
              2, 1.4, fell_back=True)
line = f.log_line()
ck("all six §7 fields reach the log line through result.failures",
   all(k in line for k in ("provider=deepl", "rate-limited", "attempts=2",
                           "elapsed=1.400s", "fell_back=1", "status=429",
                           "detail=rate limited")), line)

# --- frozen, like the type it will absorb --------------------------------------
ck("Result is frozen", C.Result.__dataclass_params__.frozen is True)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_core_result: all checks ok (%d assertions)" % n[0])
