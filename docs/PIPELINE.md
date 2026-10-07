# QTranslate end-to-end pipeline (reversed + reimplemented)

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
  │    ├─ executor (FUN_0045F6C1) ── Options bridge (UtilsDispatch: Tkk/tokens/cookies/LanguageCode)
  │    │    ├─ serviceHeader → caps tuple (FUN_00465669)
  │    │    ├─ serviceDetectLanguageRequest → RequestData (FUN_0046009D)
  │    │    ├─ serviceTranslateRequest → RequestData (FUN_00465D82)
  │    │    ├─ curl fetch (libcurl; WinHTTP proxy; SSL via crypt32)
  │    │    ├─ serviceTranslateResponse → ResponseData (FUN_00465E36)
  │    │    ├─ serviceDictionary{Request,Response} (FUN_00465EF7/00465FAB)
  │    │    └─ serviceListenRequest → mp3 → BASS playback (FUN_00461642)
  │    ├─ fallback: back-translation (004606BA) → detect retry (00460354)
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
| 17× Service.js + Common.js | `services/*.py` + `common.py` | Google/DeepL/Yandex/Bing + dicts/spell/OCR, see `tests/LIVE_RESULTS.md` |
| FUN_00404A12 orchestrator | `services/google_translate.translate()` + siblings | ✅ |
| FUN_00461642 BASS playback | `player.py` (ctypes bass.dll) | ✅ real audio |
| TaskConvertTextLayout | `layout.py` + app Ctrl+Alt+L | ✅ |
| Hotkey+clipboard+popup+Listen | `app.py` (Ctrl+Alt+Q) | ✅ |
| Options.json 20 sections | `config.py` | ✅ (reads real file) |
| History Csv/Html/Json/Txt.js | `history.py` | ✅ |
| XdxfArticle.xslt | `xdxf.py` | ✅ |
| Session bootstrap (Chakra page loads) | `session.py` (cookie-jar opener) | ✅ Bing unblocked |
