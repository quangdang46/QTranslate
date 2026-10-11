# The framework gate, found — `Common.js`'s `codeFromLanguage` is a *bounds* test, not a support test

> Read-only. Settles the question `PLUGIN_JS_VERIFIED_AGAINST_PORT_2026-10-11.md`
> §4b left explicitly open — "what native does with an unsupported pair is
> NOT measured … the framework's own gate is not recoverable from this repo".
> It is recoverable, and the answer is that **there is no support gate.**
>
> **No row state and no port file changed by this document.** It records the
> native semantics so the port's `_codes`/`supported` can be written against
> something measured rather than against a stated ambiguity.

## 1. What the framework actually does

`Common.js` (chunk `[5]` at `0x13af0`, 6,203 bytes — see
`COMMON_JS_RECOVERED_2026-10-11.md`) carries the two functions that decide
everything here:

```js
var SupportedLanguages = null,
    UNKNOWN_LANGUAGE_CODE = -1,
    UNKNOWN_LANGUAGE = 0,
    AUTO_DETECT_LANGUAGE = 1,
    ENGLISH_LANGUAGE = 17;

function isLanguage(a) {
    return a > AUTO_DETECT_LANGUAGE && a < SupportedLanguages.length
}
function codeFromLanguage(a) {
    return a === AUTO_DETECT_LANGUAGE || isLanguage(a)
           ? SupportedLanguages[a] : UNKNOWN_LANGUAGE_CODE
}
```

Read it slowly, because the conclusion is the opposite of the intuitive one:

- `isLanguage(a)` is a **bounds test on the shared language-id index** — `1 < a < length`. It says nothing about whether the *service* supports that language.
- `codeFromLanguage(a)` returns `SupportedLanguages[a]` whenever `a` is in
  bounds or is auto-detect, and `-1` otherwise.

`SupportedLanguages` here is the **shared, app-wide** language table —
`null` at load, filled by the framework. It is indexed by QTranslate's
internal language id (0..~76), not by the app's whole language set. The
`-1` entries the 11 `*_LANGS` tables contain are exactly the values this
array holds for ids the shared table does not define.

**So the "unsupported pair" case in native is: `codeFromLanguage` returns the table entry, which may be `-1`, and the caller interpolates it into the URL.** There is no refusal. The framework does not gate on support, and neither does any of the 19 service scripts (checked: no `== -1`-style test in any).

The permissive convention is what the peer's own Multitran note already described from the 12 readable `buildUri` functions — *"native's lossy build … returns the value unchanged rather than inventing a code."* That was a measured convention from twelve services; the framework now confirms it is the framework's rule, not a quirk of those twelve.

## 2. Why `-1` reaching a URL is not obviously a bug

What native does with `-1` downstream is per-service and mostly not
measurable, which is what §4b said and what remains true. But the *stage
before* that is now measured, and it is the stage the port was missing:

| situation | native | the port before this |
|---|---|---|
| `sl`/`tl` is a valid shared id | `SupportedLanguages[id]`, may be `-1` | never indexed the table at all — `app.py:3708` passes ISO strings |
| `sl`/`tl` is out of bounds and not auto | `-1` | same |
| `sl` is auto-detect (`1`) | `SupportedLanguages[1]` (typically `"auto"`) | same |

`common.py:84` implements `max_uri_len` truncation and `:90` implements
`limit_source`, both traced to `Common.js`'s `Const` — so the port's
framework layer was already written against a source the peer believed was
absent. That is the part worth noticing.

## 3. The port consequence, stated without touching the port

Two options are available now, and they are not equivalent:

1. **Reproduce the bounds test** — index the table, pass `-1` through, let
   the URL carry it. This is what native does, exactly.
2. **Refuse the request** — cleaner behaviour, and *not* native.

The peer's in-flight `dictionary.py` docstring chose to do neither, saying
the policy was unrecoverable. It is recoverable and it is (1). So the
defensible port is: `supported()` may exist as an *advisory* for callers
who want it, but it must not silently drop or rewrite a pair, because
native does not.

That is a port-owner decision, and it is theirs. The measurement above is
mine, and it is reproducible.

## 4. Reproduce

```python
import struct
p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()
n = struct.unpack_from("<I", p, 0x13af0)[0]
common = p[0x13af0+4:0x13af0+4+n].decode("utf-8")

i = common.find("function isLanguage(")
j = common.find("function codeFromLanguage(")
assert 0 < i < j
assert common[i:j] == ('function isLanguage(a){return a>AUTO_DETECT_LANGUAGE&&'
                       'a<SupportedLanguages.length}')
assert "UNKNOWN_LANGUAGE_CODE" in common[j:j+220]
assert "===-1" not in common and "== -1" not in common   # no support gate
```

The two `assert`s on the exact text are the whole finding: `isLanguage` is
`a > 1 && a < length`, and nothing in `Common.js` ever compares an entry to
`-1`.

## 5. What this does not establish

- **Not** what each service does with a `-1` that reaches its `buildUri`.
  That is per-service and remains unmeasured for most of them.
- **Not** that the port's `_codes` is wrong. It maps `None`/`""` → `-1` and
  passes strings through, which is consistent with the native bounds test.
  The docstring's *reason* is what was wrong, not necessarily the code.
- **Not** a change to any `*_LANGS` table's values. Eleven tables verified
  entry-by-entry by the peer; this document does not re-verify them.
