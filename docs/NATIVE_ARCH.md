# QTranslate 6.10 native architecture (reversed from QTranslate.exe)

PE32 i386, ImageBase 0x400000, entry 0x4B46BC.
VS2015–2019 CRT. C++ / WTL-ATL (`ATL::CWindowImpl`, thunking).
Symbols stripped, but **RTTI intact** — full class map recovered from `.rdata`.

## Startup chain (decompiled via Ghidra, verified)

- `entry 004B46BC` → `__scrt_common_main_seh 004B44E9` (CRT SEH wrapper)
- → **`FUN_00435005` = WinMain**: parses `GetCommandLineW`, singleton check
  (`FUN_00435175`), `CoInitializeEx(COINIT_APARTMENTTHREADED)`,
  DPI scale init (`FUN_0044A3D8`), then `FUN_004350B8`, `CoUninitialize`.
- → **`FUN_00435005` detail**: `CoInitializeEx(NULL,
  COINIT_APARTMENTTHREADED)` (IAT `0x50D85C`, disasm `PUSH 2; PUSH 0`) +
  conditional `CoUninitialize` (IAT `0x50D860`) — STA for the ActiveScript +
  OLEACC + SAPI apartment. Sibling COM inits at `FUN_004614BB/00448AAD/
  0043ACEA` all pass `PUSH 2` (STA) — whole app is STA including workers
  (required by ActiveScript site marshaling + SAPI callbacks).
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

0. **`FUN_00418DA0`/`FUN_004059CF` = raw-input pre-step**: registers mouse
   RawInput (`UsagePage 1 / Usage 2`, `RIDEV_INPUTSINK 0x100` when enabling)
   so mouse-mode capture receives movement even unfocused; then
   `FUN_00418B69` state sync.
0c. **`FUN_00417E4E` = RawInput mouse handler** (`GetRawInputData/RID_INPUT`
   via IAT `0x50D580`, gated by `DAT_005494E7` + `FUN_004544AE`): maps
   button flags to `WM_LBUTTONDOWN/UP (0x201/0x202)`, stamps
   `GetCursorPos` + `GetTickCount` → `FUN_004193F6` click-capture trigger.
0c2. **`FUN_0043A8C4` = menu-open guard**: `GetCursorPos` →
   `WindowFromPoint` → class name `#32768` (the system menu class) check —
   suppresses mouse-mode capture while a popup menu is showing under the
   cursor (used by the clipboard-monitor gate in `FUN_0043C02B`).
0d2. **Mouse modes** (from `Locales/English/help.txt`, behavior spec):
   1) Show icon (select → icon near cursor → click = popup); 2) Show
   translation (select → immediate popup); 3) Show translation + read aloud.
   Service-name clicks: left = switch+translate, middle = open in browser,
   right = multi-select toggle. Tray: left = mouse-mode toggle, double =
   main window; popup header double-click = main window.
0d. **`FUN_004193F6` = click-capture trigger** (on `0x201` LBUTTONDOWN):
   `WindowFromPoint` (`FUN_00450DD2` = `WindowFromPoint` → `FUN_00450D7C`
   (`EnumChildWindows` + hit-test callback `FUN_00450CFA` = `PtInRect` +
   smallest-visible-area-wins, fallback parent)
   → walk up past invisible parents via `GetParent`)
   → exclusion check (`FUN_004631DE`)
   → `GetWindowRect` + `PtInRect` confirm → store click point
   (`this+0x17F8`). Mouse-mode capture fires from here.
0b. **`FUN_00418C23` = hotkey bulk registrar**: unregisters all existing
   (`UnregisterHotKey` loop over the id vector at `this+0x17D8`) → registers
   17 hotkeys from consecutive option words (`DAT_00549466 + i*2`, matching
   the 17 `HotKey*` names in `Options.json`) when enabled (`param_1` = global
   toggle, `DAT_00549464` = EnableHotKeys).
- **`FUN_00418B69` = tray state sync** (called after bulk register):
  picks tray icon by hotkey state (199 = off, `0x8A` = partial,
  `0x84` = on, via `FUN_00454396` icon loader) + `"%s %s"` tooltip →
  add (`FUN_00405C42`) or modify (`FUN_00405CB2`) tray icon.
- **`FUN_00454396` = icon loader**: `LoadImageW(hInstance, resId,
  IMAGE_ICON, size, size, LR_SHARED)` — all icons (tray states 199/`0x84`/
  `0x8A`, service icons) come from the exe's own `.rsrc` section.
1. **`FUN_00405A17` = hotkey registrar** (`__thiscall`, calls `RegisterHotKey`
   via IAT slot `0x50D658`): parses hotkey word — `id = low byte`,
   `modifiers = (word >> 8) & 0xF`, `vk = low byte`; on success appends the id
   to a vector (`this+4` count, `this[0]` array). Two sibling registrars at
   `FUN_0040AB69` / `FUN_0040ACA3` (same IAT slot, different owners).
   `ApplicationWindow` receives `WM_HOTKEY` in the `FUN_00455061` loop.
2. **Mouse-mode capture = `FUN_00404901`**: `GetCursorPos` →
   `AccessibleObjectFromPoint` (IAT `0x50D3D0`) → `IAccessible::get_accName`,
   fallback `get_accValue` when name empty. This is the "hover a word" path.
   Dispatched by **`FUN_004052E4` = capture-mode switch** (`this+8` =
   `MouseMode` from Options): 1 = reuse supplied text, 2 = OLEACC mouse
   (`FUN_00404901` guarded by `FUN_004543C6` modifier check), 3 = clipboard
   read (`FUN_0043BEB2`). Sibling dispatcher at `FUN_0040558F`.
3b. **`FUN_0043BEB2` = clipboard reader** (`__fastcall`): open-with-retry
   → `GetClipboardData(CF_UNICODETEXT)` → `GlobalSize - 2` (wchar null) →
   `GlobalLock` + bounded copy (`FUN_00402231` = ATL CString bounded
   assign with realloc, `param_2` = max chars) →
   unlock + close. Returns 0 on empty.
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
5. **ScreenCapture paint = `FUN_004371C7`** (`__thiscall`, 2× `BitBlt/SRCCOPY`
   via IAT `0x50D120`): blit screen DC → normalize selection rect
   (`CRect::NormalizeRect`, drag-offset adjust) → draw white selection frame +
   8 resize handles (`FUN_00449B08/00449B9C` frame/fill, `FUN_00437367` label).
   Sibling blitters: `FUN_0044A611/0044A201/00437FE4/00449901/004498A0`.

- **`FUN_0045B716` = locales path builder**: `Locales\<name>` join
  (used for `help.txt` + language packs; mirrors `Locales/` folder with
  per-language UI strings).
- **`FUN_0042F2CC` = help/about text loader**: resolves `\help.txt`
  (`FUN_0045B716`) → reads via shared `FUN_0043DF32` file pipeline →
  formats `"%s %s %s\n\n"` header (version line) for the About dialog.
  Called from the startup sequencer on first run.

## Dynamic DLLs (decompiled)

- **`FUN_004356C1` = DWM loader**: `LoadLibraryW("dwmapi.dll")` +
  `GetProcAddress(DwmIsCompositionEnabled/GetWindowAttribute/
  SetWindowAttribute)` — dynamic (not linked) for XP compat; Aero glass
  popup frames when composition is on. Siblings: `msftedit.dll`
  (RichEdit), `iphlpapi.dll` (proxy route lookup). (`mscoree.dll` string
  is CRT-only — `try_cor_exit_process` mixed-mode exit, not a .NET host.)
- **`FUN_00437D22` = glass frame measurer** (via lazy singleton
  `FUN_00435636`): if composition on → `DwmGetWindowAttribute(
  DWMWA_EXTENDED_FRAME_BOUNDS)` → else `GetWindowRect` minus borders
  (skipped when zoomed on Win7+) — correct popup rect under Aero.

## String compare core (decompiled)

- **`FUN_00401FC2` = wcscmp 3-state** (`__thiscall`, null-guarded): the
  comparison behind every class-name/menu/label check in the app
  (dozens of call sites). Distinct from `FUN_004207F3` (hash-chain
  equality-bool) — this one orders, that one tests.

## Process model (verified)

- **No child processes**: zero `CreateProcess*` imports — everything runs
  in-process (UI thread + worker threads + thread pool + BASS/curl callback
  threads). External interaction is only via `ShellExecute[Ex]` (open
  docs/URLs) and COM out-of-proc (SAPI). This is why the whole app reverses
  cleanly through one binary's worth of decompile.

## Single-instance guard (decompiled)

- **`FUN_00435175` = singleton check** (called from WinMain before COM init):
  unless `allow-multiple-instances` cmdline flag, `FindWindowW(
  "QTranslate_ApplicationWindow")` → if found, `PostMessageW(hWnd,
  WM_COMMAND, 0x8009)` (show-main-window) and exit. Second launch just
  focuses the running instance.
- **CLI flags** (parsed by `FUN_0043CA85` = cmdline-parse + options-map
  lookup `FUN_0043CF37`): `allow-multiple-instances`, `startup-show`,
  `startup-minimized` (refs in `FUN_00435175` singleton + `FUN_00418F81`
  startup placement).
- **`FUN_0045AA11` = service-slot init** (called twice from the sequencer,
  translate + dictionary slots): enumerate service dirs (`FUN_0045CE4F`) →
  per-service validate (`FUN_0045A77B`, drops bad via `FUN_0041E559`) →
  commit slot vector (`FUN_0045CC98`). This is what turns `Services/*/`
  folders into the runtime provider list at startup.
- **`FUN_0045A77B` = service-id validator**: linear scan of the slot vector
  for a duplicate id (`FUN_0045AFDD` element read), returns index or 0 —
  keeps `ServicesOrder` duplicate-free across reloads.
- **`FUN_0045A867` = language-pair validator**: same linear-search shape over
  the pair vector (`this+0x2C0` count, entries at `*(this+700)`), used by the
  sequencer to confirm saved `LanguagePairs` (`[[57,17],[17,57]]`) still
  resolve — else reset to defaults.
- **`FUN_00418F81` = startup sequencer**: init service slots
  (`FUN_0045CC98`), validate language-pair defaults (`FUN_0045A867`) →
  first-run (no `Options.json`): show setup wizard (`FUN_00419DA6`) →
  else honor `startup-show` / `startup-minimized` / saved window placements.
- **`FUN_00419DA6` = first-show/wizard**: creates Static control + app icon
  (`WM_SETICON 0x80`, icon id `0x84`) → virtual show/focus/restore sequence
  (`+0x10/+0x14/+0x18` vtable) with `IsIconic`-aware `ShowWindow`.

## Settings persistence (decompiled, verified)

- **`FUN_004561F0` = options saver**: resolves `%AppData%/QTranslate/Options.json`
  (`FUN_0045B3D7` path builder) → serializes live state key by key
  (`ActiveServices`, `ActiveDictionaryServices`, `WindowMainPlacement`,
  `WindowPopupPlacement`, … via `FUN_00440893` JSON writer). Sibling savers:
  `FUN_00418F81`/`FUN_0045869F` (history/exceptions variants for
  `History.json`, `DictionaryHistory.json`, `Exceptions.json`).
- **`FUN_004638D8` = history loader**: same `FUN_0045B3D7` path builder +
  `FUN_0043DF32` BOM-aware file reader as the service loader, then
  `FUN_0043F71A` JSON parse (`+0x18` accessor) — one shared
  read-file→parse-JSON pipeline for all four persistence files. Export side
  reuses the same JSON writer as the options saver; the Csv/Html/Json/Txt
  *export* formats are JS plugins (`Plugins/History/*.js`, ported to
  `qtranslate/history.py`).
- **`FUN_00462C03` = crash-report on next launch**: same path-builder +
  file-reader + JSON-parse pipeline reads `Exceptions.json` (minidump list
  written by the unhandled-exception filter during the *previous* run) →
  `FUN_00462A82` walks entries filtering `type == 2` (real crashes, skipping
  breadcrumbs) and forwards them → `DeleteFileW` consumes the file so each
  crash reports exactly once.
- `History.json` record layout (from a real entry): `[service,
  [[srcLangIdx, trLangIdx, text]], flag]` — e.g. `["Classify",
  [[1, 17, 57, "…"]], false]` with `LanguagePairs [[57,17],[17,57]]`
  (indices into the shared `SupportedLanguages` table: 1=auto, 17=en, 57=vi).
  `DictionaryHistory.json` absent on this machine (no offline lookups yet).
- File layout (from a real install, 20 sections): Application, Exceptions,
  Contents, Advanced, Appearance, Internet, HotKeys, OfflineDictionaries, Ocr,
  Update, DisabledServices, Proxy, DictionariesOrder, DisabledLanguages,
  DisabledDictionaries, Dictionary, LanguagePairs, General, ServicesOrder,
  AutoDetection. Ported to `qtranslate/config.py` (hotkey word decode matching
  `FUN_00405A17`, default `ServicesOrder = [1,5,12,13,11,26,28,30,31]`).

## Translate orchestrator (decompiled)

- **`FUN_00404A12` = central dispatch** (called by ReplaceSelection and all
  translate tasks): picks service by id (`FUN_0045CC50`) or default
  (`FUN_0045CEDE`), checks enabled flag → runs task executor
  (`FUN_0045F6C1`) → on success stores result; on empty result tries
  back-translation (`FUN_004606BA`) then language-detect retry
  (`FUN_00460354`) → error wrap (`FUN_004047D6`) → cleanup (`FUN_00404B7B`).
  This single function is the native equivalent of our Python
  `translate()` wrappers — service select → request → fallback chain.
- **`FUN_004047D6` = error-code mapper** (`__fastcall`): switch error
  3–0xF → string-resource id (`0xB0`–`0xCF`) via `FUN_00451D23` (2-tier:
  language table `FUN_0045242D`, fallback format `DAT_00529AF0`). Covers
  backtrans/detect/fetch failures (`0xC/0xD/0xE` seen in `FUN_004606BA`).
  Resolved messages (UTF-16 `.rdata`): `"…connection…No data returned
  (timeout while sending data)."`, `"No data returned."`,
  `"No data to translat[e]"` — the exact strings our Python ports surface
  as `[error]`/empty results.
- **`FUN_00460354` = detect-retry loop** (`__thiscall`): alternates
  `FUN_00460467` (detect request) + `FUN_00460580` (apply result) until
  non-empty (error 6 = all providers exhausted) — the `AlwaysDetectLanguage`
  engine behind auto-detect.
- **`FUN_004606BA` = back-translation runner** (`__thiscall`): swaps
  sl/tl (`param_1+8` ↔ `param_1+10`, lang-index range check `< 0x4A`),
  validates both via `FUN_0045FF70`, re-runs translate (`FUN_0045FDE8`).
  Error codes: `0xC/0xD/0xE` = rerun/validate/fetch failures.
- **Service picker = `FUN_0045CEDE` / `FUN_0045CC50`**: default = first id
  of the `ServicesOrder` vector (`FUN_0045AFDD` head read on
  `DAT_005495C0`); by-id = hash lookup (`FUN_0045DAF5` on `DAT_00549590`).
  Mirrored 1:1 by `qtranslate/config.py::services_order()`.
- **`FUN_0043A121` = re-run after service switch** (`__fastcall`,
  called from dispatcher): builds `TaskShowPopupWindow` (vftable +
  `DAT_0051DE64/68` params) + `PostMessageW(0x812C)` — re-translates with
  the newly selected service without re-capture.
- **`FUN_004661D1` = dispatch-get helper** (`__thiscall`, used by both
  validators): `IDispatchEx::GetDispID (+0x14, grfdex 0x400)` + invoke
  (`FUN_00466181`) — single choke point for all JS field reads.
- **`FUN_00420C91` = prime capacity table** (lookup in `DAT_0051C8E8`
  prime list by `FUN_004F4BD0` size hint, `0xFFFFFFFF` = use-raw) —
  backing all hash-table growth in the app.
- **`FUN_00420B9E` = hash rehash/shrink** (`__thiscall`): realloc bucket
  array + rechain all entries by recomputed `hash % newcap` — standard
  unordered-map maintenance behind the DISPID + option tables.
- **`FUN_00420CD6` = hash-table cleanup** (`__thiscall`, called from
  `FUN_0043E471`): freelist push + count decrement + shrink
  (`FUN_00420B9E`) + empty-table teardown — no-leak DISPID cache lifecycle.
- **`FUN_004207F3` = chain compare** (`__fastcall`): `wcscmp` 3-state
  returning equality-bool — hash-bucket collision resolution for the
  named-item + option tables.
- **`FUN_00420824` = DJB2 string hash** (`__fastcall`, `h*0x21 + c` over
  UTF-16): backs the named-item cache + option hash-maps. Verified in
  Python: `serviceTranslateRequest→0x943703A8`, `serviceHeader→0x6A645CBA`.
- **`FUN_0043E950` = named-item hash table** (`__thiscall`, fallback in
  `FUN_0043E471`): `FUN_00420824` string hash → bucket (`% capacity`) →
  chain compare (`FUN_004207F3`) — caches JS function DISPIDs so repeat
  `serviceTranslateRequest` calls skip `GetIDsOfNames`.
- **`FUN_0043BB64` = HRESULT error mapper** (`__thiscall`, in the
  method-call funnel): builds `"Called function: %s\n\n"` +
  `FormatMessageW` → `"0x%08X: %s"` (HRESULT→system text, `GetLastError`
  fallback) — surfaces JS engine failures as readable diagnostics.
- **`FUN_0043E51E` = 0-arg invoker** (`__thiscall`): same GetDispID +
  Invoke shape but through the child engine (`this+8`) — used for
  `serviceHeader`/`serviceHost` (no-arg metadata calls).
- **`FUN_00427AD4` = N-arg marshaller** (`__thiscall`): `GetDispID
  (+0x14)` + `Invoke (+0x18)` with packed DISPPARAMS (up to 4 VARIANTs) —
  how `serviceTranslateRequest(text, sl, tl)` crosses native→JS.
- **`FUN_0043B8CE`/`FUN_0043B942` = method-call pair** (`__thiscall`,
  the single funnel for all 9 `service*` invokes): engine-ready gate
  (`this+0x40 == 2`) → 0-arg `FUN_0043E51E` vs N-arg `FUN_00427AD4` →
  HRESULT error map (`FUN_0043BB64`); `FUN_0043B942` wraps with
  VARIANT-out (`VT_DISPATCH` check) + `VariantClear`.
- **`FUN_00466181` = invoke helper** (`__thiscall`): null-guards
  (`E_INVALIDARG/E_INVALIDPTR`) + `IDispatch::Invoke (+0x18,
  DISPATCH_PROPERTYGET)` — every JS property get funnels here.
- **`FUN_0046592D` = ResponseData validator** (called after every
  `*Response` invoke): dispatch-reads `translation`, `sourceLanguage`,
  `translationLanguage`, `data`, optional `nextRequestHandler` (chained
  multi-request services like Yandex chunking) — mirrors our Python
  `ResponseData` dataclass field-for-field.
- **`FUN_0046578F` = RequestData validator** (called after every
  `*Request` invoke): dispatch-reads 6 fields (`method`, `uri`
  [`DAT_0052D1C0`, verified bytes], `data`, `headers`, `codepage`,
  optional `responseHandler`) via `FUN_004661D1` — mirrors our Python
  `RequestData` dataclass field-for-field.
- **`FUN_004601AD`/`FUN_004601EC` = request context init/cleanup**
  (`__fastcall` pair): inits 4 CString fields (`+4/+8/+0xC/+0x14`),
  releases in reverse — RAII around every fetch (no leak path even on
  error 2/4/5/10/11).
- **`FUN_0045C2F4` = network-alive gate**: `IsNetworkAlive` (SensApi,
  the `SensApi.dll` import) — every fetch path checks connectivity first;
  offline → error 4 without touching curl. (Matches the offline-first
  design: SAPI TTS + XDXF dicts keep working with no network.)
- **`FUN_00460006` = fetch dispatcher** (`__thiscall`): invokes
  `serviceHost(...)` (3 args) for the base URL, then routes to GET/POST
  wrappers — every translate/detect/listen/dictionary fetch funnels here
  after its RequestData is built.
- **`FUN_0045FF70` = language validator** (`__thiscall`): hash lookup
  (`FUN_00460E15`) on the service's language table (`this+0x54`) — gates
  every translate/listen/detect call (error 10 = unsupported pair).
- **`FUN_0046027C` = listen-fetch worker** (`__thiscall`): lang validate
  (`FUN_0045FF70`) → `serviceListenRequest` invoke (`FUN_0046606C`) →
  `FUN_00460006` fetch → GET (`FUN_0045BBAE`) vs POST (`FUN_0045BF13`) by
  mode (`local_1C` 1/2). Error codes 2/4/5/10/11 mirror the translate path.
- **`FUN_004614BB` = mp3 fetcher** (`__fastcall`, STA COM init inside):
  service caps gate (`LISTEN` bit at `+0x10`, fallback default service
  `FUN_0045CF04`) → task executor (`FUN_0045F6C1`) → `FUN_0046027C`
  (listen-request fetch → mp3 bytes into `param_1+0x20`). The online half
  of `TaskListenText` before `FUN_00461642` plays it.
- **`FUN_004613FA` = playback wrapper** (`__fastcall`, called from the
  end-sync callback): free old → `FUN_004614BB` fetch-next (1 = drained,
  0 = has chunk, else error code) → `FUN_00461642` play → on failure
  reset + `PostMessageW(0x8145)` error to main window. Chained playback
  across multi-chunk TTS responses.
- **`FUN_0046161C` = TTS queue reset** (`__fastcall`, called from the
  toggle guard): clears playing flag + releases each queued item
  (`+8` dtor via `FUN_004024F2` vector walk) — drains pending speech
  before a fresh Listen.
- **`FUN_004614A7`/`FUN_00461471` = TTS toggle guard** (dispatcher listen
  branch): if already playing (`DAT_0054961C`) → `FUN_00461691` free stream
  + `FUN_0046161C` reset state — pressing Listen twice stops instead of
  overlapping. Mirrored in our `player.play_mp3_bytes` finally-block.
- **`FUN_00405553` = TaskListenText ctor** (`__thiscall`, called from
  dispatcher listen branch): sets `TaskListenText::vftable` + fields
  (service, text, sl/tl, slow flag, extra) — the task object later run by
  `FUN_0046606C` (listen invoker) → mp3 fetch → `FUN_00461642` BASS play.
- **`FUN_0045CDBA` = service switcher** (dispatcher service-select branch):
  id lookup (`FUN_0045CC50`) → capability gate (`TRANSLATE 1` /
  `DICTIONARY 8` at `+0x10`) → move-to-front (`FUN_0041E559`) → notify
  `ServicesFactoryObserver` list (`DAT_00549584`). Click-to-switch on
  popup service names.

## Replace-selection path (decompiled)

- **`FUN_0043BE56` = clipboard writer** (`__fastcall`): open-with-retry
  (`FUN_0043BE07`) → `EmptyClipboard` → `SetClipboardData(CF_UNICODETEXT)`
  (`0xD`, via IAT `0x50D4AC`) → `CloseClipboard`. 7 callers incl.
  `FUN_0043C02B`, `FUN_00405142`, `FUN_00429813`.
- **`FUN_004056CE` = replace-selection task** (`TaskReplaceSelection`):
  read clipboard (`FUN_0043BEB2`) → translate (`FUN_00404A12`) → write
  translation back (`FUN_0043BE56`) — then the capture synth (`FUN_0043BD5C`
  with `0x56` 'V') pastes over the selection.

## Exception-list window picker (decompiled)

- **`FUN_0040E891` = window picker tracker** (`__thiscall`, Spy++-style):
  on each tick, `GetCursorPos` → `WindowFromPoint` → if changed, toggle
  highlight on old/new window (`FUN_0040E961`) → read class name
  (`FUN_00450C50`) → forward class+app to parent via `SendMessageW(0)`.
  This is the "pick a window" tool behind `PageExceptions` ("drag to add
  an app/class to the blocklist").
- **`FUN_0040E961` = highlight toggle**: `GetWindowDC` + `SetROP2(R2_NOTXORPEN)`
  + 3px pen `Rectangle` — XOR draw means calling it twice on the same window
  erases the highlight (why the tracker calls it on both old and new).
- **`FUN_00403506` = app-name resolver**: `GetWindowThreadProcessId` →
  `OpenProcess(PROCESS_QUERY_INFORMATION)` → `FUN_004036CE`
  (`QueryFullProcessImageNameW`) → `PathFindFileNameW` basename — exactly
  the `exe_name` our Python `exclusions.py::_fg_class_and_exe()` computes.

## Hotkey task dispatcher (decompiled)

- **`FUN_0043999B` = hotkey→task switch** (`__thiscall`, on `WM_HOTKEY`
  `param_3` = hotkey id): compares against registered id slots
  (`this+0x208/0x234/0x260/0x2B8/0x2E4…`): same-id → destroy (toggle);
  dictionary-id → build dict task (`FUN_00414E72`) + `PostMessageW(0x812C)`;
  replace-id → destroy + `Sleep(100)` + `TaskReplaceSelection::vftable` +
  post; copy-id → clipboard write (`FUN_0043BE56`). Service-select ids
  `0x8038–0x804A` → `FUN_0045CDBA` service switch + `FUN_0043A121` re-run;
  listen-id → `FUN_00405553` TTS task + post. This is the central fan-out
  from every registered hotkey to its `tasks::` object.

## Clipboard viewer chain (decompiled)

- **`FUN_0043EBE0` = viewer setup**: registers `QTranslateClipboardWindowClass`
  with WndProc `FUN_0043EBA1`, creates a message-only window
  (`HWND_MESSAGE = 0xFFFFFFFD`) stored at `DAT_005491B0` — the classic
  clipboard-viewer chain endpoint (`SetClipboardViewer` era pattern) used by
  the clipboard-monitor mode alongside `GetClipboardSequenceNumber` polling.
- **`FUN_0043EBA1` = viewer WndProc**: filters `WM_DESTROY (2)`,
  `0x305/0x306/0x308/0x30D` (IME/clipboard-chain messages), everything else
  → `DefWindowProcW`. No IMM32 imports exist — IME composition is forwarded,
  never processed (correct: capture reads committed text only).

## History context menu (decompiled)

- **`FUN_00404055` = menu loader** (`__thiscall`): `LoadMenuW(hInstance,
  0xB3)` + `GetSubMenu(0)`, cached at `this+8` — only the base menu comes
  from `.rsrc`; item labels live as UTF-16 in `.rdata` (e.g. `Copy
  translation` at `0x11BF98`, `Spell checking` at `0x11E4E4`) and are
  appended/patched at runtime by `FUN_00451F6D` + `FUN_004040BA`, shown by
  `TrackPopupMenu`. Full `.rdata` UTF-16 scan: **1088 UI/options strings**
  (161 menu/option-related incl. all 18 `HotKey*` names, `ActiveServices`,
  `DictionariesOrder`, `LanguagePairs` keys) — the complete options-key
  vocabulary 1:1 with `Options.json` sections. Cross-check: **123/124**
  live `Options.json` keys found verbatim in the binary (only `Ocr`
  section header missing — likely concatenated at runtime); our
  `config.py` covers all of them.
- **`FUN_004287B6` = history-item menu** (`__thiscall`, `TrackPopupMenu`
  via IAT `0x50D63C`): builds Open (`0x8028`) / Copy text (`0x806E`) /
  Copy translation (`0x8026`) / Delete (`0x8027`) / Listen to text
  (`0x8099`), pruning Copy-text+Delete vs Copy-translation by `param_2`
  (source vs translation row). 9 sibling menu builders share the
  `FUN_00451F6D`-string + `FUN_004040BA`-append + `TrackPopupMenu` pattern
  (`FUN_004041D7`, `00408FDB`, `0040BE65`, `0042DC18`, `0042DF28`, …).
- **Options menu = `FUN_0042DF28`** (main-window menu, IDs verified):
  Spell checking `0x802B`, Instant translation `0x802C`, Back translation
  `0x8034` (Ctrl+B), Extended `0x802D`, Clear-on-DnD `0x8063`, Auto-cleanup
  `0x8077`, Save-on-exit `0x8075`, Show panes `0x8071/0x8064/0x8065`
  (Ctrl+F1/F2/F3), Minimize-to-tray `0x806F/0x8070`. Sibling
  `FUN_0042DC18`: Reset (`Shift+Esc`), Edit `0x8052`, Always-detect `0x808E`.

## Capture exclusions (from real Options.json)

- Enforcement = `FUN_004631DE` (called from hotkey setup `FUN_00418E1A`):
  `GetForegroundWindow` → class name (`FUN_00450C50`, skipping own
  `QTranslate_HotKeyControl`) → match each `Exceptions.Disabled` entry via
  `FUN_004470B7` = `__wcsicmp` case-insensitive exact match (no wildcards;
  empty side matches anything, so `["", "SysListView32"]` = that class in
  any app) → capture suppressed on hit.
- `Exceptions` section = per-app / per-window-class blocklist consulted before
  capture: `{Disabled: [["", "SysListView32"], ["", "SysTreeView32"],
  ["", "ListBox"], ["", "ScrollBar"], ["", "ComboBox"],
  ["", "msctls_hotkey32"], ["", "ConsoleWindowClass"], ["mstsc.exe", ""]],
  Enabled: [], DisabledMode: true}` — mouse-mode (`FUN_00404901`) and
  clipboard capture skip these classes/apps (avoids stealing listbox/console
  content and remote-desktop keystrokes).

## Owner-draw text (decompiled)

- **`FUN_00449707` = shadow text renderer** (`__fastcall`, `DrawTextW` via
  IAT `0x50D6AC`): select font → transparent bk → optional shadow pass
  (offset rect +1,+1 in shadow color) → main pass → restore DC. Sibling
  callers: `FUN_004497C5`, `00407B18`, `0042B485` (×2), `00439F08`,
  `0044D282`; low-level blit via `ExtTextOutW` (`FUN_00449B9C`, IAT
  `0x50D0E4`). Used by ScreenCapture labels, tray balloon text, and
  keyboard-window keys.
- **`FUN_00439F08` = dialog font setup** (`__thiscall`): builds `LOGFONTW`
  (`MS Shell Dlg 2`, weight 700/Bold, `lfHeight = -MulDiv(pt*20,
  LOGPIXELSY, 72)` DPI-scaled) — popup/dialog font creation path.

## Options page init (decompiled)

- **`FUN_0040DD3B` = options-page binder**: `CheckDlgButton` for 5 flag
  checkboxes (`0x463/0x486–0x489` from `DAT_00549488`…`DAT_00549493`) +
  combobox fill (`CB_ADDSTRING 0x143`, 13 entries from format `DAT_0051D32C`,
  select `DAT_00549494` or default 5) + 3× RichEdit subclass
  (`FUN_004030AE`). The live binding behind `OptionsWindow`/`Page*` dialogs.
- **`FUN_00434577` = dialog change tracker** (`__thiscall`): filters
  `WM_COMMAND` notification codes by control class (`Edit`,
  `HotKeyControl`, `Button` id `0x4A6`, `ComboBox[Ex32]`) → enables the
  Apply button (`0x419`) on any real edit — standard "dirty" tracking
  for property-sheet-style options pages.
- **`FUN_0043471D` = list-change tracker** (sibling): `WM_NOTIFY`
  (`lParam[2] == -0x65`) from `SysListView32` with state-change bits
  (`0x3000` = check/select) → same Apply-enable — covers the
  services/dictionaries reorder lists.
- **`FUN_0040E542` = conditional control**: `CB_GETCOUNT (0x147)` on combo
  `0x493` → `ShowWindow(0x4AA, SHOW/HIDE)` — dependent-option visibility
  (e.g. proxy fields only when manual proxy selected).

## Dictionary cross-links (decompiled)

- **`FUN_00465574` = qtdp: link check**: prefix-match `qtdp:`
  (`FUN_00454482` starts-with) — internal dictionary cross-references
  (from XDXF `<kref>` and online-dict HTML) route back into lookup instead
  of the browser. Siblings `FUN_004655A9` (resolve).
- **`FUN_004266C6` = RichEdit link-click handler** (`__thiscall`, in the
  subclassed WndProc chain): `qtdp:` prefix check → strip prefix
  (`FUN_0042A10A` substring) → internal re-lookup (`FUN_00426966`) with
  history sync (`this+0x19C = this+0x18C`). Non-qtdp links fall through to
  `ShellExecute` browser open.
- **`FUN_004084C9` = display teardown** (`__fastcall`, 6 callers): flag 2
  → unsubclass (`+0x4C`), flag 4 → unhighlight (`+0x58`,
  `0xFF676986`), flag 8 → HKM clear (`0x445`) — symmetric undo of
  `FUN_00408456` builder, called on every refresh/rebuild path.
- **`FUN_00409EC0` = test-box refresh** (`__thiscall`): rebuild display
  (`FUN_00408456`) → show-layout (`FUN_00408ADE`) → `HKM_SETHOTKEY
  (0x447)` with a zeroed key struct + flag — re-arms the capture box
  after each language/service change.
- **`FUN_00408924` = language-select handler** (`__thiscall`): lang index
  validate (`< 0x4A`) → resolve (`FUN_004088A9`) → set (`+0x20`) →
  sub-layout (`+0x48/+0x54`) → hotkey-test refresh (`FUN_00409EC0`) +
  show-layout (`FUN_00408ADE`). Service ids 5/`0x1A`/`0x2A`/`0x38`/`0x3B`
  take a flag variant.
- **`FUN_00427D21` = raw applier** (`__thiscall`): bare
  `SetWindowPlacement`, no validation — internal fast path when the blob
  is already trusted (post-startup restores).
- **`FUN_00450B5C`/`FUN_00450B4D` = topmost helpers**: set via
  `SetWindowPos(hWndInsertAfter)` (`SWP_NOMOVE|NOSIZE|NOACTIVATE` =
  `0x23`); read via `GetWindowLongW(GWL_EXSTYLE)` bit test — backs the
  popup's always-on-top flag persisted in placement `flags & 0x10`.
- **`FUN_00422D8B` = placement applier** (`__thiscall`,
  `SetWindowPlacement` via IAT `0x50D514`): validates `length == 0x2C`,
  honors DPI flag (`FUN_00450B5C`), maximized shortcut (`showCmd 3`),
  fallback default-show (`FUN_00402E7F`). Twin of writer `FUN_00422DDD`
  — closes the persistence round-trip.
- **`FUN_00422DDD` = placement writer** (`__thiscall`):
  `GetWindowPlacement` + iconic→`SW_SHOW` fix + DPI flag
  (`FUN_00450B4D`) — produces the hex blobs stored as
  `WindowMainPlacement`/`WindowPopupPlacement`/… in Options.json.
- **`FUN_0042EC6C` = UI state snapshotter** (`__fastcall`): saves window
  placement (`FUN_00422DDD` + `DAT_005492D0`) + service/lang selections
  (`+0x440/+0x46C` vtable) + head-lines of 2–3 edits (`FUN_004099F3` into
  `DAT_00549424/28/2C`) — restores exact UI on next show (the
  `Window*Placement` persistence behind Options.json).
- **`FUN_00408A83` = head-lines reader** (`__thiscall`): resolve count
  (`FUN_00408AA2`) → `FUN_004099F3(0, count)` first-N-lines read — preview
  text for tooltips and history excerpts.
- **`FUN_00409ABF` = combo dropdown reader** (`__fastcall`): count
  (`0x434`), show-dropdown (`0xBB`), limit (`0xC1`) → line reads
  (`FUN_004099F3`) walking the dropdown items — feeds language/service
  combo boxes in options pages.
- **`FUN_00408D01` = select-and-open** (`__thiscall`): `0x20` → focus;
  `0x202` (LBUTTONUP) → line read (`FUN_004099F3`) → open dispatcher
  (`FUN_00450B17`) — click-to-open link/text behavior in result panes.
- **`FUN_00408B4B` = full-text reader** (`__thiscall`): `EM_GETLINECOUNT
  (0x434)` → `FUN_004099F3` range read — grabs the whole edit content for
  copy-translation and template expansion. Siblings `FUN_00408D01/
  00409ABF/00408A83/0042EC6C` (8 line-getter call sites total).
- **`FUN_004099F3` = RichEdit line getter** (`__thiscall`):
  `EM_GETLINE (1099)` range read into a fresh buffer — feeds the template
  expander and the copy-translation path with source lines.
- **`FUN_0042D198` = bracket-template expander** (`__fastcall`): splits
  text on `\r`, finds `[...]` spans (`FUN_0041BBB9` bracket match) →
  resolves each id (`FUN_004088ED`) → applies (`+0x54`) — expands
  hotkey/service references inside help/about text. (`FUN_0041BBB9` is
  just bounds-checked `CString::operator[]`, not a parser;
  `FUN_004333AC` is the `wcsspn/wcscspn` line tokenizer underneath.)
- **`FUN_004088ED` = display-text resolver** (`__thiscall`):
  `FUN_004088A9` resolve → show (`+4`) → get text (`+0x48`) → hide (`+8`)
  — reads any id's display string without leaving UI visible.
- **`FUN_004088A9` = shared id resolver** (`__thiscall`): `-1` args
  resolve via `FUN_00408AA2` (hotkey word lookup) → vtable `+0x60`
  dispatch on the resolved pair. Central fan-in for item activation,
  layout, and display paths.
- **`FUN_00408ADE` = show-layout-hide helper** (`__thiscall`):
  `FUN_004088A9` resolve → vtable show (`+4`) → layout (`+0x80`) → hide
  (`+8`). Shared tail for history-item activation and hotkey-display
  refresh paths.
- **`FUN_00409305` = history item action** (`__thiscall`): resolve
  (`FUN_004088A9`) → vtable show (`+4`) → set item text (`+0x20` via
  `FUN_00421DF6` convert + `SysFreeString`) → hotkey display refresh
  (`FUN_00408456`) → layout (`FUN_00408ADE`) → hide (`+8`). Click/keyboard
  activation of a history entry.
- **`FUN_004085CD` = history-list WndProc** (`__thiscall`): `WM_KEYDOWN
  (0x100)` → `FUN_00408DB1`; mouse range `0x201–0x209` →
  `FUN_00409685`; timer `0x113/0x114` → hide (`FUN_0040785C`); custom
  `0x84BA` → `FUN_00409305` item action + hide. Full input map of the
  history pane.
- **`FUN_0041223C`/`FUN_0040785C` = history hide pair**: IsWindow-guarded
  flag reset + `ShowWindow(SW_HIDE)` — collapses the history pane (used by
  re-lookup to clear stale results before new content arrives).
- **`FUN_00426966` = async re-lookup dispatch**: `FUN_00414E72` builds the
  dictionary task object → `PostMessageW(hwnd, 0x812C)` queues it to the
  window's message loop (custom `WM_APP`-range message for dictionary work,
  keeping link-clicks non-blocking).
- **`FUN_004106AC` = work submitter** (`__thiscall`, `QueueUserWorkItem`
  via IAT `0x50D36C`): message `0x4A7` → pool runs `FUN_00410AB8` (async
  translate/dict worker); `0x4A6` → sync `SendMessageW(0x80C8)` UI update.
  Second async path beside the `0x812C` PostMessage queue.
- **`FUN_00461F5C` = background dir setup** (runs in pool worker):
  walks `DAT_00549630` path array (`FUN_00462220` resolve +
  `FUN_0046236C` build) → `GetFileAttributesW`, `CreateDirectoryW` if
  missing (cache/history/data dirs prepared off the UI thread).
- **`FUN_00410AB8` = pool worker proc**: `PostMessageW(0x8064, 0)` start →
  `FUN_00461F5C` background job → `PostMessageW(0x8064, 1, status)` done
  (IsWindow-guarded both ends).
- **`FUN_0043AC92` = async task executor** (WndProc `0x812C` case in
  `FUN_00415EED`, alongside `0x8064/0x8069` view toggles, `0x8131` state
  query, `0x8136` refresh, `0x808C`): if worker busy → run inline (vtable
  call on task); else queue (`this+0xC`) + `SetEvent(this+0x10)` wakes the
  worker thread. Classic producer-consumer for all translate/dict/listen
  tasks.

## Double-modifier hotkey (decompiled)

- **`FUN_0041786B` = double-press detector** (`__thiscall`): `GetGUIThreadInfo`
  focus check (skips own `HotKeyControl`) → modifier bits from `param_3`
  (`0x10` Shift → 4, `0x11` Ctrl → 2, `0x12` Alt → 1, `0x5B/0x5C` Win → 8) →
  `FUN_00417DCE` match against `DAT_00549484` (Double-Ctrl pattern). This is
  the "Double Ctrl => Show main window" trigger from the hotkey docs.
- **`FUN_00417DCE` = press-pattern matcher**: modifier compare (`& 0xF`)
  + `GetTickCount` vs last-press (`this+0x183C`) within `GetDoubleClickTime`
  = double-press detected, timestamp reset. Single-press = plain equality.

## Theme-aware control dispatcher (decompiled)

- **`FUN_0040767C` = themed control proc** (`__thiscall`, theme store
  `DAT_005491E8`): dispatches by message (`1` = measure `FUN_0040793A`,
  `2` = reset, `5` = update `FUN_00407A59`, `0x14` = paint `FUN_004079DA`,
  owner `FUN_00407B18` sibling) — every owner-drawn button/list in popups
  and dialogs paints through here with the active theme palette.
- **`FUN_00407A59` = list layout update** (`__fastcall`): `GetClientRect` →
  `InflateRect(-border)` → `FUN_00421E8B` child reposition — keeps list
  content inside the themed border on resize.
- **`FUN_0040793A` = owner-draw ListBox setup** (`__fastcall`): creates
  `ListBox` with `LBS_OWNERDRAWFIXED|HASSTRINGS|SORT (0x50200050)`,
  `WM_SETFONT (0x30)` + update (`FUN_00407A59`) — history/suggestion lists.
- **`FUN_004079DA` = themed fill** (`__thiscall`): `GetClientRect` →
  brightness-adjusted theme color (`FUN_0044A163`, ±10 via `FUN_0044C5A1`
  direction flag) → `FUN_00449B08` rect frame. Single call behind all
  themed backgrounds.
- **`FUN_00449B08` = rect frame** (`__fastcall`): `CreateSolidBrush` →
  `FrameRect` → `DeleteObject` — draws themed borders (selection frames,
  popup outlines), not solid fills.
- **`FUN_00449B9C` = solid fill** (`__fastcall`): `SetBkColor` +
  `ExtTextOutW(OPAQUE)` + restore — the actual background fill behind
  themed controls and capture overlays.
- **`FUN_00449B32` = handle painter** (`__fastcall`): 1px black pen +
  null brush (`GetStockObject(5)`) + `Rectangle` — hollow resize handles
  on the ScreenCapture selection (8 points).
- **`FUN_0044C5A1` = luma direction flag**: `(B*0x4D + G*0x97 + R*0x1C) <
  0xE400` (ITU-R BT.601 luma weights) → dark bg lightens (+10), light bg
  darkens (−10). `FUN_0044A163` does the HLS shift; ported to
  `theme.adjust_brightness` (colorsys equivalent, live-tested).

## GDI+ lifecycle (decompiled)

- **`FUN_0044A3D8` = DPI scaler** (called from WinMain): `GetDeviceCaps(
  LOGPIXELSX)` cached once (`DAT_00544050`, default 96), ratio stored at
  `DAT_00544058` — drives all `MulDiv` font/layout scaling. No
  `SetProcessDpiAwareness`/`GetDpiForWindow` imports — matches the manifest
  (`<dpiAware>true</dpiAware>` = **v1 system-DPI-aware**, not per-monitor):
  Windows gives the real system DPI once at startup via `GetDeviceCaps`,
  no bitmap-scaling, but no live update on monitor change. Manifest also
  sets `requestedExecutionLevel level="asInvoker"` (no admin required).
- **`FUN_0044AAA1` = GDI+ init** (called from startup + `FUN_004010D5` CRT
  init): `GdiplusStartup(&token, version=1-input)` (IAT `0x50D844`), token
  at `DAT_005491E4`. Bitmap loaders (`GdipCreateBitmapFromFile[HBITMAP]`,
  `GdipCreateHICONFromBitmap`) serve tray/service icons.

## GDI+ themed paint (decompiled)

- **`FUN_0040647F`/`FUN_004064DE` = GDI+ fill wrappers** (`__thiscall`,
  `GdipCreateFromHDC` IAT `0x50D7E0`, `GdipFillRectangle` IAT `0x50D7EC`):
  gradient/solid brush fills for themed buttons and popup backgrounds
  (brushes from theme palettes via `GdipCreateSolidFill`/
  `GdipCreateLineBrushFromRect`).

## Options dialog refresh (decompiled)

- **`FUN_0042CF8E` = spell request runner** (`__thiscall`): ctor
  (`FUN_0042C844`) + optional ref (`FUN_004B3DE2`) — fire-and-forget
  suggestion fetch feeding `SuggestionsListCtrl`.
- **`FUN_0042C844` = SpellProvider ctor** (`__fastcall`): sets
  `common::SpellProvider::vftable` → init (`FUN_0043AFDB`/`FUN_0043AEEA`) →
  clears suggestion list (`FUN_00408010`) → base `Runnable::vftable`. Sibling
  `FUN_0042C882` mirrors for the Yandex variant.
- **`FUN_00408010` = services-list clear** (`__fastcall`): frees each
  entry (`+0xC` payload + object) and zeroes the vector — runs before every
  rebuild of the Services page list (after slot re-scan).
- **`FUN_00405B1A`/`FUN_00405AD9` = OS version gate** (cached once,
  thread-safe): `GetVersionExW` → `FUN_00405B8E` maps
  major/minor/build → internal id (`DAT_005497D8`); callers branch on
  `< 7`-style checks (`0x500/0x600` thresholds = Vista/7 feature gates for
  glass, DWM, new hotkey APIs).
- **`FUN_00405B8E` = version→id map**: 5.x→1/2 (2000/XP), 6.0→3 (Vista),
  6.1→4 (7), 6.2→5 (8), else 6 (8.1+); 10.x build-gated → 7/8/9/10
  (10578/14393/15063 cutoffs). XP→11 compat spine of the whole app.
- **`FUN_004097A9` = options-page show** (`__fastcall`): dirty →
  refresh tick (`FUN_00409CC8`); clean → rebuild display
  (`FUN_00408456`) + per-item resolve/show (`FUN_004088ED`, version-gated
  `0x500/0x600` via `FUN_00405AD9`). Entry for Hotkeys/Services pages.
- **`FUN_00409CC8` = dialog refresh tick** (`__fastcall`): state check
  (`FUN_0043AF94`) → content refresh (`FUN_00409D1C` + `FUN_00408010`) →
  1s `SetTimer` re-arm. Live preview behind service list / hotkey test
  buttons in `OptionsWindow`.
- **`FUN_00408456` = HotKeyCtrl display builder** (`__thiscall`): subclass
  wiring + `HKM_* (0x43B/0x445)` hotkey set/get + highlight
  (`0xFF676985`) on flag 4 + dropdown (`+0x48`) on flag 2 — the
  "press keys" capture box (`QTranslate_HotKeyControl` class).
- **`FUN_0040AC61` = double-press timer re-arm**: `SetTimer(1,
  GetDoubleClickTime)` + flag — sibling of the capture proc, rearms the
  second-press window after each key event.
- **`FUN_0040ABC3` = hotkey word builder**: mods from live `GetKeyState`
  (Ctrl=2, Shift=4, Alt=1, Win=8, current key counts as held) + vk; bare
  modifier press → vk=0; packs `(mods << 8) | vk` — byte-exact with our
  Python `config.decode_hotkey()`.
- **`FUN_0040AA88` = key-capture proc** (`__thiscall`, `HotKeyControl`
  WndProc): ignores bare navigation keys (Del/BS/Enter/Esc with no
  modifiers) → `FUN_0040ABC3` builds the hotkey word → double-press arm via
  `GetDoubleClickTime` timer with bit-15 `0x8000` "second press" flag
  (mirrors `FUN_00417DCE` matching).
- **`FUN_0040AA48` = hotkey display refresh** (`__fastcall`): format word
  (`FUN_00403B48`) → `SetWindowTextW` → `EM_SETSEL (0xB1)` select-all —
  updates the capture box after each key event.
- **`FUN_00408AA2` = hotkey resolver** (`__thiscall`): posts `0x45F`
  (HKM_SETHOTKEY-family) with the hotkey word struct — feeds both the
  display builder and the test runner.
- **`FUN_00409D1C` = hotkey test runner**: resolve hotkey (`FUN_00408AA2`)
  → build display string (`FUN_00408456`) → vtable show (`+4`), live test
  (`+0xEC`), hide (`+8`) — the "press keys to test" box in Hotkeys options.

## Suggestions list paint (decompiled)

- **`FUN_00465610` = language field resolver** (`__fastcall`, used by
  suggestions paint): record `[?, +4 default, +8, +0xC]` — mode 1 → `+8`
  else `+0xC`, fallback `+4`, null → 0. Picks the display language string
  per UI mode.
- **`FUN_0046563C` = service record lookup**: linear scan of 29 × `0x10`
  records at `DAT_005240D0` by service id — backs suggestions paint,
  menus, and the executor's display names. Dumped ids:
  `5,9,14,15,16,17,18,42,21,19,23,24,26,27,28,31,36,37,43,44,45,46,48,49,
  50,52,54,55,56` (covers all ported `SERVICE_ID`s). Google id=1 is **not**
  in the exe at all — ids come from each `Service.js`'s own
  `serviceHeader(id, …)` return at runtime (verified: no `Google Translate`
  string in the binary); native only stores what JS reports.
- **`FUN_0042B485` = suggestions painter** (`__thiscall`, `DrawTextW` ×2):
  theme fill (`FUN_00449B9C`) → `CB_GETCOUNT (0x146)`; empty →
  `"Selected languages (in options) are not implemented."`; else per-item
  draw via service name (`FUN_0046563C`) + language (`FUN_00465610`) +
  theme colors (`FUN_0044C4CA`).

## Font enumeration (decompiled)

- **`FUN_0044C645` = font enumerator** (`__fastcall`,
  `EnumFontFamiliesExW` via IAT `0x50D134`, callback `FUN_0044C636`):
  fills the font dropdown in Appearance options. Callers at
  `FUN_0040A037/0040A89C` (dialog init paths).

## MainWindow WndProc (decompiled)

- **`FUN_00450A0E` = file opener** (`__fastcall`): full
  `SHELLEXECUTEINFOW` (`fMask 0x900400`, verb default `open`, `nShow 1`)
  → `ShellExecuteExW` — opens local docs/help/history exports with params.
- **`FUN_00450AC2` = URL opener** (`__fastcall`): `ShellExecuteW("open",
  "rundll32.exe", "url.dll,FileProtocolHandler <url>")` — legacy-compatible
  browser launch (works back to WinXP era, no default-browser registry walk).
- **`FUN_00450B17` = open dispatcher** (`__fastcall`): existing local file
  → `FUN_00450A0E` (shell-open document) else → `FUN_00450AC2` (URL →
  default browser). Shared by `serviceLink` opens, About links, and help
  file display.
- **`FUN_0043DC23` = capacity init** (`__fastcall`, shared by registry +
  executor inits): capacities from `FUN_004F4BD0` (floor `0x11`) into
  `+0x18/+0x1C` — scales hash/vector sizes to the machine.
- **`FUN_0045ABD2` = registry init** (called once from the singleton):
  zeroed map + same tuning floats as the executor (`0x3F400000/0x3E800000/
  0x40100000`) + `FUN_0043DC23` init — shared defaults for provider timing.
- **`FUN_0045A31D` = autostart setter** (`HKCU\...\Run\QTranslate` =
  exe-path + `startup-minimized`; `param_1==0` → `RegDeleteValueW`
  removes it). `FUN_0045A431` is the checker sibling.
- **`FUN_0045A5B6` = install-path resolver** (cached `DAT_00544BD1`):
  reads `UninstallString` from both registry views (`...\Uninstall\
  QTranslate` + `Wow6432Node\...`) → derives the install dir (for
  `Services/`, `Locales/`, `Themes/` resolution regardless of CWD).
- **`FUN_0043D23A` = registry enumerator** (called once from the
  singleton guard): `RegEnumKeyExW` walk + `RegCloseKey` — discovers
  installed components (services/languages registered under the app key)
  supplementing the `Services/` dir scan.
- **`FUN_0045AB74` = service-map singleton** (thread-safe once:
  `FUN_0045ABD2` init + `_atexit` cleanup + lazy `DAT_00549834` flag) —
  the global provider registry all lookups share.
- **`FUN_0041FC4A` = shared hash lookup** (`__thiscall`, used by link
  lookup + named-item paths): DJB2 (`FUN_00420824`) → bucket → chain
  (`FUN_004207F3`, hash field at `+5`, next at `+4`) — the generic map
  behind service/link/option tables.
- **`FUN_0045AC41` = link service lookup** (`__thiscall`, used by the
  `0x812C`-adjacent link path): hash lookup (`FUN_0041FC4A`) for the
  clicked service → fallback default — resolves which provider owns a
  clicked `qtdp:`/menu link before dispatch.
- **`FUN_00401675` = link-click notify** (`NM_CLICK -2` / `NM_DBLCLK -4`
  on link controls `0x3ED/0x3F7`): opens `quest-app.appspot.com` (or
  `/download`) via `FUN_00450B17` ShellExecute wrapper — About-dialog
  homepage links.
- **`FUN_00411DEB` = MainWindow proc** (`__thiscall`): `WM_CREATE (0x110)` →
  full init (`FUN_00401530`); `WM_DESTROY (2)` → teardown (kill timer,
  unregister pretranslate, detach); `WM_COMMAND (0x111)` → button/menu
  dispatch; `WM_NOTIFY (0x4E)` → list/tree events (`FUN_00401675`);
  `WM_MOUSEWHEEL (0x20A)` scroll. Sibling popup procs share the shape.

## Popup positioning (decompiled)

- **`FUN_004072AA` = cursor-follow clamp** (`__thiscall`):
  `MonitorFromPoint` + `GetMonitorInfoW` work area → clamps the popup rect
  on all 4 sides (in/out-place adjust of `*param_1/*param_2`) — keeps
  cursor-following popups fully on-screen across monitors.
- **`FUN_00402DE9` = rect screen-to-client** (`__thiscall`): dual
  `ScreenToClient` on both rect corners (guarded second call).
- **`FUN_00434502` = dialog splitter layout** (`__thiscall`): measures
  client + toolbar child (`0x410` via `FUN_00402DE9` screen-to-client) →
  `MoveWindow` content pane (right+5, width−10) — splitter between toolbar
  and content in options dialogs.
- **`FUN_00434025` = dialog launcher** (`__fastcall`): disables Apply
  (`0x419`) → saved placement? custom pos (`FUN_004072AA`) : default
  (`FUN_00402E7F`) → thunk allocs → `CreateDialogParamW(0xAB)` modeless.
  Template for options-page dialogs.
- **`FUN_00402E7F` = popup positioner** (`__fastcall`):
  parent-or-owner anchor → `MonitorFromWindow` + `GetMonitorInfoW` work
  area → clamp → `SetWindowPos(..., SWP_NOMOVE/-SIZE flags 0x15)`.
  Multi-monitor-aware centering behind every popup show (complements the
  `FUN_0040C393` topmost+content setter).

## Icon compositor (decompiled)

- **`FUN_0044A611`/`FUN_0044A5E4` = blit + destroy** (`FUN_0044A569`
  wrapper): `BitBlt(SRCCOPY)` memDC→screen, then restore old bitmap +
  `DeleteObject` + `DeleteDC`. Completes the RAII double-buffer with
  `FUN_0044A581` — zero-flicker guarantee for all themed paint.
- **`FUN_0044A581` = memDC helper** (`__thiscall`): `CreateCompatibleDC`
  + `CreateCompatibleBitmap` + `SetViewportOrgEx` shift — RAII-ish struct
  behind all double-buffered paint (`FUN_0044D1AC`, `FUN_00449C12`);
  released by `FUN_0044A569` blit.
- **`FUN_00449C12` = icon compositor** (`__fastcall`, `DrawIconEx` IAT
  `0x50D474`, `AlphaBlend` IAT `0x50D3C4`): memDC (`FUN_0044A581`) →
  `DrawIconEx` → 4-corner `GetPixel` transparency test → `AlphaBlend`
  with/without per-pixel alpha. Sibling caller `FUN_00436F19` (capture
  overlay icons). Used for service icons, tray states, and button glyphs.

## Rounded corners (decompiled)

- **`FUN_0043A77C` = popup destroyer** (`__fastcall`): IsWindow-guarded
  `DestroyWindow` — popups are fully destroyed on hide (not just hidden),
  rebuilt fresh by `FUN_00434025` on next show. Explains the create-every-
  time cost and the placement re-apply path.
- **`FUN_0043AA90` = autohide worker** (`__fastcall`, timer `0x113`): if
  cursor left the inflated rect (`DAT_00549170` margin) and no menu is open
  (`FUN_0043A8C4` guard) → `KillTimer` + `FUN_0043A77C` hide. The
  `PopupTimeout` countdown behind auto-hiding popups.
- **`FUN_00414A7E` = transparency+autohide controller** (`__thiscall`,
  `SetLayeredWindowAttributes` via IAT `0x50D520`): custom `0x80FD` →
  opaque (`0xFF`); mouse-leave `0x2A3` → `Transparency` alpha
  (`DAT_005494A4`, default 217) + `PopupTimeout` auto-hide timer (1000);
  timer `0x113` → `FUN_0043AA90` hide. Fade in/out behind popup hover.
- **`FUN_0044E5EC`/`FUN_0044E826` = rounded-region applicators**
  (`SetWindowRgn` via IAT `0x50D540`): `CreateRoundRectRgn(11, 11)`
  (fallback `CreateRectRgn`) — matches theme `ButtonRadius`/
  `WindowBorderRadius`; sibling at `FUN_0044E826` for popup frames.

## Tooltip + balloon (decompiled)

- **`FUN_00403E00` = tooltip creator** (`__thiscall`): `CreateWindowExW(
  "tooltips_class32", style 0x80000002 = TTS_ALWAYSTIP|TTS_NOPREFIX)` —
  hover hints on popup controls.

## Tray icon + layout keys (decompiled)

- **`FUN_00405C42` = tray add** (`__thiscall`, `Shell_NotifyIconW(NIM_ADD)`
  via IAT `0x50D424`): fills NOTIFYICONDATA (`cbSize` from `this+0x3BC`,
  `uCallbackMessage = 0x80AA`, 128-wchar tooltip copy). Siblings:
  `FUN_00405CB2/00405D0C/00405D62` (modify/delete/show balloon).
- **Layout key helpers** (`FUN_0042AB07` family, `SendInput` via IAT
  `0x50D504`): single `tagINPUT` inject returning success bool — shared by
  the copy-capture synth and the `TaskConvertTextLayout` retype engine.
- **Layout converter = `FUN_00404E09`** (char, from-HKL, to-HKL): hardcoded
  EN↔RU phonetic pairs (`HKL 0x4090409`/`0x40D040D`, e.g. `q`↔`/`, `w`↔`'`,
  `,`↔`'`, `.`↔`/`) then generic fallback `VkKeyScanExW` + `ToUnicodeEx`
  (IAT `0x50D64C`) with shift-state synthesis. `GetKeyboardLayout` (IAT
  `0x50D61C`) consumer at `FUN_004140C1` (layout indicator update).

## Crypto split (decompiled)

- CSP hash (`CryptAcquireContext/HashData/GetHashParam`, ADVAPI32): app-side
  cache-key hashing (`FUN_00474178` MD5) + RNG (`FUN_00443B9A`
  `CryptGenRandom`).
- Cert store (`CertEnum/Find/FreeCertificateContext`, CRYPT32): used only
  inside static libcurl's Schannel verify path — no app-level cert code.
  (Relevant to the Babylon SSL failure: system store vs retired host chain.)

## Winsock note

- `WSAStartup`/`WSACleanup` are imported but have **zero callers** in app
  code — the statically-linked libcurl initializes Winsock itself on first
  `curl_easy` use. No app-level socket code exists outside libcurl/BASS.

## HTTP fetch wrappers (decompiled)

- **GET = `FUN_0045BCED`** (url, out, flags, timeout `0xFDE9`, retries):
  `FUN_0045BBAE` builds URL+headers → `FUN_0043B185` charset-convert response
  (`MultiByteToWideChar`). **POST = `FUN_0045BF7D`**: same shape via
  `FUN_0045BF13` body builder. Underlying transport is statically-linked
  libcurl (no curl imports; `CURLOPT_*`/timeout/proxy strings embedded);
  proxy from `WinHttpGetIEProxyConfigForCurrentUser` or `Options.json`,
  timeout from `Internet.Timeout` (default 10000ms).

## Auto-update + proxy (decompiled, probed)

- **`FUN_004D56B9` = heap bottom** (`__malloc_base` wrapper): all
  container growth bottoms out at CRT malloc — memory chain fully closed
  (freelist → chunks → malloc, no custom heap).
- **`FUN_0042133C` = freelist chunk allocator** (`__fastcall`,
  overflow-checked `count*size`): backs the DOM node pool + hash buckets —
  single allocator behind all container growth (no raw new[] in hot paths).
- **`FUN_00440C4A`/`FUN_00440F7D` = DOM grow + node create**
  (`__thiscall` pair): bucket realloc (overflow-guarded) + freelist node
  pool — completes the DOM container behind JSON/options/history.
- **`FUN_00440DD1` = DOM lookup** (`__thiscall`): same DJB2 + bucket +
  chain shape as `FUN_0043E950` (hash field `+3`, next `+2`) — one shared
  hash idiom across JS named-items, options, and JSON DOM.
- **`FUN_00440893` = DOM object insert** (`__thiscall`, used by the
  object parser + options saver): lookup (`FUN_00440DD1`) or create
  (`FUN_00440C4A` grow + `FUN_00440F7D` node) then set value — the same
  writer behind `Options.json` saves.
- **`FUN_0043F25B` = DOM array append** (`__thiscall`, used by the array
  parser): grow-on-demand (`FUN_0043F4E1`) + store — backs JSON result
  arrays before our Python `json.loads` takes over.
- **`FUN_0043FBB4` = digit run** (`__thiscall`): accumulates `0-9` into
  a fresh string (used by the number parser's int/frac/exp parts).
- **`FUN_0043F77D` = cursor advance** (`__thiscall`, used by every
  parser): `pos += n*2` (UTF-16 units) with end-clamp — bounds-safe
  scanning shared across JSON/string/comment lexing.
- **`FUN_0043F7DB` = comment parser** (`__fastcall`): both `//` line
  (to `\n`/`\r`) and `/* */` block comments — full JSONC support.
- **`FUN_0043F7D3` = whitespace+comment skipper** (`__fastcall` thunk,
  called before every token): skips `\t\n\r space` + `//` line comments
  (`FUN_0043F7DB`) — the parser accepts JSONC (defensive; the shipped
  `Options.json` has zero `//` today, verified).
- **`FUN_0043FE2D` = JSON literal parser** (`__fastcall`): `t`/`f` →
  `json::Boolean::vftable` (bool from first char), `n` handled inline as
  `json::Null` in the dispatcher — completes the literal trio.
- **`FUN_0043FA44` = JSON number parser** (`__fastcall`): optional
  `-` → digits (`FUN_0043FBB4`) → optional `.frac` → optional `e/E±exp`
  — full JSON number grammar (ints, decimals, exponents for timestamps
  and language-index numerics).
- **`FUN_0043FC8F` = JSON object parser** (`__fastcall`): `{` →
  string `:` recursive-value pairs (`FUN_00440893` insert) → `}` —
  completes the JSON trio (string/array/object + literals/numbers).
- **`FUN_0043FDA1` = JSON array parser** (`__fastcall`): `[` →
  recursive `FUN_0043FBF8` elements (`, `-separated, appended via
  `FUN_0043F25B`) → `]` — backs `translateResult`/`ParsedResults` arrays
  in provider responses.
- **`FUN_0043F865` = JSON string parser** (`__fastcall`): quote-delimited
  scan with backslash-escape decoding (`\\`, `\b`, …) — standard-compliant
  string unescaping for provider responses and config files.
- **`FUN_0043FBF8`/`FUN_0043F71A` = JSON parser** (recursive descent into
  a `json::` DOM with `Null` vftable): `"`→`FUN_0043F865` string,
  `[`→`FUN_0043FDA1` array, `{`→`FUN_0043FC8F` object, `f/t/n`→literals,
  `-/0-9`→`FUN_0043FA44` number. Backs Options/History/config + every
  provider JSON response parse. (Our Python uses stdlib `json` —
  behaviorally identical.)
- **`FUN_00461ADE` = update parser** (called from the checker):
  JSON-parse (`FUN_0043F71A`) → `urls` array (`FUN_00440A08`) → per-URL
  download jobs. Dead path now (server 404), but documents the
  self-update protocol.
- **`FUN_00461A26` = update checker** (`CheckForUpdateRunnable`'s worker):
  GET `https://quest-app.appspot.com/update?v=6.10.0` via `FUN_0045BCED`
  (curl wrapper, timeout flag `0xFDE9`, retry 2) → `FUN_00461ADE` parses
  response. **Probed 2026-10-07: HTTP 404** — update server retired along
  with the app (last release 2022); updater is dead code path now.
- Proxy modes (from strings + `PageInternet`): No proxy / system settings
  (`WinHttpGetIEProxyConfigForCurrentUser`) / auto-detect / manual
  (Scheme/Host/Port/Username/Password in `Options.json Proxy` section).
  libcurl honors `http_proxy`/`all_proxy` env as fallback.

## Offline XDXF dictionaries (decompiled + ported)

- **Options seeding = `FUN_0045D160` head**: `PreferredDomain` (from global
  `DAT_005494E0`) and siblings pushed into the JS engine via
  `FUN_00465A92`→`addOption` *before* `serviceHeader` runs — so every
  `Service.js` sees `Options.PreferredDomain/GoogleDomain/LanguageCode`
  from its first line. Our `session.py` + per-module `HOST` constants
  reproduce these values statically.
- **`Utils.md5` audit**: only Youdao's `Service.js` calls it
  (`Utils.md5("fanyideskweb"+...)`); our Python port uses `hashlib.md5`
  (byte-identical — MD5 is deterministic, verified by matching Youdao
  `errorCode 50` shape which proves the sign *format* is accepted and only
  the session fields are stale).
- **`FUN_00460ABE` = Utils exposer** (called from context init):
  QueryInterface gate on 3 IIDs (standard IDispatch/IUnknown + custom
  `Utils` GUID at `DAT_005143A0`) → exposes the native `Utils` object
  (`md5`, string helpers) that `Service.js` files call.
- **`FUN_0045F609` = executor context init** (`__fastcall`, called before
  every `FUN_0045F6C1` run): sets `Script::vftable` + tuning floats
  (`0x3F400000`=0.75, `0x3E800000`=0.25, `0x40100000`=2.25 at
  `+0x18/+0x19/+0x1A` — retry weights/timeouts) + `UtilsDispatch` vftable +
  exposes the `Utils` object (`FUN_0043E873` + `FUN_00460ABE`) that service
  JS calls as `Utils.md5(...)`.
- **`FUN_0045D6A9` = service discovery root**: `GetFileAttributesW("Services")`
  → load `Common.js` framework first (via shared `FUN_0043DF32` reader into
  `DAT_005492AC`) → enumerate per-service dirs → each `Service.js` loaded
  the same way. Mirrors our `qtranslate/services/` layout 1:1
  (`common.py` + one module per provider).
- **`FUN_00445BB9` = XDXF loader** (`__thiscall`, refs `.xdxf` at `0x52265C`):
  `PathFileExistsW` check → `PathFindExtensionW` split → register into the
  `OfflineDictionaries` list (persisted in `Options.json`, refs at
  `FUN_004561F0`/`FUN_0045869F`). File filter `XDXF Dictionary (*.xdxf)`.
- Rendering: `Resources/XdxfArticle.xslt` applied to each `<ar>` article
  (native MSXML transform). Ported 1:1 to `qtranslate/xdxf.py` with stdlib
  `xml.etree` (no XSLT engine): `<k>`→bold div, `<tr>`→brackets,
  `<kref>`→`qtdp:` link, `<iref>`→ext link, `<ex>`→gray example. Live-tested
  render output matches the XSLT semantics.

## Auto-detect flow (decompiled)

- **`FUN_0046009D` = detect invoker** (`__thiscall`): invokes
  `serviceDetectLanguageRequest(text)` on the service JS via IDispatch
  (`FUN_0043B942`) → parses the returned `RequestData` with `FUN_0046578F` →
  executes HTTP via `FUN_00460006` → curl wrappers `FUN_0045BCED` (GET) /
  `FUN_0045BF7D` (POST) with timeout+retry args. Response charset fixed at
  `0xFDE9` = 65001 UTF-8 (`FUN_0043B207` wrapper → `FUN_0043B185`
  `MultiByteToWideChar`) — matches `CodePage.UTF8` in `Common.js`; the other
  `CodePage` enum values (WINDOWS1251/ISO8859_1) are for legacy provider pages.
  Sibling at `FUN_00465CCE`
  (same `serviceDetectLanguageRequest` string ref — dictionary-window path).
- Options driving it: `AlwaysDetectLanguage`, `BackTranslation`,
  `BackTranslationSplitterPos` (refs in `FUN_004561F0`/`FUN_0045869F` savers).
- **Request/response pair = `FUN_00465D82` / `FUN_00465E36`** (`__thiscall`):
  request side invokes `serviceTranslateRequest(text, sl, tl)` (3 VARIANT
  args via `FUN_0043B942`) and validates the returned `RequestData` with
  `FUN_0046578F`; response side invokes `serviceTranslateResponse(...)`
  (4 args) and parses the `ResponseData` with `FUN_0046592D`. The Python
  `RequestData`/`ResponseData` dataclasses in `qtranslate/common.py` mirror
  exactly these two native parse functions' field layouts.
- **Dictionary pair = `FUN_00465EF7` / `FUN_00465FAB`**: same 3-arg/4-arg
  IDispatch pattern for `serviceDictionaryRequest/Response` — the dictionary
  render fork (HTML into `DictionaryWindow` instead of plain text).
- **Options bridge = `UtilsDispatch` table in `FUN_0045F6C1`**: before
  running service JS, the executor exposes native settings as JS `Options.*`
  (`PreferredDomain`, `GoogleDomain`, `GoogleTkk`, `BingToken/BingKey/BingCookie`,
  `PromtCookie/PromtXsrf/PromtPaft`, `LanguageCode` — string refs at
  `0045F88D`…`0045FB9F`). Name resolution through a string hash-map
  (`FUN_00460E15` lookup). `qtranslate/session.py` reproduces the *values*
  side of this bridge by scraping provider pages.
- **`GoogleTkk` seed pipeline = `FUN_0040FB54` → `FUN_0040FEC9`** (correction
  to the earlier note): the *native* side fetches the seed itself —
  GET `https://translate.google.<PreferredDomain>/translate_a/element.js`,
  extract the TKK substring between two markers, cache hourly
  (`GetSystemTime` compare at `DAT_0054977C`, `_atexit` cleanup, second
  fetch with a different timestamp query on empty). Only the *slot* is
  exposed to JS via `Options`.
  Our Python port defaults `tkk="0.0"` and relies on the `dict-chrome-ex`
  fallback when `gtx` is rate-limited — same net effect (live-verified);
  a faithful `refresh_tkk()` would port `FUN_0040FB54` 1:1 (fetch element.js
  + hourly cache).
- **Link opener = `FUN_0045FCCD`** (`__thiscall`): invokes
  `serviceLink(text, sl, tl, flag)` (4 args via `FUN_0043B9BE`)
  → URL string → `ShellExecute` opens the provider page in the browser
  ("open in browser" context action). `serviceHost` refs at
  `FUN_00465BD3`/`FUN_00460006` (base URL for fetch + Referer header).
- **Listen invoker = `FUN_0046606C`** (`__thiscall`): invokes
  `serviceListenRequest(text, lang, slowFlag)` (3 args, `param_3` = slow
  playback toggle) → `RequestData` parse (`FUN_0046578F`) → curl fetch mp3 →
  `FUN_00461642` BASS playback. `TaskListenText`'s entry point.

## Popup render path (decompiled, verified)

- **`FUN_0040C393` = popup content+position setter** (`__fastcall`, calls
  `SetWindowTextW` via IAT `0x50D5C0`, `SetWindowPos` via `0x50D5A0`):
  set window text from `this+0x3C` → `WM_SETICON (0x80)` if icon present →
  RichEdit child (`GetDlgItem 0x49E`) content update (`FUN_004030AE`) →
  `EM_EXLIMITTEXT`-style config msg `0xD3` → result text into second control
  (`this+0x40`) → auto-resize (`FUN_0044B4F4`, `FUN_0040C475`) →
  `SetWindowPos(HWND_TOPMOST, SWP_NOMOVE|NOSIZE|SHOWWINDOW = 0x40B)`.
  Sibling renderers share the pattern: `FUN_00411F80`, `FUN_004127DA`,
  `FUN_0042EFDA/0042F96B/0042F19A`.
- Menu builders confirmed sharing `FUN_00404055` loader (7 sites):
  `FUN_00432082` = Show Full History (`0x806D`); all use
  `FUN_00451F6D`-build + `FUN_004040BA`-patch + `TrackPopupMenu`.
- **`InstantTranslation` flag** (options only, `FUN_004561F0`/`FUN_0045869F`
  save/load refs): when on, the 50ms debounce timer (`FUN_00401530`) fires
  translate on every keystroke instead of waiting for Ctrl+Enter — no
  separate code path, just the timer armed from the edit-change notify
  (`EN_CHANGE` arrives via the MainWindow `WM_COMMAND` case in
  `FUN_00411DEB`; no dedicated handler needed).
- **`FUN_00401530` = main-window init**: RichEdit subclass (`0x4AE` via
  `FUN_004030AE`) + 50ms debounce `SetTimer` (IAT `0x50D498`, 10 sites:
  instant-translate delay, popup auto-hide `PopupTimeout`, OCR region
  settle) + format text
  (`DAT_0051C490`) into `0x3ED` + layout (`FUN_0044B4F4`) + pretranslate
  register (`FUN_004551D6`) — the full MainWindow bring-up sequence.
- **`FUN_004030AE` = RichEdit subclasser**: ATL thunk alloc + `SetWindowLongW(GWL_WNDPROC)`
  — popup text controls get a custom WndProc for link-click/hover handling.
- **`FUN_0044FB11` = content-control classifier**: picks SysListView32 (lists)
  → SysTreeView32 (trees) → RICHEDIT50W / RichEdit20W (`msftedit.dll`,
  default font Segoe UI) by content type — the popup instantiates the right
  control class per result kind (translation text vs dictionary HTML vs
  history list).
- **`FUN_0044FCD9` = control initializer** (called by the classifier):
  ListView branch sends `LVM_SETTEXTCOLOR/BKCOLOR` (`0x1024/0x1001`) +
  extended style (`0x1026`); TreeView branch sends `TVM_SETTEXTCOLOR/BKCOLOR`
  (`0x111D/0x111E`) — colors from `GetSysColor` or the `Appearance`
  `ColorText/ColorBack` overrides. RichEdit branch (type 3) sends
  `EM_SETCHARFORMAT (0x444)` with a `CHARFORMAT` struct then
  `EM_SETBKGNDCOLOR (0x443)` — translation-text styling path.
- **`FUN_0044FE1B` = theme-state selector** (called by all 3 init branches):
  picks theme index by control state — disabled → 3, focused → 4, has-text →
  1, empty → 0 — via `FUN_0044C51C` on the shared theme store
  (`DAT_005491E8`, `Themes/` folder: per-service icons + color schemes).
- **`FUN_0044C4CA` = theme color accessor** (`__thiscall`, vtable init
  first): kind→offset (`1→0xB4, 2→0xD4, 3→0xF4, 4→0x114, else→0x94`,
  stride `0x20`) — per-kind colors (text/back/border/...) backing
  `theme.py::window_colors`.
- **`FUN_0044C51C` = theme palette accessor**: state→struct offset
  (1→`+0x14C`, 3→`+0x164`, 4→`+0x17C`, else→`+0x134`, stride `0x18`) —
  palettes ported to `qtranslate/theme.py` (`window_colors` per state;
  8 themes verified loadable).
- **`FUN_0044D3C3` = button-type painter** (`__fastcall`, types 2/3/5/6):
  same state machine + focus-rect (`BM_GETSTATE` bit0) for push/check/radio
  buttons; GDI+ gradient path (`FUN_0040647F` family) for glass styles.
- **`FUN_004496AD` = line primitive** (`__fastcall`): 1px solid pen +
  `MoveToEx`/`LineTo` + cleanup — the atomic stroke under etched lines,
  separators, and focus rects.
- **`FUN_0044D8CB` = etched-line helper** (`__fastcall`): theme frame
  (`FUN_00449B08`) + 4 highlight edges (`FUN_004496AD` line draws,
  skipped when color is `0xFFFFFFFF`) — sunken/etched groupbox look.
- **`FUN_0044D282` = group/separator painter** (`__fastcall`, type 7):
  measures label (`GetTextExtentPoint32W`) → etched line halves
  (`FUN_0044D8CB`) + left-indented label (`FUN_0042248C` text) — groupbox
  headers in options dialogs.
- **`FUN_0044D502` = default control painter** (`__fastcall`):
  `BM_GETSTATE (0xF2)` + enabled/hover/pressed bits → state index
  (disabled 3 / pressed 2 / hover 1-or-4 / normal 0, feeding the
  `FUN_0044FE1B` theme selector) → theme colors (`FUN_0044C4CA`) → fill.
  The state machine behind every themed button.
- **`FUN_0044D1AC` = double-buffered paint worker** (`__fastcall`): memDC
  (`FUN_0044A581`) → per-type painter (button 2/3/5/6 → `FUN_0044D3C3`,
  type 7 → `FUN_0044D282`, else → `FUN_0044D502`) → blit
  (`FUN_0044A569`). Flicker-free themed paint core.
- **`FUN_0044D008` = themed custom dispatcher** (`__fastcall`):
  `WM_PAINT (0xF)` → `FUN_0044D1AC`; `WM_ERASEBKGND (0x14)` skip;
  `WM_MOUSEMOVE (0x200)` hover-set + invalidate; `0x2A3`
  (`WM_MOUSELEAVE`-family) hover-clear; NC range `0xF1–0xF7` +
  `0x47` via pre/post (`FUN_0044CF07/0044CF52`) + invalidate — full
  hover-aware themed paint for subclassed controls.
- **`FUN_0044BFB6` = subclass proc** (SetWindowSubclass callback):
  custom dispatch (`FUN_0044D008`, handled-flag) → `WM_NCDESTROY (0x82)`
  cleanup (`FUN_0044BCC1`) → `DefSubclassProc` fallback.
- **`FUN_0044BD0F` = modern subclasser** (`__fastcall`,
  `SetWindowSubclass` id 100 with refcounted data — cf. legacy
  `SetWindowLong` in `FUN_004030AE`): theme-compare (`FUN_0044CD0E` on
  `FUN_0044C4CA` colors) decides subclass need; `FUN_0044BFB6` proc.
- **`FUN_0044B4F4` = popup layout engine**: walks child windows
  (`GetWindow GW_CHILD`), classifies Button vs Static vs
  `QTranslate_HotKeyControl` (custom key-capture control, class refs at
  `0044B676/0044B8B5` — skipped during resize like buttons) via class-name compare,
  resizes/repositions each (`FUN_0044BD0F`/`FUN_0044BECE`) — the auto-fit
  logic that sizes the popup to content length.

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
- **Service metadata = `FUN_0045D160`**: boots `Script` engine
  (`services::Script::vftable` on stack), runs service JS, then invokes
  `serviceHeader` via IDispatch (`FUN_0043B942`) and reads capabilities with
  `FUN_00465669` (= field reader: `id`/`name`/`info`/`capabilities` via
  `FUN_004661D1` dispatch-get + `VariantChangeType` to int, stored as
  `[id, name, info, caps]` tuple) — this is how the app knows which providers offer
  TRANSLATE vs DICTIONARY vs LISTEN (the bitmask in `Common.js`), driving
  both the ServicesMenu filter and the translate-vs-dictionary render fork.
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
- **Offline SAPI fallback = `FUN_00448BEC`**: `CoCreateInstance(CLSID
  {29333BF9-7B36-11D2-B20E-00C04F983E60} = SAPI SpVoice, CLSCTX 0x17)` →
  `OleRun` → `QueryInterface` → vtable init (`+0xFC/+0x110/+0x118`).
  When online TTS mp3 fails, `TaskListenText` falls back to system SAPI
  voices — no network needed for English/Vietnamese system voices.
- Speech input (from strings + RTTI + decompile, endpoint probed 2026-10-07):
  hotkeys `HotKeySpeechInput`/`HotKeyTextRecognition` → mic via
  **`FUN_0044555D`** (`BASS_RecordStart(rate, mono, RECORDPROC
  `FUN_00445606`, ctx)` via IAT `0x50D7A4`, init at `FUN_00445515`/
  `FUN_0044187E` via IAT `0x50D79C`, error via `BASS_ErrorGetCode`) →
  **`FUN_00445606` record callback**: chunk → `FUN_00444D94` (FLAC encode:
  `FUN_0044DC8` alloc via `FUN_004C0BA7` + `FUN_00444E53` process via
  `FUN_004C0200`, statically-linked libFLAC — `FLAC__STREAM_ENCODER_*`
  strings confirm)
  → `FUN_00445659` (jitter buffer) → consumer at `ctx+0x18`
  (`EVENT_AUDIO_CHUNK` → full-duplex `up` stream) →
  FLAC encode → POST `speech-api/full-duplex/v1/up` (probed: HTTP 400 without
  key, i.e. host alive but needs valid key + FLAC body — same class of block
  as Bing/Promt, documented not hidden). State machine
  `STATE_WAITING_FOR_SPEECH` → `STATE_RECOGNIZING` with `EVENT_AUDIO_CHUNK`
  streaming; `EnergyEndpointer` (RTTI-only, no dedicated strings — simple
  inline RMS-threshold VAD) cuts silence.

## JS framework (`Services/Common.js` → `qtranslate/common.py`)

`ServiceHeader`/`RequestData`/`ResponseData`, capability bitmask
(TRANSLATE=1, DETECT=2, LISTEN=4, DICTIONARY=8), limits (URI 1800 / source 5000 chars).
17 providers; see `qtranslate/services/`.
