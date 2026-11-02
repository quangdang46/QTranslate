# Reliability Recovery Reconnaissance

Status: `INITIAL`. Reviewed 2026-10-31. This is a bounded inspection for the
Ctrl+Q and current-feature reliability plan, not a full repository audit.

## Inspected

- Product direction: `docs/PROJECT_VISION.md`.
- Gate and blocker records: `docs/RE_COVERAGE_CHECKLIST.md`,
  `docs/roadmap/BLOCKERS.md`.
- Feature/status records: `docs/COMPATIBILITY_MATRIX.md`,
  `docs/roadmap/FEATURE_MATRIX.md`, `docs/roadmap/TEST_RESULTS.md`.
- Runtime entry point and bundle: `start_qt.py`, `qtranslate.spec`,
  `tools/build_bundle.py`.
- Ctrl+Q path: `qtranslate/qt/hotkeys.py`, `qtranslate/macos_hotkeys.py`,
  `qtranslate/qt/app.py`, `qtranslate/selection.py`, `qtranslate/qt/popup.py`.
- Related tests: `tests/regress_qt_features.py`,
  `tests/regress_selection_capture.py`, `tests/regress_hotkey_coverage.py`,
  `tests/regress_hotkey_decode.py`.
- Selected upstream sources and license, listed in
  `UPSTREAM_REFERENCE_AUDIT.md`.
- Git status and current HEAD. Existing modified files were not changed.

There is no repository-root `AGENTS.md` in this working tree.

## Confirmed current path

The package spec names `start_qt.py` as its entry point and describes a single
PySide6 front end. `qtranslate/qt/app.py::main()` creates the UI and tray,
then calls `qtranslate.qt.hotkeys.install(app)`. The default config assigns
`HotKeyPopupWindow` code `593` (`0x251`), which `config.hotkey_combo()` decodes
as `ctrl+q`.

`qtranslate/qt/hotkeys.py` reads `HotKeys.EnableHotKeys`. On Windows it uses
the `keyboard` backend and wraps handlers with `app._on_ui`. On macOS it uses
`qtranslate.macos_hotkeys` and Carbon. The current Carbon event handler reads
the hotkey ID from `kEventParamDirectObject`; commit `e0ac592` records that
correction. Source inspection establishes intended routing, not OS delivery.

After dispatch, `QtApp.hotkey_popup()` starts worker work, calls
`selection.copy_selection()`, falls back to clipboard text when capture is
empty, translates, then dispatches `show_translation()` to the UI.

## What the tests establish

- `regress_qt_features.py` replaces the selector, translator, and popup with
  controlled test doubles. It checks callback-level behavior and selected-text
  handling in the Qt app.
- The same suite inspects or fakes hotkey registration and UI-thread
  marshalling. It does not inject Ctrl+Q through Windows or Carbon.
- `regress_selection_capture.py` controls the copy, clipboard, sequence
  counter, key state, and timing seams. It has no real foreground application.
- `regress_hotkey_coverage.py` checks source structure and action-table
  coverage. `regress_hotkey_decode.py` pins the configured shortcut codec.
- None of these tests proves a real OS event reaches the callback or that the
  popup appears over an external application on both systems.

## Current diagnostics and limits

- `qtranslate.qt.hotkeys` writes registration metadata to
  `~/.qtranslate_hotkeys.log`.
- The macOS Carbon backend logs registration and handler metadata to that
  file. The Windows backend records installed bindings, while the app's
  `hotkey_popup()` trace in `qt_mouse_debug.log` is the next observable callback
  boundary.
- The app trace logs lengths and statuses, not selected text. Keep future
  diagnostics metadata-only.
- The current session host is macOS 25.4. No Windows desktop reproduction was
  performed. A prior session recorded that the PySide6 runtime suite was
  skipped because PySide6 was unavailable in that environment; rerun it in a
  suitable test environment before using it as implementation evidence.
- The exact package, version, config, target app, and logs from the user's
  Windows and macOS attempts have not been reviewed.

## Existing repository changes

At inspection, the working tree already had modifications to `.gitignore`,
`qtranslate/placement.py`, `qtranslate/qt/app.py`, `qtranslate/qt/popup.py`,
`tests/regress_placement.py`, and `tests/regress_selection_capture.py`.
These are pre-existing work and are outside this planning change.

## Documentation drift to resolve during later status refresh

`docs/roadmap/PROJECT_INVENTORY.md` still describes the Tk front end as shipped,
while `qtranslate.spec` and `tools/build_bundle.py` describe Qt as the only
packaged front end. `start_qt.py` also has a stale introductory note about the
retired front end. Several status documents are dated 2026-10-24 or earlier.
Treat those documents as historical until checked against a current run.
