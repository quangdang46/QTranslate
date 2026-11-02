# Upstream Reference Audit: `ahatem/QTranslate`

Status: `INITIAL`, reviewed 2026-10-31. This is a bounded audit of findings
relevant to runtime reliability and future feature selection, not a full
feature comparison.

## Source and reuse boundary

- Repository: <https://github.com/ahatem/QTranslate>
- Local checkout inspected: `/tmp/QTranslate-upstream-20261031`
- License: upstream `LICENSE` identifies Mozilla Public License 2.0.
- Relevant source: upstream changelog, `MainGlobalKeyListener.kt`, and
  `MainGlobalKeyListenerTest.kt`.

No upstream implementation code is proposed for copying. This project is
Python/PySide6 and the reference is Kotlin/Swing. Transfer only test ideas and
failure-handling principles where the Python evidence justifies them.

## Findings and transfer

| Source finding | Evidence | Interpretation | Classification | Target decision | Validation |
|---|---|---|---|---|---|
| A single conflicting global shortcut previously caused the complete hotkey set to be rejected. | Upstream `CHANGELOG.md`; `MainGlobalKeyListener.kt::isolateRejectedBindings`; `MainGlobalKeyListenerTest.kt` conflict tests. | Partial registration can preserve unrelated working shortcuts, but the Python backend and current failure must be measured first. | `ADAPT` | `DEC-006`, then consider during M3 if observed. | Simulate a conflict in a Python backend test; verify independent acceptance on each OS. |
| A held modifier can contaminate a synthetic Ctrl+C and trigger another app's shortcut. | Upstream changelog; `MainGlobalKeyListener.kt::captureForHotkey` and `awaitCopyNeutral`. | Modifier neutralization is a safety/test scenario for selection capture. It is not evidence of a Python defect. | `ADAPT` | `DEC-006` and `DEC-008`. | Run capture tests with held Ctrl/Shift/Alt/Meta and real target applications. |
| Rapid input can make a result reflect stale state. | Upstream issue #413 and related changelog entry. | Verify request/result ownership and stale completion behavior in the Python path before adapting any coordination mechanism. | `INVESTIGATE` | `DEC-008`. | Reproduce with overlapping requests; assert a result cannot replace newer state unexpectedly. |
| Popup placement can jump to the primary display or behave poorly with multiple monitors. | Upstream issue #412; upstream changelog multi-monitor entries. | Use as a test case, not a claim that the Python placement code fails. | `ADAPT` | `DEC-006`, `DEC-008`. | `TEST-CTRLQ-DISPLAY` against the actual app on each OS. |
| Long results may need a scrollable popup. | Upstream issue #416. | This is a candidate only if current popup behavior or user feedback demonstrates truncation. | `INVESTIGATE` | `DEC-009`. | Test long translations and establish an observed need before planning a UI change. |
| Pinned-language behavior may differ in a popup. | Upstream issue #410. | Potential feature gap, not a reliability issue and not automatically in scope. | `DEFER` | `DEC-009`. | Revisit after stabilization if the user requests it. |

## Traceability notes

The upstream fixes and test cases are not portable by assumption. The target
app's backend, event loop, capture method, settings format, popup implementation,
and platform constraints differ. Any adopted idea must map to:

1. A confirmed Python-side symptom or a user-selected feature.
2. A requirement in the recovery plan.
3. A regression test plus Windows and macOS acceptance where the OS boundary
   is involved.
