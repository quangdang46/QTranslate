# PROGRESS

The running log. Newest first. Every entry names what changed and what
was run to show it.

## 2026-10-22 -- the user ran the app, and found four bugs

The PySide6 front end was handed to the user to try. Four things came
back, and all four were real defects rather than cosmetic ones.

**Ctrl+Q crashed the process.** The `keyboard` package fires a global
hotkey on its OWN listener thread, and the handler went straight to the
widgets from there. Qt does not guard cross-thread widget access: it is
an access violation, not a catchable exception, so the app died. The
fix is `_UiInvoker` and `QtApp._on_ui` in `qtranslate/qt/app.py`, and
`qtranslate/qt/hotkeys.py` wraps every registered callback in it. The
suite pins the marshalling (`regress_qt_features.py`, 81 assertions).

**The Options dialog opened a new window per page.** `OptionsBase._goto`
built a fresh page window and closed the old one. The shell is now ONE
window: the page's own `build()` is called again with the shell as
`self`, after pointing the instance's ORIGIN, SIZE and CHROME at the
page's own (the Hotkeys page's capture is a different size and its
chrome sits elsewhere). The measure is unchanged -- **0.0037** over
twelve screens -- because the chrome is described per page and the
widgets are hidden rather than deleted (deleting one with a paint event
still queued is the same access violation).

**The mouse mode did nothing.** The Qt front end had a label for it and
never started the hook; only the tkinter front end ever did. The hook,
the capture (OLEACC in the third mode, Ctrl+C + clipboard otherwise),
native's gate order and the mode's own names (the English lang.json,
ids 60/70/71) are all in place now, and native's third mode speaks the
selected text in BOTH front ends.

**The language combo's list ran off the screen.** NOT fixed; it is the
first item in `HANDOFF.md`. The combo lists all 75 provider languages;
native's lists a fixed set from its locale pack.

**The extension platform reached the UI.** The audit was right: the
registry existed, was tested, and nothing in the running app ever read
it. The Qt front end now loads the user extensions through the SAME
shared loader, keeps the manager (`extensions.last_manager()`), and the
tray menu, the theme's palette and the main window's panes read the UI
and theme slots. `tests/regress_qt_extension_ui.py` (16 assertions)
proves each of them, including that a window with no extension has no
panel strip, so the pixels stay the native's.

Also: the language table moved out of the tkinter module into
`qtranslate/languages.py` (Core), so the Qt view no longer imports
tkinter for two constants, and `qtranslate/platforms.py` gained a macOS
adapter whose per-user folder the extension loader can resolve.

```
135 suites, 0 failed, 48.4s
```

## 2026-10-22 -- the mouse mode and Ctrl+Q in the Qt front end

Native's mouse mode is the one that lets you BÔI ĐEN: select text in
another program, click, and the selection is captured and translated.
The Qt front end only had a LABEL for it -- the hook was never started,
so "bôi đen" did nothing. Ctrl+Q (the popup hotkey) DID work: it
translates the clipboard's text and shows the popup.

The wiring: `qtranslate/qt/app.py` now starts and stops the Win32
low-level mouse hook (`qtranslate/mouse_capture`) with the mode, and a
selection click captures the text and translates it through the same
`show_translation` step Ctrl+Q uses (the panes, the history, the popup).
The work runs on a worker thread and the result crosses to the UI thread
through a queued signal (`_MouseBridge`), because the hook's proc has to
return fast and the widgets belong to the UI thread.

Three things were wrong on the first pass, and each one was evidence:

- The mode names were the port's invention ("Translate in popup
  window", "Translate in main window"). The native's OWN strings are in
  the shipped English lang.json, ids 60/70/71: "Show icon", "Show
  translation", "Show translation and read". Corrected, with the source
  in the comment.
- The config write was missing: native keeps the mode in
  General.MouseMode (DAT_005493F8) and General.MouseModeOn, and the Tk
  front end writes both. The Qt front end wrote neither, so a restart
  lost the mode. Now it writes both, and the session restore reads them
  back -- the two front ends and the core share one state.
- The gate was half of native's. Native's order is EnableGuiTranslation
  (DAT_005494e4) -> EnableMouseModeOnCtrl -> exclusions -> the mode-2
  OLEACC capture -> the clipboard fallback. The port had folded
  `mouse_capture.available()` INTO the gate's try block, so a missing
  hook looked like a closed gate. Now the gate is its own function,
  `_mouse_gate_ok()`, in native's order.

Native's third mode speaks the selected text, and the Tk port had the
same half missing (its comment said "we do not have a TTS sink" -- but
the port HAS one: `player.play_text`, online mp3 first, offline SAPI
when that fails). Fixed in both: the mode's selection is now spoken
through the TTS chain in the Qt front end (`_speak`) and the Tk one
(`speak`).

The suite: `tests/regress_qt_features.py` now has 71 assertions (was
55), covering Ctrl+Q, the hook start/stop, the mode's config write, the
gate, both capture paths, the read-aloud half, and the worker-to-UI
handoff. `tools/render_qt.py --compare` is unchanged (the pixels did not
move): mean 0.0037 over twelve screens.

## 2026-10-22 -- the PySide6 parity programme, part two

**The font was wrong, and it was measurable.** The spec said Segoe UI
9pt and marked it as an inference. Measuring the ink width of the
native's own text against the candidates showed it is **Tahoma 8pt
(11px) for the controls and Tahoma 9pt (12px) for the two text panes of
the main window**: the native's "Double Ctrl => Show main window (with
translation of selected text, if any)" is 418px wide, which is Tahoma 9pt
(420) and not Tahoma 8pt (363). The spec and `qtranslate_style.py` were
corrected, and the measurement is written into the spec so it can be
re-checked.

**The measure was wrong, and it was measurable too.** The pixel
difference was counting ClearType fringes: the same glyph puts its ink
on different subpixels in the native than in the render, which is a
200-level difference in one channel for text that is identical. The
measure is now the total ink (the sum of the three channels), which is
what ClearType preserves. On the main window that took the number from
0.0926 to 0.0237 without changing a single pixel.

**The main window, measured against capture 2131:**

| | before | after |
|---|---|---|
| ink diff | - | **0.0144** |
| rgb diff | 0.1703 | 0.0611 |

What moved it: the real 16x16 icons recovered from the binary (the
back/forward arrows, the menu, the mic, the headphone, the new-document
button, the swap button), the provider strip with its nine real service
icons and native's own 56px geometry, the two text panes on native's
line box, the pane borders, the scrollbar at native's 17px, the splitter
grip, and the result pane's own "No data returned (timeout while sending
data)."

**The strip's short names were wrong.** Native draws `Go...` with THREE
dots, at x = 45, 49 and 53; the Tk port drew `Go..` with two. Fixed in
the Tk port, and the test that checked it now reads the rendered
widgets instead of grepping the source (the strip had moved from
`app.py` to `windows.py`, so the grep had been checking nothing).

**The Options page order was wrong in the test, not in the port.** The
test asserted the dialog TEMPLATE's order (Hotkeys seventh). The
native's RUNTIME order, read off the nav list in captures 2140/2141, has
Hotkeys SECOND. The port was right; the test was wrong. Fixed, with the
evidence in the comment.

**The settings defaults did not match the native's.** The native's real
`Options.json` had been lost from this machine, so the port's defaults
had become the only thing there was to read -- and they disagreed with
the native in three places: `ExpandHistoryItems` was `True` (the
native's is `False`), the `HotKeys` section carried three of the
native's seventeen keys (the native's file has all seventeen, unbound
being 0), and the hotkey table had the replace-selection code (343 =
Alt + W) on the wrong key. Corrected, and the test now asserts the
port's DEFAULT document rather than the user's live file, which is what
it was really about.

**The suite is green.**

```
133 suites, 0 failed, 67.0s
```

Three failures were fixed along the way, each a real defect and not a
test rewritten to pass:

- `regress_wiring.py` did not understand relative imports, so the new
  `qtranslate/qt` package's modules looked like orphans. The test now
  resolves them.
- `regress_options_pages_native.py` still expected tkinter `Labelframe`
  widgets, but the group boxes are drawn by hand since commit
  `fa77943` (a Win32 etched frame cannot be a `LabelFrame`). The group
  box now carries its caption, and the test reads it.
- `ui_match.py` had four assertions that read the live `Options.json`,
  which is the USER's file. They now read the port's defaults, and the
  placement codec is checked against the rect the native actually saved
  (`rcNormal` 786,228 -> 1316,658), which is on the record.

**Also landed:** `tools/ui_measure.py`, a tool that measures a native
capture (its client origin, its rows, its text bands, an ASCII dump of
any rectangle) -- the thing that made every number in this log
checkable.

## 2026-10-22 -- the first Qt window

The main window was built on the measured geometry and rendered against
capture 2131 for the first time: **0.1703** on the RGB measure, 0.1734
for the layout-only reference renderer. The reference renderer used the
spec's numbers, which were mostly right and had three errors: the pane
was 3px too far left, the font was wrong, and the result pane had no
text.

## 2026-10-22 -- the fresh-install bug

`config.load()` raised on a missing `Options.json`. The app persists a
setting from about 38 places and each one reads the file before writing
it, so on a machine with no settings file yet EVERY write raised and
was swallowed. A missing file is the state of a fresh install, not an
error: `load()` now yields the defaults, a corrupt file is moved aside,
and the app writes the defaults on first run.

The same commit fixed the `tk.PhotoImage` lifetime bug: an image
created without a `master=` died with the default root, and the icons
died with their window.

## 2026-10-15 to 2026-10-21 -- the phases before this

- Phase 7: five of the six window classes were extracted out of
  `app.py` and proven byte-identical (`qt-phase7-classes-landed-ifn`).
- Phase 8: the PyInstaller bundler and a Windows bundle that verifies
  (`qt-phase8-bundle-landed-fho`).
- G9 part (a): the native window spec fully recovered and cross-verified
  (`qt-g9-part-a-closed-qyy`).
