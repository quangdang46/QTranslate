# Native's per-service auto-detect capability, derived from the recovered JS (2026-10-21)

> **Scope:** closes the checklist item `SOURCE_LANGUAGE_RULE_2026-10-10.md` §5
> left open — "Which services actually answer `usesAutoDetectCode` as true?"
> — and replaces the port's hand-listed capability set with a *derived* one.
>
> The mechanism was already `VERIFIED`; the **per-service truth table** was
> not, because the `Services/*/Service.js` files were thought to be
> unrecoverable. They are not: the installer payload carries all 19.

---

## 1. The hook is a framework function, not a per-service one

`SOURCE_LANGUAGE_RULE_2026-10-10.md` §1 established the mechanism from the
binary: the host calls the JS hook `usesAutoDetectCode` on the service
(`FUN_0043b8ce(this, L"usesAutoDetectCode", 0, 0, &piStack_1c)`) and stores
the boolean at request `+0x50`; the translate stage `FUN_004606ba` runs
detect itself only when that flag is false, or when the destination is also
unset.

What the document could not say is **who answers true**, because the answer
lives in the runtime-loaded `Service.js`. The recovered `Common.js` answers
it — and it answers it for *every* service, because the hook is a **framework
function**:

```js
// Services/Common.js
var SupportedLanguages=null, UNKNOWN_LANGUAGE_CODE=-1, UNKNOWN_LANGUAGE=0,
    AUTO_DETECT_LANGUAGE=1, ENGLISH_LANGUAGE=17;

function usesAutoDetectCode(){
    return SupportedLanguages[AUTO_DETECT_LANGUAGE] !== UNKNOWN_LANGUAGE_CODE
}
```

So the answer is: **"does this service's own language table hold a real code
in slot 1?"** — a rule, not a list. Which means the truth table is
*derivable* from the recovered JS rather than merely observable.

## 2. The truth table

Measured by `tools/_scratch/auto_detect_table.py` over the 19 recovered
`Service.js` files; committed at
`docs/review/auto_detect_capability_table.json`.

| service | `SupportedLanguages[1]` | `usesAutoDetectCode()` |
|---|---|---|
| DeepL | `"auto"` | **true** |
| Google | `"auto"` | **true** |
| Google Search | `""` | **true** |
| ImTranslator | `""` | **true** |
| Microsoft | `"auto-detect"` | **true** |
| Oxford Learner Dictionary | `1` | **true** |
| Papago | `"auto"` | **true** |
| Promt | `"au"` | **true** |
| Urban Dictionary | `1` | **true** |
| Wikipedia | `""` | **true** |
| WordReference | `""` | **true** |
| youdao | `"AUTO"` | **true** |
| ABBYY Lingvo Live | `-1` | false |
| Babylon | `-1` | false |
| Babylon Dictionary | `-1` | false |
| Baidu | `-1` | false |
| Multitran | `-1` | false |
| Reverso | `-1` | false |
| Yandex | `-1` | false |

**12 true, 7 false.** Note the values are each service's *own* spelling of
the auto source — `"auto-detect"` for Microsoft, `"AUTO"` for youdao, `"au"`
for Promt — so the port cannot send a literal `"auto"` to all of them.

## 3. What changed in the port

### 3.1 The capability table is derived, not listed

`qtranslate/registry.py` previously carried a hand-listed
`USES_AUTO_DETECT = {"google": True, "microsoft": True, "bing": True,
"deepl": True}` — four names carried over from the old `_NATIVE_AUTO` set,
with a comment saying the table was *not* native-derived because the hook's
answers were unreachable.

They are reachable. The port's `SUPPORTED_LANGS` tables are transcriptions
of exactly the per-service `SupportedLanguages` arrays (slot 1 agrees
name-for-name and value-for-value for all nine translate providers), and
`qtranslate.common.uses_auto_detect_code` is already the port of the hook.
So the table is now computed:

```python
USES_AUTO_DETECT = _auto_capability()
```

which yields `{google: True, microsoft: True, bing: True, deepl: True,
yandex: False, baidu: False, naver: True, youdao: True, promt: True,
babylon: False}` — the four the port had, **plus** naver, youdao and promt,
which native also answers true for.

### 3.2 Each provider gets its own auto code

Native sends each service `codeFromLanguage(1)` — the service's own slot-1
code — not a literal `"auto"`. The port's request keeps the canonical
`"auto"` (that is what the UI shows); the provider's own spelling is
applied at the adapter boundary, via the new
`registry.auto_detect_code(service)`.

So the port now sends:

| provider | what it sends for an auto source | native |
|---|---|---|
| google | `auto` | `auto` ✓ |
| deepl | `auto` | `auto` ✓ |
| naver (Papago) | `auto` | `auto` ✓ |
| microsoft | **`auto-detect`** | `auto-detect` ✓ (the port sent `auto` before) |
| youdao | **`AUTO`** | `AUTO` ✓ (the port sent `auto` before) |
| promt | **`au`** | `au` ✓ (the port sent `auto` before) |

### 3.3 A vocabulary leak in the detect chain, fixed

`registry.detect_language()`'s docstring promised "everything is normalized
to a code string here". It did not: Google's detector returns a language
**index** (`detect` → `getSourceLanguage` → `languageFromCode`), and the
chain returned it raw.

The consequences were real:

- `TranslationRequest.src` carried an `int` (e.g. `17`) instead of a code,
  so the UI would show a number;
- a **different** provider read that int as *its own* index — Google's 17 is
  English, but so is every other provider's 17, and any other index named a
  different language in each table;
- `_t_deepl` does `sl.upper()`, which raises `AttributeError` on an int.

Google's detector now resolves its index against Google's own table
(`google_translate.detect_code`), and `detect_language` skips any
detector that does not answer with a code string, so a future vocabulary
leak cannot reach the request.

**The port's own source-language rule was already right** — the
`src == dst` echo and the capability lookup are both in place
(`engine.py`, `registry.py`) — and the checklist's §4 claim that "the port
has no equivalent of the dispatcher's short-circuit" was **stale**; the echo
has been there since the Phase 7 slice.

## 4. Verification

`tests/regress_auto_detect_capability.py` — **26 assertions**, all calling
the real code:

1. the derived capability table equals native's measured truth table, for
   every provider the port has that native also has;
2. each provider's own auto code is the native one;
3. `detect_language` answers with a code string even when a detector
   returns an index;
4. the engine sends the provider's own auto code, and does **not** run the
   detect chain at all for a provider that accepts one (the detector is
   replaced by one that raises if called);
5. a provider with no auto slot gets a concrete detected code instead.

`tests/regress_source_language.py` was updated: it used to pin "the table's
comment says it is NOT native-derived" and read the table out of the source
with a regex. Both are gone — the table is derived, and the test now
asserts the derivation and the native answers.

## 5. What this does not claim

- The **detect fallback** is unchanged: when no detector can name a source,
  the port degrades to `"auto"` rather than stopping (the reliability
  audit's item (i), decided by the reliability agent and recorded in
  `engine.py`'s `_detect_source`). Native's `FUN_0045fde8` instead falls
  back to **English** (index `0x11`) when the default detect service is the
  one that failed. That divergence is recorded, not closed.
- The **dictionary** services' own `SupportedLanguages` tables are native's
  (their slot 1 is 1 or -1, so they accept or reject auto), but the port's
  single `dictionary.py` module does not model per-dictionary source
  languages yet. The dictionary row is unchanged.
- The port's `USES_AUTO_DETECT` covers the **translate** providers. The
  dictionary and suggest providers are not in the table, so they take the
  native default (detect yourself) — which matches native for every
  dictionary service except the ones whose slot 1 is `1` (Oxford, Urban).
