# Core/Extensions slices 1–5 — landed + verified (2026-10-15, commit `7b8ea7a`)

> Source of truth for the Phase 2/3/4/5 slices that landed on
> `main` at `7b8ea7a`. Design decisions locked *before* any code
> (the design-only phase) are restated here so the record matches what
> was implemented. **No RE row changed by this document** and this work
> does **not** open the RE Gate.

## 0. Scope note (do not conflate)

These slices are the **Core/Extensions migration** — a separate axis from
the RE checklist. The Gate is still `151 VERIFIED / 1 UNKNOWN (G9)`,
`BLOCKED (1)`: G9 part (b) is a runtime screenshot-diff (banned in this
mission, harness deleted per user order; no waiver taken). Landing Core
slices neither closes G9 nor waives it.

Design decisions locked in the design-only phase, *before* Slice 1:

| Item | Decision |
|---|---|
| `SUPPORTED_LANGS` | stays per-provider; no vocabulary merge, no index/semantic change |
| `detect_language` | stays owned by `registry`; engine calls it, never relocates it to hoover code |
| SDK surface | `translate`, `detect`, `speak`, `dict_lookup`, `Result`; `back_translate` stays internal until contract + callers are verified |
| Provider contract | thin adapters wrapping existing callables; **no** provider rewrite |
| Engine | alias-first, native behavior preserved 1:1 |
| Extension Manager | built-in only; registered ≠ enabled; no discovery/sandbox |
| Ordering | `ordered_services()` and `router_order()` are two contracts and are never merged |
| `bing` | **rule (b)** — alias of `microsoft` (same adapter object), never a separate fallback entry |

## 1. Slice 1 — Provider contract + thin adapters

- `qtranslate/providers/__init__.py`: a `Provider` Protocol
  (`name`, `uses_auto_detect`, `translate`, `detect`, `langs`) plus
  `_Adapter`, which wraps one existing `_t_*` callable. `langs()` returns
  that provider's **own** table — never merged.
- **Rule (b) — `bing` is an alias, not a provider.** Evidence used to
  settle this (from the image, not guessed):
  - native `Services/` has **19 directories and no `Bing`** (Microsoft
    lives in `Microsoft Translator/`);
  - `config.SERVICE_NAMES` has **no `bing` key** (only `5: "microsoft"`);
  - `TRANSLATORS` mapped both `"bing"` and `"microsoft"` to `_t_bing`.
  So `"bing"` is a port-side alias of `microsoft`. `build_adapters()`
  makes `table["bing"] is table["microsoft"]` — identity, not equality.
- `registry.router_order()` now **dedupes by callable identity**, so the
  chain never tries one implementation twice. Before this slice the append
  rule added `bing` as a *second* chain entry for the same callable —
  burning retry budget on a duplicate implementation.
- Pinned: `tests/regress_provider_contract.py` (67 checks), including a
  mock-chain proof that a request with `requested="bing"` still routes
  successfully and the shared callable is invoked **at most once**.

## 2. Slice 2 — Engine cutover

- `qtranslate/engine.py` now owns what `app.do_translate` used to inline:
  pick → detect → execute → reliability fallback → back-translation →
  J7 phonetics. `app.do_translate` is a thin forwarder with the **same
  signature**, so every caller is untouched.
- The `auto_detect` branch carries the RE finding from
  `docs/review/SERVICES_PAGE_PARITY_2026-10-15.md` §44: the true flag is
  `DAT_0054941f` (nav-menu `0x808e`), packed into `FUN_004606BA`, whose
  first branch detects **even for a concrete source**;
  `DAT_005494e6` is `RemoveLineBreaks`.
- Request shaping still happens **exactly once** (inside
  `ProviderRouter.translate` via `reliability.normalize_request`); the
  no-router fallback shapes explicitly because it bypasses the router.
- `detect_language` was **not** moved — it stays in `registry`, per the
  locked decision.
- Pinned: `tests/regress_engine.py` (16 checks) — signature equality,
  src == target echo, empty text, fallback call order, detect-call
  counts (auto on a non-auto service → 1; concrete, no flag → 0; concrete
  + `auto_detect` → 1), back-translation via the answering provider, and
  the native no-data string on total failure.

## 3. Slice 3 — Extension Manager (built-in only)

- `qtranslate/extensions.py`: `ExtensionManager` with
  `register()` / `providers()` / `enabled()` / `strip()` / `active()` /
  `conflicts()`.
- registered ≠ enabled: retired-host providers (babylon, baidu) stay
  registered — dead ≠ deleted — while `enabled()` is derived from
  `router_order()` (same enablement semantics as the engine).
- The two order contracts stay separate: `strip()` reproduces
  `App.ordered_services()` (ServicesOrder-minus-disabled, **no** extras);
  `enabled()` reproduces `router_order()` (fallback, deduped per rule b).
  They are never merged.
- Override conflicts are **reported** — `OverrideConflict("… the user must
  pick the winner")` plus `conflicts()` — never auto-resolved by scan or
  load order (D18).
- Fail-open: a non-callable registration raises `TypeError`; the built-in
  stays active.
- Pinned: `tests/regress_extensions.py` (12 checks).

## 4. Slice 4 — Platform interfaces + Windows adapter

- `qtranslate/platforms.py`: `Clipboard`, `Hotkey`, `Capture`, `Audio`,
  `Window`, `Paths`, `SpeechInput` interfaces plus `WindowsAdapter` and
  an honest `UnavailableAdapter`.
- Capability reporting is honest, per `ARCHITECTURE.md` §4: `speech` is
  `needs-permission` (SAPI/COM), and any unknown capability reports
  `unavailable` rather than pretending. `current()` picks per platform.
- Pinned: `tests/regress_platforms.py` (15 checks).

## 5. Slice 5 — Public SDK surface

- `qtranslate/sdk.py` exports `translate`, `detect`, `speak`,
  `dict_lookup`, `Result`. `back_translate` stays internal
  (`back_translate_internal`, deliberately outside the documented surface).
- `examples/demo_translate.py` is a consumer that uses **only** the SDK —
  no `app.py` import — which is the Phase 6 "copy folder, no rebuild"
  demo shape.
- Pinned: `tests/regress_sdk.py` (17 checks).

## 6. Verification (offline, no GUI)

- **61/61** headless `tests/regress_*.py` suites PASS after the slices
  (63 total minus the 2 window-opening suites — see
  `HEADLESS_SWEEP_RULE_2026-10-15.md`; 42/42 was the count at slice time)
  (37 pre-existing + 5 new).
- `tools/coverage_tally.py --check`: `151 VERIFIED / 1 UNKNOWN (G9)`,
  `gate=BLOCKED (1 unresolved)` — unchanged, as expected: Core/Extension
  work does not move RE states.
- New modules are tkinter-free (each pinned by a static check); none of
  them imports `app`.

## 7. Not in scope (explicitly)

- G9 part (b): blocked on screenshots; harness deleted per user order.
- Bridge onto macOS adapters: the interface is published, the macOS
  implementation is a separate slice.
- `SUPPORTED_LANGS` unification: gated behind an explicit migration plan.
- UI service extensions (panel/menu/popup) and the extensions-dir
  discovery: designed for, not implemented here.
