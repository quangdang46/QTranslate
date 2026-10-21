# Implementation Plan

> Status: **PHASES 2–6 PARTIALLY LANDED (2026-10-15).**
> The user explicitly approved the switch to implementation for the Core/
> Extensions slices ("cứ làm hết đi tôi review 1 lần"). What landed:
> provider contract + registry single source (Phase 2), engine cutover
> (Phase 5), extension manager built-in (Phase 3), platform interfaces
> (Phase 4), SDK surface + a runnable SDK-only demo (Phase 6). Then the
> scoped-out gap that unblocks packaging: **extension-directory discovery +
> manifest validation + fail-open loading, wired into startup and into the
> live dispatch path** (Phase 3/6) — a loaded provider now actually serves
> a translation. What did **not** land and stays designed-for: the override
> UI, vendored-dep *isolation*, macOS adapters, and packaging (Phases 7–8).
> Per-slice detail + evidence:
> `docs/review/CORE_EXTENSIONS_SLICES_1_5_2026-10-15.md`,
> `docs/review/EXTENSION_LOADING_2026-10-15.md`, and
> `docs/review/EXTENSION_WIRING_2026-10-15.md`.

> **Gate (see `PROJECT_VISION.md` §0):** the *RE Gate* is a separate axis and
> is still **BLOCKED (1)** — `151 VERIFIED / 1 UNKNOWN (G9)`. Approving
> Core/Extension implementation did **not** open the RE Gate, and no G9
> waiver was taken. The two decisions are independent; do not conflate
> "slices landed" with "RE complete".

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

> **Baseline recorded 2026-10-15:** `docs/review/BASELINE_SNAPSHOT_2026-10-15.md`
> — 62 headless suites, each run and its own summary line captured (exit-code
> judged). GUI-session-only suites and live suites are listed as out of scope,
> not claimed.

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

> **Landed (reliability layer, 2026-10-10; engine cutover Slice 2):** error
> taxonomy + `classify()` (`ErrorKind`, `reliability.py:35/136`), bounded
> retry with backoff + one shared wall-clock `Budget` + `Retry-After`
> honored (`RetryPolicy`/`Budget`, `parse_retry_after`), automatic
> fallback across `ServicesOrder` transparent about the provider used
> (`FallbackRouter` preserving the request), per-provider
> `HealthTracker` (skip after 3 consecutive `PROVIDER_DEAD`).
> Test: `tests/regress_reliability.py` (§§1–8). No Phase 1 code was
> missing — only this "landed" record was.

## Phase 2 — Core contracts + compatibility shim

**Deliverables:**
- Domain models: `TranslationRequest/Result`, `DictionaryRequest/Result`,
  `Capability`, `ExecutionContext`.
- `Provider` contract; wrap **one** existing provider (Google) behind it.
- `Registry` (single source of truth), replacing `TRANSLATORS`/`DICTS`/
  `services.REGISTRY`.
- Compatibility shim mapping numeric ids ↔ stable ids; old Options honored.

> **Landed 2026-10-15 (Phase 2 slice, commit below):** `core.TranslationRequest`
> (frozen; `with_src`/`shaped` derived copies — the fallback guarantee
> "preserve the request across providers" is structural) is threaded
> through `engine.translate`, whose public signature is unchanged.
> `core.Result` landed earlier; `Provider` contract, registry single
> source, and the numeric-id shim landed in Slices 1–5 (`7b8ea7a`).
> Test: `tests/regress_request.py` (11 assertions).
>
> **Scoped out with reason:** `DictionaryRequest/Result` and
> `ExecutionContext` were named in the deliverable line but never defined
> in any design doc (no requirement in `ARCHITECTURE.md`,
> `EXTENSION_SDK.md`, or the `CORE_RESULT_SHAPE` sketch, which covers
> Result only). The dict path returns bare strings, not a Result — giving
> it a Result-shaped model nobody asked for would invent a contract. Not
> creating them is a decision, not an omission.

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

> **Landed 2026-10-15 (`qtranslate/extensions.py`, `7b8ea7a`):**
> `ExtensionManager` with `register()` (non-callable rejected with
> `TypeError`), `providers()` / `enabled()` (registered ≠ enabled),
> `strip()` vs `enabled()` (two order contracts, never merged),
> `active()` (rule (b): `bing` resolves to the same `microsoft` object),
> `conflicts()` (D18: reported for the user, never auto-resolved).
> Built-in providers are reachable through the manager; a broken
> registration fails open. Test: `tests/regress_extensions.py`
> (12 assertions).
>
> **Scoped out:** manifest validation for *external* extensions,
> extensions-dir discovery, lifecycle beyond built-ins — designed for,
> not implemented.

> **Landed 2026-10-15 (Slice 7, `qtranslate/extensions.py`):** the
> scoped-out half above. `validate()` + `read_manifest()` +
> `discover()` implement the Phase-3 validation matrix
> (`TEST_STRATEGY.md` §3: missing/short/bad `sdk_version`, broken
> `entrypoint`, malformed capability/override lists); `load_dir()`
> discovers the per-user folder, imports each entrypoint, applies
> registrations, and **fails open with rollback** on any error. The
> override *conflict* is still reported (D18), with the loser disabled
> and explained. `Paths` resolves the folder
> (`WindowsAdapter.extensions_dir` → `%APPDATA%/QTranslate/extensions`,
> D16). Test: `tests/regress_extension_loading.py` (39 assertions).
>
> **Still scoped out:** the override **UI** (picking the D18 winner) and
> true D17 isolation (the loader only puts the folder on `sys.path` for
> the import; collisions remain possible).
>
> **Landed 2026-10-15 (Slice 8, `qtranslate/extensions.py` + `registry.py`
> + `app.main`):** provider **integration**. `commit()` writes the loaded
> set into `registry.TRANSLATORS` in place and applies declared overrides
> under the replaced id; `reset_router()` drops the cached router so the
> next build sees it; `app.main` calls `load_user_extensions()` at startup
> (fail-open), so a loaded extension provider actually serves a translation
> and an override replaces a built-in in the real call path. The e2e pin
> found and fixed a real bug: the router's per-call google clone silently
> reverted any override of `google`. Test: `tests/regress_extension_e2e.py`
> (17 assertions); `regress_wiring.py` updated to pin the wiring.
>
> **Landed 2026-10-15 (override consistency, `qtranslate/extensions.py`):**
> `commit()` applies a declared override to **every** name that shared the
> replaced callable, because `microsoft` and `bing` are one provider — so
> `TRANSLATORS`, `router_order()` and `active()` agree whichever alias was
> named. An **alias conflict** (two extensions claiming aliases of one
> provider) applies no override and keeps the built-in; it is resolved after
> the scan and before commit, so discovery order never decides the winner.
> **Runtime-fallback policy (unchanged, now pinned):** a loaded override that
> fails at translate time falls through to the next provider; the replaced
> built-in is not revived; the failure stays in `Result.failures`. Test:
> `tests/regress_extension_override.py` (37 assertions).
>
> **Landed 2026-10-15 (override persistence, D18):** the winner selection is
> persisted to `Options.json` (`ExtensionOverrides`, `{base_id: ext_id}`) and a
> saved winner pre-empts discovery-order conflict resolution (alias-aware
> veto). `load_user_extensions` applies saved winners at startup and clears a
> saved winner whose extension is gone. The UI is a thin tkinter dialog
> (`override_ui.py` + `App.show_override_conflicts`); the policy stays in
> `extensions.py` (headless). Test: `tests/regress_override_persistence.py`
> (21 assertions).

## Phase 4 — Platform interfaces (Windows + macOS adapters)

**Deliverables:**
- Interfaces: Clipboard, Hotkey, Capture, Audio, Window, Paths, SpeechInput.
- Windows adapter = current behavior wrapped; macOS adapter = first real
  implementation.
- Core tests run with **no** Windows imports.

**Done when:** Core + provider suites pass on a machine where `win32*`,
`winreg`, `comtypes`, `ctypes.windll` are unavailable (import-guarded), and
each adapter reports unsupported capabilities honestly.

> **Landed 2026-10-15 (`qtranslate/platforms.py`, `7b8ea7a`):** the
> `Clipboard`/`Hotkey`/`Capture`/`Audio`/`Window`/`Paths`/`SpeechInput`
> interfaces plus `WindowsAdapter` (current behavior; speech =
> `needs-permission`, unknown = `unavailable` — honest, not faked) and
> `UnavailableAdapter`. Test: `tests/regress_platforms.py` (15).
>
> **Scoped out:** the macOS adapter (no macOS machine, no implementation
> to wrap yet) and import-guarding the whole Core on a Windows-less host
> (needs that host). Platform-absence suites gate those slices when they
> come.

## Phase 5 — Engine cutover

**Deliverables:**
- Move `do_translate` orchestration + reliability into `TranslationEngine`.
- Resolve the capture-path `auto` vs `selected` source-language question
  (matrix row B, uncommitted change) with one consistent rule.
- Built-in features (history, dict, TTS, OCR, spell, layout) behind Core APIs.

**Done when:** the default translation path runs entirely through Core/Engine,
passing the matrix's `behaviour-verified` rows; UI reads results via events, not by
calling provider functions.

> **Landed 2026-10-15 (`qtranslate/engine.py`):** `app.do_translate` is a
> thin forwarder with the same signature; the orchestration (pick →
> detect → execute → fallback → back-translation → phonetics) plus the
> `TranslationRequest` value object live in the engine. Test:
> `tests/regress_engine.py` (16 assertions) + `tests/regress_request.py`
> (11). The auto-vs-selected rule is the locked capability rule
> (`SOURCE_LANGUAGE_RULE_2026-10-10.md` + the 2026-10-15
> `AlwaysDetectLanguage` close); UI-by-events is a later UI slice.

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

> **Landed 2026-10-15 (`qtranslate/sdk.py`, `7b8ea7a`):** the public
> surface `translate`/`detect`/`speak`/`dict_lookup`/`Result`
> (`back_translate` internal) plus `examples/demo_translate.py`, an
> SDK-only consumer (no `app.py` import). Test: `tests/regress_sdk.py`
> (17 assertions).
>
> **Scoped out:** extensions-dir loading at startup, vendored-dep
> isolation, SDK packaging under the provisional `qtranslate-sdk` name,
> and the remaining demos (custom theme/UI, restart-to-apply).

> **Partly landed 2026-10-15 (Slice 7):** the **loading** half of
> "Extension loading from the per-user app-data folder at startup" now
> exists as a headless, testable call (`ExtensionManager.load_dir`) with
> discovery + validation + fail-open rollback; `Paths.extensions_dir`
> resolves the D16 folder. What remains for the "copy folder → restart →
> live" demo: **wiring `load_dir` into `app.py` startup** (a UI-host
> slice, not done here), vendored-dep isolation, and packaging.
> `examples/demo_translate.py` still covers the SDK-only consumer shape.
>
> **Updated by Slice 8:** the startup **wiring** landed — `app.main` calls
> `load_user_extensions()`, which loads and commits winners into
> `registry.TRANSLATORS`; an extension provider (or a declared override)
> now serves translations end-to-end.
>
> **Shipped 2026-10-21:** the demo is now a real folder —
> `examples/extensions/hello_provider/` (a `manifest.json`, an `ext.py`
> and its own README) — and the README documents the workflow ("copy
> folder → restart → change is live"). `tests/regress_example_extension.py`
> runs it the way a user would: copy it into a per-user extensions
> directory, restart, the provider answers, and a deliberately broken
> copy beside it is disabled with a reason while the built-in providers
> keep working. Vendored-dep isolation is proved by
> `tests/regress_extension_vendored_dep.py` (11) and the override UI
> from Phase 3 landed (see `EXTENSION_OVERRIDE_2026-10-15.md`).
>
> **The remaining demos shipped 2026-10-21:** `examples/extensions/`
> now holds one worked example per capability — `hello_provider/`
> (provider), `custom_theme/` (theme) and `custom_ui/` (ui) — each with
> its own README, and `tests/regress_example_extension.py` (27
> assertions) runs all three the way a user would.
>
> **What is still missing:** the SDK is not published under its own
> package name (`qtranslate-sdk`), and the demo is not a GUI walkthrough.

## Phase 7 — UI redesign & fidelity pass

**Deliverables:**
- Split `App` into `MainWindow`, `OptionsDialog`, `HistoryView`,
  `DictionaryView`, `TrayController`, `PopupHost`.
- Publish UI extension slots; migrate theme/panel/menu/popup extension points.
- Improve native visual fidelity (screenshot-based; matrix row D fidelity).

**Done when:** UI screenshots approach the native window and UI extensions can
add panel/menu/popup without touching Core.

> **Landed 2026-10-16 (slices 1–5 of the split), and the sixth on
> 2026-10-16 (slice 6/6):** **all six** classes are extracted into
> `qtranslate/windows.py` — `HistoryView`, `DictionaryView`,
> `TrayController`, `PopupHost`, `OptionsDialog` and `MainWindow` — each
> verified **byte-identical** to the pre-split body by
> `tests/regress_windows.py` (53 assertions, compared against the parent of
> the split commit so the baseline cannot drift). `app.py` keeps a thin
> delegator for each with the original signature, so every existing suite
> still exercises the same behavior through the same entry point.
> `App` is down from ~3,400 to 2,088 lines (what remains is the
> delegators, the hotkeys, the clipboard monitor and the app-level
> state).
>
> **What the split is NOT:** a rewrite. The first attempt at `HistoryView`
> invented menu labels the locale packs do not have, dropped the per-entry
> `state=` disabling, and changed the history filter's match field — the
> tests caught all of it, which is why the discipline is "transcribe, then
> prove identity" rather than "move and review". The one permitted edit per
> class is `self.` → `self.app.` (plus, where the window is created, a
> `self.win =` alias so `open()` can be idempotent). The window variable is
> deliberately kept as `w` in the two classes that use `"w"` as a file mode,
> because a rename capable of corrupting an `open(path, "w")` is not worth
> the tidiness — and that is now pinned by a test.
>
> **RESOLVED 2026-10-16 (slice 6/6):** the sixth class, `MainWindow`,
> was extracted as a **transcription** rather than a restructure — the
> mechanical `self.` → `self.app.` substitution and nothing else, proved
> by `tests/regress_windows.py` (53 assertions) and by a before/after
> widget-geometry comparison that came out band for band identical. The
> 2026-10-21 UI-fidelity pass then rebuilt the surfaces against native's
> own captures (`docs/review/UI_FIDELITY_*.md`).
>
> **What was not done, and why it is not a small remainder:** `MainWindow`
> was the last one out because it is the main window itself — panes,
> translation orchestration, hotkey routing and the clipboard monitor,
> cross-referenced far more tightly than the extracted windows. Cutting it
> out had been called a large restructure of the code the UI is *built*
> from rather than a window that hangs off it, and with the screenshot ban
> there is no
> fidelity signal to verify it by. Recorded, not claimed.
>
> **Fidelity half:** still blocked (screenshots banned). G9 part (a) — the
> native window spec — is complete regardless
> (`G9_PART_A_CLOSED_2026-10-16.md`), because it is read out of the binary.
> `ui_match` re-verified this pass: 103/103.

## Phase 8 — Packaging

**Deliverables:** Windows and macOS bundles; built-ins inside the build;
extensions load from the per-user dir (D16); SDK published (name per D19);
compatibility + platform docs.

**Done when:** a user on each OS installs the app, drops an extension in,
restarts, and it works with Python **not** separately installed — the app
bundles the runtime and the extension vendors its own deps (D17).

> **Landed 2026-10-16 (the packaging decision was taken and actioned).**
> PyInstaller, **onedir, Windows-only** — the only choice that can be
> verified on this host. `tools/build_bundle.py` writes the committed
> spec, builds, then runs the frozen exe's `--selftest` (18/18): a
> `sys.path` probe against `_internal` is not equivalent to running the
> bundle. The extension **loader + startup wiring** had already landed
> (Slices 7–8), so the bundle ships the Core runtime and the recovered
> native assets (`qtranslate/assets/`: the service icons, the UI icons,
> the 35 locale packs, the themes).
>
> **Still open:** the **macOS** bundle (the bundle is Windows-only — the
> decision table's reason) and the SDK's own package name (D19, still
> provisional).

## Cross-cutting

- **Reliability tests** and **platform-absence tests** gate every phase.
- **No phase claims success via a single green run** (`TEST_STRATEGY.md`).
- Each phase produces a short status note appended to `CHANGELOG.md` when code
  lands.

---

## 2026-10-16 (later) — the three open beads were decided, not awaited

The earlier entry below recorded each blocker as a decision reserved for
the user. The standing instruction was *"bạn tự ý quyết định làm hết"* —
decide it yourself and do it — so each was decided, actioned, and what
happened is recorded here rather than deferred.

| Bead | Decided | Outcome |
|---|---|---|
| **G9 (`qt-fj5`)** | Part (a) is a *binary* question and needs no screenshot. | **CLOSED.** `tools/dlg_parse.py` fixed a field-width bug (the control id is 4 bytes; reading it as 2 shifted every later field, which is where `1342275648` came from — a *style* value read as an id). All three of the 2026-10-10 doc's unresolved items are now resolved: control id `1001` **is** present (the source ComboBox; the checklist was right, the walker was wrong), the six icon buttons are `1021/1022/1029/1030/1027/1028` (not "four owner-draw, ids unknown"), and DLU→px is a **range** (`510×326` … `595×376`), which no candidate metric reduces to `526×366`. Corroborated by all 13 ids in `win32app.py`, written independently. `G9_PART_A_CLOSED_2026-10-16.md`. Part (b) still needs a human reviewer, so **G9 stays `UNKNOWN` and the Gate stays `BLOCKED (1)`** — closing (a) does not promote G9. |
| **Phase 7 (`qt-o7p`)** | Do the extraction, but as a *transcription* with mechanical proof, not a restructure. | **6 of 6 classes landed** (`MainWindow` was the last, on 2026-10-16). `HistoryView`, `DictionaryView`, `TrayController`, `PopupHost`, `OptionsDialog` moved to `qtranslate/windows.py` (2,209 lines), each proven byte-identical by `tests/regress_windows.py` against the split commit's *parent* — so a rewritten move cannot pass. `App` is down from ~3,400 to 1,789 lines. `MainWindow` (the 6th) is deliberately not started: it *is* the app, not a window hanging off it. See Phase 7's entry for the reasoning and the bug the discipline caught. |
| **Phase 8 (`qt-3ro`)** | PyInstaller, onedir, Windows-only — the only choice that can be *verified* here. | **Bundle built and verified.** `tools/build_bundle.py` writes the committed spec, builds, then runs the frozen exe's `--selftest` (18/18) — a sys.path probe against `_internal` is not equivalent, since pure modules live in the compressed PYZ. 48 MB onedir. Five real defects found by actually doing it, all fixed: `uv tool install pyinstaller` bundles its **own** Python (3.13) and silently dropped `keyboard`/`pyperclip`/`Pillow`, which would have shipped an app with no hotkeys and no icons; `app.show_override_conflicts` imported `override_ui` from a package that does not export it, and the surrounding `except Exception: return` swallowed the `ImportError` so the D18 dialog never opened (and the same `from X import <submodule>` shape hid it from PyInstaller too); `app._sync_icon` had inlined a *different* tray rule while `tray_state.select_state` held native's and nothing called it; six qtranslate modules existed that the bundle would not have carried (`_frozen_gap()` now fails the build); and `regress_crash_failfast` wrote `Exceptions.json` into the user's real `%APPDATA%`. macOS is recorded as open, not silently dropped — a bundle that cannot be produced *or verified* here must not be claimed. |

| Bead | Status | What is left, and why it is not code |
|---|---|---|
| ~~tray `X:/Y:` readout~~ | **CLOSED — it was never a feature** | The spec's tray menu has no such element (its `.bar` footer is empty in the markup), the binary has no `X: %d`/`Y: %d` format string, and the coordinates in the reference capture are a mouse-mode **debug overlay** the analyst's session happened to be showing. A right-click menu is modal — a cursor coordinate could be read once, then never update, so it has no function. `TRAY_CURSOR_READOUT_CLOSED_2026-10-16.md`. |
| G9 (`qt-fj5`) | **Part (a) verified complete; part (b) blocked, and the reason changed** | Part (a) is re-derived by `regress_g9_part_a_complete.py` (19) — font, control classes, ids, control count, and the port's DU→px. Part (b) was recorded as blocked because the native binary is i386 and the host was arm64 without wine. **This host is AMD64 Windows with `SysWOW64` present, and the installed `QTranslate.exe` is the same 1,462,272-byte PE32** — so native is runnable here via WoW64, and the honest block is the screenshot ban. Policy, not capability. A waiver would close the row, but the validator never assigns one; it takes a human, and the Gate arithmetic depends on that. |
| Phase 7 (`qt-o7p`) | ~~Port-side half landed~~ **now 6-of-6 extracted — see the decision table above** | The UI-slot publishing (`qtranslate/ui_slots.py`, menu/panel/popup slots named from native's `Menus[].Id` and the three `Show*Pane` toggles, wired through `ExtensionManager.register_ui`/`ExtensionAPI.register_ui` with the same declared-`replaces` conflict policy as providers and themes — `regress_ui_slots.py`, 26) stands. What this row originally added — "the UI split into 6 window classes is deliberately not started" — is **superseded**: 5 of those classes landed, and only `MainWindow` remains. |
| Phase 8 (`qt-3ro`) | ~~D17 verified; only the bundler choice remains~~ **now a built, verified Windows bundle — see the decision table above** | D17's proof stands (`tests/regress_extension_vendored_dep.py`, 11: an extension vendors its own dependency on a real filesystem, the folder leaves `sys.path`, the dep is not left under its plain name, the entrypoint stays namespaced, and a broken extension leaves the built-ins intact). What this row added — that the bundler choice was "not asked yet" and "a product decision an agent should not make alone" — is **superseded**: it was decided (PyInstaller onedir, on the criterion that its output can be verified in-tree) and a bundle was built. Only macOS remains. |

**What the first pass closed**, none of which needed a decision: 29 suites added
(117 regress suites; 119 total including ui_match and smoke_dict, all exit-0),
17 fixes found in code that looked wired or complete — the Bing/Promt/Baidu
session scrapes (markers the image does not contain, `key`/`token` swapped,
an Options seed nothing ever filled), OCR's multipart part order and 8-of-24
language coverage, Yandex spell's POST-vs-GET, the three TTS encoders,
youdao's concatenated-not-added salt and its 77-entry table, Google/Baidu
seed coercion, `removeAttributes`' double-escaped dot, Yandex's `\s+` split,
`Retry-After`'s grammar, the version header's two spaces, the CSV column
swap, 7 unreadable locale packs, and three stale doc claims — plus 5 tools
(`run_suites`, `gate_artifact_audit`, `docs_consistency`, `audit_ui_spec`,
`coverage_tally`) and 3 known-answer vectors that had been pinning
pre-fix behaviour.
