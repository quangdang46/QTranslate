# qtranslate-re

Clean-room reverse engineering of the **QTranslate 6.10 service pipeline** for
educational purposes: how a multi-provider translation client works end to end
(native hotkey/clipboard capture → JS service plugins → public translate APIs →
popup render + TTS).

## Layout

- `qtranslate/` — Python reimplementation (runs for real)
  - `common.py` — port of the `Common.js` framework (`RequestData`,
    `ResponseData`, capability bitmask, URL/length limits, HTML helpers)
  - `services/` — one module per provider, ported from `Services/*/Service.js`
  - `tts.py` — text-to-speech audio download (`translate_tts`, Yandex/Baidu TTS)
- `docs/` — analysis notes (native binary, PE, imports, hotkey/clipboard flow)
- `tests/` — live smoke tests against the real provider endpoints

## Quick start

```bash
python -I qtranslate/services/google_translate.py "Hello world" vi
python -I qtranslate/tts.py "Xin chào" vi google.mp3
```

## Provider status

| Provider | Translate | Detect | Listen | Dictionary | Status |
|----------|-----------|--------|--------|------------|--------|
| Google Translate | ✅ | ✅ | ✅ | — | live-tested (gtx 429 → dict-chrome-ex fallback) |
| Google TTS | — | — | ✅ | — | live-tested (MP3 downloads) |
| DeepL | ✅ | ✅ | — | — | ported (needs live test) |
| Microsoft (Bing) | ✅ | ✅ | — | — | **live OK** (shared cookie jar — decompile insight from `FUN_00465A92`) |
| Yandex | ✅ | ✅ | ✅ | — | **live OK via Android variant** (`srv=android` + ucid, researched 2026-10-07) |
| Baidu | ✅ | ✅ | ✅ | — | detect live OK; translate needs page token (web API locked, 2026-10-07) |
| Naver (Papago) | ✅ | ✅ | ✅ | — | ported, **endpoint dead (/apis/* → 404, 2026-10-07)** |
| Promt | ✅ | — | — | — | ported |
| Youdao | ✅ | — | — | — | ported |
| Reverso | ✅ | — | — | ✅ | ported |
| ImTranslator | ✅ | — | — | — | ported |
| WordReference | — | — | — | ✅ | ported |
| Oxford Learner | — | — | — | ✅ | ported |
| Multitran | — | — | — | ✅ | ported |
| Babylon / Babylon Dict | — | — | — | ✅ | ported |
| ABBYY Lingvo Live | — | — | — | ✅ | ported |
| Urban Dictionary | — | — | — | ✅ | ported |
| Wikipedia / Google Search | — | — | — | ✅ | ported |

## Disclaimer

Clean-room reimplementation for interoperability research and education.
All provider endpoints belong to their respective owners; use at your own risk
and respect their terms of service.
