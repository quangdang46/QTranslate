# HANDOFF

What this session did, what it changed, and what the next session should
pick up. Written 2026-10-22, on `main`, after the PySide6 parity work
reached the point where the app runs for the user and the extension
platform reaches the UI.

The standing rules still apply: the GitHub token is used transiently in
a push URL only (never in a file, never in `.git/config`, output
redacted); the native's installer is never run (the installed copy at
`C:/Program Files (x86)/QTranslate/` is read only); `docs/NATIVE_ARCH.md`
is frozen; every Python run uses `python -I`; downloaded files are
untrusted.

## 1. The four bugs the user found, and their causes

The user ran the app for the first time and hit four things. All four
are fixed; the causes are recorded here because each one was a real
defect, not a cosmetic one.

### 1.1 Ctrl+Q crashed the process (access violation)

**Symptom.** The app started, and pressing Ctrl+Q killed it outright.

**Cause.** The `keyboard` package fires a global hotkey on ITS OWN
listener thread, not on Qt's. The handler (`hotkey_popup`) went
straight to the widgets -- `win.src.setPlainText`, `win.render`, and
opening a popup window -- from that foreign thread. Qt does not guard
cross-thread widget access: it is an access violation, not a catchable
exception, so the process died.

**Fix.** `qtranslate/qt/app.py` gained `_UiInvoker` (a `QObject` with a
queued `invoke` signal) and `QtApp._on_ui(fn)`, which marshals a call
onto the UI thread (and runs it directly when the caller already is the
UI thread). `qtranslate/qt/hotkeys.py` wraps every registered callback
in `app._on_ui`, so the handler runs where the widgets live.

**Pinned by** `tests/regress_qt_features.py`: the marshalling from a
worker thread, and the fact that the registered callback is not the raw
app method.

### 1.2 The Options dialog re-rendered into a new window

**Symptom.** Clicking a page in the Options sidebar opened a NEW window
and closed the old one, so the app flickered and the window jumped.

**Cause.** `OptionsBase._goto` created a fresh page window and closed
the one it came from. Each page was a separate top-level window.

**Fix.** One window, one shell. `OptionsBase` now rebuilds the body in
place: the page's own `build()` is called again with the shell as
`self`, after pointing the instance's `ORIGIN`/`SIZE`/`CHROME` at the
page's own. The chrome (sidebar panel, rows, rule, three buttons) is
described by a `CHROME` dict, because the Hotkeys page's capture (2126)
is a different size and its chrome sits elsewhere.

**Pinned by** `tests/regress_qt_features.py` (the swap keeps the same
`winId`, the old widgets are gone, the new ones are there, the size goes
back to 644 after visiting the 650-wide Hotkeys page).

**Pixel parity preserved.** The first attempt deleted the widgets with
`deleteLater()`, which is an access violation when a paint event is
still queued for them -- the suite crashed. The widgets are now hidden
and unparented instead. The measure is unchanged: mean ink diff
**0.0037** over twelve screens (rgb 0.0355), the same as before the
refactor.

### 1.3 The language combo's list was far too long

**Symptom.** The target-language combo opened a list that ran off the
screen (see the user's screenshot 2160.png).

**Status.** NOT FIXED YET. The combo is populated from
`app.target_names()`, which returns every language the Google provider
supports (75 codes) with their display names. Native's own combo is a
fixed list the native's locale pack declares. This needs the native's
list, and the measurement of how the native's combo behaves (does it
scroll? does it have a filter?). It is listed in §4 below.

### 1.4 The mouse mode did nothing

**Symptom.** "Bôi đen" (select text, click) produced nothing.

**Cause.** The Qt front end had a LABEL for the mouse mode but never
started the hook. Only the tkinter front end ever did.

**Fix.** `qtranslate/qt/app.py` now starts and stops the Win32
low-level mouse hook with the mode, and a selection click captures the
text (OLEACC in the third mode, Ctrl+C + clipboard otherwise) and
translates it through the same `show_translation` step Ctrl+Q uses. The
work runs on a worker thread and crosses to the UI thread by a queued
signal (`_MouseBridge`).

**Also fixed while doing it:**

- The mode NAMES were the port's invention. The native's own strings
  are in the shipped English `lang.json`, ids 60/70/71: "Show icon",
  "Show translation", "Show translation and read". Corrected in
  `qtranslate/qt/tray.py`.
- The mode was not persisted. Native keeps it in `General.MouseMode`
  (DAT_005493F8) and `General.MouseModeOn`; the tkinter front end
  writes both. The Qt front end now writes both too, and
  `_load_session` reads them back -- one state for both front ends.
- The gate was half of native's. Native's order is
  `EnableGuiTranslation` (DAT_005494e4) -> `EnableMouseModeOnCtrl` ->
  exclusions -> the mode-2 OLEACC capture -> the clipboard fallback.
  The port had folded `mouse_capture.available()` INTO the gate's try
  block, so a missing hook looked like a closed gate. Now the gate is
  its own function, `_mouse_gate_ok()`, in native's order.
- Native's third mode speaks the selected text. The tkinter front end
  had that half missing (its comment said "we do not have a TTS sink",
  but the port does: `player.play_text`, online mp3 first, offline
  SAPI when that fails). Both front ends speak it now.

## 2. The extension platform, connected to the UI

The user's audit found the right thing: the extension registry existed
and was tested, but **nothing in the running app ever read it back**.
`ui_slots.winner()` had no consumer outside the tests, and the theme
resolver the UI used was not the one the extension manager resolves
through.

What changed:

| Piece | Before | After |
|---|---|---|
| Qt startup | never called `load_user_extensions()` | calls the SAME shared loader the tkinter one uses (`qtranslate/qt/app.py`) |
| The manager handle | `load_user_extensions()` created it locally and threw it away | `qtranslate.extensions.last_manager()` returns it; the app keeps it as `app.ext_manager` |
| Tray menu | no extension entries | the tray menu reads `ui_slots.entries("menu", "tray")` and adds each contribution as an action (`qtranslate/qt/tray.py`) |
| Theme | `theme.active_theme()` never saw an extension theme | `theme.active_theme(name, manager=...)` resolves an extension theme first; `qtranslate_style.apply_style(app, theme=...)` lets the theme's colours override the measured tokens; `QtApp.apply_theme()` wires it at startup |
| Panel | no consumer at all | the main window docks a strip for a contributed panel at the bottom of the pane it claimed (`qtranslate/qt/main_window.py`); with no extension there is NO strip, so the pixels are unchanged |

`qtranslate_style.py`'s QSS now carries `@FACE@`, `@TEXT@`, `@DIM@` and
`@ACCENT@` placeholders that `apply_style` fills, so a theme can change
the app's colours.

**Pinned by** the new `tests/regress_qt_extension_ui.py` (16 assertions):
the extension loads, the manager is reachable, the contribution is in
the tray slot, the tray menu shows it, the theme resolver returns the
extension's theme, the theme reaches the app's PALETTE, the panel shows
in the main window, and a window with no extension has no panel.

## 3. Other changes in this session

- **`qtranslate/languages.py` (new, Core).** The language table
  (code -> display name) lived in `qtranslate/app.py`, the tkinter
  module, so the Qt view had to import tkinter for two constants. It is
  now Core data; both views read it.
- **`qtranslate/platforms.py`: a macOS adapter.** `platforms.current()`
  returned `UnavailableAdapter` off Windows, whose `extensions_dir()`
  raises -- so the extension loader silently returned `[]` on macOS. The
  new `MacOSAdapter` resolves `~/.config/QTranslate/extensions` and the
  clipboard, and still reports the Win32-only pieces (hotkey hook, mouse
  hook, clipboard sequence counter) unavailable honestly.
- **`tests/regress_extension_e2e.py`**: now also checks that the Qt
  front end wires the shared loader (20 checks).
- **`tests/regress_platforms.py`**: the macOS branch is pinned (31
  checks).
- **`tests/regress_qt_features.py`**: 71 -> 81 assertions.

## 4. What is NOT done -- the next session's list

In the order it should be picked up.

### 4.1 The language combo's list (the user's 2160.png)

The combo lists all 75 provider languages and overflows the screen.
Native's combo shows a fixed list from its locale pack. To close it:

- read the native's own language list and its ORDER out of the shipped
  `Locales/English/lang.json` (the same file the mouse-mode names came
  from),
- measure the native's combo behaviour off a capture (does it scroll? is
  there a filter box?), and
- make `qtranslate/qt/main_window.py`'s combo use that list.

The list the combo needs is in the locale pack, so this is a
transcription job, not a measurement job -- but the BEHAVIOUR (scroll
or filter) needs a capture of native's open combo, which does not exist
yet.

### 4.2 Delete the tkinter front end (the user's explicit request)

**Decision taken:** delete tkinter, KEEP the extension platform.

The scope, and what each step costs:

| File | Lines | What depends on it |
|---|---|---|
| `qtranslate/app.py` | 2,097 | the tkinter view; 32 files import it |
| `qtranslate/windows.py` | 5,234 | the six extracted tkinter window classes |
| `start_app.py` | 47 | the tkinter entry point |
| `qtranslate.spec` / `tools/build_bundle.py` | -- | package BOTH `QTranslate.exe` (tk) and `QTranslate-Qt.exe` (Qt) |

The tests that exercise the tkinter view and must be ported to Qt or
dropped (they are the reason the removal is more than a delete):

```
regress_aux_windows_fidelity.py   regress_main_window_fidelity.py
regress_core_result_uses.py       regress_options_pages_native.py
regress_crash_failfast.py         regress_packaging.py
regress_crash_reporter.py         regress_registry.py
regress_delegators.py             regress_reliability.py
regress_dict_window_fidelity.py   regress_source_language.py
regress_enable_history.py         regress_startup_entry.py
regress_engine.py                 regress_translate_errors.py
regress_exact_search.py           regress_tray_menu.py
                                  regress_windows.py
                                  ui_match.py          (the live GUI suite)
tools/ui_parity.py                (the tkinter render-compare tool)
```

Also `qtranslate/screens.py` and `qtranslate/win32app.py` import
`qtranslate/app.py` -- check what they take from it before deleting.

The Qt view already covers what those tests cover (the nine Options
pages, the History/Dictionary/Keyboard windows, the popup, the tray,
the hotkeys, the strip) -- `tests/regress_qt_features.py` is the
tkinter suite's successor, and it is where the ported assertions
should land.

### 4.3 The extension platform -- DONE, except the conflict UX

All three of the audit's items were closed on 2026-10-23:

1. **The popup slot** -- `qtranslate/qt/popup.py` reads
   `("popup", "body")` and lets a contribution render the body. With no
   extension the built-in label is untouched, so the pixels are the
   native's. Pinned in `regress_qt_extension_ui.py`.
2. **The SDK's public surface** -- `back_translate_internal` is out of
   `qtranslate/sdk.py`'s `__all__` (the docstring always said it was
   internal); a star-import now exposes exactly the public surface.
   Pinned in `regress_sdk.py`.
3. **The SDK as a package** -- `sdksrc/` holds a standalone
   `qtranslate_sdk` distribution (contracts, `Result`, the slot names,
   the language index, `FakeAPI` for an extension's own tests) with a
   `pyproject.toml` and NO dependencies. `tests/regress_sdk_package.py`
   proves it imports with no desktop app on the path, that its
   contracts match the host's field for field, that it imports no GUI,
   and that its wheel builds and installs into a CLEAN virtualenv.
   Publishing to PyPI (D19) still needs a human to verify the name.

4. **The override-conflict UX** -- also closed on 2026-10-23.
   `qtranslate/qt/override_picker.py` offers one row per conflicted
   provider with every claimant AND the built-in (choosing nothing is a
   real choice), preselects the saved winner, and writes the choice
   through the core's `write_saved_overrides` -- the same reader
   `load_user_extensions` uses at startup. The tray menu shows
   "Choose the winning extensions..." only while a conflict exists.
   Pinned in `regress_qt_extension_ui.py`.

So the extension platform's audit list is fully closed. What remains
for the SDK is the RELEASE step, which is a human's: verify the PyPI
name and its usage rights (D19), then publish.

### 4.4 The docs that must follow this session's code

- `docs/roadmap/PROGRESS.md`: an entry for this session (the four
  bugs, the extension wiring, the macOS adapter).
- `docs/roadmap/TEST_RESULTS.md`: the suite count (135 now) and the
  assertion counts (81 in `regress_qt_features.py`, 16 in
  `regress_qt_extension_ui.py`).
- `docs/COMPATIBILITY_MATRIX.md`: the mouse-mode row now covers the Qt
  view; a row for the UI/theme/panel extension slots.
- `docs/EXTENSION_SDK.md`: what the host now does with a registered
  contribution (tray menu, panel strip, theme), which was "designed-for"
  when it was written.
- `docs/CURRENT_STATE.md`: the tkinter view is on its way out.

### 4.5 The gates

`docs/roadmap/BLOCKERS.md` still holds the two human-only gates
(B1: a human reviews the G9 screenshots; B2: a human writes the
waiver). Neither may be self-assigned. The only open bead is
`qt-fj5`, which is exactly those two.

## 5. How to run the app (this session's setup)

A virtualenv was created for the project because the Python on PATH is
uv-managed and refuses `pip install`:

```
uv venv C:/Users/ADMIN/qtranslate-re/.venv --python 3.12
uv pip install --python C:/Users/ADMIN/qtranslate-re/.venv/Scripts/python.exe \
    PySide6 keyboard pyperclip Pillow
```

Run it:

```
.venv/Scripts/python.exe -I start_qt.py google vi
```

The venv is in `.gitignore` (added this session).

## 6. The state of the tree when this file was written

- Working tree: the changes of this session, uncommitted.
- Pixel measure: mean ink diff **0.0037** over twelve screens
  (rgb 0.0355) -- unchanged by the Options refactor.
- Suites: **135 suites, 0 failed, 48.4s** (`python -I
  tools/run_suites.py`), re-run after the Options refactor. The new
  suites are `regress_qt_features.py` (81 assertions),
  `regress_qt_extension_ui.py` (16), `regress_platforms.py` (31) and
  `regress_extension_e2e.py` (20).

**A note on the run.** One sweep in this session came back with 82
suites failing, every one of them with exit code `0xC0000142`
(`STATUS_DLL_INIT_FAILED`) -- Windows refusing to initialise a DLL in
the freshly spawned process. Every one of those suites passes when it
is run on its own, and the next full sweep was 135/0. It was the
machine being out of resources (12 other Python processes were running
at the time: MCP servers and an unrelated project), not a defect in the
code. If a sweep comes back like that, check the process count and
re-run before believing it.
