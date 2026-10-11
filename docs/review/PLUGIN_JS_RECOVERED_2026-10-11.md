# The `Service.js` artifacts are recoverable — the 25-row premise is falsified

> Read-only. **This document retracts the premise of
> `SERVICE_JS_PROVENANCE_2026-10-10.md`, `E_ROW_AFFECTED_COUNT_2026-10-10.md`,
> and the pending 5-row `Plugins/History/*.js` writeup I owed the checklist
> owner.** Every `Service.js` named by the E rows, and every
> `Plugins/History/*.js` named by the I rows, is present in an artifact
> already recovered and already in the repo directory. They were never in
> `QTranslate.6.10.0.exe`. They are in the installer that ships it.
>
> **No row state changed by this document.** It changes what evidence is
> available, which is a different thing from what a row should say.

## 1. The premise, and why it was false

The earlier documents searched **the extracted program image** for the
plugin JS and reported the artifacts ABSENT. That measurement was correct
and is reproduced below. The conclusion drawn from it — that the rows cannot
be re-verified from anything in this repo — was wrong, because the search
stopped at the wrong artifact.

`docs/review/ARTIFACT_RECOVERY_2026-10-10.md` §2 already recovered and
documented the install payload:

| path | bytes | what it is |
|---|---|---|
| `docs/review/artifacts/QTranslate.6.10.0.exe` | 1,462,272 | the program |
| `docs/review/artifacts/nsis_payload_unpacked.bin` | 2,263,053 | the whole unpacked solid stream — **includes every shipped data file** |

The payload is a length-prefixed solid stream: each entry is
`<uint32-LE length><body>`, back to back, no delimiters. Walking it from a
known anchor enumerates the entire installed file tree:

```python
import struct
p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()
off = 0x156b1                     # first Service.js length field
while True:
    n = struct.unpack_from("<I", p, off)[0]
    body = p[off+4:off+4+n]
    assert len(body) == n
    off += 4 + n
```

**All 19 `Service.js` files, `Common.js`, and all four
`Plugins/History/*.js` exporters are in this stream.** So are the locale
`lang.json` packs, theme files, help text, and the icons. Chunk 10 of the
walk is the 1,462,272-byte program itself — SHA-256
`f35a3bc8e09e…38227`, byte-identical to
`docs/review/artifacts/QTranslate.6.10.0.exe`. Same stream, one artifact.

## 2. The exe-only search, reproduced — and why it misled

The measurement the retracted premise rested on is sound. Confirmed,
both encodings, on the extracted image:

| string | in `QTranslate.6.10.0.exe` |
|---|---|
| `Services/` | ABSENT |
| `Csv.js` / `Html.js` / `Json.js` / `Txt.js` | ABSENT |
| `www2.deepl.com/jsonrpc` | ABSENT |
| `/apis/nsmt` | ABSENT |

`Service.js` and `Common.js` are present as **wide strings** at `0x121aa4`
/ `0x121a90` — which is the loader's filename vocabulary, and which is what
made the earlier reading look like a naming-only artifact. The loaders
themselves are real and both are now readable:

- `FUN_0045d6a9` (`0x45d6a9`, 446 B) — builds `<config>/Services`, bails if
  absent, loads `Common.js`, then each subdirectory's `Service.js`, compiles
  via `FUN_0043df32`, registers via `FUN_0045d160`.
- `FUN_0042836e` (`0x42836e`, 277 B) — the `Plugins/History` side: builds
  `<config>/Plugins`, appends `History\`, enumerates `*.js` from disk, and
  runs each through `FUN_00428096` with a `plugins::HistoryScript::vftable`
  on the stack.

The loader for the I rows exists. The claim it did not was mine and the
peer's, and it was wrong. One xref to the wide string `Plugins` at
`0x523d84` — exactly one, at `0x428396` — is this function.

**`FUN_0043df32` is not a JS interpreter.** Decompiled: it reads the file,
checks for a BOM (`0xFFFE`/`0xFEFF`), and if there is none falls through to
`FUN_0043b207(bytes, len, out)`. The `\0`-string case at
`*local_18 != -0x4411` is the "skip a UTF-16 BOM" path. There is no
`JSON.parse`, no `toString`, no `__proto__` in the image — see §5.

## 3. The 19 `Service.js` files, extracted

Byte counts from their own length fields; SHA-256 over the chunk body:

| # | service | bytes | sha256 (16) |
|---|---|---|---|
| 1 | ABBYY Lingvo Live | 2,029 | `4c0ef8506ff322ce` |
| 2 | Babylon | 1,243 | `c12e825d73cbf78c` |
| 3 | Babylon Dictionary | 1,243 | `f406c6fb359820dc` |
| 4 | Baidu | 3,490 | `910dfe9adcd7994c` |
| 5 | DeepL | 2,757 | `0abf802669004dd0` |
| 6 | Google | 3,388 | `f3459f952a2f5a33` |
| 7 | Google Search | 1,449 | `82885d093a2c8cbd` |
| 8 | ImTranslator | 1,303 | `76a9612fe84bac2f` |
| 9 | Microsoft | 3,291 | `b1c12a050eda6d7f` |
| 10 | Multitran | 1,322 | `b9a6da58fe67c6f4` |
| 11 | Papago | 9,462 | `8eee5f6cb20217ab` |
| 12 | Oxford Learner Dictionary | 3,379 | `60d291430ea09863` |
| 13 | Promt | 2,040 | `1135da5bb2b118d9` |
| 14 | Reverso | 1,462 | `c9f069e3ddd8bb0b` |
| 15 | Urban Dictionary | 1,231 | `270440849c25582e` |
| 16 | Wikipedia | 1,495 | `b2dd1f2f396698e0` |
| 17 | WordReference | 1,531 | `2ada261c54f054a0` |
| 18 | Yandex | 4,431 | `93136ba152bf334b` |
| 19 | youdao | 3,343 | `6b2ee411798c6f20` |

Total 49,889 bytes of JS. The count is not a heuristic: the installer's
own manifest (UTF-16LE, around `0x9880`) lists **19** service directories
in the same order, and each chunk's `new ServiceHeader(id, "Name", …)`
matches one of them exactly. 19 strings → 19 chunks → 19 directories.

## 4. The four `Plugins/History/*.js` exporters, extracted verbatim

These are the I3 / I4a–I4d artifacts. All four checklist claims are
confirmed **verbatim** against the recovered bytes:

| row | cited claim | recovered source | verdict |
|---|---|---|---|
| I3 / I4a | `[a,c,b,e,d]` | `return[escapeValue(a),escapeValue(c),escapeValue(b),escapeValue(e),escapeValue(d)].join()` | **exact** |
| I4b | `quoteHtml` + table rows | `function quoteHtml(a){return a?a.replace(/&/g,"&amp;")…:"&nbsp;"}` | **exact** |
| I4c | `escapeStr` ESC map | `var escMap={'"':'\\"',"\\":"\\\\","\b":"\\b","\f":"\\f","\n":"\\n","\r":"\\r","\t":"\\t"}` | **exact** |
| I4d | — | `historyHeader(){return""}…historyItemEnd(){return"===…"}` | present |

`Csv.js` is 439 B (`11c43d156c846c91`), `Html.js` 984 B
(`af07a14e423b9e7a`), `Json.js` 753 B (`3115b9a220596f2f`), `Txt.js` 381 B
(`082fbc40e118aa55`). The chunk chain also hands over the `.xsl` stylesheet
and the theme JSON files immediately after `Txt.js`, which is a
cross-check that the walk boundary is right and not a coincidence of the
last chunk.

The port already implements the order correctly —
`qtranslate/history.py:29` comments `# native Csv.js: [a,c,b,e,d] = service,
srcLang, src, trLang, tr` and the code emits exactly that. What was missing
was not the port; it was the artifact the port cites. That artifact now
exists.

## 5. Two things this does NOT establish

1. **Not that the exe is a JS host.** The interpreters are host-side:
   `FUN_0043df32` reads bytes and hands them to a native compiler; the JS
   itself is data on disk. The image contains no `JSON.parse`, no
   `__proto__`, no `JSON.stringify`. The 15-of-25 "JS-looking" signatures
   an image-wide substring scan returns are false positives from ordinary
   C/C++ identifier strings (`function`, `return`, `this`, `null`).
2. **Not that any row's interpretation is now re-verified.** This
   establishes that the *artifact exists and is byte-exact*. Whether a given
   row's reading of that artifact is correct is a separate check, per row,
   which is what the row owner needs to do. The bars are: previously "no
   artifact", now "artifact in hand, hash-pinned, reproducible".

## 6. Why the earlier reading failed — the transferable part

Three consecutive searches all reported the same wrong conclusion, and
each one was locally correct:

1. Search the exe for `Service.js` content → absent. **True.**
2. Search the exe for each endpoint literal → absent. **True.**
3. Conclude the rows cannot be verified from this repo. **False.**

The step that never ran was: *which artifact did I search?* The repo
contained a second, 55%-larger artifact — recovered in an earlier
document, by a peer, whose title ("Solid stream") says it contains the
files — and the go-no-go question about the plugins was asked only of the
smaller one.

The tell was available and I did not act on it. `SERVICE_JS_PROVENANCE`
§2 lists `Service.js | PRESENT — 0x121aa4 (wide)` in the same table as
`Services/ | ABSENT`. A file *name* present without its path prefix means
the name is used as a runtime datum — i.e. something loads it from
somewhere. That is a pointer to where the file lives, not evidence that it
is gone. I read it as "the name is all that survives."

## 7. Reproduce

```python
import lzma, struct, hashlib, re

stub = open("/Users/tranquangdang21/Downloads/QTranslate.6.10.0.exe", "rb").read()
props = {"id": lzma.FILTER_LZMA1, "dict_size": 0x800000, "lc": 3, "lp": 0, "pb": 2}
dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[props])
stream = b""
while True:
    c = dec.decompress(stub[0xF621:], max_length=1 << 22)
    stream += c
    if len(c) < (1 << 22):
        break

assert len(stream) == 2263053 and dec.eof
assert stream[0x9bfa9:0x9bfa9 + 0x165000] == open(
    "docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()

# every Service.js, by finding each chunk that STARTS with the hook name
out = {}
for m in re.finditer(rb"function serviceHeader", stream):
    off = m.start() - 4
    n = struct.unpack_from("<I", stream, off)[0]
    body = stream[off+4:off+4+n]
    if len(body) == n and body.startswith(b"function serviceHeader"):
        name = re.search(rb'new ServiceHeader\(\s*\d+\s*,\s*"([^"]+)"', body).group(1)
        out[name.decode()] = hashlib.sha256(body).hexdigest()

assert len(out) == 19, len(out)
assert out["Babylon Dictionary"] .startswith("f406c6fb359820dc")
```

Run on 2026-10-11 against `~/Downloads/QTranslate.6.10.0.exe`:
`len(stream) == 2263053`, `dec.eof is True`, the embedded image matches the
committed extracted exe byte-for-byte, and 19 hashes come back.

## 8. What this changes for the checklist

Not the tally. The 20 `Service.js` rows and the 5 `Plugins/History/*.js`
rows were proposed for `VERIFIED → UNRECOVERABLE` on the grounds that
their artifact could not be recovered. It can be, it is in the repo
directory, and it is hash-pinned and reproducible. **That proposal should
be withdrawn**, and the two classes should not be merged into one
"unverifiable" bucket in either direction.

What it does change: `SERVICE_JS_PROVENANCE_2026-10-10.md` §4's standing
claim that `qtranslate/services/dictionary.py`'s "Reversed from
…Services/*/Service.js" is unsupported by anything on disk. It now has
something on disk to be checked against — 19 files, 49,889 bytes, with
per-file SHA-256. That is a re-read of the port against real source, which
is more useful than the reclassification it was heading toward.
