# Runtime Reliability Recovery Plan

Status: `DRAFT / RESEARCH`. This document plans the next reliability work. It
does not authorize implementation.

Updated: 2026-10-31

## Destination

For QTranslate users on Windows and macOS, restore confidence in the current
QTranslate 6.10-compatible app by first making Ctrl+Q selected-text translation
work end to end, then measuring and fixing other confirmed failures. Success is
based on reproducible acceptance runs against the actual app on both operating
systems, not only mocked callbacks or UI renders.

Keep the current product direction: QTranslate 6.10 compatibility, reliability,
extensions, and Windows plus macOS. Stabilize existing features before selecting
new ones. Upstream `ahatem/QTranslate` is a source of lessons and candidates,
not a parity checklist.

## User evidence and scope

- Reported symptom: selecting text in another app and pressing Ctrl+Q produces
  no response or popup.
- Affected platforms: Windows and macOS.
- The failure stage is unknown. No real reproduction or diagnostic log has been
  reviewed in this planning pass.
- The exact app artifact/build under test is unknown. The current `qtranslate.spec`
  and `tools/build_bundle.py` point to `start_qt.py` as the single packaged
  front end, while some older documents and the `start_qt.py` module docstring
  describe a retired Tk front end. Confirm the user's artifact before applying
  evidence from a specific code path.

### In scope

1. Diagnose Ctrl+Q independently on Windows and macOS.
2. Verify selection capture, translation, and popup display only after dispatch
   is proven.
3. Triage existing features from user-reported failures and platform acceptance
   gaps. Do not label an untested feature as broken.
4. Select future upstream-inspired work only after existing-feature acceptance
   results identify user value.

### Not in scope

- Full feature parity with upstream QTranslate.
- Replacing the current product direction or UI framework.
- Porting upstream Kotlin implementation code into this Python project.
- Adding new features before the Ctrl+Q and current-feature acceptance gaps are
  measured.

## Current evidence boundary

The Python source has an offline Ctrl+Q path test, seam-injected selection tests,
hotkey codec checks, and mocked registration checks. These do not prove that an
OS-level hotkey is registered, delivered, or displayed on a real desktop.

The current Qt route is:

`start_qt.py` -> `qtranslate.qt.app.main()` -> `qtranslate.qt.hotkeys.install()`
-> OS backend -> `QtApp.hotkey_popup()` -> `selection.copy_selection()` ->
translation worker -> UI dispatch -> popup.

Windows uses the `keyboard` package and marshals callbacks to Qt's UI thread.
macOS uses Carbon `RegisterEventHotKey`; commit `e0ac592` corrected the event
parameter used to read the hotkey ID. Neither path has a recorded real-desktop
acceptance run in the evidence reviewed here.

`QtApp.hotkey_popup()` currently falls back to clipboard contents when selection
capture returns empty. Whether that fallback can display stale text is an open
behavior decision, not a diagnosed cause of the reported no-response symptom.

## Work sequence

### M0. Identify the build and establish a reproducible baseline

**Priority:** P0. **Status:** blocked on user/runtime evidence.

Record, separately for Windows and macOS:

- App version, executable or app bundle path, and source commit if known.
- OS version, architecture, package type, and launch method.
- Whether global hotkeys are enabled and the configured Ctrl+Q binding.
- Target application and control where text is selected.
- Whether the app is visible or running from the tray.
- Result of one attempt with selected text and one attempt without selection.
- Startup registration logs and the hotkey/popup diagnostic log, if present.

Do not include selected text, clipboard contents, API keys, or other user data
in reports. Existing diagnostics should be inspected before adding new ones.

**Exit criteria:** one reproducible, evidence-backed row per OS, with the exact
artifact and the last confirmed stage in the event path.

### M1. Prove registration and event dispatch

**Priority:** P0. **Depends on:** M0.

Trace these boundaries separately:

1. The app starts the expected front end and reads the intended config.
2. Global hotkeys are enabled and Ctrl+Q decodes to the expected combo.
3. The platform backend is available and accepts the registration.
4. The OS delivers the registered event.
5. The action callback runs and reaches `hotkey_popup()`.
6. Callback work reaches Qt's UI thread safely on both platforms.

Do not patch capture or popup code to compensate for an unproven registration
failure. If existing logs cannot distinguish registration from event delivery,
specify the smallest safe diagnostic addition after the implementation gate is
open. Log metadata only.

**Exit criteria:** each OS has a recorded pass/fail at steps 1-6. A registration
success alone is not a dispatch pass.

### M2. Prove capture, translation, and popup

**Priority:** P0. **Depends on:** M1.

Once `hotkey_popup()` is confirmed to run, test each next boundary in order:

1. Selected text is copied from the foreground application.
2. Capture returns the new selection rather than stale clipboard data.
3. The translation request starts and returns a result or a visible error.
4. The result is marshalled to the UI thread.
5. The popup is created, positioned on the relevant display, and shown.
6. The source and result in history match the request.

Exercise a normal selection, a slow target application, no selection, an empty
clipboard, a stale clipboard, a translation failure, and multi-monitor
placement. Record current behavior before changing fallback semantics.

**Exit criteria:** the manual acceptance cases pass on both OSes, or a specific
failure stage and regression test are recorded.

### M3. Triage the rest of the current feature set

**Priority:** P1. **Depends on:** M2 baseline.

Use the existing feature and compatibility matrices as inventories, not proof
of current runtime behavior. Prioritize actual user-reported failures and
high-frequency desktop flows: provider translation and fallback, clipboard,
history, tray and settings, selection capture, popup placement, extensions,
dictionary, OCR, and speech. For each row record:

- `OBSERVED`, `UNVERIFIED`, `PLAUSIBLE RISK`, or `NOT REPORTED`.
- Exact platform and artifact tested.
- Reproduction steps and evidence.
- A root-cause hypothesis only when evidence distinguishes it.
- A regression test or manual acceptance procedure.

Do not reopen working features solely because an upstream issue mentions a
similar symptom.

**Exit criteria:** every P0/P1 row has a real acceptance result, an owner and
next action, or a documented reason to defer.

### M4. Select upstream-inspired features

**Priority:** P2. **Depends on:** M3.

Choose only the candidates that address a measured user problem. The
reference audit records lessons around conflicting hotkeys, held modifiers
during synthetic copy, stale input, and multi-monitor popup behavior. These
are hypotheses for Python acceptance tests, not claims that the Python app has
the same defects.

**Exit criteria:** each selected feature has a target requirement, user
rationale, implementation boundary, and Windows/macOS verification plan.

### M5. Cross-platform release acceptance

**Priority:** P1. **Depends on:** M3 and selected M4 work.

Run the deterministic regression suite and packaged-app acceptance on Windows
and macOS. Keep automated tests, desktop behavior tests, and pixel-fidelity
tests as separate evidence types. Update stale status documentation only from
current runs.

**Exit criteria:** each supported OS has a named artifact, test record, and
pass/fail result for the acceptance rows included in that release.

## Requirements

These are proposed runtime requirements for the recovery work. They become
implementation contracts only after the project gate is open and any open
product behavior is resolved.

| ID | Priority / status | Requirement | Verification |
|---|---|---|---|
| `REQ-CTRLQ-001` | P0 / PROPOSED | When global hotkeys are enabled and Ctrl+Q is configured, the actual Windows and macOS packages must register and dispatch the action from an external application. | `TEST-CTRLQ-WIN`, `TEST-CTRLQ-MAC` |
| `REQ-CTRLQ-002` | P0 / PROPOSED | A dispatched Ctrl+Q with selected text must capture that current selection, translate it, and show the result in the popup. | `TEST-CTRLQ-WIN`, `TEST-CTRLQ-MAC`, `TEST-CTRLQ-FAILURE` |
| `REQ-CTRLQ-003` | P0 / PROPOSED | A capture failure must not present unrelated stale clipboard contents as the selected text. | `TEST-CTRLQ-NEGATIVE` |
| `REQ-CTRLQ-MAC-001` | P0 / APPROVED, SCOPED | macOS Ctrl+Q requests Accessibility only after the user invokes Ctrl+Q, then uses Command+C. A denied or failed capture returns no selection and must not translate the old clipboard. No permission request occurs at startup and no copied content is logged. | `TEST-CTRLQ-MAC-PERMISSION`, offline sender and capture regressions |
| `REQ-DIAG-001` | P1 / PROPOSED | Diagnostics used for runtime triage must identify the failing stage without recording selected text, clipboard content, credentials, or translation output. | Review log fields during `TEST-CTRLQ-WIN` and `TEST-CTRLQ-MAC` |
| `REQ-CURRENT-001` | P1 / PROPOSED | A feature may be called behavior-verified for Windows and macOS only after a passing acceptance run on each supported OS and the named package. | `TEST-CURRENT-FEATURES`, `TEST-RELEASE-OS` |

## Acceptance IDs

| ID | Acceptance |
|---|---|
| `TEST-CTRLQ-WIN` | On the actual Windows package, select text in at least two external applications, press configured Ctrl+Q, and record registration, callback, capture, translation, and visible-popup outcomes. |
| `TEST-CTRLQ-MAC` | Repeat `TEST-CTRLQ-WIN` on the actual macOS package, recording Carbon registration and event delivery separately. |
| `TEST-CTRLQ-MAC-PERMISSION` | With the actual macOS package not yet trusted, press Ctrl+Q and confirm the system Accessibility prompt appears only then. After granting access, repeat and verify current selection capture. If permission is denied or injection fails, verify stale clipboard text is not translated. |
| `TEST-CTRLQ-NEGATIVE` | With no selection and a known stale clipboard, verify the behavior explicitly. No prior clipboard text may be mistaken for the current selection. |
| `TEST-CTRLQ-FAILURE` | Simulate or induce capture and translation failures separately; verify a bounded, visible, non-misleading outcome. |
| `TEST-CTRLQ-DISPLAY` | Verify popup placement on primary and secondary displays, including a display arranged with negative desktop coordinates where supported. |
| `TEST-CURRENT-FEATURES` | Run prioritized feature rows on both supported OSes and bind each result to its exact artifact. |
| `TEST-RELEASE-OS` | Run deterministic tests plus packaged acceptance on Windows and macOS; do not infer one platform's result from the other. |

## Readiness and handoff

**Implementation readiness: AMBER, scoped to Ctrl+Q only.** On 2026-10-31 the
operator explicitly accepted the unresolved G9 risk and authorized this one
workstream. `docs/PROJECT_VISION.md` records the exception. The general
implementation gate remains closed, and the exception does not authorize
unrelated production changes or full upstream parity.

The exact user-tested artifact remains unknown, so the first implementation
action is still evidence collection. This work is R3 because it crosses the
global-input and OS event boundary. Failure modes include a shortcut that is
not registered, an event that is not delivered, a callback on the wrong
thread, stale selection data, translation failure, and a popup that is created
but not visible. Rollback is limited to reverting the narrow Ctrl+Q changes
and their tests; preserve all other working-tree changes. Do not claim
cross-platform success without desktop acceptance on Windows and macOS.

**Next smallest action:** identify the exact app build tested on each OS and
review the existing startup and popup logs for those attempts. Then continue
with M0/M1. The available macOS log currently proves only that Carbon accepted
bindings at an earlier time; it does not prove delivery during the reported
failure.

## Research documents

- [Reconnaissance](RELIABILITY_RECONNAISSANCE.md)
- [Research register](RELIABILITY_RESEARCH_REGISTER.md)
- [Evidence log](RELIABILITY_EVIDENCE_LOG.md)
- [Decision map](RELIABILITY_DECISION_MAP.md)
- [Upstream reference audit](UPSTREAM_REFERENCE_AUDIT.md)
