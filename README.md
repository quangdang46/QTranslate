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
| DeepL | ✅ | ✅ | — | — | **live OK** (detect + translate, 2026-10-07) |
| Microsoft (Bing) | ✅ | ✅ | — | — | **live OK** (shared cookie jar — decompile insight from `FUN_00465A92`) |
| Yandex | ✅ | ✅ | ✅ | — | **live OK via Android variant** (`srv=android` + ucid, researched 2026-10-07) |
| Baidu | ✅ | ✅ | ✅ | — | detect live OK; translate needs page token (web API locked, 2026-10-07) |
| Naver (Papago) | ✅ | ✅ | ✅ | ✅ | **live OK** (new `/api/text/*`, `/api/tts/*`, `/api/dictionary/*` — no auth, 2026-10-07) |
| Promt | ✅ | — | — | — | signing verified; API 400 (needs JS `paft`) |
| Youdao | ✅ | — | — | ✅ | **live OK** (`jsonapi_s` translate + `/w/` dictionary, no sign needed, 2026-10-07) |
| Reverso | ✅ | — | — | ✅ | **live OK** (context JSON API, no auth; legacy HTML path 403) |
| ImTranslator | ✅ | — | — | — | ported; ASMX retired (was Google/MS wrapper — no live API left) |
| WordReference | — | — | — | ✅ | **live OK** (headless Chromium via `headless.py`, 2026-10-07) |
| Oxford Learner | — | — | — | ✅ | **live OK** |
| Multitran | — | — | — | ✅ | **live OK** (anchor-table slice fix, 2026-10-07) |
| Babylon / Babylon Dict | — | — | — | ✅ | ported; translate 404 + dict TLS-handshake-fail (servers retired) |
| ABBYY Lingvo Live | — | — | — | ✅ | **live OK** |
| Urban Dictionary | — | — | — | ✅ | **live OK** |
| Wikipedia | — | — | — | ✅ | **live OK** (Vector-skin fallback slice) |
| Google Search | — | — | — | ✅ | ported; JS-render + consent wall (urllib + headless both blocked) |

## Disclaimer

Clean-room reimplementation for interoperability research and education.
All provider endpoints belong to their respective owners; use at your own risk
and respect their terms of service.

## License

This project is licensed under the **Mozilla Public License 2.0 (MPL-2.0)** —
see [LICENSE](LICENSE) for the full text.

- You may fork, modify, add features, and use commercially.
- Modified MPL-covered files must keep their source available.
- Your own new files may use a different license.
- This license covers only the code written in this repo; it grants no
  rights over QTranslate itself or any third-party binaries, assets,
  keys, or data referenced for interoperability research.
