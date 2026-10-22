# BLOCKERS

What is stopping work, and what exactly would unblock it. A blocker
here is a thing no agent may clear on its own: it needs a person, a
machine, or a decision.

## B1 -- G9 part (b): the screenshot review needs a human

**Bead:** `qt-fj5` (open, priority 1)

**What it is.** The G9 gate is closed by comparing the native's window
with the port's, pixel by pixel, and confirming the capture was taken
under the right conditions. `G9_HARNESS.md` sections 3.1 and 6 say a
PASS is only ELIGIBLE for review: a human has to open `native.png`,
`port.png` and `diff.png` and confirm the circumstances. The screenshot
ban forbids an agent from doing that.

**Why it is not a capability problem.** This host CAN run the native --
AMD64 Windows, SysWOW64, the same 1 462 272-byte PE32. The native's
window was captured here, and the captures are in
`docs/review/native_screens/`. What is missing is the human judgement
that the capture is a fair comparison, and the rule says an agent may
not make that call.

**What unblocks it.** A human opens the three images and writes the
verdict. The pixel measurement this project CAN do is already done: the
mean ink difference is 0.0037 over twelve screens, and the per-screen
numbers are in `BASELINE_RESULTS.md`.

## B2 -- G9's waiver needs a human to write it

**Bead:** `qt-fj5` (the second, separate requirement)

**What it is.** Closing the G9 row needs a WAIVER token, and the
validator only validates a token a human put in the document -- it never
assigns one. The gate arithmetic depends on that token, so no agent may
self-assign it. The gate currently reads `BLOCKED (1)`.

**What unblocks it.** A human writes the token into the document the
validator reads.

## B3 -- the macOS bundle: CLOSED, and the premise was wrong

**Bead:** `qt-3ro` -- **closed** 2026-10-21.

**What it was.** The Windows bundle is done (`qt-phase8-bundle-landed-fho`:
PyInstaller onedir, `tools/build_bundle.py`, a frozen-exe selftest 18/18).
What was left was macOS, and the bead claimed that a macOS bundle could
be neither produced nor verified from an AMD64 Windows machine.

**How it closed.** The premise was wrong: the machine that did the
Phase 8 work IS macOS arm64, and the bundle builds and verifies there
(`dist-mac/QTranslate/QTranslate --selftest PASS 17/17`, commit
`91d454b`). So the remainder was agent-tractable after all.

**What is left of it here.** The bundle builder now carries the
PySide6 front end as a second entry point (`start_qt.py` ->
`QTranslate-Qt.exe` beside `QTranslate.exe`, one shared `_internal`),
which was done on this Windows host. The macOS side of that change has
not been rebuilt on a macOS host, because there is no macOS host here.

## B4 -- the Options "Basics" page has no native capture

**Bead:** none -- a gap in the evidence, recorded so it is not lost.

**What it is.** The eight Options pages that were captured (2135-2141
and 2126) cover Internet, Services, Languages, Appearance, Exceptions,
Advanced, Updates and Hotkeys. There is no capture of the FIRST page,
Basics (DLG171). The page is implemented from the settings the port
supports, not from a measured picture, and it is therefore the one
Options page whose layout is not evidence-backed.

**What unblocks it.** One capture of native's Options dialog with the
Basics page open. It is a single screen on this machine -- the native
runs here -- so it needs a person to open it and take the shot.

## B5 -- the native's real `Options.json` is gone from this machine

**Bead:** none -- a lost input, mitigated.

**What it was.** The native's own settings file, at
`%APPDATA%/QTranslate/Options.json`. It was the input for the settings
defaults, and it is no longer on this machine.

**What was done about it.** The values that were read out of it before it
went are in `qtranslate/config.py`'s `default_config()` and in the
`DEFAULT_*` tables, and the test that checked them now checks the
port's DEFAULT document rather than whatever happens to be on disk. Two
values could not be recovered and were NOT invented: the hotkey codes of
the fifteen actions the native leaves unbound are 0, and the saved
window placement is a user setting, so a fresh install has none and the
codec is checked against the rect the native saved, which is on the
record in `G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md`.

## B6 -- the Tk `MainWindow` split: CLOSED

**Bead:** `qt-o7p` -- **closed** 2026-10-21.

**What it was.** Five of the six window classes had been extracted out
of `app.py` (Phase 7). The sixth, `MainWindow`, was deliberately not
started: it is not a window hanging off the app, it IS the app -- the
panes, the translation orchestration, the hotkey routing and the
clipboard monitor -- and cutting it out was a large restructure of the
code the UI is built from, with no fidelity signal to verify it by.

**How it closed.** The deferral's stated reason was gone: the port's own
window CAN be captured on the host, so a restructure has a signal. The
main window's body is now `qtranslate.windows.MainWindow`, with
`app.py` keeping a thin delegator for each of the 50 moved methods, and
it was verified behaviour-preserving -- the widget geometry before and
after the split is identical band for band, with the suite green.
`docs/review/PHASE7_APP_SPLIT_2026-10-16.md`.

**What it means for the Qt port.** The Tk front end is whole again, and
the PySide6 one is a second view over the same core. The two share the
core, not the widgets.

## The bead state, as the tracked record has it

`.beads/issues.jsonl` is the git-tracked record (the SQLite database is
gitignored and, on this host, a schema the installed `bd` cannot open
-- "historical SQLite workspace detected"). Six of the seven beads are
closed:

| Bead | State | Closed |
|---|---|---|
| `qt-ekh` | the tray X:/Y: readout, verified against native | 2026-10-16 |
| `qt-phase7-classes-landed-ifn` | 5 of 6 window classes extracted, byte-identical | 2026-10-16 |
| `qt-phase8-bundle-landed-fho` | the bundler chosen, a Windows bundle that verifies | 2026-10-16 |
| `qt-g9-part-a-closed-qyy` | the native window spec recovered and cross-verified | 2026-10-16 |
| `qt-3ro` | the macOS bundle | 2026-10-21 |
| `qt-o7p` | the MainWindow split (6 of 6) | 2026-10-21 |
| `qt-fj5` | **open** -- G9 part (b) | -- |

So the one open bead is B1/B2, the human-only gate.

## Not blockers

- **The ClearType residual.** The ink difference that is left on the
  text is the sub-pixel phase, which no renderer reproduces exactly. It
  is measured, bounded and reported; it is not a defect to be fixed.
- **The 14px vs 13px Options page order.** The native draws the Options
  dialog at two sizes (663x388 for Hotkeys, 646x389 for the rest). The
  Hotkeys page declares its own `ORIGIN` and `SIZE`, so both are
  reproduced.
