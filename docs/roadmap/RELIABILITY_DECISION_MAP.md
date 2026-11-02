# Reliability Recovery Decision Map

This file records product choices separately from open technical questions.
Detailed evidence lives in `RELIABILITY_EVIDENCE_LOG.md`; the work sequence is
in `RELIABILITY_RECOVERY_PLAN.md`.

## Settled

| ID | Decision | State | Source |
|---|---|---|---|
| `DEC-001` | Keep the current QTranslate 6.10 compatibility, reliability, extension, Windows and macOS direction. | `LOCKED` | `docs/PROJECT_VISION.md`, D1-D20 |
| `DEC-002` | Stabilize current features before adding more; Ctrl+Q is the first runtime priority. | `LOCKED` | User decision in the planning conversation |
| `DEC-003` | Do not pursue full upstream feature parity in this work. | `LOCKED` | User decision in the planning conversation |
| `DEC-004` | Treat Windows and macOS as separate acceptance targets. | `LOCKED` | User reports the same no-response symptom on both |
| `DEC-011` | Permit one bounded Ctrl+Q diagnosis/fix/test slice while G9 remains blocked; preserve the residual G9 risk and do not open general Phase C work. | `APPROVED, SCOPED` | User approval on 2026-10-31; recorded in `docs/PROJECT_VISION.md` |
| `DEC-012` | On macOS Ctrl+Q only, request Accessibility access on the user's first action and use Command+C to capture selection. If capture fails, do not translate stale clipboard text; do not log copied content. | `APPROVED, SCOPED` | User approval on 2026-10-31 |

## Open

| ID | Question | State | Depends on | Reopen or resolve with |
|---|---|---|---|---|
| `DEC-005` | Which exact executable, app bundle, and commit did the user test on each OS? | `OPEN` | `RQ-001` | Record build identity before interpreting logs or code paths. |
| `DEC-006` | At which boundary does Ctrl+Q stop on each OS? | `OPEN` | `RQ-002` to `RQ-004` | Stage-specific desktop evidence from M0-M2. |
| `DEC-007` | If the selected-text copy fails, should Ctrl+Q fall back to clipboard text or fail without translating unrelated text? | `OPEN` | `RQ-005` | Compare native evidence and confirm expected UX; test stale clipboard explicitly. |
| `DEC-008` | Which other features deserve P0/P1 acceptance after Ctrl+Q? | `OPEN` | `RQ-006` | Use user reports and M3 results, not upstream issue similarity alone. |
| `DEC-009` | Which upstream-inspired additions are worth implementing after stabilization? | `DEFERRED` | `RQ-009` | Revisit only after M3 establishes current reliability. |

## Gate dependency

| ID | Decision | State | Source |
|---|---|---|---|
| `DEC-010` | General production implementation may begin only after the explicit gate in `docs/PROJECT_VISION.md` is approved. | `BLOCKED` | `docs/PROJECT_VISION.md` and `docs/roadmap/BLOCKERS.md` |

The RE coverage checklist and `docs/roadmap/BLOCKERS.md` identify the remaining
human G9 review and waiver. This planning package is not that approval and
cannot self-authorize code changes. `DEC-011` is the only current exception.

## Dependency sketch

```text
DEC-005 / exact build
        |
        v
M0 reproduce each OS
        |
        v
DEC-006 / failing boundary
        |
        +--> M1 hotkey registration and dispatch
        |
        +--> M2 capture, translate, popup
                    |
                    v
DEC-007 / stale-clipboard behavior
                    |
                    v
M3 existing-feature acceptance
                    |
                    v
DEC-008 and DEC-009 / select next work
```
