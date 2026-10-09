# QTranslate end-to-end pipeline (reversed + reimplemented)

> Status: **HISTORICAL PIPELINE MAP (Phase A source).** This doc's native
> function map stays, but later RE corrected several labels. Known
> tensions (all logged in `docs/RE_PROGRESS.md` §Tensions, not edited into
> `docs/NATIVE_ARCH.md`):
>
> 1. `FUN_0045F6C1` is option/token seeding, **not** the executor — the
>    request loop is `FUN_00460354` (#1).
> 2. `FUN_00460354` is a build→fetch→parse loop, **not** a detect-retry (#2).
> 3. `FUN_00442C909`→`FUN_0042C909`: the cited spell addresses decompose to a
>    destructor, not spell logic (#3).
> 4. `FUN_004638D8` is the history **loader**; the saver is `FUN_00463B04` (#4).
> 5. `FUN_00448BEC` is the **MSXML XSLT engine** — no native SAPI TTS found (#5).
> 6. `EVENT_STOP_CAPTURE` is a speech-recognizer FSM event, not OCR (#6).
> Authoritative RE status lives in `docs/RE_COVERAGE_CHECKLIST.md`;
> the progress log is `docs/RE_PROGRESS.md`.

```
User action (hotkey Ctrl+C+C / Ctrl+Q+Q / hover / Ctrl+Alt+L)
  │
  ├─ RegisterHotKey (FUN_00405A17, IAT 0x50D658)
  ├─ Message loop (FUN_00455061) + PreTranslate chain (FUN_004551D6)
  │
  ├─ Capture dispatcher (FUN_004052E4, MouseMode 1/2/3)
  │    ├─ 1: reuse text
  │    ├─ 2: OLEACC mouse (FUN_00404901: GetCursorPos→AccessibleObjectFromPoint→accName/accValue)
  │    └─ 3: clipboard (viewer WndProc 0043EBA1 + FUN_0043BF30 monitor + FUN_0043BDB4 SendInput synth)
  │
  ├─ Orchestrator (FUN_00404A12)
  │    ├─ picker: ServicesOrder head (0045CEDE) / by-id hash (0045CC50)
  │    ├─ option/token seed (FUN_0045F6C1 — NOT the executor, see tension #1) ──
  │    │        Options bridge (UtilsDispatch: Tkk/tokens/cookies/LanguageCode)
  │    ├─ loop: request/response (FUN_00460354, NOT a detect-retry — tension #2)
  │    │    ├─ serviceHeader → caps tuple (FUN_00465669)
  │    │    ├─ serviceDetectLanguageRequest → RequestData (FUN_0046009D)
  │    │    ├─ serviceTranslateRequest → RequestData (FUN_00465D82)
  │    │    ├─ curl fetch (libcurl; WinHTTP proxy; SSL via crypt32)
  │    │    ├─ serviceTranslateResponse → ResponseData (FUN_00465E36)
  │    │    ├─ serviceDictionary{Request,Response} (FUN_00465EF7/00465FAB)
  │    │    └─ serviceListenRequest → mp3 → BASS playback (FUN_00461642)
  │    ├─ fallback: back-translation (004606BA) → request loop (00460354; NOT a detect-retry — tension #2)
  │    └─ ReplaceSelection variant: write-back (0043BE56) + synth Ctrl+V
  │
  ├─ Render (FUN_0040C393 + siblings)
  │    ├─ SetWindowTextW + WM_SETICON, RichEdit subclass (004030AE)
  │    ├─ layout engine auto-fit (0044B4F4: Button vs Static walk)
  │    └─ SetWindowPos TOPMOST/SHOWWINDOW
  └─ History save (FUN_004638D8) → History.json (+ Csv/Html/Json/Txt export plugins)

Aux: Tray (00405C42), Options saver (004561F0), crash-once reporter (00462C03),
     updater (00461A26, dead 404), OCR upload (ocr.space multipart),
     spell (Google suggest + Yandex speller), XDXF offline dict (00445BB9),
     layout convert (FUN_00404E09 → layout.py), speech-in (BASS record → FLAC → speech-api)
```

## Python mirror (`qtranslate/`)

| Native | Python | Live |
|---|---|---|
| **19**× Service.js + Common.js | `services/*.py` + `common.py` | Google/DeepL/Yandex/Bing + dicts/spell/OCR, see `tests/LIVE_RESULTS.md` |
| FUN_00404A12 orchestrator | `services/google_translate.translate()` + siblings | ✅ |
| FUN_00461642 BASS playback | `player.py` (ctypes bass.dll) | ✅ real audio |
| TaskConvertTextLayout | `layout.py` + app Ctrl+Alt+L | ✅ |
| Hotkey+clipboard+popup+Listen | `app.py` (Options.json registrar + monitor + Ctrl+C+C) | ✅ |
| Options.json 20 sections | `config.py` | ✅ (reads real file) |
| History Csv/Html/Json/Txt.js | `history.py` | ✅ (col order + unicode fixed) |
| XdxfArticle.xslt | `xdxf.py` | ✅ (templates tested) |
| Session bootstrap (Chakra page loads) | `session.py` (cookie-jar opener) | ✅ Bing unblocked |
| 19 DLGs + menus/accels/icons | `app.py` windows + Options 9/9 | ⚠️ structure/strings (NOT screenshot — see `CURRENT_STATE.md` §2.2) |
| lang.json 36 strings + 14 windows | `locale.py` + `_T/_W/_Cw` | ✅ vi verified |
| RT_HTML-192 dict template | `dict_template.html` | ✅ byte-identical |
| RichEdit links (FUN_004266C6) | `tag_links` (result + dict) | ✅ |
| Tray states 199/0x84/0x8A | `_make_tray` + `_sync_icon` | ✅ (pystray optional) |
| Crash once-reporter (00462C03) | hook + consume | ✅ |
