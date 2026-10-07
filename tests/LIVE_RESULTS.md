# Live verification results (2026-10-08)

Run: `python -I tests/live_providers.py`

```
LIVE-OK  google.translate EN->VI      Chào buổi sáng
LIVE-OK  google.tts                   mp3-bytes
LIVE-OK  deepl.detect                 EN
LIVE-OK  deepl.translate EN->VI       Chào buổi sáng
LIVE-OK  baidu.detect                 en
LIVE-OK  baidu.suggest                suggest-entries
LIVE-OK  yandex.translate EN->RU      Доброе утро
LIVE-OK  bing.translate EN->VI        Chào buổi sáng
LIVE-OK  youdao.translate_web EN->ZH  早上好
LIVE-OK  youdao.dictionary            dict-html
LIVE-OK  naver.detect                 en
LIVE-OK  naver.translate EN->VI       Xin chào thế giới
LIVE-OK  naver.dict                   dict-items
LIVE-OK  naver.tts                    mp3-bytes
LIVE-OK  dict.oxford                  <div><style>.phonetics-font,.eph,.phon{font-family:"Lucida Sans Unicode",Arial}.
LIVE-OK  dict.lingvo                  <div class="_QT6_ALLs"><style>._QT6_ALLs *{font-size:100%}._QT6_ALLs table{borde
LIVE-OK  dict.urban                   <div><style>.justify-between,.mug-ad,.ad-panel{display:none}.italic{font-style:i
LIVE-OK  dict.wikipedia               <div aria-labelledby="firstHeading" data-mw-ve-target-container>
LIVE-OK  dict.multitran               <div><style>.gray{border:1px dotted gray}</style><table width="100%">
LIVE-OK  reverso.translate EN->FR     bonjour tout le monde
LIVE-OK  dict.wordreference           <div><style>.rh_me,span.phrase,span.hw{font-weight: bold}.rh_ex,.FrEx,.ToEx{disp
21/21 live OK
```

Extended regression (same day, ad-hoc): `yandex-android` EN→RU OK,
`bing` (shared-jar) EN→VI OK, `urban` HTML OK, `lingvo` HTML OK,
`google_suggest` list OK, `yandex_spell` corrections OK.
(Console `charmap` errors on this Windows shell are print-only; payloads
verified non-empty. Total live-verified endpoints: 12.)

## TTS re-probe (2026-10-07, later same day)

| TTS | Status |
|---|---|
| Google TTS | **LIVE-OK** (MP3 downloads, BASS playback verified) |
| Yandex TTS (`tts.voicetech.yandex.net`) | connect timeout — host dead with the API |
| Baidu TTS (`tts.baidu.com/text2audio`) | JSON `err_detail` (locked like translate API) |

## Dictionary providers (probed 2026-10-07)

| Provider | Status |
|---|---|
| Urban Dictionary | **LIVE-OK** (old `/define.php?term=` markup intact) |
| ABBYY Lingvo Live | **LIVE-OK** (dictionary HTML path intact) |
| Reverso | 403 Forbidden (Cloudflare/bot-wall since ~2020) |
| ImTranslator | 404 (endpoint `/translation/dictionary/DicService.asmx` retired) |
| Babylon | SSL verify fail (host cert chain broken/retired) |
| Wikipedia | **LIVE-OK** (Vector-skin fallback slice, 2026-10-07) |
| Multitran | **LIVE-OK** (anchor-table slice fix, 2026-10-07) |
| WordReference | **LIVE-OK via headless Chromium** (`qtranslate/headless.py`, stealth flags beat the Anubis wall, 2026-10-07) |

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
`UtilsDispatch`, see `docs/NATIVE_ARCH.md`).

## Follow-up: qtranslate/session.py (token scraping)

Added `qtranslate/session.py` to reproduce that bootstrap step:

- `bing_session()` — scrapes `IG`/`token`/`key` + `Set-Cookie` from
  `bing.com/translator`. **Still 401 Unauthorized live** — Bing's
  `ttranslatev3` now rejects this cookie set entirely (tested 2026-10-07);
  likely needs a full browser-grade TLS/header fingerprint, not just cookies.
- `promt_session()` — scrapes `XSRF-TOKEN` cookie from `online-translator.com`.
  **Still 400 Bad Request live** — the `paft` field regex no longer matches
  the current page markup (site redesigned since the JS was written).

Both are honest dead ends with urllib alone, documented rather than hidden;
a real fix needs either reverse-engineering the current page's JS for the
new token format, or driving an actual headless browser.

## Update 2026-10-07: Bing UNBLOCKED via shared cookie jar

Decompiling `FUN_00465A92` (native option setter → JS `addOption`) revealed
cookie *values* come from the engine's own jar across sequential page loads —
not from native code. Reproducing with one shared `CookieJar` opener for
scrape + translate (`session.bing_translate()`) returns live translations.
**Bing is now LIVE-OK.**

## Verified JS-rendered (need headless, not just cookies)

Probed 2026-10-07 with shared-jar sessions — tokens absent from static HTML:

- Baidu: fresh BAIDUID/BIDUPSID/PSTM cookies OK, but v2transapi → errno
  1022 (anti-bot: needs live `gtk`+`token` from the JS bundle).
  `/sug` suggest + `/langdetect` are **LIVE-OK with no auth** (reversed
  2026-10-07 from headless traffic capture). New `/transapi` goes through
  `v2Fetch` with `acsToken` (per-session JS challenge); the AIT endpoint
  `/ait/text/translateIncognitoAi` returns errno 995 (not authorized)
  even in-browser.
- Youdao: live OUTFOX cookie plumbed through (was hardcoded), but
  translate_o → `errorCode 50` (new `bv`/`mysticTime` fields required).
- Promt: Antiforgery cookies OK, `paft` absent → API 400. ghcs() verified.
- Naver: legacy `/apis/*` 404 (migrated), but new web API
  (`/api/text/translation`, `/api/langs/dect`, `/api/dictionary/search`,
  `/api/tts/makeID` + `/api/tts/{id}`) is **LIVE-OK with no auth**
  (reversed 2026-10-07 from Next.js chunks; speaker map ported).

## 2026-10-08 note: DeepL 429

DeepL endpoints rate-limit this IP after repeated suite runs
(HTTP 429 on detect + translate; code path verified working
earlier same day — 21/21 green). Retry after cooldown.
WordReference Anubis wall flaps (EMPTY/500 transient); headless
fallback covers it.
