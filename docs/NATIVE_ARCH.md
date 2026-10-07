# QTranslate 6.10 native architecture (reversed from QTranslate.exe)

PE32 i386, ImageBase 0x400000, entry 0x4B46BC.
VS2015–2019 CRT. C++ / WTL-ATL (`ATL::CWindowImpl`, thunking).
Symbols stripped, but **RTTI intact** — full class map recovered from `.rdata`.

## Startup chain (decompiled via Ghidra, verified)

- `entry 004B46BC` → `__scrt_common_main_seh 004B44E9` (CRT SEH wrapper)
- → **`FUN_00435005` = WinMain**: parses `GetCommandLineW`, singleton check
  (`FUN_00435175`), `CoInitializeEx(COINIT_APARTMENTTHREADED)`,
  DPI scale init (`FUN_0044A3D8`), then `FUN_004350B8`, `CoUninitialize`.
- → **`FUN_004350B8` = AppInit**: `LoadLibraryW("msftedit.dll")`
  (RichEdit for popup text), registers WTL window classes
  (`FUN_00421892`), creates main window (`FUN_0043527D`), then `FUN_00455061`.
- → **`FUN_00455061` = message loop**: `GetMessageW` → pre-translate hook
  chain (`DAT_005491EC` filter array — hotkey handling lives here) →
  `TranslateMessage` → `DispatchMessageW`.
- **`FUN_004551D6` = pretranslate-hook registrar** (vector push_back with
  `realloc` doubling at `DAT_005491F4` capacity, count at `DAT_005491F0`;
  10 registered callers `FUN_00455024`…`FUN_004552AB` + unregister at
  `FUN_004552DC`). This is WTL's `PreTranslateMessage` chain — every window
  (MainWindow, popups, hotkey window) filters messages here before dispatch.
- **`FUN_0043527D` = WTL CreateWindow wrapper**: `AtlThunk` alloc + `CreateWindowExW`
  (thunk converts `__thiscall` WndProc → `__stdcall`).
- **`FUN_00416470` = app-object ctor**: lays out the whole window tree by
  vftable (`ApplicationWindow`, `KeyboardWindow`, `LanguagesComboSimple`,
  `WindowPopupIcons`, `ProgressWindow`, RichEdit init) — offsets give the
  member layout for a future C++ reconstruction.
- **`FUN_00403057` = ATL thunk allocator** (`AtlThunk_AllocateData/InitData`).
- **`FUN_00421892` = WndClass registration** (cursor, `GetClassInfoExW` chain,
  `RegisterClassExW`).
- Audio imports confirmed: `BASS_StreamCreateFile/ChannelPlay/Init/Free`,
  `BASS_RecordInit/Start` (mic capture for speech-to-text), `BASS_ChannelSetSync/Stop`
  — playback path is `TaskListenText` → mp3 bytes → `StreamCreateFile` → `ChannelPlay`.
  RTTI `TaskListenText` type descriptor at VA `0x44603c`.

## UI windows (`windows::` namespace, WTL dialogs)

| Class | Role |
|---|---|
| `MainWindow` (+`MainWindowMenu`, `LayoutManager`) | main popup window, translation display |
| `WindowPopup` / `WindowPopupBase` (+`WindowHover`, `TopmostWindow`) | hover popup near cursor/selection |
| `DictionaryWindow`, `HistoryWindow`, `KeyboardWindow` (virtual keyboard), `LanguagesWindow`, `OptionsWindow`, `AboutWindow`, `ExceptionWindow`, `InfoWindow` | aux dialogs |
| `HotKeyWindow` + `HotKeyCtrl` (`controls::`) | global hotkey settings UI |
| `ScreenCaptureWindow` + `InfoCaptureButton` | OCR region select overlay |
| `SpeechLevelWindow` | mic level meter |
| `LayoutIndicatorWindow` | keyboard layout indicator |
| `ApplicationWindow` | hidden message-only window (hotkey msgs) |

Settings pages (`Page*`): Basics, Hotkeys, Languages, Services, Internet,
Appearance, Advanced, Updates, Exceptions.

## Task pipeline (`tasks::windows::`)

Each user action = a `Task` object posted to a worker thread:

- `TaskTranslateClipboard` — clipboard-monitor mode (`GetClipboardSequenceNumber` polling)
- `TaskCopySelection` → `TaskTranslateInMainWindow` — Ctrl+C+C flow: synthesize copy, read clipboard, translate, render
- `TaskReplaceSelection` — paste translation back over selection
- `TaskShowPopupWindow` / `TaskShowMainWindow` — render paths
- `TaskDictionary` — dictionary lookup path
- `TaskListenText` — TTS playback (via `bass.dll`)
- `TaskOcr`, `TaskOcrCopyImageTextToClipboard` — screenshot → OCR providers
- `TaskAutoBackTranslation`, `TaskConvertTextLayout` (keyboard layout fix), `TaskRenderHistoryItemInMainWindow`

## Capture path (hotkey → text) — decompiled, verified

1. **`FUN_00405A17` = hotkey registrar** (`__thiscall`, calls `RegisterHotKey`
   via IAT slot `0x50D658`): parses hotkey word — `id = low byte`,
   `modifiers = (word >> 8) & 0xF`, `vk = low byte`; on success appends the id
   to a vector (`this+4` count, `this[0]` array). Two sibling registrars at
   `FUN_0040AB69` / `FUN_0040ACA3` (same IAT slot, different owners).
   `ApplicationWindow` receives `WM_HOTKEY` in the `FUN_00455061` loop.
2. **Mouse-mode capture = `FUN_00404901`**: `GetCursorPos` →
   `AccessibleObjectFromPoint` (IAT `0x50D3D0`) → `IAccessible::get_accName`,
   fallback `get_accValue` when name empty. This is the "hover a word" path.
3. **Clipboard open = `FUN_0043BE07`** (`__thiscall`): `OpenClipboard(hwnd)`
   with 5× retry (`Sleep(5)` between attempts) — the Ctrl+C+C path's
   front door. Related readers: `FUN_0043BF30` (sequence-number poll),
   `FUN_0043ECA5`/`FUN_0043BEB2` (`GetClipboardData`).
4. **Copy-capture = `FUN_0043BF30`/`FUN_0043C02B`** (the Ctrl+C+C engine):
   wait for Alt (`0x12`)/Shift (`0x10`) release via `GetKeyState` →
   snapshot `GetClipboardSequenceNumber` → `FUN_0043BD5C('C')` synthesizes
   Ctrl+C → exponential-backoff poll (`8→320ms`) for sequence change =
   proof the app received the copy. `param_1` selects `0x43` ('C') vs
   `0x2D` (Insert → Ctrl+Ins alternate path).
5. **Key synthesizer = `FUN_0043BD5C` → `FUN_0043BDB4`**: Ctrl-down
   (`0x11`) → key-down → `Sleep(0x20)` → key-up → Ctrl-up, via zeroed
   `tagINPUT` + `SendInput(1, &input, 0x1C)` (IAT `0x50D504`).
6. **Keyboard/layout cluster** (`FUN_0042AADC/0042AB07/0042AB33/0042AB5F`,
   `FUN_0042AEC9/0042AEF2`, `FUN_0042B935` — all `SendInput` callers via same
   IAT slot): single-key inject helper `FUN_0042AADC(key, up/down)` — the
   `TaskConvertTextLayout` engine that retypes text in the fixed layout.
4. OCR: `OcrProvider`/`OcrSpaceProvider` (`common::`) — screenshot from `ScreenCaptureWindow` → upload to OCR API.

## JS engine hosting (decompiled, verified)

- **`FUN_0043E32F` = ActiveScript bootstrapper** (`__fastcall`, `CoCreateInstance`
  via IAT `0x50D878`): CLSID `{BB1A2AE1-A4F9-11CF-8F20-00805F2CD064}` =
  **IActiveScript** (JScript), site IID
  `{F414C260-6AC0-11CF-B6D1-00AA00BBBB58}` = **IActiveScriptSite**,
  then vtable `+0xC` (SetSite) and `+0x28` (InitNew). This is how
  `Services/*/Service.js` gets executed at runtime with `UtilsDispatch`
  exposing native `Options`.
- **Service dispatch = `FUN_0043B777` → `FUN_0043E471`**: boot engine, walk
  the service function hash-map invoking each entry, then `GetDispID` on the
  script object; `FUN_0043E471` calls `IDispatch::GetIDsOfNames` (vtable
  `+0x20`) with `AddNamedItem` fallback — the actual
  `serviceTranslateRequest(...)` invocation boundary between native and JS.
- **Task executor = `FUN_0045F6C1`** (`__thiscall`, 3 callers incl.
  `FUN_00428096`): runs `FUN_0043B777` (service JS) then post-processes via
  script helpers — `usesAutoDetectCode`, `codeFromLanguage` (VARIANT bool/u32
  marshalling through `FUN_0043B8CE`/`FUN_0043B9BE`). This is
  `TaskTranslateInMainWindow`'s core: JS result → native language-code
  resolution → render.
- **Service file loader = `FUN_00428096` → `FUN_0043DF32`**: `GetFileAttributesW`
  existence check on `Services/<name>/Service.js` → `FUN_0043E004` read file →
  BOM detect/strip (UTF-16LE `FF FE` vs UTF-8) → hand text to `FUN_0043B777`.
  This is how the 17 JS plugins enter the engine at startup/service-switch.

## TTS playback path (decompiled, verified, reimplemented)

- **`FUN_00461642` = play function** (`__fastcall`, calls BASS via IAT slots
  `0x50D7AC`/`0x50D7B4`):
  `FUN_00461691` (free old stream) → `BASS_StreamCreateFile(mem=1, data, 0, len, 0, 0)`
  → `ctx[0x30] = stream` → `BASS_ChannelSetSync(stream, END, 0, on_end, ctx)`
  → `BASS_ChannelPlay(stream, restart=TRUE)`.
- Reimplemented in `qtranslate/player.py` via ctypes against the real
  `bass.dll` (32-bit — run with 32-bit Python). Live-verified: downloads
  Google TTS mp3 and plays it through BASS end to end.

## Service execution (`services::` + `net::`)

- `Script` + `ActiveScript`/`ActiveScriptSite` (`base::`) — **Chakra/JScript engine** hosting; loads `Services/*/Service.js` at runtime via `CoCreateInstance`.
- `UtilsDispatch` (IDispatch bridge) exposes native `Options` (IG/BingToken/Cookie, GoogleTkk, proxy) into JS.
- `CurlHandle` + `HttpDelegate` (`net::`) — embedded libcurl (strings: `Downgrades to HTTP/1.1!`, `Uses proxy env variable`, `Netscape HTTP Cookie File`) performs the actual HTTP; `WINHTTP.dll` used for IE proxy config (`WinHttpGetIEProxyConfigForCurrentUser`) and `WS2_32`/`CRYPT32` for TLS.
- Audio: `SpeechRecognizer`, `SpeechRecognitionEngine` (Google `speech-api/full-duplex` URLs in strings), `SpeechToText`, `AudioRecorder`, `EnergyEndpointer`; playback via `bass.dll`.

## JS framework (`Services/Common.js` → `qtranslate/common.py`)

`ServiceHeader`/`RequestData`/`ResponseData`, capability bitmask
(TRANSLATE=1, DETECT=2, LISTEN=4, DICTIONARY=8), limits (URI 1800 / source 5000 chars).
17 providers; see `qtranslate/services/`.
