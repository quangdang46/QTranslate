# Reliability Recovery Research Register

Status labels: `OPEN`, `INVESTIGATING`, `ANSWERED`, `DEFERRED`.
Priorities: `P0` blocks diagnosis or the first acceptance milestone, `P1`
changes the recovery sequence or release evidence, `P2` can wait until the
current feature set is measured.

| ID | Priority / status | Question | Why it matters and decision affected | Best method / next action |
|---|---|---|---|---|
| `RQ-001` | P0 / OPEN | Which exact app artifact and build were tested on Windows and macOS? | The repo contains a Qt runtime path and stale documents describing a retired Tk path. Diagnosis must match the user's executable. | Record executable or bundle path, app version, source commit if known, launch method, and package type for each OS. |
| `RQ-002` | P0 / INVESTIGATING | On each OS, does startup load the intended hotkey setting and does the OS accept Ctrl+Q registration? | Separates config/backend/registration failures from event-dispatch and later failures. | Inspect `~/.qtranslate_hotkeys.log`, config state, and startup output from the exact artifact. |
| `RQ-003` | P0 / OPEN | Does a real Ctrl+Q event invoke `QtApp.hotkey_popup()` on each OS? | A registered binding does not prove the OS delivers it. | Correlate backend event evidence with `qt_mouse_debug.log`; add only minimal metadata diagnostics if current logs cannot distinguish the boundary after gate approval. |
| `RQ-004` | P0 / OPEN | If the action runs, which first stage fails: selection copy, translation, UI dispatch, popup construction, or display? | Determines the smallest corrective change and regression test. | Run the staged procedure in M2 of `RELIABILITY_RECOVERY_PLAN.md`, recording only status and lengths. |
| `RQ-005` | P1 / OPEN | What should Ctrl+Q do when selection capture fails but the clipboard still contains unrelated text? | The current app falls back to clipboard contents; stale input can produce a misleading translation. | Compare native behavior evidence and user intent; test empty and stale clipboard cases before fixing policy. |
| `RQ-006` | P1 / OPEN | Which other existing features fail in normal use, on which platform and artifact? | Avoids treating old status tables or upstream reports as proof of Python defects. | Collect user repros and run the prioritized `TEST-CURRENT-FEATURES` matrix. |
| `RQ-007` | P1 / OPEN | Does the macOS package used by the user include the Carbon registration code and required Qt runtime? | The current machine is macOS, but actual package and user runtime are unknown. | Verify the user's package version and run the packaged app's startup and hotkey tests on macOS. |
| `RQ-008` | P1 / OPEN | Which current documentation accurately describes supported packages and feature status? | Stale entry-point and platform claims can send debugging toward the wrong runtime. | Reconcile the inventory, feature matrix, blocker record, and current artifacts after M0. |
| `RQ-009` | P2 / DEFERRED | Which upstream-inspired feature, if any, should follow stabilization? | The user chose stability first and rejected full upstream parity. | Revisit after M3; rank by confirmed user impact and implementation cost. |

## Completion rule

Do not mark `RQ-002` or `RQ-003` answered from static code inspection alone.
Do not mark `RQ-004` answered from a mocked callback. Each operating system
needs its own artifact-bound desktop evidence.
