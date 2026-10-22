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
mean ink difference is 0.0194 over ten screens, and the per-screen
numbers are in `BASELINE_RESULTS.md`.

## B2 -- G9's waiver needs a human to write it

**Bead:** `qt-fj5` (the second, separate requirement)

**What it is.** Closing the G9 row needs a WAIVER token, and the
validator only validates a token a human put in the document -- it never
assigns one. The gate arithmetic depends on that token, so no agent may
self-assign it. The gate currently reads `BLOCKED (1)`.

**What unblocks it.** A human writes the token into the document the
validator reads.

## B3 -- the macOS bundle cannot be produced or verified here

**Bead:** `qt-3ro` (open, priority 2)

**What it is.** The Windows bundle is done (`qt-phase8-bundle-landed-fho`:
PyInstaller onedir, `tools/build_bundle.py`, a frozen-exe selftest
18/18). What is left is macOS. A macOS bundle can be neither produced
(nothing to build it on) nor verified (nothing to run it on) from an
AMD64 Windows machine. Building it blind and claiming it would be a
claim with no artifact, which is exactly what this project's honesty
rules forbid.

**What unblocks it.** A macOS host, or a hosted macOS runner, that runs
`tools/build_bundle.py`'s own verify step. That is the agent-tractable
remainder, and it is a machine, not a decision.

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

## B6 -- the Tk `MainWindow` is still one class

**Bead:** `qt-o7p` (open, priority 2) -- a SCOPING question, not a
defect.

**What it is.** Five of the six window classes were extracted out of
`app.py` (Phase 7). The sixth, `MainWindow`, was deliberately not
started, and the bead says why: it is not a window hanging off the app,
it IS the app -- the panes, the translation orchestration, the hotkey
routing and the clipboard monitor, cross-referenced far more tightly
than the five extracted windows were. Cutting it out is a large
restructure of the code the UI is built from.

**Where it stands now.** The PySide6 front end is a second view over the
same core, and it is the one the parity programme is driving the UI
towards. The Tk `MainWindow` is the view that is being replaced, so
restructuring it is work on the view that is on its way out.

**What unblocks it.** A decision on whether the Tk front end stays
supported after the Qt one lands, and if it does, whether the split is
worth the risk. This is a product call, not a technical one.

## Not blockers

- **The ClearType residual.** The ink difference that is left on the
  text is the sub-pixel phase, which no renderer reproduces exactly. It
  is measured, bounded and reported; it is not a defect to be fixed.
- **The 14px vs 13px Options page order.** The native draws the Options
  dialog at two sizes (663x388 for Hotkeys, 646x389 for the rest). The
  Hotkeys page declares its own `ORIGIN` and `SIZE`, so both are
  reproduced.
