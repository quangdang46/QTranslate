# Port fixes — landed 2026-10-15 (commit `7b8ea7a`)

> Native-to-port gaps closed, with offline tests green. **Landed and
> pushed** at `7b8ea7a` (rule 7 was lifted by the user on 2026-10-15).
> This document records what landed and the evidence behind it.

## 1. Dict-task source follows `General.LanguageDictionary`

- **Native:** `FUN_00414f54` overwrites `param_1[4]` with `DAT_005493f4`
  (`General.LanguageDictionary`, default 17) when `== 1` (auto).
  Evidence: `docs/review/DICT_LANG_BUILDER_2026-10-15.md`.
- **Port (before):** `qtranslate/app.py:3768` `go_all` hardcoded `"en"`.
- **Port (after, working tree):** `go_all` resolves `_dsl` from
  `General.LanguageDictionary` (default 17), guards the auto/`-1`
  sentinel and out-of-range indices back to `"en"`, and calls
  `fn(word_q, _dsl, self.target)`.
- **Note:** `SUPPORTED_LANGS[17] == "en"`, so the default behavior is
  unchanged; only a user who changes the "Dictionary:" combo sees a
  difference — which is exactly the native semantics.
- **Test:** `tests/regress_dict_lang.py` — 9 checks, PASS.

## 2. Router fallback order follows `ServicesOrder`

- **Native D2 (`FUN_0045CEDE`):** picker takes the head of the ordered
  set, i.e. first in `ServicesOrder`.
- **Port (before):** `_router` passed a hardcoded 5-name order
  (`google, microsoft, bing, deepl, yandex`), silently excluding promt,
  babylon, baidu, naver, youdao from every fallback chain.
- **Port (after, working tree):** order built from
  `config.services_order()` numeric ids → `SERVICE_NAMES`, unknown ids
  skipped, TRANSLATORS-only names appended. Default resolves to
  `[google, microsoft, promt, babylon, yandex, youdao, baidu, naver,
  deepl]` (+ `bing` appended — `TRANSLATORS` key absent from
  `SERVICE_NAMES`, kept reachable by the append rule).
- **Test:** `tests/regress_router_order.py` — 9 checks, PASS.

## 3. Layout pairs match P2 decompile set (same tree)

- **Native:** `FUN_00404E09` explicit pairs (±build-order: generic →
  mirrors → explicit last) — evidence
  `docs/review/DIALOG_GEOMETRY_MAP_2026-10-15.md`.
- **Port (before):** 6/8 explicit pairs wrong; uppercase-mirror pass
  clobbered `w`→`W`.
- **Port (after):** `qtranslate/layout.py` reordered generic → mirrors →
  explicit last; `app.py` fallback shaping `if False else` cleaned to
  take `[0]`.
- **Test:** `tests/regress_layout_pairs.py` — 13 checks, PASS.

## 4. Template geometry + win32app (same tree)

- `app._place_main` no-blob fallback was stale `"526x366"` → now
  `TEMPLATE_GEOMETRY = "595x376"` (DLG129 340×201 DU at MS Shell Dlg
  8pt; evidence `G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md`). Pinned by
  `ui_match` `placement-template-const` + `-arith`.
- `win32app.py` same stale `W, H` → 595x376; dead `_font_handle`
  (wrong Tahoma 9, no callers) deleted rather than fixed; `_translate`
  now reads combos 1001/1002 via `_combo_text` (was hardcoded
  `("google", text, "vi")`), pinned by `regress_ui_parity_fixes` §4.
- `ui_match` `logic-detect-6` expectation updated for Phase 2 alias
  shape (`detectors()` unprefixed in `registry.detect_language`).

## 5. auto_detect flag is live (RE-closed same day)

- **Native:** nav-menu 0x808e writes `DAT_0054941f`; `FUN_00404a12`
  packs it into `FUN_004606ba`, whose first branch detects
  (`FUN_0045fde8`) even for a concrete source. `DAT_005494e6` is
  `RemoveLineBreaks` (drives `FUN_004046d6`), not the detect flag.
  Evidence: `SERVICES_PAGE_PARITY_2026-10-15.md` §44.
- **Port (before):** `do_translate(..., auto_detect=False)` accepted
  the flag but never read it; detection ran only on
  `uses_auto_detect(service)`.
- **Port (after):** flag forces detection for `auto` sources and
  re-detects concrete sources, mirroring the native branch.
- **Test:** `tests/regress_provider_auto.py` — 2 new static checks.

## 6. Verification (2026-10-15, offline, no GUI)

- 37/37 `tests/regress_*.py` PASS + `tests/ui_match.py` 103/103 PASS
  (GUI session then; `ui_match` creates a Tk root and is not re-run in a
  no-GUI session — see `HEADLESS_SWEEP_RULE_2026-10-15.md`).
- `tools/coverage_tally.py --check`: 151 VERIFIED / 1 UNKNOWN (G9),
  Gate BLOCKED (1) — unchanged, as expected (port-side fixes do not
  move RE states).

## 7. What remains (blockers, honest)

1. **G9 `UNKNOWN`** — needs a native-vs-port screenshot pair; screenshots
   are banned (user order 2026-10-15: "đừng screenshot nữa"), and
   `tools/g9_screenshot_diff.py` was deleted per user order (deletion
   landed at `7b8ea7a`) with its README line removed. Historical
   references in `G9_HARNESS.md` / `G9_RESULT_2026-10-09.md` /
   `g9_samples/` reports are kept as record. Gate stays BLOCKED (1), no
   waiver taken.
2. **Core + Extensions migration** — slices 1–5 landed at `7b8ea7a`
   (see `CORE_EXTENSIONS_SLICES_1_5_2026-10-15.md`). Remaining:
   extensions-dir discovery, override UI, macOS adapters, packaging.
3. ~~These fixes are uncommitted~~ **landed** at `7b8ea7a` (user lifted
   rule 7). The file list below is kept as the record of what that commit
   contained (`M
   (dict `_dsl`, router order, auto_detect wiring, aliases),
   `M qtranslate/layout.py`, `M qtranslate/tts.py`, `M
   qtranslate/win32app.py`, `M tests/regress_dict_args.py`, `M
   tests/regress_provider_auto.py`, `M tests/regress_source_language.py`,
   `M tests/ui_match.py`, plus new `qtranslate/registry.py`,
   `qtranslate/placement.py`, 5 regress suites, and 7 review docs).
