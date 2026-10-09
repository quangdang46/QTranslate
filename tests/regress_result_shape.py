"""Regression: the result value object's field ORDER.

This looks like a strange thing to test, and it exists because of a bug in
a design sketch rather than in code — `docs/review/CORE_RESULT_SHAPE_2026-10-10.md`
§2. `ProviderRouter.translate` builds a `Result` with **six positional
arguments** (`reliability.py:704` and `:708`):

```python
return Result(route.provider_used, route.text, route.requested,
              route.failures, route.attempts, route.note)
```

Inserting a new field anywhere before `requested` **still parses** and
silently mis-binds every value: `phonetics='deepl', source_language=(),
translation_language=1, note=<the real note>`. Nothing raises; results are
just wrong. So the invariant this suite pins is: *the six existing fields
stay in their current order, and new fields are appended after them.*

If someone reorders the dataclass for readability, this fails loudly instead
of corrupting results quietly.

Phase 5's `core.Result` (the phase-5 sketch) will absorb this type as an
alias; this suite is what makes that swap mechanical rather than risky.
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import reliability as R  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


def t(name, ok, detail=""):
    n[0] += 1
    if not ok:
        fail.append(f"{name} -- {detail}" if detail else name)


# --- the six positional arguments must land in the fields they are named ---
# This reproduces the exact call shape at reliability.py:704/:708.
SENTINEL = "SENTINEL"
# NOTE: comparisons use `is`/`==` explicitly, not the ck() truthiness of the
# value — `failures == ()` is True but a bare `ck(..., ())` reads as falsy.
r = R.Result("prov", "text", "deepl", (), 1, "note")
t("positional 1 -> provider_used", r.provider_used == "prov", repr(r.provider_used))
t("positional 2 -> text", r.text == "text", repr(r.text))
t("positional 3 -> requested", r.requested == "deepl", repr(r.requested))
t("positional 4 -> failures", r.failures == (), repr(r.failures))
t("positional 5 -> attempts", r.attempts == 1, repr(r.attempts))
t("positional 6 -> note", r.note == "note", repr(r.note))

# A field added before `requested` is what makes the above mis-bind, so the
# order itself is asserted rather than only the values.
_names = [f.name for f in dataclasses.fields(R.Result)]
t("requested is the 3rd field",
   _names[:6] == ["provider_used", "text", "requested", "failures",
                  "attempts", "note"], repr(_names))

# The phase-5 additions, when they arrive, must come AFTER the existing six.
# Asserted here so a future insertion is caught rather than shipped.
_expected_tail = [x for x in _names[6:]
                  if x not in ("phonetics", "source_language",
                               "translation_language")]
t("no unexpected field sits inside the first six",
   not _expected_tail, repr(_names))
if len(_names) > 6:
    t("any added field comes after the original six",
       _names[6:] == [x for x in _names[6:]
                      if x in ("phonetics", "source_language",
                               "translation_language")], repr(_names))

# --- keyword construction is unaffected by the order ---
r2 = R.Result(provider_used="p", text="t", requested="q", attempts=2,
              note="note")
t("keyword ctor, existing field", r2.requested == "q", repr(r2.requested))
t("keyword ctor, existing attempts", r2.attempts == 2, repr(r2.attempts))
t("keyword ctor, existing note", r2.note == "note", repr(r2.note))

# --- the proposed Phase 5 fields, IF AND WHEN they land ---
# They do not exist yet — the sketch that proposes them is a document, not
# code (docs/review/CORE_RESULT_SHAPE_2026-10-10.md). So this suite asserts
# the invariant that makes adding them safe, rather than asserting the
# fields themselves. When Phase 5 lands, these become the real assertions.
t("the proposed new fields are not present yet (Phase 5 pending)",
   not hasattr(R.Result, "phonetics")
   and not hasattr(R.Result("p", "t", "q"), "phonetics"))

# --- ok semantics unchanged ---
t("ok is True when a provider answered", R.Result("p", "t").ok is True)
t("ok is False on a failed route", R.Result("", "t").ok is False)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_result_shape: all checks ok (%d assertions)" % n[0])
