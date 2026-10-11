"""Engine result value object — Phase 5 public type (review before code: done).

Settled design: ``docs/review/CORE_RESULT_SHAPE_2026-10-10.md``, reviewed in
``docs/review/CORE_RESULT_REVIEW_2026-10-10.md`` ("§2 agreed, code may be
written against it").

What this replaces, and why one type: ``do_translate`` returns ``str`` and
cannot express source language, phonetics, or which provider answered;
``reliability.Result`` has the right fields but is reliability's type;
``google_translate._ROMANIZATION`` carries J7's phonetics through module
state because the ``_t_*`` contract is a bare ``str``; ``common.ResponseData``
is the Common.js compatibility shim, not the contract. Two callers already
want different fields from the same place (J7 needs ``phonetics``, the
reliability adapter needs ``provider_used``/``failures``), so this is one
type, not a refactor of each.

Migration order (per the sketch §4, alias-first):
1. THIS STEP — ``core.Result`` exists as a new type. ``reliability.Result``
   is unchanged. Nothing imports this yet.
2. ``reliability.Result = core.Result`` as a name rebinding (not a
   subclass), only when both sides land together.
3. Move call sites — ``ProviderRouter.translate`` first, then
   ``do_translate``.
4. Delete the ``reliability.Result`` name only after nothing imports it.
"""
from __future__ import annotations

import dataclasses

# APPEND-ONLY RULE: new fields go at the END of this dataclass, after the
# existing fields, keyword-defaulted. ``ProviderRouter.translate`` builds a
# Result with six positional arguments, and a dataclass's positional
# construction validates arity and nothing else — so inserting a field
# anywhere before the end silently mis-binds every value (verified in the
# review §2: six-positional construction against an insert shape assigns
# requested=1, failures='n' with no exception). The position is part of the
# design, not a detail.
@dataclasses.dataclass(frozen=True)
class Result:
    # --- lifted verbatim from reliability.Result, in their existing order ---
    provider_used: str
    text: str
    requested: str = ""
    failures: tuple[Failure, ...] = ()
    attempts: int = 0
    note: str = ""
    # --- Phase 5 additions; APPENDED, so positional calls are unchanged ---
    phonetics: str = ""  # native entry[5]; Google's dt=rm fills it
    # PORT-side; no native slot (the slot that first looked like a language
    # code pair turned out to be formatter state — sketch §3a). The integer
    # index is the shared vocabulary across all five provider tables.
    source_language: int | None = None

    @property
    def ok(self) -> bool:
        """True when some provider answered.

        ``provider_used`` is set to the fallback that answered, so ``ok``
        means "some provider answered" — the property ``do_translate``
        branches on. A route that exhausted its budget produces
        ``provider_used=''`` and a non-empty ``note``: not ok, correctly.
        """
        return bool(self.provider_used)
