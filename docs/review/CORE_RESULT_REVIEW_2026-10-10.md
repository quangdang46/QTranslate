# Review of `CORE_RESULT_SHAPE_2026-10-10.md` — agreed, with one correction and one addition

> **Status: my read of the peer's Phase 5 proposal.** Nothing here is
> implemented and no port file is touched. The proposal says "review before
> code" and this is the review, kept in my own file because the sketch is
> theirs to own.

## 1. Agreement, and what it rests on

I agree with the field set and the ordering. The two native-pinned fields are
pinned correctly, and the one thing I wanted to satisfy myself about — that
the §7 diagnostics requirement survives the merge — does survive. That was a
constraint I raised against the proposal on a first read and it was wrong:

```
Failure('deepl', RATE_LIMITED, 429, 'rate limited', 2, 1.4, fell_back=True).log_line()
->
provider=deepl kind=rate-limited attempts=2 elapsed=1.400s
fell_back=1 status=429 detail=rate limited
```

`fell_back` is on `Failure` (`reliability.py:259`), set by
`FallbackRouter._exhausted`'s look-ahead at `:565`, and it is reachable
through the `failures: tuple` the proposal already carries. All six §7 fields
are present in the log line produced through `result.failures`. **The shape
needs no amendment for §7.** I recorded the retraction here rather than
deleting my first message, because the shape of that mistake is one I had
just criticized elsewhere and it is worth having in the file.

## 2. The field-order argument is right, but its stated mechanism is too weak

The proposal says inserting the new fields between `text` and `requested`
"silently turned `('deepl', (), 1, 'note')` into
`phonetics='deepl', source_language=(), translation_language=1, note='note'`."
The first half of that example does **not** parse under the draft shape: with
two new defaulted fields inserted, a 4-positional call assigns
`provider_used='deepl', text=(), phonetics=1, source_language='note'` — which
is *louder* than the proposal claims, since `text=()` is plainly wrong.

The real case is the call sites that exist, which are **six-positional**.
Against the insert shape:

```
Result("deepl", "txt", "deepl", (), 1, "n")
->
provider_used='deepl'   text='txt'      phonetics='deepl'
requested=1             failures='n'    attempts=0     note=''
```

Arity is satisfied, no exception is raised, and `requested` becomes the
integer `1` while `failures` becomes the string `'n'`. **Undetectable by any
type-checker**, because each misplaced value is a legal type for the field it
landed in: `requested` would need to be `str` to catch it, and `failures` would
need to be `tuple[Failure, ...]` to catch it — and neither is, in either
result type today. So the warning is correct and the danger is *greater* than
described, for a reason worth writing down: **a dataclass's positional
construction validates arity and nothing else.**

The practical consequence for implementation: make the new fields
**keyword-only** at construction where possible, or annotate `requested: str`
and `failures: tuple[Failure, ...]` so the next reshuffle fails loudly. With
no annotation on `failures: tuple`, the exact corruption above passes today.

## 3. Correction on my own claim about which fields are non-defaulted

I told the peer the first two fields are non-defaulted and inferred the danger
from that. Measured from `reliability.Result`:

| field | default |
|---|---|
| `provider_used` | **none** |
| `text` | **none** |
| `requested` | `''` |
| `failures` | `()` |
| `attempts` | `0` |
| `note` | `''` |

So *appending* is safe, but the safety comes from position, not from
defaults: any insertion **after** position 2 is also arity-compatible with the
existing six-positional call sites and produces the corruption in §2. The
append rule is right; the reason to obey it is stronger than "the first two
are required."

## 4. `ok` — confirm, and confirm the thing it hides

§7.4 asks whether `ok` should stay `bool(self.provider_used)`. **Yes**, and
the reason is stronger than "it keeps current semantics": `provider_used` is
set to the fallback that answered, so `ok` already means "some provider
answered", which is the property `do_translate` branches on at `app.py:691`.

But there is a case worth pinning in a test when the type lands. A route that
exhausts its budget produces `provider_used=''` and a non-empty `note` — not
`ok`, correctly. A route that succeeded on fallback produces
`provider_used='google'` with `note='google answered (fallback from deepl)'` —
`ok`, correctly, and **not** the user's pick. The invariant that matters is
that no `Result` can be simultaneously `ok` and attributed to a provider the
user did not select *without* saying so. `note` carries it today, so the
proposal holds; a test that asserts `ok` and `provider_used != requested`
implies a non-empty `note` would make it durable.

## 5. `source_language` — the justification in §7.2 is the right one, keep it

The proposal retracted the native-slot argument for `source_language` (§3a)
and then re-justified the field on "four providers resolve-then-drop the
value." That is the correct basis and the stronger one, because it names a
real consumer today rather than a hypothetical one:

| provider | where it drops |
|---|---|
| microsoft | `microsoft.py:186` — `_ = sl_idx` |
| google | `google_translate.py:208` — 4th tuple element, one caller discards |
| deepl | `deepl.py:145` — returns `int`, caller drops it |
| babylon | builds the triple by hand; `app.py:216` takes only the text |

I verified each site is as described. The generalisation worth naming: this
is the *same bug shape* as J7's romanization being parsed-then-discarded since
`3d9da8d`, in a second disguise. A reviewer asking "who reads this field?"
gets four file:line answers, which is what makes it not-speculative. Do not
weaken this when the native half stays unknown.

## 6. Migration order — agreed, with one ordering detail

**Alias before rename**, agreed, and the reason is the one the proposal gives:
`reliability.Result` has 15/15 suites behind it and the phonetics side is
mid-flight, so a hard rename in the same commit is only safe if both land
together.

One addition to step 2. When `reliability.Result = core.Result` becomes a name
rebinding, the two `Result(...)` call sites inside
`ProviderRouter.translate` start producing `core.Result`s — which is the
intent — but the `__init__.py`/`__all__` surface and any `isinstance` check
that names `reliability.Result` keep working only if nothing did
`from reliability import Result` and re-exported it under a third name. That is
a 30-second check at cutover time and worth putting in the commit message
rather than discovering: `git grep -n "reliability import Result\|reliability\.Result"`.

The peer's rejection of subclass-over-alias is right. Subclass leaves
`isinstance(x, reliability.Result)` true for values that are not full
`core.Result`s, which is precisely the ambiguity the alias exists to delete.

## 7. What I'd want before any code is written

1. **Annotate `failures: tuple[Failure, ...]`** (and `requested: str`) in
   whichever type is added. Today's bare `tuple` is what lets §2's corruption
   pass silently.
2. **A construction-site assertion**, not a comment: something that fails if
   a `Result` is built with more than two positional args. That converts the
   §2 warning from prose into a test, and it is the only protection that
   survives the next field addition.
3. **Keep the append-only rule in the field list itself** — a comment above
   the dataclass naming that new fields go at the end, so the next person
   does not have to re-derive why.

## 8. Not my call, stated plainly

Whether this lands at all, and whether `do_translate`'s signature changes with
it (§6), is the port owner's decision. This is a read of their proposal from
the reliability side, which is the side with the most positional-construction
risk and the §7 requirement.
