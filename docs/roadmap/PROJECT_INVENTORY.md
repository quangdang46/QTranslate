# PROJECT INVENTORY

What exists in this repository, what it is for, and where the evidence for
each claim lives. Written 2026-10-22. Every number here was read off the
tree, not estimated.

## 1. The two front ends

The port has a toolkit-agnostic core and TWO views over it.

| View | Path | Toolkit | State |
|---|---|---|---|
| Tk | `qtranslate/app.py` + `qtranslate/windows.py` | tkinter/ttk | Shipped, the app that runs today |
| Qt | `qtranslate/qt/` | PySide6 | The parity port, measured against the native pixel by pixel |

The core is shared and knows nothing about either toolkit: `engine.py`,
`registry.py`, `config.py`, `history.py`, `reliability.py`, `session.py`,
`extensions.py`, `sdk.py`, `providers/`, `services/`.

The Qt view is the one the spec in `qtranslate-pyside6-spec.md` describes.
`qtranslate_style.py` holds its tokens, and `qtranslate_ui.py` is the
layout-only reference renderer that proved the geometry before the real
windows existed.

## 2. The package, file by file

### Core (toolkit-agnostic)

| File | Lines | What it owns |
|---|---|---|
| `qtranslate/engine.py` | 261 | `translate(service, text, target, src, auto_detect, back_translate)` -> `core.Result` |
| `qtranslate/registry.py` | 481 | `TRANSLATORS` (10), `DICTS` (11), `services_order`, `detect_language` |
| `qtranslate/config.py` | 370 | the settings file, `default_config()`, the language and service tables |
| `qtranslate/core.py` | 118 | the `Result` shape every front end renders |
| `qtranslate/history.py` | 264 | the history list, its file, its export formats |
| `qtranslate/reliability.py` | 985 | `ErrorKind`, `classify()`, `FallbackRouter`, `ProviderHealth` |
| `qtranslate/extensions.py` | 845 | the extension manifest loader, overrides, the provider contract |
| `qtranslate/sdk.py` | 65 | the published SDK surface |
| `qtranslate/common.py` | 597 | the shared HTTP/JSON plumbing |
| `qtranslate/clipboard.py` | 44 | the clipboard monitor |
| `qtranslate/exclusions.py` | 88 | the excluded-process rules |
| `qtranslate/locale.py` | 145 | the language packs |
| `qtranslate/placement.py` | 190 | the WINDOWPLACEMENT codec and the template geometry |
| `qtranslate/phonetics.py` | 101 | the phonetic passes |
| `qtranslate/player.py` | 106 | the audio player |
| `qtranslate/sapi.py` | 40 | the Windows speech API |
| `qtranslate/mouse_capture.py` | 564 | the mouse-mode capture |
| `qtranslate/dict_render.py` | 161 | the dictionary card renderer |
| `qtranslate/headless.py` | 88 | the no-UI entry point |
| `qtranslate/crash.py` | 60 | the crash reporter |
| `qtranslate/fonts.py` | 37 | the font list |
| `qtranslate/platforms.py` | 156 | the platform interfaces |
| `qtranslate/layout.py` | 68 | the layout helpers |
| `qtranslate/override_ui.py` | 60 | the extension override UI |
| `qtranslate/sendkeys.py` | 37 | the key synthesis |
| `qtranslate/cli.py` | 28 | the command line |

### Providers

`qtranslate/services/`: `google_translate.py` (427), `microsoft.py` (340),
`naver.py` (324), `babylon.py` (146), `baidu.py` (271), `deepl.py` (200),
`promt.py` (268), `yandex.py` (341), `youdao.py` (227), `dictionary.py`
(1110, the eleven dictionary providers), `spell.py` (111), `ocr.py` (88).

### The Qt view

| File | Lines | What it owns |
|---|---|---|
| `qtranslate/qt/__init__.py` | 10 | the package: this is the VIEW, the core stays toolkit-agnostic |
| `qtranslate/qt/app.py` | 537 | `QtApp`: the shell around the core, and the state native keeps in its own session fields (the service, the language pair, the history) |
| `qtranslate/qt/main_window.py` | 266 | the main window (native DLG 129), on the geometry measured off capture 2131 |
| `qtranslate/qt/widgets.py` | 203 | the ONE implementation of the layout helpers, on the coordinates read off the captures |
| `qtranslate/qt/icons.py` | 85 | the recovered icons, with the face keyed out |
| `qtranslate/qt/dictionary.py` | 172 | the Dictionary window, on the geometry measured off capture 2132 |
| `qtranslate/qt/history_window.py` | 78 | the History window (native DLG 178), on the geometry measured off capture 2133 |
| `qtranslate/qt/keyboard.py` | 256 | the virtual keyboard (native DLG 213), every key's rectangle read off capture 2134 |
| `qtranslate/qt/popup.py` | 62 | the translation popup, the frameless 200x68 window of capture 2130 |
| `qtranslate/qt/tray.py` | 109 | the tray icon and its menu: a `QSystemTrayIcon` with a `QMenu`, so the OS draws it |
| `qtranslate/qt/hotkeys.py` | 79 | the global hotkeys and the routing, on the core's `config.hotkey_combo` packing |
| `qtranslate/qt/ocr_pick.py` | 120 | the OCR region picker: a full-screen translucent window, a rubber band, and the grabbed PNG |
| `qtranslate/qt/options/__init__.py` | 39 | the Options dialog's page registry and the nine page classes |
| `qtranslate/qt/options/base.py` | 105 | the Options shell: the page frames and the settings the port writes |
| `qtranslate/qt/options/basics.py` | 37 | the Basics page |
| `qtranslate/qt/options/hotkeys.py` | 80 | the Hotkeys page (capture 2126, a 663x388 shot and so a different size) |
| `qtranslate/qt/options/internet.py` | 23 | the Internet page (capture 2135) |
| `qtranslate/qt/options/services.py` | 85 | the Services page (capture 2136) |
| `qtranslate/qt/options/languages.py` | 57 | the Languages page (capture 2137) |
| `qtranslate/qt/options/appearance.py` | 47 | the Appearance page (capture 2138) |
| `qtranslate/qt/options/exceptions.py` | 52 | the Exceptions page (capture 2139) |
| `qtranslate/qt/options/advanced.py` | 31 | the Advanced page (capture 2140) |
| `qtranslate/qt/options/updates.py` | 16 | the Updates page (capture 2141) |

The nine Options pages are one module each, so one page can be measured
and fixed without touching the others.

`qtranslate_style.py` (224) holds the design tokens and `apply_style(app)`.
`qtranslate_ui.py` (300) is the layout-only reference renderer.

### The Tk view

`qtranslate/app.py` (2111) is the entry point; `qtranslate/windows.py`
(5234) holds the five extracted window classes (`HistoryView`,
`DictionaryView`, `TrayController`, `PopupHost`, `OptionsDialog`);
`qtranslate/screens.py` (865) is the standalone reference/capture port.

## 3. The tests

`tests/` holds **136** files, **21 960** lines, run by
`tools/run_suites.py`. The suite is a set of `regress_*` files, each
asserting ONE behaviour, plus `ui_match.py` (the live GUI suite) and two
smoke files.

The naming is the contract: `regress_<area>_<thing>.py`. The suite
runner prints `ok`/`FAIL` per file and a summary line.

`regress_qt_features.py` (71 assertions) covers the Qt front
end's FEATURES, not its pixels: it builds the PySide6 app, stubs the
engine so nothing goes on the wire, and asserts that the front end
behaves (translate, new, swap, the nine Options pages, the sidebar, the
History/Dictionary/Keyboard windows, the popup and the Ctrl+Q hotkey,
the mouse mode, the tray, the hotkeys,
the assets, the font, the OCR region grab).

**Current state (2026-10-22, measured):**

```
134 suites, 0 failed, 42.0s
```

(`ui_match.py` is counted as a suite and is a live-GUI suite: 96 checks.)

## 4. The tools

`tools/` holds **21** top-level files, **5406** lines (**76** files and
**12 628** lines counting the `_scratch/` and `_scratch_xdxf/`
subdirectories).

| Tool | What it does |
|---|---|
| `run_suites.py` | the test runner |
| `render_qt.py` | renders the REAL Qt windows and compares them with the native captures; `--only` re-renders one screen without touching the others |
| `inkalign.py` | for a named region of a screen, compares the SUM of the ink in each column and each row between the native capture and the render, and prints the offset that best aligns the two and how much of the region matches at that offset. It is not fooled by ClearType, which puts a glyph's ink on different subpixels in the two images even when the text is in the same place |
| `rows.py` | the text bands of a screen, the native's and the render's, side by side, so a page's coordinates can be corrected in one pass |
| `hotspots.py` | a cell-by-cell map of where the remaining difference is, so the next fix goes at the biggest patch |
| `shots.py` | refreshes the pictures in `screenshots/screens/` from the PySide6 front end (it now writes all sixteen) |
| `ui_measure.py` | measures a native capture: the client origin, the rows, the text bands, an ASCII dump |
| `ui_parity.py` | renders the Tk port's windows and compares them with the native |
| `ui_compare.py` | compares one render against one native capture |
| `ui_geometry.py` | the per-feature geometry report, native against port |
| `audit_ui_labels.py` | audits every UI string against the shipped English locale pack |
| `audit_ui_spec.py` | the static audit of the Tk screens against the UI-FULL spec, by text and without building a widget |
| `docs_consistency.py` | the cross-document drift check over `docs/` |
| `gate_artifact_audit.py` | checks that every `VERIFIED` row of the coverage checklist cites a concrete artifact |
| `g9_screenshot_diff.py` | the G9 screenshot gate |
| `build_bundle.py` | the PyInstaller bundler |
| `dlg_parse.py`, `measure_*.py`, `rtstring_check.py`, `coverage_tally.py` | the RE helpers |

## 5. The assets

`qtranslate/assets/`: `app_icon/` (4), `dict_icons/` (12), `locales/` (36),
`service_icons/` (10), `themes/` (9), `ui_icons/` (16 PNGs and a
manifest).

The icons are RECOVERED, not drawn. Eleven of the sixteen in `ui_icons/`
are the 16x16 icons out of the EXE's `RT_ICON` resources (mic, headphone,
back, forward, menu, new, swap, star, star_off, search, history), and the
manifest names the binary they came from and the capture they were
matched against. The other two groups came out of the CAPTURES, because
they are the OS theme's artwork and not icons the EXE carries:
`check_blue.png` (the 12x13 blue list checkbox of the Languages page,
with its white tick) and `ap_icon1..4.png` (the four "Icons:" pictograms
of the Appearance page, with the theme's shadow under each).
`service_icons/` (nine icons and a manifest) came from the installer
payload's `Services/<Name>/Service.ico`.

## 6. The native captures

`docs/review/native_screens/` holds **14** captures of the real
QTranslate 6.10.0 on this machine:

| File | Window |
|---|---|
| 2126 | Options -> Hotkeys (663x388, a different size from the others) |
| 2130 | the Ctrl+Q popup (the 200x68 window inside a 265x115 shot of the desktop around it) |
| 2131 | the main window (516x423) |
| 2132 | the Dictionary window (476x333) |
| 2133 | the History window (476x320) |
| 2134 | the virtual keyboard (464x198) |
| 2135 | Options -> Internet |
| 2136 | Options -> Services |
| 2137 | Options -> Languages |
| 2138 | Options -> Appearance |
| 2139 | Options -> Exceptions |
| 2140 | Options -> Advanced |
| 2141 | Options -> Updates |
| 2144 | the main window, a second take (with a tooltip) |

## 7. The docs

`docs/` holds 13 documents, 4899 lines, plus `docs/review/` with **90**
dated review notes (the evidence trail for every claim in the other
documents) and `docs/roadmap/` with the eight gate deliverables.

| Document | What it is |
|---|---|
| `ARCHITECTURE.md` | the module map and the design rules |
| `COMPATIBILITY_MATRIX.md` | feature by feature: native against port |
| `CURRENT_STATE.md` | where the port stands today |
| `EXTENSION_SDK.md` | the extension contract |
| `IMPLEMENTATION_PLAN.md` | the original build plan |
| `NATIVE_ARCH.md` | the reverse-engineered native (1668 lines) |
| `PIPELINE.md` | the CI pipeline |
| `PROJECT_VISION.md` | what the project is for |
| `RE_COVERAGE_CHECKLIST.md` | the RE coverage, row by row (924 lines) |
| `RE_PROGRESS.md` | the RE log |
| `RELIABILITY.md` | the reliability model |
| `SECURITY.md` | the security notes |
| `TEST_STRATEGY.md` | what the tests are for |
