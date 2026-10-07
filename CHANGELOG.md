# Changelog (reverse-engineering log)

All entries are clean-room RE of QTranslate 6.10.0 for education.
`LIVE-OK` = verified against the real provider endpoint.

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
