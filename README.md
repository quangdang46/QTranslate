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
# Full native-like UI (main + popup + Options 9/9 + History + Dictionary
# + tray + hotkeys from your real Options.json):
python -I start_app.py
```

## Test suites (all green 2026-10-08)

```bash
python -I tests/live_providers.py  # 21/21 vs real endpoints
python -I tests/ui_match.py        # 92/92 vs native window/Options.json
python -I tests/smoke_dict.py      # 9/9 (dict + config + hotkeys)
```

## Provider status

| Provider | Translate | Detect | Listen | Dictionary | Status |
|----------|-----------|--------|--------|------------|--------|
| Google Translate | ✅ | ✅ | ✅ | — | live-tested (gtx 429 → dict-chrome-ex fallback) |
| Google TTS | — | — | ✅ | — | live-tested (MP3 downloads) |
| DeepL | ✅ | ✅ | — | — | **live OK** (detect + translate, 2026-10-07) |
| Microsoft (Bing) | ✅ | ✅ | — | — | **live OK** (shared jar + live data-iid; standalone tlookupv3 dict 401-walled, translate chaining unaffected) |
| Yandex | ✅ | ✅ | ✅ | — | **live OK via Android variant** (`srv=android` + ucid, researched 2026-10-07) |
| Baidu | ✅ | ✅ | ✅ | Suggest ✅ | detect + `/sug` suggest live OK; `/transapi` needs `acsToken` (JS challenge); AIT endpoint needs per-session auth (995) |
| Naver (Papago) | ✅ | ✅ | ✅ | ✅ | **live OK** (new `/api/text/*`, `/api/tts/*`, `/api/dictionary/*` — no auth, 2026-10-07) |
| Promt | ✅ | — | — | — | signing verified; API 400 (needs JS `paft`) |
| Youdao | ✅ | — | — | ✅ | **live OK** (`jsonapi_s` translate + `/w/` dictionary, no sign needed, 2026-10-07) |
| Reverso | ✅ | — | — | ✅ | **live OK** (context JSON API, no auth; dict falls back to API when legacy HTML 403s) |
| ImTranslator | ✅ | — | — | — | ported; ASMX retired (was Google/MS wrapper — no live API left) |
| WordReference | — | — | — | ✅ | **live OK** (headless Chromium via `headless.py`, 2026-10-07) |
| Oxford Learner | — | — | — | ✅ | **live OK** |
| Multitran | — | — | — | ✅ | **live OK** (anchor-table slice fix, 2026-10-07) |
| Babylon translate | ✅ | — | — | — | ported 1:1 (ID 13, JSONP); endpoint SSL dead (server retired) |
| Babylon Dictionary | — | — | — | ✅ | ported (ID 20); dict TLS-handshake-fail (server retired) |
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
