# QTranslate-RE — Project Vision

> Status: **PLANNING (no implementation started).** This document records the
> locked product direction agreed before any new code is written. It is a
> decision record, not a proposal. Anything not marked *LOCKED* is still open.

## 0. Mandatory gate — read this before touching code

This project has three **distinct** phases and they do not collapse into each
other:

| Phase | What happens | Who can start it |
|-------|--------------|-------------------|
| **A — RE** | Inventory and verify native QTranslate 6.10 behavior (binary via Ghidra, JS sources, assets, Options.json, live traffic) against the Python port. Every item gets an evidence state (§7a). | ongoing |
| **B — Doc audit** | Cross-check all docs in `docs/` against each other and against Phase A evidence; fix contradictions, unproven claims, missing coverage. Markdown edits only. | ongoing, in parallel with A |
| **Gate — RE-complete approval** | The RE coverage checklist (`RE_COVERAGE_CHECKLIST.md`) has every in-scope item resolved to `VERIFIED` or `UNRECOVERABLE (reason + impact)` — never silently dropped — and the user approves explicitly. | — |
| **C — Implementation** | Writing or refactoring application code, migration, SDK, adapters. | **only after the Gate is explicitly approved by the user** |

**Finishing or approving a Markdown document does not open the Gate.**
Agreeing on D1–D20, or any future document edit, is Phase B work and does
**not**, by itself, authorize Phase C. The Gate is a separate, explicit act
tied to RE coverage — not to documentation tidiness.

## 1. Why this project exists

The starting point is not "reimplement QTranslate for fun". It is three real
problems with the original QTranslate 6.10.0:

1. **Windows-only.** QTranslate 6.10.0 is a Win32 binary. The user wants to
   use it on macOS as well.
2. **It frequently fails to translate.** A provider drops, an endpoint
   changes, a session token expires, and the user gets "no data returned"
   with no recovery. This is the single biggest day-to-day pain point.
3. **It is a closed monolith.** Every provider, every UI detail, every
   workflow is compiled in. Users cannot add a provider, restyle the popup,
   or change the translation flow without a rebuild.

The response is **not** to patch the closed binary. It is to build a
**cross-platform Core + Extension platform** that (a) preserves QTranslate
6.10 behavior for users who depend on it, (b) is reliable by design, and
(c) lets users — internal team and community — extend it in Python without
touching Core.

## 2. The three-layer model

```
User extensions   (physical folder, Python, loaded at startup)
       │  override / extend via published SDK contracts
QTranslate Core   (translation engine, reliability, config, storage, events)
       │  uses platform interfaces, never OS APIs directly
Platform Adapters (Windows · macOS: hotkey, clipboard, capture, audio, window)
       │
Desktop UI (Tkinter, unchanged framework) + built-in features (packaged in build)
```

The developer experience the project is aiming for:

```python
# User writes an extension using the published SDK, drops the folder in, restarts.
from qtranslate_sdk import TranslationProvider, register

@register.provider(id="provider.my_google", replaces="provider.google")
class MyGoogle(TranslationProvider):
    async def translate(self, req): ...
```

## 3. Locked decisions

These were explicitly confirmed during planning. They are the contract the
architecture must satisfy.

| # | Area | Decision |
|---|------|----------|
| D1 | **Target product** | A redesigned Core/Extension platform built *from* QTranslate (not a patch of the binary, not a unrelated new app). |
| D2 | **Platform scope** | Cross-platform. MVP ships **Windows + macOS day one** — no "Windows first, port later". |
| D3 | **UI framework** | Keep the current Python UI framework (Tkinter). Do **not** migrate to Qt/wx/Electron. |
| D4 | **UI approach** | Redesign module boundaries and extension points, but do not treat the current UI as pixel-perfect truth. |
| D5 | **Extension language** | Python only. SDK published as a Python package. |
| D6 | **Extension source** | Built-in first, external published under the **same contract** (difference is distribution + trust policy, not API). |
| D7 | **Extension install** | Copy a folder into the extensions directory, then **restart** the app. **No realtime hot reload.** |
| D8 | **Override level** | C — MVP supports per-component override (provider / theme / UI part); Core is designed so deeper override can be added later without breaking the API. |
| D9 | **Custom UI (MVP)** | Level B — theme/color/font **plus** adding new panel / widget / menu / popup. Replacing the entire main UI is not an MVP requirement but must not be architecturally blocked. |
| D10 | **Compatibility** | Level A — preserve nearly all QTranslate 6.10 behavior and features; fix bugs and improve reliability underneath. |
| D11 | **Core responsibility** | Option 2 — Core owns shared logic (capture→translate→history orchestration, config, storage, events). UI is presentation only. |
| D12 | **Provider failure** | B — bounded retry, then **automatic fallback** to the next available provider. |
| D13 | **Architecture order** | B — design Core/Extension first, then migrate features into it (do not refactor incrementally around the current app.py layout). |
| D14 | **Distribution** | Bundled extensions + install from package/folder. No marketplace, no store (yet). |
| D15 | **Reliability scope** | Reliability is a **Core** concern, not per-provider. |
| D16 | **Extensions folder** | Per-user app-data dir, one per OS. Never auto-load extensions from the install directory. |
| D17 | **Dependencies** | The app bundles the Python runtime; an extension may vendor its own dependencies **inside its own folder**. No automatic `pip install` or dependency download at startup. |
| D18 | **Override conflict** | Two extensions replacing the same id → Core reports the conflict and the **user picks the winner**. Never auto-resolve by scan order, load order, or id. Winner fails to load → fall back to built-in. |
| D19 | **SDK name** | `qtranslate-sdk` is used **provisionally** in docs. Not a release commitment until the PyPI name and usage rights are verified. |
| D20 | **Workflow format** | Python **code-only** in MVP. No visual builder and no second (JSON/declarative) workflow format without a real need. |

## 4. MVP definition

The MVP must **demo, in the README, a working end-to-end custom extension** —
not merely "the Core can load a plugin".

| Demo | Proves |
|------|--------|
| **Custom provider** | A Python extension registers a provider via the SDK and QTranslate uses it. |
| **Custom theme** | An extension changes colors/fonts/style without touching Core. |
| **Custom UI** | An extension adds a panel / widget / menu / popup. |
| **Extension loading** | Copy folder → restart → change takes effect. No rebuild. |

MVP is *explicitly* not: realtime hot reload, a visual workflow builder, an
extension store, or per-extension process isolation. Those are non-goals for
v1 (see §6).

## 5. Success criteria

The MVP is done when **all** of the following are true, each backed by a test:

- A user can copy an extension folder into `extensions/`, restart, and see the
  custom provider/theme/UI active — with **the app still starting normally if
  the extension is broken** (fails open to built-in).
- When the selected provider fails, Core retries within a bounded time budget
  and transparently falls back, **telling the user which provider answered**.
- Core and provider tests run on a machine **without** Windows APIs imported.
- The QTranslate 6.10 behaviors listed in `COMPATIBILITY_MATRIX.md` as
  *mandatory* have a passing acceptance test.

## 6. Explicit non-goals (v1)

- **Visual workflow builder.** "Workflow" is one *kind of extension* the user
  writes in code, not a drag-and-drop UI. (This corrected an earlier
  over-scoping.)
- **Realtime hot reload.** Restart-to-load is sufficient and much safer.
- **Extension marketplace / dependency resolver.**
- **Microkernel / process-per-plugin isolation.** Extensions run in-process
  for v1; the reliability of untrusted code is a later, separate design.
- **Instruction-level fidelity of the binary.** We do not prove that every CPU
  instruction or unreachable internal branch is reproduced. This is *not* the
  RE goal and does **not** relax the Gate: the Gate requires **100% coverage of
  the in-scope feature list** (see §7a and `RE_COVERAGE_CHECKLIST.md`), not
  byte-for-byte binary equivalence. "Scope complete" ≠ "every machine
  instruction understood".

## 7. Honesty rules for this project

### 7a. Evidence vocabulary (two separate axes — do not merge)

**RE evidence state** (what we know about native behavior):

| State | Meaning | May count toward the Gate? |
|-------|---------|----------------------------|
| `VERIFIED` | Proven by decompile/binary evidence, source, assets, or a live/behavioral test. | yes |
| `INFERRED` | Reasoned from a plausible source but not directly proven. | **no** — must be resolved or downgraded |
| `UNKNOWN` | Not yet investigated. | no |
| `UNRECOVERABLE` | Cannot be recovered; reason **and** impact recorded. | yes, only with reason + impact |

**Implementation (port) state** — state of the Python side (a *different* axis).
**Canonical labels (single source of truth; every doc must use exactly these):**

```
not-started → analysed → ported → behaviour-verified
                                   (plus terminal: dead:<reason>)
```

A row can be `VERIFIED` on native evidence while its port is merely `ported`.
Never use one axis to imply the other. A doc statement is **not** self-validating
evidence — writing "the native does X" in Markdown does not make X `VERIFIED`
until it traces to a binary/source/test artifact.

> **Two different notions of "cannot proceed" — do not conflate:**
> - `UNRECOVERABLE` is an **RE** state: the native artifact genuinely cannot be
>   obtained.
> - `dead:<reason>` is a **port/product** state: the native behavior *is*
>   understood, but the endpoint/feature cannot run (retired server, token wall).
> An endpoint being dead is **not** an RE gap.

### 7b. Rules

Carried forward from the planning discussion and enforced in every later doc:

1. **No compatibility claim without evidence.** "Ported" ≠ "verified". Port
   vocabulary is fixed to the canonical set above (`analysed → ported →
   behaviour-verified`, plus terminal `dead:<reason>`) — identical in
   `COMPATIBILITY_MATRIX.md`, `RE_COVERAGE_CHECKLIST.md`, and
   `CURRENT_STATE.md`.
2. **Do not assume old providers still work.** Several endpoints are dead
   (Babylon, ImTranslator, Google Search) or token-walled; the matrix records
   that instead of pretending recovery is a refactor away.
3. **Separate "API is dead" from "our port is wrong."** These need different
   fixes.
4. **Do not overwrite the uncommitted working-tree change.** (See
   `CURRENT_STATE.md` §Working tree.)
5. **Keep Tkinter.** Framework churn is not a goal.
6. **No implementation code during planning.** This phase produces documents
   only.

## 8. Document map

| Doc | Answers |
|-----|---------|
| `RE_COVERAGE_CHECKLIST.md` | **The Gate artifact.** Per-feature native RE coverage + evidence state. |
| `CURRENT_STATE.md` | What exists today, what is verified, what is missing. |
| `COMPATIBILITY_MATRIX.md` | Which 6.10 behaviors must be preserved, with evidence + test per row. |
| `ARCHITECTURE.md` | Core / Platform / UI / Extension boundaries and the migration shape. |
| `EXTENSION_SDK.md` | Manifest, lifecycle, provider/workflow/theme/UI APIs, override rules. |
| `RELIABILITY.md` | Timeout, retry, fallback, error classification, diagnostics. |
| `IMPLEMENTATION_PLAN.md` | Phase order, deliverables, done criteria. |
| `TEST_STRATEGY.md` | How every claim above gets proven. |
