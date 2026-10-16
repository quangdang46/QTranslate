# Registry migration slice — single source of truth (2026-10-15, working tree)

> Phase 2 slice (alias-first) of the Core/Extension migration
> (`IMPLEMENTATION_PLAN.md` Phase 2). Code landed and pushed at
> `7b8ea7a`. No row state changed.

## 1. What was wrong

`CURRENT_STATE.md` §3 names the three-source-of-truth layout:

1. `app.TRANSLATORS` / `app.DICTS` — hardcoded tables in the UI module.
2. A hardcoded 6-provider `candidates` tuple in `app.detect_language`.
3. The dead `services.REGISTRY` (already removed earlier).

Additionally the router order in `app._router` was a hardcoded 5-name list
that silently excluded promt, babylon, baidu, naver, youdao from every
fallback chain — contradicting native D2 (`FUN_0045CEDE`: head of the
ordered set = first in `ServicesOrder`).

## 2. What the slice does

`qtranslate/registry.py` now owns:

- `TRANSLATORS` / `DICTS` — the nine `_t_*` adapters moved verbatim from
  `app.py` (same bodies, same comments), plus the dict lambdas.
- `detectors()` — the 6-provider detect chain, order unchanged.
- `router_order()` — built from `config.services_order()` numeric ids →
  `SERVICE_NAMES`, unknown ids skipped, TRANSLATORS-only names appended.
  Deliberately NOT unified with `App.ordered_services()`: the strip
  shows exactly ServicesOrder-minus-disabled (no extras appended),
  while the fallback chain must reach every callable (extras appended).
  Merging them would either show phantom strip buttons or drop
  fallback providers — do not "deduplicate".
- `google_suggest()` — spell suggestion entry, moved from direct
  `services.spell` use.
- `USES_AUTO_DETECT` + `uses_auto_detect()` — the port-side
  auto-detect capability table (was `app._USES_AUTO_DETECT`); `app.py`
  holds an alias and `do_translate` consults `uses_auto_detect()`.
- `build_router(sink)` — OWNS the singleton + per-call clone
  (health/policy shared); `app._router` is now a 6-line forwarder kept
  for existing callers, returning None only when the layer is
  unimportable (old degrade contract preserved).
- `call_with_sink` + `apply_phonetics` (were `app._t_call` /
  `app._apply_phonetics`) — sink dispatch + J7 append; `app.py` holds
  aliases, and the now-unused `inspect` import there is removed.
- `detect_language` (was `app.detect_language`) — the FUN_00460354
  detect-retry loop over `detectors()`; behavior verified unchanged
  (`detect('')` → 17 before and after the move — a provider index the
  caller normalizes, not a regression). `app.py` holds an alias.
- `SERVICE_LINKS` + `service_link()` (were `app._SERVICE_LINKS` /
  `app._dict_service_link`) — provider home pages; `app.py` holds
  aliases.
- `qtranslate/placement.py` (new module, tkinter-free): the
  WINDOWPLACEMENT codec (`decode/encode_placement`), `TEMPLATE_GEOMETRY`
  (`"595x376"`), and `place_main/place_aux/save_placement` — moved
  verbatim from `app.py` (~120 lines → 6-line alias block). Roundtrip
  byte-exact verified headless against the real blob.
- `app.speak` de-duplicated: was a second TTS fallback chain nested in
  the UI module; now a thin forwarder to `player.play_text` (which owns
  slow-flag + online-first + SAPI-fallback). No test called `app.speak`
  directly.
- `tts.google_tts` de-duplicated: hand-rolled a second TTS URL format
  string (with bare `urllib.parse.quote`, missing `encode_get_param`
  truncation + language-code normalize); now delegates to
  `google_translate.listen_url`, verified byte-identical offline incl.
  the `&ttsspeed=0.24` slow flag. Unused `tk` import and
  `GOOGLE_TTS_HOST` constant removed.

`app.py` holds only aliases:

- `from qtranslate.registry import TRANSLATORS, DICTS`
- `from qtranslate.registry import (_t_google, ..., _t_promt)` for the
  direct call sites (`do_translate` fallbacks; the `_router` google
  closure moved into `registry._google_for_call`).
- `detect_language` calls `registry.detectors()`.
- `registry.build_router(sink)` owns the singleton + per-call clone
  (health/policy shared); `app._router` is a thin forwarder kept for
  existing callers.
- Zero `from qtranslate.services import X as _Y` dispatch aliases remain
  (verified by source scan; `SUPPORTED_LANGS` constant imports are
  explicitly allowed — shared language-index table, not dispatch).
- The dead `dictionary as _D` import in the services options page is
  gone (display names now come from `config.SERVICE_DISPLAY` /
  `DICT_DISPLAY`); the languages page reads `SUPPORTED_LANGS` via a
  direct constant import.

`registry.py` imports no tkinter and no `app` at module level (both
pinned by static checks that run headless — peer finding 2026-10-15:
the no-tkinter assertions used to sit below a tkinter gate and were
silently skipped exactly where they mattered). Core/headless callers get
dispatch without a display.

## 3. Tests

- `tests/regress_registry.py` (43 checks, two halves): static half
  (always runs headless — table ownership, no app literals, no
  dispatch aliases, detectors + capability + helper + detect + links
  wiring, tkinter-free construction) + live half (table equality,
  alias identity, order, router build, detectors; honestly SKIPPED
  when tkinter is absent).
- `tests/regress_router_order.py` (9 checks): ServicesOrder mapping,
  alias assertion, full-order routing.
- `tests/regress_dict_lang.py` (9 checks): `LanguageDictionary`
  resolution (default 17 → `en`, auto/`-1`/bad → `en`, real index
  passes through).
- `tests/ui_match.py` `logic-detect-6` updated to assert through
  `registry.detectors()` instead of the old inline tuple.
- `tests/regress_dict_args.py` + `tests/regress_provider_auto.py`
  updated to read the canonical `registry.py` source (tkinter-free)
  instead of importing `app`. The latter caught a real drift:
  `regress_provider_auto` still read the capability table from
  `app.py`, where only an alias remains — fixed to read
  `registry.USES_AUTO_DETECT`, back to green.
- Full headless sweep: **37/37** `regress_*.py` suites PASS +
  `ui_match` 103/103 PASS (GUI session then; `ui_match` creates a Tk
  root). The suite has since grown to **61/61 headless** (one suite per
  module plus the port-fix pins; 63 total minus the 2 window-opening
  suites — `HEADLESS_SWEEP_RULE_2026-10-15.md`).
  Peer-audit fixes landed since: TTS `listen_url` delegation
  **reverted** (it silently changed `/`-encoding, dropped the caller
  `tkk` seed, and floated the host — documented in `tts.py`
  docstring); registry docstring rewritten to describe the landed
  design instead of the pre-flip plan; a false FAIL in
  `regress_source_language` fixed (attribution-comment search anchored
  on the definition line, not the docstring mention).

## 3b. Template-geometry fallback (G9 part-a follow-up, same tree)

`app._place_main`'s no-blob fallback was the stale pixel constant
`"526x366"` (another machine's saved placement). It is now
`TEMPLATE_GEOMETRY = "595x376"`, computed from the measured DLG129
template (340×201 DU at MS Shell Dlg 8pt, baseunit 7×15) with the
arithmetic pinned by two new `ui_match` checks
(`placement-template-const`, `placement-template-arith`), verified
headless. *(It read `595x753` here when first written: both axes were
divided by 4. `/4` horizontally, `/8` vertically — corrected 2026-10-16
along with the constant, and the `ui_match` pin that had been asserting
the wrong divisor.)* Evidence:
`docs/review/G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md`. This changes no
RE state (A7 stays VERIFIED, G9 stays UNKNOWN — part (b) still needs a
capture pair). Follow-up in the same tree: `win32app.py` `W, H` was the
same stale 526x366 constant — now 595x376 from the template; stale
docstring/comment references to the old size corrected to describe the
blob-vs-template distinction instead of citing one machine's rect.

## 3c. Request-shaping dedup (same tree)

`do_translate` pre-collapsed RemoveLineBreaks and then
`ProviderRouter.translate` ran `normalize_request` again — harmless
(idempotent) but double Options.json reads contradicting the layer's
own "happens ONCE" invariant. The pre-transform is removed; the
`_r is None` fallback (which bypasses the router) shapes explicitly.
Equivalence verified headless (`'hello world test'` both ways).

## 4. Deliberately not done in this slice

- Moving `SUPPORTED_LANGS` itself (shared constant; separate slice).
- `Provider` contract / `qtranslate-sdk` (Phase 2 full + Phase 6).
- Committing — forbidden by user rule 7.
