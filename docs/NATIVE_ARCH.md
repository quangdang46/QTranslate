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

## Capture path (hotkey → text)

1. `RegisterHotKey` (USER32 import) bound in `HotKeyWindow`; `ApplicationWindow` receives `WM_HOTKEY`.
2. Text sources: clipboard chain (`OpenClipboard`/`GetClipboardData`), caret/selection via MSAA (`OLEACC.dll` → `AccessibleObjectFromWindow`).
3. OCR: `OcrProvider`/`OcrSpaceProvider` (`common::`) — screenshot from `ScreenCaptureWindow` → upload to OCR API.

## Service execution (`services::` + `net::`)

- `Script` + `ActiveScript`/`ActiveScriptSite` (`base::`) — **Chakra/JScript engine** hosting; loads `Services/*/Service.js` at runtime via `CoCreateInstance`.
- `UtilsDispatch` (IDispatch bridge) exposes native `Options` (IG/BingToken/Cookie, GoogleTkk, proxy) into JS.
- `CurlHandle` + `HttpDelegate` (`net::`) — embedded libcurl (strings: `Downgrades to HTTP/1.1!`, `Uses proxy env variable`, `Netscape HTTP Cookie File`) performs the actual HTTP; `WINHTTP.dll` used for IE proxy config (`WinHttpGetIEProxyConfigForCurrentUser`) and `WS2_32`/`CRYPT32` for TLS.
- Audio: `SpeechRecognizer`, `SpeechRecognitionEngine` (Google `speech-api/full-duplex` URLs in strings), `SpeechToText`, `AudioRecorder`, `EnergyEndpointer`; playback via `bass.dll`.

## JS framework (`Services/Common.js` → `qtranslate/common.py`)

`ServiceHeader`/`RequestData`/`ResponseData`, capability bitmask
(TRANSLATE=1, DETECT=2, LISTEN=4, DICTIONARY=8), limits (URI 1800 / source 5000 chars).
17 providers; see `qtranslate/services/`.
