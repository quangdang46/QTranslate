# Implementation Plan

> Status: **PLANNING — NOT STARTED, AND MUST NOT AUTO-START.** Phase order and
> done-criteria only. No code is written during this plan phase. Phases are
> ordered so each is independently testable and rollback-able; no big-bang
> refactor.

> **Gate (see `PROJECT_VISION.md` §0):** Phase 0 **must not begin** merely
> because the documents are agreed or D1–D20 are locked. The entire plan below
> stays closed until RE is complete per `RE_COVERAGE_CHECKLIST.md` **and the
> user explicitly approves the switch to implementation.** Agreeing documents is
> Phase B; starting Phase 0 is Phase C.

## Guiding constraints

- **D13:** design Core/Extension boundaries first, then migrate — do not port
  app.py's layout forward.
- **D10:** preserve 6.10 behavior per `COMPATIBILITY_MATRIX.md`.
- The uncommitted `app.py` change is preserved untouched
  (`CURRENT_STATE.md` §4).
- Each phase ends with tests (§ `TEST_STRATEGY.md`) and a review checkpoint.

## Phase 0 — Baseline & freeze  *(no code)*

**Deliverables:** `COMPATIBILITY_MATRIX.md` accepted as the baseline;
working-tree change documented and preserved; CI runs the existing suites.

**Done when:** every matrix row has an agreed *must-keep / drop* decision, and
a baseline snapshot of current test results is recorded (re-run, not copied
from README).

## Phase 1 — Reliability baseline

**Why first:** it answers the user's #1 complaint ("mất kết nối") and is
independent of the extension work.

**Deliverables:**
- Error taxonomy + classification (`RELIABILITY.md` §2).
- Bounded retry with backoff + total budget; honor `Retry-After`.
- Automatic fallback across `ServicesOrder`, transparent about the provider used.
- Per-provider health; skip `PROVIDER_DEAD`.

**Done when:** a provider-failure test forces fallback and asserts (a) the next
provider answered, (b) the user sees which provider, (c) total time ≤ budget.
Dead endpoints are marked, not retried.

## Phase 2 — Core contracts + compatibility shim

**Deliverables:**
- Domain models: `TranslationRequest/Result`, `DictionaryRequest/Result`,
  `Capability`, `ExecutionContext`.
- `Provider` contract; wrap **one** existing provider (Google) behind it.
- `Registry` (single source of truth), replacing `TRANSLATORS`/`DICTS`/
  `services.REGISTRY`.
- Compatibility shim mapping numeric ids ↔ stable ids; old Options honored.

**Done when:** Google goes through the new contract and produces
**byte-identical** results to the current path on a fixed input set; all other
providers still work via their old path.

## Phase 3 — Extension Manager (built-in only)

**Deliverables:**
- Manifest validation, lifecycle, fail-open loading.
- Migrate built-in providers onto the contract, one at a time, behind adapters.
- Registry serves both old and new paths during transition.
- Override-conflict handling per D18 (report conflict, user picks winner).

**Done when:** every built-in provider is registered and callable through the
one interface; a deliberately broken extension is skipped without crashing
startup.

## Phase 4 — Platform interfaces (Windows + macOS adapters)

**Deliverables:**
- Interfaces: Clipboard, Hotkey, Capture, Audio, Window, Paths, SpeechInput.
- Windows adapter = current behavior wrapped; macOS adapter = first real
  implementation.
- Core tests run with **no** Windows imports.

**Done when:** Core + provider suites pass on a machine where `win32*`,
`winreg`, `comtypes`, `ctypes.windll` are unavailable (import-guarded), and
each adapter reports unsupported capabilities honestly.

## Phase 5 — Engine cutover

**Deliverables:**
- Move `do_translate` orchestration + reliability into `TranslationEngine`.
- Resolve the capture-path `auto` vs `selected` source-language question
  (matrix row B, uncommitted change) with one consistent rule.
- Built-in features (history, dict, TTS, OCR, spell, layout) behind Core APIs.

**Done when:** the default translation path runs entirely through Core/Engine,
passing the matrix's `behaviour-verified` rows; UI reads results via events, not by
calling provider functions.

## Phase 6 — Extension SDK + MVP demos

**Deliverables:**
- `qtranslate-sdk` package (name provisional, D19): provider/workflow/theme/UI/
  lifecycle/settings APIs + test harness. Provider deps vendored per extension
  (D17); workflow is Python code-only (D20).
- Extension loading from the per-user app-data folder at startup (D7, D16).
- **MVP demos** wired into the README: custom provider, custom theme, custom UI,
  extension load (restart-to-apply).

**Done when:** the README demo is runnable end-to-end: copy folder → restart →
change is live; breaking the extension falls open to built-in. No rebuild of
QTranslate.

## Phase 7 — UI redesign & fidelity pass

**Deliverables:**
- Split `App` into `MainWindow`, `OptionsDialog`, `HistoryView`,
  `DictionaryView`, `TrayController`, `PopupHost`.
- Publish UI extension slots; migrate theme/panel/menu/popup extension points.
- Improve native visual fidelity (screenshot-based; matrix row D fidelity).

**Done when:** UI screenshots approach the native window and UI extensions can
add panel/menu/popup without touching Core.

## Phase 8 — Packaging

**Deliverables:** Windows and macOS bundles; built-ins inside the build;
extensions load from the per-user dir (D16); SDK published (name per D19);
compatibility + platform docs.

**Done when:** a user on each OS installs the app, drops an extension in,
restarts, and it works with Python **not** separately installed — the app
bundles the runtime and the extension vendors its own deps (D17).

## Cross-cutting

- **Reliability tests** and **platform-absence tests** gate every phase.
- **No phase claims success via a single green run** (`TEST_STRATEGY.md`).
- Each phase produces a short status note appended to `CHANGELOG.md` when code
  lands.
