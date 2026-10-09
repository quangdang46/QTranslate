# The `Service.js` rows: what the image can and cannot support

> Read-only verification. This is not a correction of any row — it is the
> evidence that decides which rows the recovered binary is able to verify at
> all, which turns out to be a much smaller set than the checklist's
> `VERIFIED` column implies.
>
> **No row state changed by this document.** It records what I measured, so
> any row reclassification is a decision made on measured facts. This is
> also not a "the checklist is wrong" note: I do not know where the rows'
> original evidence came from, and this document cannot see it.

## 1. The premise, checked

The E-group rows cite `Services/<Name>/Service.js` as their native artifact
(23 rows name a `Service.js`). The checklist's own RE-state rule is:

> `VERIFIED` — Proven by a concrete artifact: Ghidra address **+** decompile,
> **JS source**, asset bytes, or a behavioral test.

So `VERIFIED` for a `Service.js` row requires one of: the JS source, its
asset bytes, or a behavioral test. This document asks whether the first two
are obtainable from the artifact in this repo.

## 2. No `Service.js` is in the image, and none ever was

Searched the whole 1,462,272-byte image in ASCII, UTF-16LE and UTF-16BE:

| String | Result |
|---|---|
| `Services/` | **ABSENT** |
| `Service.js` | PRESENT — `0x121aa4` (wide) |
| `ServicesOrder` | PRESENT — `0x121e7c` |
| `Common.js` | PRESENT — `0x121a90` |
| `serviceHeader` | PRESENT — `0x12c300` |
| `serviceTranslateRequest` | PRESENT — `0x12c3c4` |
| `serviceTranslateResponse` | PRESENT — `0x12c3f4` |
| `serviceURL` | **ABSENT** (with qtranslate-ed's own correction) |
| `dictionaryRequest` | **ABSENT** |
| `Authenticator.js` | **ABSENT** |
| `getTranslation` | **ABSENT** |

This is the *hook* vocabulary, not the plugins. `Services/` — the path prefix
that would build a service directory — is absent, and so is every service
endpoint the E rows cite:

| Row | Endpoint cited in the checklist | In image |
|---|---|---|
| E4 DeepL | `www2.deepl.com/jsonrpc`, `LMT_handle_jobs` | ABSENT |
| E6 Naver/Papago | `papago.naver.com/apis/{n2mt,nsmt}` | ABSENT |
| E9 Youdao | `fanyi.youdao.com/translate_o` | ABSENT |
| E10 / E11 Babylon | `*.babylon-software.com` | ABSENT |
| E12 ImTranslator | `imtranslator.net` | ABSENT |
| E13 Reverso | `dictionary.reverso.net` | ABSENT |
| E14 ABBYY Lingvo | `lingvolive.com` | ABSENT |
| E15 Multitran | `multitran.com` | ABSENT |
| E16 Oxford Learner | `oxfordlearnersdictionaries.com` | ABSENT |
| E17 Urban Dictionary | `urbandictionary.com` | ABSENT |
| E18 Wikipedia | `m.wikipedia.org` | ABSENT |
| E19 WordReference | `wordreference.com` | ABSENT |
| E20 Google Search | `google.com/search` | ABSENT |

None is present in any encoding. The complete set of plain `http(s)://` URLs
in the whole image is four, none of them a translation service:

```
http://schemas.microsoft.com/SMI/2005/WindowsSettings
https://curl.se/docs/alt-svc.html
https://curl.se/docs/hsts.html
https://curl.se/docs/http-cookies.html
```

The wide-string equivalents that *are* present are 29 runs, and the
service-relevant ones are exactly the **natively compiled** clients:

```
0x119  google.com, translate.google., quest-app.appspot.com
0x121  speech-api/full-duplex/v1/{up,down}
0x128  api.ocr.space/parse/image, status.ocr.space
0x129  fanyi.baidu.com, bing.com/translator, bing.com/ttranslatev3,
       translate.yandex.com, online-translator.com, cloud-api.yandex.net
0x11e  speller.yandex.net
```

Google, Microsoft/Bing, Yandex, Baidu, OCR.space. **Those rows are verifiable
from the image.** The dictionary/JS-plugin rows are not, because the plugins
are fetched at runtime by name and the binary only stores the names.

## 3. What is left for the JS-plugin rows

The checklist's `VERIFIED` rule allows a **behavioral test** as evidence, so
these rows are not automatically wrong — a live round-trip would satisfy the
rule, and several rows' evidence column says "live Win" or "headless Win".
That is a peer measurement made against the live services, and it is
legitimate evidence for *the row's behavior claim*.

What it is **not** evidence for is the claim the row text makes, which is
about the *native* implementation: `Services/<Name>/Service.js` — a
concatenated URL, a specific parameter order, a caps mask. A live test proves
the endpoint responds that way; it does not prove the native client asked in
that shape. The distinction is exactly `PROJECT_VISION.md` §7a's two axes, and
the row text and the row state live on **different** axes.

So the honest reading of a JS-plugin row is:

- **Port/behaviour column** — supported by the live test, if one was done.
- **RE column, as written** ("`Services/X/Service.js`: GET `<url>`") — the
  URL shape is *inferred from the port's implementation*, not read from the
  binary, because the binary does not contain it.

That is a reclassification candidate (`VERIFIED` → `INFERRED` for the
endpoint-shape claim, keeping the behaviour evidence what it is), not a
defect. Recording it rather than acting on it: the reclassification is the
checklist owner's call and it changes the Gate tally.

## 4. The port's own provenance claim, which this bears on

`qtranslate/services/dictionary.py:3` says:

```python
"""Python ports of QTranslate dictionary/search Service.js plugins.
Reversed from QTranslate 6.10.0 - Services/*/Service.js.
```

Neither the source it cites nor the artifact it cites exists here. `dictionary.py`
was added in `9cdba2b` ("Port all 17 QTranslate services + TTS to Python
(clean-room RE)"), whose message names no artifact, and no `Service.js` has
ever been committed to this repo:

```
$ git log --all --oneline --diff-filter=A -- "*Service.js"
(no commits)
```

So the module docstring's "Reversed from" is unsupported by anything on disk.
I am **not** claiming the port is wrong or unattributed — the peer measured
these endpoints live and they work, and the URLs are real and reachable. The
claim is narrower and it is the one this document can support: **there is no
artifact in this repo against which the URL shapes can have been reversed.**
A reader who wants to re-verify `dictionary.py`'s URL has nothing to check it
against, which is the same position §3 leaves the checklist row in.

## 5. What I could not determine

- **Where the original evidence came from.** The rows may have been verified
  from a Service.js that existed in an earlier session, on the peer's host, or
  from the peer's live probes. I cannot see any of those. This document must
  not be read as "the peer fabricated the claims" — it says the claims are not
  re-derivable from the artifact in *this* repo.
- **Whether the JS plugins are recoverable at all.** The binary names the
  hooks (`serviceHeader`, `serviceTranslateRequest`, `ServicesOrder`), so the
  *hook vocabulary* is in the image. I took that one step too far earlier and
  am recording the correction: I found two code xrefs to `ServicesOrder`
  (`0x45826f`, `0x459fb1`) and decompiled the enclosing one, `FUN_004561f0`
  — which is an **`Options.json` handler**, not a plugin loader. Its
  `L"ActiveServices"` / `L"ActiveDictionaryServices"` keys are about *which*
  services are enabled, not about loading one. The immediate-scan hit an
  operand reuse, exactly the "a grep result is evidence about naming, never
  about behavior" failure in a different costume. So: the hook names exist;
  a host-side loader has **not** been located, and I cannot yet claim the
  plugin protocol is readable from the host side. That question stays open.
  Locating it would need a full-analysis run (the `Service.js` xref at
  `0x45d7a0` falls in a region `-noanalysis` leaves undefined), and it is
  worth doing separately.
- **Whether the compiled-in clients (Google/Bing/Yandex/Baidu) are complete
  enough to verify their rows from the image alone.** Presence of a hostname
  proves the endpoint is real and native; it does not prove the parameter
  order. That needs a decompile of the request builder, which is different work
  from this check.
