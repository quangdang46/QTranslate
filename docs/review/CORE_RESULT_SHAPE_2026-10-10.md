# `qtranslate/core.Result` — proposed shape (Phase 5, review before code)

> **Status: PROPOSAL. Nothing here is implemented.** This is the design
> sketch the two sessions agreed to exchange before either writes code
> against it. It is deliberately a document, not a branch: the decision it
> asks for is *which fields and in what shape*, and getting that wrong is
> more expensive than the commit that follows.
>
> Companion decisions already settled (so they are not re-litigated here):
> - **`classify()` has exactly one call site** — `reliability.py:324`, inside
>   `run_provider`'s `except`. `Failure` is the *output* of that boundary,
>   not a field something transports. Verified by grep from both sessions.
> - The engine's public value object carries `failures: tuple[Failure, ...]`,
>   so there is **no second taxonomy** and no classifier at the result edge.
> - The label for J7 is the native `"Romanization: "`, not our wording.

## 1. What is being replaced

| Today | Where | Problem |
|---|---|---|
| `do_translate(...)` returns `str` | `app.py:545` | cannot express source language, phonetics, or which provider answered |
| `reliability.Result` | `reliability.py:614` | right fields, but it is *reliability's* type, so the engine's public type would be a second one |
| `google_translate._ROMANIZATION` | module state | J7's phonetics travels through a global because the `_t_*` contract is a bare `str` |
| `common.ResponseData` | `common.py:62` | the Common.js port's 5-field struct; `ARCHITECTURE.md:137` already calls it a compatibility shim, not the contract |

Two callers already want different fields from the same place: J7 needs
`phonetics`, and the reliability adapter needs `provider_used`/`failures`
without re-deriving text from a tuple. So the proposal is **one type**, not a
refactor of each.

## 2. Proposed shape

```python
@dataclasses.dataclass(frozen=True)
class Result:
    # --- lifted verbatim from reliability.Result, in their existing order ---
    provider_used: str = ""
    text: str = ""
    requested: str = ""
    failures: tuple = ()             # tuple[reliability.Failure, ...]
    attempts: int = 0
    note: str = ""
    # --- Phase 5 additions; APPENDED, so positional calls are unchanged ---
    phonetics: str = ""              # native entry[5]; Google's dt=rm fills it
    source_language: int | None = None       # native entry[1]
    translation_language: int | None = None  # native entry[2]

    @property
    def ok(self) -> bool:
        return bool(self.provider_used)
```

**The field order is load-bearing, not cosmetic.** `ProviderRouter.translate`
builds a `Result` with **six positional arguments** at `reliability.py:704`
and `:708`:

```python
return Result(route.provider_used, route.text, route.requested,
              route.failures, route.attempts, route.note)
```

The first draft of this sketch inserted the three new fields *between* `text`
and `requested` — which silently turned `('deepl', (), 1, 'note')` into
`phonetics='deepl', source_language=(), translation_language=1, note='note'`.
It parses, it type-checks under a loose reviewer, and it corrupts every
result. Verified before writing this section: appending the new fields after
the existing six keeps both call sites byte-identical, and keyword
construction still works for the new ones.

## 3. Which fields native evidence actually pins

Native's result struct (`FUN_0042ED3F`'s `param_1`) has at least six
dword-stride slots. What the decompile shows is called out *at the call
site*, which is why this is evidence rather than taste:

| Slot | Offset | Evidence | Proposed field |
|---|---|---|---|
| `entry[1]` | `+0x04` | source-language field, read alongside `entry[2]` (`J7_PHONETICS_NATIVE` §1) | `source_language` |
| `entry[2]` | `+0x08` | translation-language field | `translation_language` |
| `entry[3]` | `+0x0c` | `FUN_00408924(param_1 + 3, param_1[4])` — the **primary result** | `text` |
| `entry[4]` | `+0x10` | the value written into `entry[3]` | (a buffer, not an output) |
| `entry[5]` | `+0x14` | `ADD ESI,0x14` @ `0x0042edf9` → `PUSH ESI` → `FUN_004089fe`; the phonetics appended after the label | `phonetics` |

The `ADD ESI,0x14` is the only place the phonetics slot's *offset* is pinned
rather than inferred, and it lands exactly on `entry[5]`'s stride — the one
slot where the binary pins the shape. Everything else above is a slot number
read off the same decompile, which is weaker: **`source_language` and
`translation_language` are indexed from the same struct but not individually
confirmed**, so they are the two fields most likely to need correcting once
the provider side is re-read.

**Cross-check that the offsets are real, not arithmetic:** the append target
is pinned twice in `FUN_0042ED3F` — `ADD ESI,0x14` at `0x0042edf9` sets `ESI`
to `&entry[5]`, then `PUSH ESI` at `0x0042ee59` feeds it to the same
`FUN_004089fe` `CString::operator+=` used for the separator and the label
(`J7_PHONETICS_NATIVE_2026-10-10.md` §4c). So `0x14` is not derived from a
stride assumption; it is the constant in the instruction.

What this table does **not** establish, and the proposal does not claim:

- native's slots 1/2 are not confirmed to be *language indices* — only that
  they are the two fields the consumer reads next to each other.
- `failures`/`attempts`/`note` have **no native equivalent at all**; they are
  `RELIABILITY.md` §7's requirements. That is a *deliberate addition*, and
  `docs/COMPATIBILITY_MATRIX.md` §H already lists the reliability layer as
  "new capabilities (no native equivalent)".
- no provider but Google fills `phonetics` in the port today. An empty field
  on other providers is **correct behavior**, not a stub.

## 4. Migration order — alias first, rename never

The peer's condition, accepted: `reliability.Result` keeps working while the
merge lands, because it has 15/15 suites behind it and the phonetics side is
mid-flight. Concretely:

1. **Add `core.Result` as a new type.** `reliability.Result` unchanged.
   The three new fields are **appended after** the existing six and
   keyword-defaulted, so existing positional construction
   (`Result(provider, text, requested, failures, attempts, note)`) is
   untouched. Ordering them mid-struct is the one way this step can silently
   corrupt every result, so the position is part of the design, not a
   detail — see §2.
2. **`reliability.Result = core.Result`** as a name alias — a *rebinding of
   the name*, not a subclass, so `isinstance` has one answer and there is no
   "is this the reliability one or the full one" question. The suites keep
   passing because the alias *is* the same class.
3. Move call sites — `ProviderRouter.translate` first, then `do_translate`.
4. Delete the `reliability.Result` name **only after** nothing imports it.

The alias step is what keeps the cutover mechanical: `reliability.Result`
stays importable, the suites keep passing, and "which type is this" has one
answer during the transition. Hard rename in the same commit is the
alternative, and it is only safe if the phonetics and reliability sides land
together — which they will not, so **alias first**.

The peer proposed subclass-over-peer rather than alias. Subclass is
acceptable but weaker here: `isinstance(x, reliability.Result)` would stay
true for values that are not full `core.Result`s, which is the ambiguity the
alias avoids. Preferring the alias. (Step 1 with defaulted fields is what
makes a plain alias *possible* — the alternative is a required-field set that
breaks every caller, which is the hard rename.)

## 5. What this unblocks

- **J7 stops using module state.** `_ROMANIZATION`/`set_romanization`/
  `get_romanization` get replaced by `Result.phonetics`, which is where the
  field belongs and where the 429-fallback bug (appending a *previous* call's
  romanization) stops being possible by construction.
- **The reliability adapter stops re-deriving** text from the route tuple.
- **`google_translate._translate_response` returns the struct directly**
  instead of a 4-tuple whose 4th element one caller discards — the exact bug
  this sketch is named after.

## 6. What is explicitly *not* decided here

- **Whether `do_translate` keeps its signature.** `ARCHITECTURE.md` §3.1
  wants `(service, text, target, src, detect, backtr)` to become a
  `TranslationRequest`/`Result` pair. This sketch covers **Result only**;
  the request-side value object is a separate review.
- **Whether `common.ResponseData` gains `phonetics` now.** It is the
  documented shim; adding a field to it would make it a third result type,
  which is the failure this proposal exists to prevent. **Recommend against.**
- **The registry.** It is not a separate id map (`RE_COVERAGE_CHECKLIST.md`
  rows, the reliability fallback order, and DLG129's control ids all have to
  agree with it), so it should bind to this settled shape — but it is not
  part of this change.

## 7. Open questions for review

1. **`source_language`/`translation_language` as `int | None` indices, or as
   provider codes?** Native's slots look like indices; the port's providers
   work in codes (`en`, `zh-CN`). Choosing indices means every provider
   adapter converts; choosing codes loses native's shape. **Leaning indices**
   because the struct is the native one, but this is the question most likely
   to be decided wrong and it is cheap to pick wrongly.
2. **Does `note` remain a `str`, or become a structured diagnostic?** §7 wants
   a log line, and `Failure.log_line()` already builds one. Keeping `note: str`
   is simpler and matches the current router.
3. **`ok` as `bool(self.provider_used)`** keeps current semantics — a route
   that fell back to nothing is not ok. Worth confirming rather than
   assuming, since `text` can be non-empty on a fallback that succeeded.
