# Changelog (reverse-engineering log)

All entries are clean-room RE of QTranslate 6.10.0 for education.
`LIVE-OK` = verified against the real provider endpoint.

## Keys loop (2026-10-08, help.txt 100% bound)

- Ctrl+K virtual keyboard; Ctrl+Space suggestion accept (label
  clickable); toolbar New (id1021)
- Right-click multi-select translate (fan-out + groove marks)
- All 17 main-window hotkeys bound; global registrar from Options.json
- `tests/ui_match.py` 82/82

## Babylon translate (2026-10-08, ID 13 ported 1:1)

- `services/babylon.py`: header/host/link, SupportedLanguages (76),
  JSONP request/response (paren-strip, [1] branch, `*` -> NL);
  endpoint SSL dead server-side (native error string via do_translate)
- Strip now 9/9 ServicesOrder; dict fixed to ID 20 lookup
- `tests/ui_match.py` 79/79

## UI 1:1 loop (2026-10-07/08, verified side-by-side vs native window)

- Main: full help.txt default text, ServicesOrder strip
  (Go..Mi..Pr..Ba..Ya..yo..Ba..Pa..DeepL), mic/headphone overlays,
  native error string, Tahoma, WINDOWPLACEMENT restore (526x366)
- Options 9/9 live on real Options.json: Basics, Appearance,
  Hotkeys (17 actions + Change/Clear), Services, Languages,
  Internet, Exceptions, Advanced, Updates
- History = DLG164 (Treeview + Clear + Save as) + History.json
  persistence; popup = borderless themed + dbl-click; Dictionary =
  services pane + XDXF-offline-first + zoom + history
- Hotkeys registrar reads Options.json (Alt+W replace, Ctrl+Q popup,
  clipboard monitor toggles); tray (pystray, optional); TTS slow flag;
  net stack honors Timeout+Proxy; OCR uses real OcrApiKey
- Suites: live 21/21, `tests/ui_match.py` 95/95, smoke 9/9

## Full-fidelity loop 2 (2026-10-08, 66 commits, all suites green)

- Hotkeys registrar from Options.json (Alt+W replace, Ctrl+Q popup,
  clipboard monitor, Ctrl+C+C, 17-action routing) + in-window keys
  (Shift+Esc, Ctrl+Tab, slots, Alt+Left/Right, Ctrl+Up, F11, panes)
- Net stack honors Timeout+Proxy; OCR region overlay + real key;
  SAPI speech fallback; TTS slow flag; spell gate
- History.json + placements (main/aux) + session restore + Cancel
  snapshot; 75-language table; tray states; crash hook
- All 19 DLGs mapped; dead services verified unrevivable with cause
- Suites: live 21/21, `tests/ui_match.py` 40/40, smoke 9/9

## i18n loop (2026-10-08, vi pack verified)

- `_pack`/`_T`/`_W`/`_Cw` helpers (lang.json Id maps; English fallback)
- Localized: nav/result menus, Options titles+pages order (Ids 10-18),
  full Basics, Appearance (+PopupIcons bitmask), Hotkeys actions,
  Internet, Advanced, Updates, Exceptions, History, aux titles
- `tests/ui_match.py` 46/46 (pages order/ids + vi resolve + fallback)

## i18n full (2026-10-08, vi 36 strings + 14 windows mapped)

- Helpers `_T`/`_W`/`_Cw` (menu/strings/windows/control Ids; en fallback)
- Localized: Translate btn (W1/1004), nav + result menus, Options
  titles/pages/labels (Basics full, Appearance + icons bitmask,
  Hotkeys actions, Internet, Advanced, Updates, Exceptions,
  History, aux titles), error 190, Update Check-now
- Verified: vi strings resolve (Chép bản dịch/Từ điển), en fallback
- Native orders kept: pages Ids 10-18, ProxyType 0-3, PopupIcons bits

## Render loop (2026-10-08, dict template + XSLT + links)

- `dict_template.html` byte-identical to RT_HTML-192 (3062 bytes,
  tested); XSLT k/tr/kref/iref/ex templates verified by test
- Result + dict panes: auto-URL tags (qtdp: internal re-lookup,
  http browser, FUN_004266C6); shared `tag_links` helper
- History CSV order fixed [a,c,b,e,d]; JSON `ensure_ascii=False`
  (native escapeStr keeps unicode)
- `tests/ui_match.py` 95/95

## History favorites (2026-10-08, strings 201/202)

- Star column + Favorite toggle + HistoryFilterFavorites filter;
  4-slot tuples with 3-slot file compat; tuple-safe unpacks
- Toolbar New (DLG129 id1021); DLG129 17-control table documented
- `tests/ui_match.py` 71/71

## Exclusions live (2026-10-08, DisabledMode both ways)

- `foreground_excluded` reads live Disabled/Enabled/DisabledMode
  (was hardcoded blocklist); allowlist mode supported
- `tests/ui_match.py` 95/95 (wcsicmp vectors + live lists)

## Session loop (2026-10-08, panes + langs + options roundtrip)

- Contents.Edit*/SaveOnExit pane cache; SaveHistoryPath export dir;
  OptionsPageIndex last page; ActiveServices/DictionaryServices +
  LanguageFrom/To restore + persist (swap/combo/switch)
- CLI args override session; source combo shows LanguageFrom
- Full native defaults in config.py; stale 18s fixed
- 20/20 Options.json sections wired end to end

## Flags coverage (2026-10-08, all General keys audited)

- Wired: panes, tray, startup, cleanup, langs, services, detect,
  instant, spell, slow-TTS, OCR key/lang/archive, proxy, browser,
  mouse, phonetic (flag), favorites, history, placements, fonts
- Noted limits: cursor-hook mouse icon, DnD (tkinterdnd2),
  Extended (absent in modern Options.json), TTS phonetic (no API)
- `tests/ui_match.py` 71/71

## Theme loop (2026-10-08, ThemeName roundtrip)

- Theme choice persists `Appearance.ThemeName`; popup honors it
  (was hardcoded Flat Dark); `theme._hex` always 6-digit for Tk
- `tests/ui_match.py` 95/95 (hex + 8 palettes + vi boot)

## Services (`qtranslate/services/`)

- google_translate.py — `tk()` token + `/translate_a/single?client=gtx`,
  `dict-chrome-ex` fallback on 429 — **LIVE-OK**
- deepl.py — JSON-RPC split/translate — **LIVE-OK**
- microsoft.py — `ttranslatev3` + dynamic IID + 205 retry — **LIVE-OK**
  (via shared-jar `session.bing_translate()`)
- yandex.py — chunking + `srv=android` fallback — **LIVE-OK**
- baidu.py — GTK sign; detect **LIVE-OK**, translate needs page token
- youdao.py — md5 salt sign; needs page token
- naver.py — HmacMD5 PPG auth; endpoint 404 (stack migrated)
- promt.py — ghcs hash; needs `paft` (markup changed)
- dictionary.py — 11 providers; Urban + Lingvo **LIVE-OK**, rest dead/changed
- spell.py — Google suggest + Yandex speller — **LIVE-OK**
- ocr.py — ocr.space multipart — endpoint verified (demo-key limited)

## Native (`docs/NATIVE_ARCH.md`, `docs/PIPELINE.md`)

Startup → hotkey reg → msg loop + pretranslate → 3-mode capture →
SendInput synth → ActiveScript boot (GUIDs) → 9 JS-boundary invokers →
libcurl fetch → popup render (classifier/initializer/subclass/layout) →
BASS TTS → history/options/crash/XDXF/tray/update/OCR/spell/menus.

## App (`qtranslate/`)

- app.py — hotkey translate popup + Listen + layout-convert hotkeys, themed
- player.py — ctypes BASS playback (**real audio verified**)
- layout.py, config.py, history.py, theme.py, xdxf.py, session.py, tts.py
