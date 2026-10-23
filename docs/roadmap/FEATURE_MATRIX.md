# FEATURE MATRIX

Which native feature groups the port covers, in what state, and where the
evidence is. This is the gate-level view; the row-level view, with the
two independent axes (native RE evidence and port state) and the fixed
status vocabulary, is `docs/COMPATIBILITY_MATRIX.md`. Nothing here is
marked verified without a run behind it.

## 1. The status vocabulary

Two independent axes, never one implying the other.

**Native RE evidence**: `VERIFIED` (read out of the binary or measured off
a capture) · `INFERRED` (reasoned, not observed) · `UNKNOWN` ·
`UNRECOVERABLE(reason)`.

**Port state**: `not-started` · `analysed` · `ported` (the code exists,
the behaviour is not proven) · `behaviour-verified` (an acceptance test
proves it) · `dead:<reason>` (the port exists, the endpoint cannot run).

Every `behaviour-verified` row below is Windows-only, because every
acceptance run in this project is Windows-only. No row may be described
as cross-platform verified until a macOS run exists.

## 2. The UI windows (the parity programme)

The measure is the total-ink pixel difference between the native capture
and the Qt render -- see `BASELINE_RESULTS.md` for the method and the
numbers.

| Window | Native capture | Native evidence | Port state | Evidence |
|---|---|---|---|---|
| Main window (DLG129) | 2131 | VERIFIED (17 controls parsed, cross-checked against the DLG ids) | behaviour-verified (ink diff 0.0107) | `tools/render_qt.py --compare` |
| Dictionary (DLG164) | 2132 | VERIFIED | behaviour-verified (ink diff 0.0028) | same |
| History (DLG178/184) | 2133 | VERIFIED | behaviour-verified (ink diff 0.0046) | same |
| Virtual keyboard | 2134 | VERIFIED | behaviour-verified (ink diff 0.0010) | same |
| Options shell + nine pages | 2126, 2135-2141 | VERIFIED (the nine DLG templates: 171, 179, 172, 173, 174, 175, 176, 185, 205) | behaviour-verified on all twelve compared screens (hotkeys 0.0047, internet 0.0039, services 0.0009, languages 0.0018, appearance 0.0045, exceptions 0.0009, advanced 0.0065, updates 0.0022; the Basics page has no capture of its own) | same |
| Popup window (Ctrl+Q) | 2130 | VERIFIED (the 200x68 window inside the desktop shot: border `#53606c`, interior `#d0d0d0`) | ported (Tk + Qt) | `regress_qt_features.py` (the popup takes its text), `screenshots/screens/popup.png` |
| Tray menu | none (the native's menu is the OS's own taskbar menu) | VERIFIED (item order read off capture 2126 and the spec's section 9) | ported (Tk + Qt, native's own mouse-mode names) | `regress_tray_menu.py`, `regress_qt_features.py` |

## 3. The core features

| Feature | Native evidence | Port state | Evidence |
|---|---|---|---|
| Clipboard capture (mode 3) | `FUN_0043EBE0` | behaviour-verified | `regress_clipboard.py` |
| Mouse capture (mode 2, OLEACC) | `FUN_00404901` | behaviour-verified (Windows) | `regress_mouse_capture_c8.py` |
| SendInput synthesis (Ctrl+C) | `FUN_0043BD5C` | behaviour-verified (Windows) | `regress_keyboard.py` |
| Replace-selection write-back | `FUN_0043BE56` | behaviour-verified (Windows) | `regress_replace_selection.py` |
| Foreground exclusion list | `FUN_004631DE` | behaviour-verified | `regress_exclusions.py` |
| 17 global hotkeys | `FUN_00405A17` | behaviour-verified (the names and the codec) | `regress_hotkey_*` |
| Hotkey display string | `FUN_00403B48` | behaviour-verified | `regress_format_hotkey.py` |
| Provider router, 10 translators | `registry.py` | behaviour-verified | `regress_engine.py`, `regress_registry_*` |
| 11 dictionary providers | `registry.py` | behaviour-verified | `regress_dict_*` (30 files) |
| Auto-detect, 6 steps | `regress_auto_detect_capability.py` | behaviour-verified | the same |
| Reliability, fallback router | `reliability.py` | behaviour-verified | `regress_reliability.py` |
| Extension loading + overrides | `extensions.py` | behaviour-verified | `regress_extension_*` |
| All eight capabilities hosted | `extensions.ExtensionAPI` | behaviour-verified (each register_* reaches a real call site; a raising one falls through) | `regress_extension_capabilities.py` (9) |
| The extension SDK | `sdk.py` | behaviour-verified (the public surface; a star-import exposes exactly `__all__`) | `regress_sdk.py` (20) |
| The SDK as an installable package | `docs/EXTENSION_SDK.md` §1 | behaviour-verified (contracts match the host; the wheel installs into a clean virtualenv and pulls in no desktop code) | `regress_sdk_package.py` (22) |
| Override-conflict UX (D18) | `extensions.override_conflicts` | behaviour-verified (the user picks the winner; the pick is persisted) | `regress_qt_extension_ui.py` |
| The popup UI slot | `ui_slots.POPUP_SLOTS`, §8 | behaviour-verified (a contribution renders the popup's body) | `regress_qt_extension_ui.py` |
| History list + its exports | `history.py` | behaviour-verified | `regress_history*.py` |
| The settings file, 20 sections | `NATIVE_ARCH.md` | behaviour-verified | `regress_options_roundtrip.py` |
| The settings file's DEFAULTS | the native's real Options.json | behaviour-verified | `config.default_config()` + `ui_match.py` |
| Themes | `themes/` (9 shipped) | ported | `regress_theme_*` |
| Language packs (36 files) | `locale.py` | ported | `regress_locale*.py` |
| OCR | `services/ocr.py` | ported (needs an API key) | `regress_ocr.py` |
| Speech (SAPI) | `sapi.py` | ported (Windows) | `regress_sapi.py` |
| Virtual keyboard | 2134 | ported (Tk + Qt) | `regress_vk_*`, `regress_qt_features.py` |
| Tray icon + menu | `FUN_00463xxx` | ported (Tk + Qt, native's own mouse-mode names) | `regress_tray_menu.py`, `regress_qt_features.py` |
| Qt front end's mouse mode + Ctrl+Q | the English lang.json (ids 60/70/71), `DAT_005493F8` | ported | `regress_qt_features.py` (81 assertions: the hook, the gate, both capture paths, the read-aloud half, the UI-thread marshalling) |
| Qt front end's twelve windows | captures 2126, 2131-2141 | ported (mean ink diff 0.0037) | `render_qt.py --compare`, `BASELINE_RESULTS.md` |
| Extension UI reaching the RUNNING app | `EXTENSION_SDK.md` §8, `ui_slots.py` | behaviour-verified (the tray menu, the theme's palette, the panel strip) | `regress_qt_extension_ui.py` (16 assertions) |
| The macOS platform adapter | `platforms.py` | behaviour-verified (the per-user folder, the clipboard; the Win32-only pieces stay unavailable) | `regress_platforms.py` (31) |

## 4. The reverse engineering

| Item | State | Evidence |
|---|---|---|
| DLG129 (the main window) | VERIFIED -- all 17 controls parsed, the walker's 2-byte control-id bug fixed, cross-verified against the 13 ids `win32app.py` reads | `docs/review/G9_PART_A_CLOSED_2026-10-16.md` |
| The nine Options page templates | VERIFIED -- 171, 179, 172, 173, 174, 175, 176, 185, 205 | `docs/review/DIALOG_GEOMETRY_MAP_2026-10-15.md` |
| The 16 RT_ICON resources | VERIFIED -- the icons are pixel-identical to the capture | `qtranslate/assets/ui_icons/manifest.json` |
| The service icons | VERIFIED -- from the installer payload | `qtranslate/assets/service_icons/manifest.json` |
| The CommonJS service sources | VERIFIED -- recovered from the installer payload | `docs/review/rea/js_root/` |
| The RE coverage itself | 924 rows | `docs/RE_COVERAGE_CHECKLIST.md` |
