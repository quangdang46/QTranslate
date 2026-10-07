# Live verification results (2026-10-07)

Run: `python -I tests/live_providers.py`

```
LIVE-OK  google.translate EN->VI      Chào buổi sáng
LIVE-OK  google.tts                   mp3-bytes
LIVE-OK  deepl.detect                 EN
LIVE-OK  deepl.translate EN->VI       Chào buổi sáng
LIVE-OK  baidu.detect                 en

5/5 live OK
```

## Known-dead / blocked endpoints (as of 2026-10-07)

| Provider | Endpoint | Status |
|---|---|---|
| Yandex | `translate.yandex.net/api/v1/tr.json/*` | HTTP 403 Forbidden — API retired |
| Naver Papago | `papago.naver.com/apis/*` | HTTP 404 — path changed/retired |
| Baidu translate | `fanyi.baidu.com/v2transapi` | needs live page `token`+`gtk` (JS-rendered page, not scrapable with urllib) |
| Youdao | `fanyi.youdao.com/translate_o` | needs live page `salt`/cookie refresh |
| Microsoft | `bing.com/ttranslatev3` | needs session `IG`/`token`/`key`/cookie scraped from page |
| Promt | `/api/getTranslation` | needs `XSRF-TOKEN`/cookie from page |

These providers' *request-building and response-parsing logic* is still a
faithful port of the original `Service.js` — what's missing is the ephemeral
session-token scraping step the native app does by first loading the
provider's web page (handled by the embedded Chakra/JS engine +
`UtilsDispatch`, see `docs/NATIVE_ARCH.md`). A `session.py` helper that scrapes
these tokens via `urllib` + regex would unblock them; tracked as follow-up.
