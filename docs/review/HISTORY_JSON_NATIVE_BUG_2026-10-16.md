# Json.js emits an invalid JSON export for 2+ entries (native bug) — 2026-10-16

`C:/Program Files (x86)/QTranslate/Plugins/History/Json.js` (753 bytes,
installed copy) writes the entry separator **twice**. Transcribed
expression for expression and run, its 2-entry output is:

```json
[{"src":"hello","trs":[{"service":"Google","srcLang":"en","trLang":"vi","tr":"xin chao"},]},{"src":"bye","trs":[{"service":"DeepL","srcLang":"en","trLang":"vi","tr":"tam biet"}]}]
```

That is invalid JSON twice over: a **trailing comma inside `trs`** (after
the `}`), and the comma that should separate the two top-level objects
lands *inside* the inner array rather than after `]}`.

## Why

The plugin's two functions both add a separator:

```js
function historyItem(a,b,c,d,e,f,g){
  return '{"service":'+escapeStr(a)+',"srcLang":'+escapeStr(c)
         +',"trLang":'+escapeStr(e)+',"tr":'+escapeStr(d)+"}"+(g<f-1?",":"")}

function historyItemEnd(a,b){
  return "]}"+(b<a-1?",":"")}
```

`historyItem`'s own trailing test is `g<f-1`, so its last two parameters
are `(f=count, g=index)`. A 7-parameter plugin hook passes that same pair
to `historyItemEnd(a,b)`, which makes `b<a-1` — with `b=index`,
`a=count` — the identical "not the last entry" test. Both fire for every
non-last entry, so each separator is written twice.

(The alternative reading of `historyItemEnd`'s `(a,b)` — the begin's
`(src, service)` — is a JS `TypeError`, `str - int`, so it cannot be what
runs.)

## Consequence in the port

The port's `json_item` used to emit no separator and `json_item_end`
emitted one, which is valid JSON — a silent fix for the native bug that
nobody had documented.

While fixing a **different** bug found the same day (CSV columns 1 and 3
swapped — `[a,c,b,e,d]` is `src, srcLang, service, trLang, tr`, not
`service, srcLang, src, trLang, tr`), the JSON comma briefly moved into
`json_item` to follow native literally. That made the multi-entry export
byte-identical to native's — and invalid. Reverted to the port-side fix.

**Current behaviour:** `json_item` emits no separator; `json_item_end`
emits `"]}"` plus one comma when the entry is not the last. For `n == 1`
neither native test fires, so the single-entry export is byte-identical
to native.

Pinned by `tests/regress_history_export.py`, which asserts the fix rather
than native's broken output, and says so in its own docstring.
