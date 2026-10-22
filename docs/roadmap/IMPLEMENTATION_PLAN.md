# IMPLEMENTATION PLAN

The ten gates, what each one demands, and where it stands. The gates are
ordered: each one is the precondition for the next, and a gate is not
"passed" because the code looks right -- it is passed when the evidence
in the "Gate" column exists and has been run.

## G0 -- Baseline and inventory

**Demands:** an inventory of what exists, a measured baseline, and a
feature matrix, before anything is built.

**Gate:** `PROJECT_INVENTORY.md`, `BASELINE_RESULTS.md` and
`FEATURE_MATRIX.md` exist in this directory, and every number in them
came out of a run.

**State:** DONE (2026-10-22).

## G1 -- Reverse-engineering closure

**Demands:** the native's windows, controls and strings are known well
enough to be reproduced, and the gaps are named rather than guessed.

**Gate:** the RE coverage checklist has no row that is `UNKNOWN` without
a reason, and the DLG129 control list is cross-verified against a second
source.

**State:** DONE for the windows (`G9_PART_A_CLOSED_2026-10-16.md`). The
remaining gap is the G9 screenshot review, which is G9, not G1.

## G2 -- Feature matrix

**Demands:** every native feature has a row, with its native evidence,
its port state and its test.

**Gate:** `docs/COMPATIBILITY_MATRIX.md` (223 lines, the row-level view)
and `FEATURE_MATRIX.md` (the gate-level view).

**State:** DONE.

## G3 -- Core and SDK contracts

**Demands:** the core is toolkit-agnostic and the contracts (the
`Result` shape, the provider contract, the extension manifest, the SDK)
are pinned by tests, so a front end cannot change them by accident.

**Gate:** the core imports no toolkit. `regress_wiring.py` names the
orphan set and fails if it grows.

**State:** DONE. The Qt view was built on top of the core without
changing it.

## G4 -- Extension platform

**Demands:** an extension can add a provider, a theme or a UI, and the
app loads it.

**Gate:** `regress_extension_*`, and the three shipped example
extensions (`hello_provider`, `custom_theme`, `custom_ui`).

**State:** DONE.

## G5 -- The move of the logic out of the UI

**Demands:** the windows are views. A window may not own translation
logic, persistence or network calls.

**Gate:** the Qt view calls `engine.translate()` and `config`; it owns
no provider code. The Tk view's five window classes were extracted from
`app.py` for the same reason (`qt-phase7-classes-landed-ifn`).

**State:** DONE for the Qt view. The Tk `MainWindow` is still one
class -- that is bead `qt-o7p`, and it is a scoping question, not a
defect (see `BLOCKERS.md`).

## G6 -- Feature parity

**Demands:** every window and every control the native has, the port has.

**Gate:** the render-and-compare pipeline, with a number per screen.

**State:** DONE for the main window, the Dictionary and eight of the
nine Options pages. The History and the keyboard are in flight
(`PROGRESS.md`).

## G7 -- Reliability

**Demands:** a provider that fails does not take the app with it.

**Gate:** `reliability.py`, the fallback router, `ProviderHealth`, and
`regress_reliability.py`.

**State:** DONE.

## G8 -- UI and platform parity

**Demands:** the pixels match the native, and the platform-specific
behaviour is in the right place.

**Gate:** the ink diff per screen (`BASELINE_RESULTS.md`).

**State:** the mean ink diff is **0.0194** over ten screens. The residual
is ClearType phase and icon edges, not layout.

## G9 -- Packaging

**Demands:** a bundle that runs.

**Gate:** `tools/build_bundle.py`, a PyInstaller onedir bundle, and a
frozen-exe selftest (18/18).

**State:** DONE for Windows (`qt-phase8-bundle-landed-fho`). The macOS
bundle is BLOCKED -- see `BLOCKERS.md`. The G9 screenshot review is also
BLOCKED -- see `BLOCKERS.md`.

## G10 -- Final acceptance

**Demands:** the whole suite green, the docs true, no claim without
evidence.

**Gate:** `tools/run_suites.py` exits 0, and every document's claims
point at a run.

**State:** the suite is green (133 suites, 0 failed). The final
acceptance waits on the two blocked gates.

## The order the work was done in

1. The core was extracted and pinned, so that a second front end could
   be built without touching it.
2. The native's windows were measured off the captures, pixel by pixel.
3. The Qt view was built on the measured geometry, one window at a time,
   each one verified by rendering it and comparing it with the capture.
4. The spec was corrected where the measurement contradicted it (the
   font, the link colour, the strip's colours).
5. The defaults were corrected where the native's real settings file
   disagreed with the port's.
