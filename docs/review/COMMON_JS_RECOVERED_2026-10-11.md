# `Common.js` recovered too — E1's artifact, and the constants the port already had

> Read-only. `E_ROW_AFFECTED_COUNT_2026-10-10.md` exempted **E1** from the
> affected count on the grounds that it cites `Services/Common.js`, "the
> framework the loader provably loads first," and that `FUN_0045d6a9` is
> itself E1's address-backed evidence. That reasoning was correct and the
> exemption still holds — but it was made while `Common.js` was believed
> unobtainable. **It is obtainable, at stream offset `0x13af0`, 6,203 bytes,
> SHA-256 `a03d677a8b3788b5…78a8f8b93`**, and it closes E1 from the source
> side as well as the address side.
>
> **No row state changed.** This makes an existing `VERIFIED` row's artifact
> checkable rather than trusted.

## 1. It is chunk 5 of the stream

Chunk `[5]` at `0x13af0`, immediately after chunk `[4]` (`System.dll`) and
before the service icons. It begins:

```js
var Const={MAX_URI_LEN:1800,MAX_SOURCE_LEN:5E3,NL:"\r\n",NL2:"\r\n\r\n"},
Capability={TRANSLATE:1,DETECT_LANGUAGE:2,LISTEN:4,DICTIONARY:8},
HttpMethod={UNDEFINED:0,GET:1,POST:2},
CodePage={WINDOWS1251:1251,UTF8:65001,ISO8859_1:28...
```

and ends with the ES5 `Array.prototype.filter` polyfill. It is the shared
framework `FUN_0045d6a9` loads before the subdirectory loop — which is the
one thing E1's exemption already established. The point of this document is
that E1 no longer has to rest on that inference.

## 2. Every constant the port carries is in it, with the same value

| native `Common.js` | `qtranslate/common.py` |
|---|---|
| `MAX_URI_LEN: 1800` | `MAX_URI_LEN = 1800` (`:12`) |
| `MAX_SOURCE_LEN: 5E3` | `MAX_SOURCE_LEN = 5000` (`:13`) |
| `NL: "\r\n"` | `NL = "\r\n"` (`:14`) |
| `NL2: "\r\n\r\n"` | `NL2 = "\r\n\r\n"` (`:15`) |
| `TRANSLATE:1, DETECT_LANGUAGE:2, LISTEN:4, DICTIONARY:8` | `TRANSLATE=1, DETECT_LANGUAGE=2/DETECT=2, LISTEN=4, DICTIONARY=8` (`:23-28`) |
| `HttpMethod {UNDEFINED:0,GET:1,POST:2}` | `UNDEFINED=0, GET=1, POST=2` (`:31-34`) |

`common.py:12`'s `1800` is the one that matters most and it is the kind of
number that gets typed from memory: it is the threshold that decides
whether `google_translate.py` sends a GET or a POST, and a wrong value
changes the request shape without changing the result for short inputs. It
is now checkable against `Common.js` rather than against the port's own
test.

The port also carries `UNKNOWN_LANGUAGE_CODE = -1`, `UNKNOWN_LANGUAGE = 0`,
`AUTO_DETECT_LANGUAGE = 1`, `ENGLISH_LANGUAGE = 17`, which are in
`Common.js`'s language-id declarations.

## 3. The complete payload inventory

The stream is fully accounted for, which is the kind of check that makes
the rest of the recovery trustworthy. **131 chunks, consuming all
2,263,053 bytes exactly:**

| contents | count |
|---|---|
| `Service.js` | 19 |
| `Common.js` | 1 |
| `Plugins/History/*.js` exporters | 4 |
| theme JSON | 8 |
| locale `lang.json` packs | 35 |
| PE files (the program, `bass.dll`, 3 NSIS helper DLLs) | 5 |
| icons (16×16 `.ico`) | 18 |
| `XdxfArticle.xslt` | 1 |
| other (NSIS stub header, help-text hotkey docs, license) | 39 |
| **total** | **131** |

**19 services, 18 icons — and that 18 is not a rounding artefact.** Every
service's `Service.js` is immediately preceded by one icon chunk except
`Babylon Dictionary`, which shares the one preceding `Babylon` (manifest
order is `Babylon`, `Babylon Dictionary`; only one icon sits before both).
The sizes are not uniform — sixteen 1,150-byte chunks, plus one 894-byte and
one 318-byte — and all eighteen hashes are distinct, so these are eighteen
different images rather than one repeated. The installer's manifest names
exactly **one** `Service.ico`, in `ABBYY Lingvo Live`; the other seventeen
are interleaved in the stream without being named in the manifest at all.

Saying "19 icons, one per service" would have been the tidy claim and it is
not what the chunks give. The pairing is a positional inference, and the one
exception is why it is stated as 18 rather than 19.

The four `Plugins/History` exporters are 4 separate chunks, not one, so
the four I rows map to four distinct files.

## 4. Reproduce

```python
import struct, hashlib
p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()

n = struct.unpack_from("<I", p, 0x13af0)[0]
common = p[0x13af0+4:0x13af0+4+n]
assert len(common) == 6203
assert hashlib.sha256(common).hexdigest().startswith("a03d677a8b3788b5")
assert common.startswith(b"var Const={MAX_URI_LEN:1800,MAX_SOURCE_LEN:5E3")

src = open("qtranslate/common.py", encoding="utf-8").read()
for c in ("MAX_URI_LEN = 1800", "MAX_SOURCE_LEN = 5000",
          'NL = "\r\n"', 'NL2 = "\r\n\r\n"', "DICTIONARY = 8"):
    assert c in src, c
```

The two `NL` assertions need the escape written as `\r\n` in the *asserted
string*, not as actual CR/LF bytes — `common.py` writes the escape sequence,
so a source-text check must look for the backslash form.

## 5. What this does not establish

- **Not** that every `Common.js` function is ported. The constants are
  checked; the helper functions (`format`, `stringFindSub`, `unquoteHtml`,
  `codeFromLanguage`, the language tables) are present in the recovered file
  and were not audited here.
- **Not** a change to E1's state. It stays `VERIFIED`, now with two
  independent artifacts — the loader address and the source file.
- **Not** that the port's `common.py` was *derived* from this file. It may
  have been written from the same source another way. The claim supported is
  only that the values agree, which is what a re-check needs.
