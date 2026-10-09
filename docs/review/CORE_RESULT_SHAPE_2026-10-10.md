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
    source_language: int | None = None      # PORT-side; no native slot (§3a)

    @property
    def ok(self) -> bool:
        return bool(self.provider_used)
```

**Two additions are native-pinned, one is a port-side addition.** `phonetics`
is `entry[5]` — pinned by an instruction. `source_language` has **no
confirmed native slot**: the slot that first looked like a language code pair
(`entry[1]`/`entry[2]`) turned out to be formatter state (§3a), and after the
retraction it sits alongside `failures`/`attempts`/`note` as a field the port
needs on its own terms. Its type is chosen on port-side grounds (§3b: the
integer index is the one shared vocabulary across all five provider tables),
not on native grounds, and the doc no longer implies otherwise.

**One proposed field fewer than the first draft had.** The draft proposed both
`source_language` and `translation_language` on the reading that slots 1/2
were a source/translation code pair. Neither is established, so the proposal
carries one — `source_language` — because it is the one a known consumer
(the source-language consistency row in the compatibility matrix, §B) can
name. A field whose consumer is unknown is how a value object grows fields
nothing reads.

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
| `entry[1]` | `+0x04` | **UNKNOWN.** Producer direction attempted and inconclusive — see §3c | UNKNOWN |
| `entry[2]` | `+0x08` | **UNKNOWN.** Same | UNKNOWN |
| `entry[3]` | `+0x0c` | `FUN_00408924(param_1 + 3, param_1[4])` — the **primary result** | `text` |
| `entry[4]` | `+0x10` | the value written into `entry[3]` | (a buffer, not an output) |
| `entry[5]` | `+0x14` | `ADD ESI,0x14` @ `0x0042edf9` → `PUSH ESI` → `FUN_004089fe`; the phonetics appended after the label | `phonetics` |

**§7.1's first answer was wrong and is retracted below; the second is narrower
and holds.** Native evidence pins exactly two things about this struct:
`entry[5]` (phonetics) and `entry[3]` (the result text). Slots 1/2/4 are passed
into `FUN_00408924` in a way whose *meaning* the consumer cannot establish,
because that function's body has to be read too — and reading it is what
overturned the first reading. **Slots 1 and 2 have no confirmed meaning, and
`source_language` is no longer claimed to have a native slot.**

**Cross-check that the offsets are real, not arithmetic:** the append target
is pinned twice in `FUN_0042ED3F` — `ADD ESI,0x14` at `0x0042edf9` sets `ESI`
to `&entry[5]`, then `PUSH ESI` at `0x0042ee59` feeds it to the same
`FUN_004089fe` `CString::operator+=` used for the separator and the label
(`J7_PHONETICS_NATIVE_2026-10-10.md` §4c). So `0x14` is not derived from a
stride assumption; it is the constant in the instruction. That chain never
touches `FUN_00408924`, which is why the phonetics finding is unaffected by
the §3a retraction.

## 3a. `FUN_00408924` is a char-formatting setter, and slots 1/2 are formatter state

The first draft of this section named slots 1/2 `source_language` /
`translation_language` on the strength of a reading of the *call site*
asymmetry — `LEA` (by address) for slot 1, `PUSH` (by value) for slot 2 —
and of `FUN_00408924` being a language setter. **That is retracted.** Reading
the callee's body:

```c
FUN_00409ec0((byte)flag);
  └─ FUN_00408456(*(HWND *)(in_ECX + 4), *(unk *)(in_ECX + 0x24), 0xc);
     _memset(&fmt, 0, 0xbc);           // cbSize = sizeof(CHARFORMAT)
     local_cc = 0x10000;               // dwMask = CFM_* bits
     local_c6 = (ushort)param_1;
     SendMessageW(hwnd, 0x447, 0, (LPARAM)&fmt);   // EM_SETCHARFORMAT
```

`0x447` is `EM_SETCHARFORMAT`, `0xbc` is `sizeof(CHARFORMAT)`, `0x10000` is a
`CFM_` mask — the canonical ATL wrapper around rich-edit character
formatting. So slots 1/2 are **formatting/display state**, not the language
pair. The `CMP EAX,0x49 / CMOVBE` that made the first reading look settled is
a generic bounded-int clamp (`param_2 - 2U < 0x4a ? param_2 : 1`), not a
vocabulary range — `PUSH 0x1` at `0x0042ebd8` passes a value *outside* the
supposed range and is accepted as the clamped case.

The lesson recorded rather than smoothed over: the first reading's evidence
got *more* convincing the further it went, because a range that "matched" this
port's ids twice looked like two independent confirmations when it was one
number arriving by two paths that didn't know about each other. What settled it
was reading the **callee** to learn what the argument *means*, and testing the
claim against a counterexample before asserting it.

## 3a. `FUN_00408924` is one name with two jobs

`FUN_00408924` is called from `FUN_0042ED3F` with **two different shapes**:

```c
FUN_00408924(edi + 0x98, &entry[1], entry[2]);   // language pair: (this, CString*, int)
FUN_00408924(param_1 + 3, param_1[4]);            // result text:   (CString*, CString)
```

One FUN_ name, two roles — a setter reused for the language pair and for the
result text. A reader who assumes a single semantic will read slot 3's write
as the same kind of store as slot 2's, and it is not. Recorded here so the
name doesn't mislead (decompile evidence: peer session, 2026-10-10).

## 3b. What native does and does not pin (after the §3a retraction)

**Two slots are pinned by the binary:** `entry[5]` (phonetics, via
`ADD ESI,0x14` @ `0x0042edf9` and `PUSH ESI` into `CString::operator+=`) and
`entry[3]` (the result text). **Slots 1 and 2 are not pinned** — their meaning
is formatter state established only by reading `FUN_00408924`, which the
consumer does not do and which the first reading got wrong.

So the honest field table is:

| Proposed field | Native slot | Native evidence |
|---|---|---|
| `phonetics` | `entry[5]` | **pinned** — offset in an instruction |
| `text` | `entry[3]` | **pinned** — the primary result write |
| `source_language` | **none confirmed** | no native slot; see below |
| `provider_used` / `failures` / `attempts` / `note` | none | **deliberate additions** (`RELIABILITY.md` §7) |

What follows is the port-side half of Q1, which is separable from the native
half and does **not** retroactively justify a native slot. **Measured
2026-10-10 from the five provider tables:**

| provider | table len | slot `i` = Google's slot `i`? | string differs at |
|---|---|---|---|
| google | 76 | (reference) | — |
| naver | 76 | **16/16 agree, 0 disagreements** | none |
| yandex | 76 | 69/72 | `11/12: zh→zh`, `26: iw/he` |
| microsoft | 76 | 44/52 | `1: auto-detect`, `11/12: zh-hans/hant`, `20: tl/fil`, `26: iw/he`, `47: sr/sr-Cyrl`, `61: hmn/mww`, `74: bn/bn-BD` |
| deepl | **78** | 24/25 | `11: zh-CN/ZH` |

**The integer index is shared; the spelling is per-provider; and some
providers legitimately *collapse* distinctions the index makes.** Yandex maps
both slot 11 (`zh-CN`) and slot 12 (`zh-TW`) to `'zh'` — one spelling for two
indexed languages. That is not a numbering fault, and a strict "every slot
spells the same way" assertion would be **false**, which is worth stating
because it is the natural thing to write.

So the property that actually holds is weaker and more useful: the index
means the same language everywhere, and the disagreements are collapses and
modern spellings, never transpositions of two languages. Which still answers
the field-type question on port-side grounds — `int | None` is the value that
means the same thing to every consumer, and
`code_from_language(index, provider_table)` is the boundary conversion.

Pinned by `tests/regress_language_index.py` (32 checks), which enumerates the
known collapses by slot so they cannot drift silently.

**Why the weaker claim is the useful one.** "The index means the same
language everywhere *except these enumerated slots*" is a pinning test;
"the index is shared" is not — it passes today and means nothing tomorrow.
naver 16/16, microsoft 7 slots, yandex 3, deepl 1: the disagreements are
few, named, and checkable, which is what turns a hedge into an assertion.

**The trap that produced the strong version, recorded because both sessions
hit it within one exchange.** My check was "does native's `2..75` match the
port's `SUPPORTED_LANGS`?" and it matched exactly — which felt like
corroboration and was not: `SUPPORTED_LANGS` is the port's own table, so the
comparison was port-against-port. The peer's error was the mirror image: they
built a mechanism and then found evidence for it. In both cases **the
evidence never had a chance to say no.** The re-derivable test, which is the
actual output of the correction: *a check corroborates only if you can name
where the thing being compared did **not** come from you.* If the comparator
was derived from the same assumption as the claim, agreement is guaranteed
and carries no information.

**It does not re-establish a native slot, and the doc does not pretend it
does.** After the §3a retraction, `source_language` is a port-side addition —
one with a well-defined vocabulary, sitting alongside `failures`/`attempts`/
`note` as a field whose need is the port's own.

Three limits on the table above, recorded so it is not read as stronger than
it is:

- **DeepL lists 78 entries, not 76.** Its extra slots lie beyond Google's
  table, so the shared index holds over the common range — but 76 is not a
  universal constant.
- **`-1` inside a table means "provider does not support this language", not
  a numbering fault.** DeepL and Naver genuinely lack the language at slot 2,
  which is why a naive "does index 2 resolve" check reads as disagreement.
- **`config.py:18`'s service ids are a different numbering and unverified.**
  Explicitly not covered by this agreement.

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

1. **~~Indices vs. provider codes for the language field?~~ — SPLIT, and half
   of it retracted.**
   - *Native half — retracted.* The peer's reading that `entry[2]` is a
     language code range-checked 2..75 was withdrawn: `FUN_00408924` is an
     `EM_SETCHARFORMAT` wrapper, the range check is a generic clamp, and
     `PUSH 0x1` passes a value outside the supposed range. **There is no
     confirmed native language slot.** Retraction is at §3a rather than
     deleted, because the finding that the *index* vocabulary is shared came
     out of chasing it.
   - *Port half — answered and tested.* The integer language index is shared
     across all five provider tables while the code string is a
     per-provider detail (§3b, `tests/regress_language_index.py`). So
     `int | None` is safe on port-side grounds alone.
   - **Still open:** the peer is re-deriving slots 1/2 from the *producer*
     (who fills the struct) rather than the consumer, which is the direction
     that can actually answer it. That is the only part left.
2. **What consumes `source_language`, given no native slot? — KEEP IT, and
   the citation is a line of code that exists today.**
   `qtranslate/services/microsoft.py:183-186`:

   ```python
   sl_idx = sl if isinstance(sl, int) else UNKNOWN_LANGUAGE
   if isinstance(sl, int) and not is_language(sl, SUPPORTED_LANGS):
       sl_idx = get_source_language(entry)
   _ = sl_idx  # resolved source index, returned via tuple below if needed
   ```

   Microsoft computes the resolved source index and discards it, because the
   contract is a bare `str`. **Four providers do the same work and drop it:**

   | provider | how it resolves | where it goes |
   |---|---|---|
   | microsoft | `get_source_language(entry)` | `_ = sl_idx` — **discarded** (`microsoft.py:186`) |
   | google | `get_source_language(obj)` | tuple element nobody destructures (`google_translate.py:208`) |
   | deepl | `get_source_language(..., "lang")` | returns a bare `int` to a caller that drops it (`deepl.py:145`) |
   | babylon | builds the `(text, sl, tl)` triple by hand | `_translate_response` returns it; `app.py:216` takes only the text |

   **This is the reason for the field, and it is stronger than the slot
   mapping it was originally argued from.** Note the shape, which is different
   from J7's: the romanization was *parsed-then-dropped*; the source index is
   *resolved-then-dropped*, and four providers independently do it. A reviewer
   asking "who reads this?" gets a real answer today rather than a promise —
   so the field survives the §3a retraction intact, since it never depended on
   a native slot in the first place. `app.py`'s `_t_*` adapters
   (`app.py:177-216`) all take `(t, sl, tl)` and return a bare `str`, which is
   the precise place the value is lost.
3. **Does `note` remain a `str`, or become a structured diagnostic?** §7 wants
   a log line, and `Failure.log_line()` already builds one. Keeping `note: str`
   is simpler and matches the current router.
4. **`ok` as `bool(self.provider_used)`** keeps current semantics — a route
   that fell back to nothing is not ok. Worth confirming rather than
   assuming, since `text` can be non-empty on a fallback that succeeded.
