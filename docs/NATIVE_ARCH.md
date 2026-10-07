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

0. **`FUN_00418DA0`/`FUN_004059CF` = raw-input pre-step**: registers mouse
   RawInput (`UsagePage 1 / Usage 2`, `RIDEV_INPUTSINK 0x100` when enabling)
   so mouse-mode capture receives movement even unfocused; then
   `FUN_00418B69` state sync.
0c. **`FUN_00417E4E` = RawInput mouse handler** (`GetRawInputData/RID_INPUT`
   via IAT `0x50D580`, gated by `DAT_005494E7` + `FUN_004544AE`): maps
   button flags to `WM_LBUTTONDOWN/UP (0x201/0x202)`, stamps
   `GetCursorPos` + `GetTickCount` → `FUN_004193F6` click-capture trigger.
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

- **`FUN_0042F2CC` = help/about text loader**: resolves `\help.txt`
  (`FUN_0045B716`) → reads via shared `FUN_0043DF32` file pipeline →
  formats `"%s %s %s\n\n"` header (version line) for the About dialog.
  Called from the startup sequencer on first run.

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

## Replace-selection path (decompiled)

- **`FUN_0043BE56` = clipboard writer** (`__fastcall`): open-with-retry
  (`FUN_0043BE07`) → `EmptyClipboard` → `SetClipboardData(CF_UNICODETEXT)`
  (`0xD`, via IAT `0x50D4AC`) → `CloseClipboard`. 7 callers incl.
  `FUN_0043C02B`, `FUN_00405142`, `FUN_00429813`.
- **`FUN_004056CE` = replace-selection task** (`TaskReplaceSelection`):
  read clipboard (`FUN_0043BEB2`) → translate (`FUN_00404A12`) → write
  translation back (`FUN_0043BE56`) — then the capture synth (`FUN_0043BD5C`
  with `0x56` 'V') pastes over the selection.

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
- **`FUN_00426966` = async re-lookup dispatch**: `FUN_00414E72` builds the
  dictionary task object → `PostMessageW(hwnd, 0x812C)` queues it to the
  window's message loop (custom `WM_APP`-range message for dictionary work,
  keeping link-clicks non-blocking).
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
  direction flag) → `FUN_00449B08` rect fill. Single call behind all
  themed backgrounds.

## GDI+ lifecycle (decompiled)

- **`FUN_0044A3D8` = DPI scaler** (called from WinMain): `GetDeviceCaps(
  LOGPIXELSX)` cached once (`DAT_00544050`, default 96), ratio stored at
  `DAT_00544058` — drives all `MulDiv` font/layout scaling (per-monitor DPI
  unaware, system-DPI snapshot at startup).
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

- **`FUN_00409CC8` = dialog refresh tick** (`__fastcall`): state check
  (`FUN_0043AF94`) → content refresh (`FUN_00409D1C` + `FUN_00408010`) →
  1s `SetTimer` re-arm. Live preview behind service list / hotkey test
  buttons in `OptionsWindow`.
- **`FUN_00408456` = HotKeyCtrl display builder** (`__thiscall`): subclass
  wiring + `HKM_* (0x43B/0x445)` hotkey set/get + highlight
  (`0xFF676985`) on flag 4 + dropdown (`+0x48`) on flag 2 — the
  "press keys" capture box (`QTranslate_HotKeyControl` class).
- **`FUN_00409D1C` = hotkey test runner**: resolve hotkey (`FUN_00408AA2`)
  → build display string (`FUN_00408456`) → vtable show (`+4`), live test
  (`+0xEC`), hide (`+8`) — the "press keys to test" box in Hotkeys options.

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
- **`FUN_0044C51C` = theme palette accessor**: state→struct offset
  (1→`+0x14C`, 3→`+0x164`, 4→`+0x17C`, else→`+0x134`, stride `0x18`) —
  palettes ported to `qtranslate/theme.py` (`window_colors` per state;
  8 themes verified loadable).
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
