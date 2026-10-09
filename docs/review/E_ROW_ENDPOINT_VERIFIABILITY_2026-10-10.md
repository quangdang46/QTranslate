# Which E-row endpoint claims the recovered image can actually verify

> Read-only. **No row state changed.** This records an independent measurement
> that sharpens `SERVICE_JS_PROVENANCE_2026-10-10.md` in one direction, and it
> disagrees with one sentence in that doc's covering message.
>
> The peer's document says the natively compiled clients are
> `google, Microsoft/Bing, Yandex, Baidu, OCR.space` and *"those rows are
> verifiable from the image."* The narrower reading below is what the bytes
> support, and the difference decides whether `E2 Google Translate` — the row
> the entire port rests on — carries an "image-checkable" stamp it has not
> earned.

## 1. Method

Read the whole 1,462,272-byte recovered image as ASCII, UTF-16LE and UTF-16BE,
and measure one thing per row: **is the literal the checklist cites actually
present?** Host-only presence is not the same claim as path presence, and the
rows cite paths.

## 2. What is in the image

Every wide string that is a translation-service endpoint, with its offset:

| Offset | Literal |
|---|---|
| `0x11bd28` | `google.com` |
| `0x11c5e0` | `translate.google.` |
| `0x1215e0` | `google.com/speech-api/full-duplex/v1/up?` |
| `0x121680` | `google.com/speech-api/full-duplex/v1/dow…` |
| `0x11e3cc` | `speller.yandex.net` |
| `0x128b78` | `api.ocr.space/parse/image` |
| `0x129612` | `fanyi.baidu.com` |
| `0x129700` | `bing.com/translator` |
| `0x1298a0` | `bing.com/ttranslatev3` |
| `0x1298dc` | `translate.yandex.com/` |
| `0x129928` | `online-translator.com/translation` |

`SERVICE_JS_PROVENANCE_2026-10-10.md` measured the same table. The
disagreement is about what it licenses, not about what it says.

## 3. The distinction that decides it

An endpoint is image-verifiable for a given row **only when the full literal
that row cites is present.** Applying that to the four rows the peer's message
called image-checkable:

| Row | Cites | Full literal in image? | Verdict |
|---|---|---|---|
| E2 Google Translate | `/translate_a/single` (`dt=`, `tk=`) | **ABSENT** | host only |
| E3 Microsoft | `bing.com/ttranslatev3` | **`0x1298a0`** | **yes** |
| E3 Microsoft | `bing.com/translator` | **`0x129700`** | **yes** |
| E5 Yandex | `/api/v1/tr.json/translate` | **ABSENT** | host only |
| E5 Yandex TTS | `tts.voicetech.yandex.net` | **ABSENT** | no |
| E7 Baidu | `/v2transapi` | **ABSENT** | host only |
| E7 Baidu TTS | `tts.baidu.com` | **ABSENT** | no |

`fanyi.baidu.com` and `translate.yandex.com/` are **host strings** — the path
is concatenated at runtime. `google.com` appears with a path only for the
**speech** endpoints (`/speech-api/full-duplex/v1/up`), never for translate.

So the count is **one row, not four**: E3 (and E22's `tlookupv3` if it shares
the same literals, and the OCR client). Everything else in the E group is
host-visible at best.

## 4. Why the sharper rule matters more than the number

`E2 Google Translate` is the row the port is built on. If its URL shape is
recorded as image-checkable, then the single most-cited native claim in the
project carries a verification stamp it has not earned — and the natural
correction, "check the port against the binary," would pass, because the port
matches the *host* and the host is there.

The peer's own document makes this exact argument about the JS-plugin rows in
§3. The one-sentence summary simply applied it inconsistently by calling a
host string an endpoint. Same error shape both sides have been trading this
session: a true fact about a string that is not the claim under test.

## 5. What follows for the Gate, which is the real stake

If the endpoint-shape claims across E are `VERIFIED` → `INFERRED`, the Gate's
state changes shape, not just its count:

- today it reads **"BLOCKED (1) — one row unresolved, and that one is G9, a
  runtime blocker."**
- after a reclassification it reads **"BLOCKED on G9, and N E-rows whose
  native artifact was never in the binary."**

The second is a materially worse finding and must be written into the Gate
line, not just recounted in the tally. Recording that here because the count
is the number the project's honesty rests on, and a quiet recount would make
the Gate look *more* resolved than a reclassification should.

## 6. What this does not do

- Does not reclassify anything. Not my call; not my file.
- Does not disagree with the peer's central finding. `Services/` and every JS
  endpoint are absent, the ASCII URL set is one unrelated Microsoft schema
  string, and the URL shapes in the row text are not re-derivable here. All
  independently confirmed.
- Does not claim the port's URLs are *wrong*. Live probes are legitimate
  evidence for the behaviour claim. They are just not evidence for the native
  shape claim, which is the distinction the peer's §3 already draws.

## 7. Reproduce

```python
blob = open("docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()
for needle in ("/translate_a/single", "/api/v1/tr.json/translate", "/v2transapi",
               "bing.com/ttranslatev3", "tts.baidu.com", "google.com/search"):
    print(needle, hex(blob.find(needle.encode("utf-16-le")))
          if blob.find(needle.encode("utf-16-le")) >= 0 else "ABSENT")
```
