# Phase 0 baseline snapshot — re-run, not copied (2026-10-15)

> `IMPLEMENTATION_PLAN.md` Phase 0, "Done when": *a baseline snapshot of
> current test results is recorded (re-run, not copied from README).* This
> file IS that baseline: every suite was executed on 2026-10-15 in a no-GUI
> session, and each line below is that run's own summary line (or, where the
> suite prints its pass line, verbatim tail).

## Method

- Each `tests/regress_*.py` run as `python -I <suite>`; pass = exit code 0.
  (`TEST_STRATEGY.md` rule 7: exit code, not a text grep.)
- Excluded (GUI-session-only, open a Tk root):
  `tests/regress_screens.py`, `tests/regress_tray_menu.py`.
- Also excluded here (not a regress suite): `tests/ui_match.py`
  (103 `check(`, creates a Tk root), `tests/smoke_dict.py`, live suites.
- RE state at snapshot time: `151 VERIFIED / 1 UNKNOWN (G9)`,
  `gate=BLOCKED (1 unresolved)` — recorded separately, unchanged by this.

## Results (62 headless suites, all exit 0)

| suite | result line (verbatim tail) |
|---|---|
| regress_cli_args | all checks ok (9 assertions) |
| regress_clipboard | all checks ok (9 assertions) |
| regress_common_framework | all checks ok (73 assertions) |
| regress_core_result | all checks ok (20 assertions) |
| regress_core_result_uses | all checks ok (9 assertions) |
| regress_crash_reporter | all checks ok (9 assertions) |
| regress_dict_args | OK: multitran args + call-site pass-through |
| regress_dict_card | all checks ok (40 assertions, artifact=used) |
| regress_dict_lang | 9 checks, 0 failed |
| regress_dict_template | all checks ok (6 assertions, 1 skipped — pefile absent) |
| regress_enable_history | OK: EnableHistory gates push_hist |
| regress_engine | 16 checks, 0 failed |
| regress_exact_search | OK: DictionaryExactSearch gates XDXF match breadth |
| regress_exclusions | all checks ok (12 assertions) |
| regress_extensions | 12 checks, 0 failed |
| regress_fonts | all checks ok (12 assertions) |
| regress_google_romanization | all checks ok (25 assertions) |
| regress_history_dispatch | all checks ok (18 assertions) |
| regress_history_export | OK: history exporters match native (JSON fix verified) |
| regress_hotkey_coverage | all checks ok (6 assertions) |
| regress_hotkey_decode | all checks ok (10 assertions) |
| regress_lang_tables | OK: all 11 dict language tables are 76 entries + spot values match |
| regress_language_index | all checks ok (32 assertions) |
| regress_layout_pairs | 13 checks, 0 failed |
| regress_locale | all checks ok (11 assertions) |
| regress_mouse_capture | all checks ok (40 assertions) |
| regress_net_open | all checks ok (5 assertions) |
| regress_ocr_multipart | all checks ok (9 assertions) |
| regress_oleacc_contract | all checks ok (26 assertions) |
| regress_options_roundtrip | all checks ok (5 assertions) |
| regress_phonetics | all checks ok (35 assertions) |
| regress_placement | all checks ok (11 assertions) |
| regress_platforms | 15 checks, 0 failed |
| regress_player | all checks ok (8 assertions) |
| regress_plugin_js_recovered | all checks ok (121 assertions, payload used) |
| regress_popup_smoke | all checks ok (15 assertions) |
| regress_promt_pageload | all checks ok (11 assertions) |
| regress_provider_auto | OK: bing/microsoft receive native 'auto' source |
| regress_provider_contract | 67 checks, 0 failed |
| regress_proxy_options | all checks ok (10 assertions) |
| regress_registry | 43 checks, 0 failed, 0 skipped |
| regress_reliability | OK: reliability classify/retry/fallback/health/adapter |
| regress_result_shape | all checks ok (17 assertions) |
| regress_router_order | 10 checks, 0 failed |
| regress_sdk | 17 checks, 0 failed |
| regress_sendkeys | all checks ok (9 assertions) |
| regress_session | all checks ok (12 assertions) |
| regress_single_instance | all checks ok (9 assertions) |
| regress_source_language | all checks ok (17 assertions, app_import=True) |
| regress_speech_input | OK: full-duplex speech URL builder matches native FUN_004434FE |
| regress_spell_headers | all checks ok (8 assertions) |
| regress_startup_entry | all checks ok (6 assertions) |
| regress_theme_colors | all checks ok (304 assertions, payload used) |
| regress_tkk_markers | all checks ok (17 assertions) |
| regress_translate_errors | OK: provider failures route to the native error string |
| regress_tray_state | all checks ok (12 assertions) |
| regress_tts_slow | all checks ok (7 assertions) |
| regress_ui_parity_fixes | 31 checks, 0 failed |
| regress_updater | OK: updater manifest parser |
| regress_wiring | all checks ok (7 assertions, orphans=[…]) |
| regress_xdxf_render | all checks ok (10 assertions) |
| regress_yandex_disk | all checks ok (8 assertions) |

## Notes

- `regress_dict_template`'s single skip is by design: the RT_HTML-192
  byte-identity check needs `pefile`, and degrades honestly to
  `+1 skipped` without it. With pefile the same suite runs 7/7.
- Artifact-backed suites used the in-repo payload
  (`docs/review/artifacts/`, NSIS blob + recovered exe).
- GUI-session-only suites are out of scope for this baseline, not claimed:
  `regress_screens`, `regress_tray_menu`, `ui_match` (103 `check(`s),
  `smoke_dict`, live suites.
