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
| `qtranslate/qt/app.py` | 210 | `QtApp`: the state (service, language pair, history) and the behaviour |
| `qtranslate/qt/main_window.py` | 262 | the main window, on the measured geometry |
| `qtranslate/qt/widgets.py` | 160 | the ONE implementation of the layout helpers |
| `qtranslate/qt/icons.py` | 85 | the recovered icons, with the face keyed out |
| `qtranslate/qt/options.py` | 292 | the Options dialog and its nine pages |
| `qtranslate/qt/dictionary.py` | 172 | the Dictionary window |

`qtranslate_style.py` (untracked, the user's file) holds the design tokens
and `apply_style(app)`. `qtranslate_ui.py` (untracked) is the reference
renderer.

### The Tk view

`qtranslate/app.py` (2111) is the entry point; `qtranslate/windows.py`
(5234) holds the five extracted window classes (`HistoryView`,
`DictionaryView`, `TrayController`, `PopupHost`, `OptionsDialog`);
`qtranslate/screens.py` (865) is the standalone reference/capture port.

## 3. The tests

`tests/` holds **135** files, **21 698** lines, run by
`tools/run_suites.py`. The suite is a set of `regress_*` files, each
asserting ONE behaviour, plus `ui_match.py` (the live GUI suite) and two
smoke files.

The naming is the contract: `regress_<area>_<thing>.py`. The suite
runner prints `ok`/`FAIL` per file and a summary line.

**Current state (2026-10-22, measured):**

```
133 suites, 0 failed, 67.0s
```

(`ui_match.py` is counted as a suite and is a live-GUI suite: 96 checks.)

## 4. The tools

`tools/` holds **17** files, **11 924** lines.

| Tool | What it does |
|---|---|
| `run_suites.py` | the test runner |
| `render_qt.py` | renders the REAL Qt windows and compares them with the native captures |
| `ui_measure.py` | measures a native capture: the client origin, the rows, the text bands, an ASCII dump |
| `ui_parity.py` | renders the Tk port's windows and compares them with the native |
| `ui_compare.py` | compares one render against one native capture |
| `ui_geometry.py` | the per-feature geometry report, native against port |
| `audit_ui_labels.py` | audits every UI string against the shipped English locale pack |
| `g9_screenshot_diff.py` | the G9 screenshot gate |
| `build_bundle.py` | the PyInstaller bundler |
| `dlg_parse.py`, `measure_*.py`, `rtstring_check.py`, `coverage_tally.py` | the RE helpers |

## 5. The assets

`qtranslate/assets/`: `app_icon/` (4), `dict_icons/` (12), `locales/` (36),
`service_icons/` (10), `themes/` (9), `ui_icons/` (12).

The icons are RECOVERED, not drawn: `ui_icons/` from the EXE's `RT_ICON`
resources, `service_icons/` from the installer payload's
`Services/<Name>/Service.ico`. Each carries a `manifest.json` that names
the binary it came from and the capture it was matched against.

## 6. The native captures

`docs/review/native_screens/` holds **14** captures of the real
QTranslate 6.10.0 on this machine:

| File | Window |
|---|---|
| 2126 | Options -> Hotkeys (663x388, a different size from the others) |
| 2130 | the tray menu |
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

`docs/` holds 14 documents, 4851 lines, plus `docs/review/` with **89**
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
