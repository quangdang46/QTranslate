# Compatibility Matrix — QTranslate 6.10.0 → new Core

> **2026-10-22/23: the front end IS the PySide6 view.**
> `qtranslate/qt/` is the only view (`6636686` deleted the tkinter one).
> Its windows are drawn on the geometry measured off
> native's own captures and compared with them pixel by pixel
> (`tools/render_qt.py --compare`): the mean difference over twelve screens is
> **0.0037** of the pixels, measured as the TOTAL INK, which is the
> ClearType-invariant measure (the plain RGB difference counts the
> sub-pixel fringes, and the spec says to ignore them).
>
> Two rows below change because of it, and both were **wrong before**:
>
> - *Main window (DLG129)* -- the port's layout is now measured against
>   native's capture rather than against the template, and the FONT is
>   settled: **Tahoma 8pt (11px) for the controls, Tahoma 9pt (12px) for
>   the two text panes**. The native's own text says which font it is in
>   pixels ("Double Ctrl => Show main window (with translation of selected
>   text, if any)" is 418px wide there, which is Tahoma 9pt at 420 and not
>   Tahoma 8pt at 363), and the line pitch is 14px. The spec's "Segoe UI
>   9pt" was an inference and it was wrong. See
>   `docs/review/PYSIDE6_PARITY_2026-10-22.md`.
> - *Settings defaults* -- the native's real `Options.json` had been lost
>   from the machine, so the port's defaults were the only thing left to
>   read, and they disagreed with the native in three places
>   (`ExpandHistoryItems`, the seventeen `HotKeys` keys, and the
>   replace-selection code on the wrong key). Corrected.
>
> The **port state** vocabulary is unchanged: a row is `behaviour-verified`
> only when an acceptance test proves it, and every acceptance run in this
> project is Windows-only, so no row may be called cross-platform verified.
>
> Status: **PLANNING.** Decision D10 = preserve **nearly all** behavior
> (Level A). This matrix is the **acceptance baseline**: each row is a behavior
> that must be preserved or consciously dropped, with evidence and a test.
> Nothing is marked *verified* because code exists — only because a test proves
> it.

## Status vocabulary (fixed)

Two **independent** axes (`PROJECT_VISION.md` §7a). A row carries one from each;
never let one imply the other.

**Axis 1 — native RE evidence** (what we know about QTranslate 6.10 itself):
`VERIFIED` · `INFERRED` · `UNKNOWN` · `UNRECOVERABLE(reason+impact)`.

**Axis 2 — Python implementation (port state).** Canonical labels (identical to
`PROJECT_VISION.md` §7a and `RE_COVERAGE_CHECKLIST.md`):

| Tag | Meaning |
|-----|---------|
| `not-started` | no implementation |
| `analysed` | native behavior understood, no port |
| `ported` | Python exists, behavior **not proven equivalent** |
| `behaviour-verified` | an acceptance test proves it **on the platforms named in Test-on** |
| `dead:<reason>` | port preserved but endpoint/feature cannot run (retired server, token wall) |

> **Not a port state:** "we decide not to preserve this" is a **product
> decision**, recorded in the row's *Must keep* column as `drop`, while its
> Port state stays real (`dead:<reason>` if it cannot run, else `ported`). There
> is no `intentional-drop` port state — it was removed to match the canonical
> vocabulary (`RE_COVERAGE_CHECKLIST.md`).

**Platform columns are split — this is the correction:**
- **Target** = platforms the feature must eventually support.
- **Test-on** = platforms where an acceptance test has actually been run.

A row is only `behaviour-verified` when `Test-on` covers every platform in **Target**.
Today **every row's `Test-on` is Windows-only** (all evidence in
`CURRENT_STATE.md`/`LIVE_RESULTS.md` is from a Windows machine). Therefore **no
row is mac-verified**, and none may be described as cross-platform-verified
until macOS tests exist.

**Rule:** a row moves to `behaviour-verified` only when its acceptance test passes on both
platforms it claims. Evidence column cites `file:line` where available.

## A. Startup · window · hotkey

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| Single-instance guard | `FUN_00435005`, `docs/NATIVE_ARCH.md:367` | present (`single_instance` lock) | yes (bring existing window forward) | Win+mac | `tests/regress_single_instance.py` (9) | `behaviour-verified` — **Win only** |
| Main window (DLG129, template `340×201` DU @ `MS Shell Dlg` 8pt, 17 ctls) | `FUN_00411DEB`, `NATIVE_ARCH.md:1086` | `qtranslate/qt/main_window.py` (Qt view; DLG129 geometry per G9) | layout + control ids | Win+mac | `tests/ui_match.py` structure + `tools/render_qt.py --compare` (0.0037 over 12 screens) | `behaviour-verified` — **Win only**, geometry only | **corrected 2026-10-10:** earlier said `526×366, Tahoma`. `526×366` is a *runtime pixel* size from a saved `WINDOWPLACEMENT` (not the template), and the font is `MS Shell Dlg` 8pt, not Tahoma (`docs/review/G9_SPEC_NATIVE_WINDOW_2026-10-10.md`). `qtranslate/placement.py:TEMPLATE_GEOMETRY` still sizes to `526x366` — template-vs-placement is a Phase 7 decision. **RESOLVED 2026-10-16:** `placement.py`'s `TEMPLATE_GEOMETRY` is now `595x376` — the DU→px conversion of `340×201` at `MS Shell Dlg` 8pt with the standard `7×15` baseunit, using `/4` horizontally and `/8` vertically (`G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md`). **Arithmetic re-corrected 2026-10-16:** the first fix divided *both* axes by 4 and produced `595×753` — a main window nearly twice as tall as native's. `ui_match` had been pinning that wrong value (`201 * 15 // 4 == 753`), so it looked verified. `G9_PART_A_CLOSED_2026-10-16.md` §1 — and the first-run fallback is that value, not a stale pixel constant from another machine's saved placement. When a `WindowMainPlacement` blob exists, `place_main` restores it instead, which is what native does. Pinned by `tests/regress_g9_part_a_complete.py` |
| WINDOWPLACEMENT restore | `NATIVE_ARCH.md:1086` | `qtranslate/placement.py:place_main` | yes | Win+mac | reopen → same geom; `tests/regress_placement.py` (13) | `behaviour-verified` — **Win only** |
| 17 global hotkeys | `FUN_00405A17`, `NATIVE_ARCH.md:677` | `qtranslate/qt/hotkeys.py:install` (`keyboard`) | all 17, from Options.json | Win ✓ / mac needs perm | `tests/regress_hotkey_decode.py` (10) + `regress_hotkey_coverage.py` (6) | `behaviour-verified` — **Win only** |
| Hotkey display string | `FUN_00403B48/D3C` | `config.format_hotkey` | "Double Ctrl + Q" form | Win+mac | `tests/regress_hotkey_option_keys.py` (9) known-answer vectors | `behaviour-verified` — **Win only** |
| Double-press detection | `FUN_0041786B`, `NATIVE_ARCH.md:915` | partial | Ctrl+C+C / Ctrl+Q+Q | Win+mac | manual desktop test, NO automated suite | `ported` — unpinned, needs a human |
| Menu accelerators / help.txt default | `NATIVE_ARCH.md:404` | `qtranslate/qt/main_window.py` + `qtranslate/assets/locales/English/help.txt` | yes | Win+mac | `tests/ui_match.py` (tray order) + `tests/regress_menu_slots.py` (37) | `behaviour-verified` — **Win only**, menus only |
| Cursor-hook mouse icon | `NATIVE_ARCH.md:121` | **none** | decide | Win | — | `not-started` |

## B. Capture (3 modes)

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| Mode 3 clipboard capture | viewer `FUN_0043EBE0` | `qtranslate/selection.py:copy_selection` (sequence-number proof, not a fixed sleep) | yes | Win+mac | `tests/regress_selection_capture.py` (15) + `regress_qt_features.py` Ctrl+Q path | `behaviour-verified` — **Win only** |
| Mode 2 mouse (OLEACC) | `FUN_00404901` | `mouse_capture.cursor_text()` via `_capture_selection` (`qtranslate/qt/app.py`); the Tk path is gone with the front end | yes (native core UX) | Win | OLEACC contract suite (`regress_oleacc_contract.py`) + `tests/regress_mouse_capture.py` (42) + `regress_qt_features.py` (hook, gate, capture, speak) | `behaviour-verified` — **Win only** |
| Mode 1 reuse-text | `FUN_004052E4` | partial | yes | Win+mac | — | `ported` — no suite, unpinned |
| SendInput synth (Ctrl+C) | `FUN_0043BD5C` | `qtranslate/sendkeys.py:send` | yes | Win / mac perm | `tests/regress_selection_capture.py` (15) drives the send + backoff | `behaviour-verified` — **Win only** |
| Replace-selection write-back | `FUN_0043BE56`, `NATIVE_ARCH.md:650` | `qtranslate/sendkeys.py:write_text` via `QtApp.hotkey_replace_selection` | yes | Win / mac perm | `tests/regress_sendkeys.py` + `regress_selection_capture.py` (the selection read) | `behaviour-verified` — **Win only** |
| Foreground exclusion list | `FUN_004631DE/004470B7` | `exclusions.py` | yes (Disabled/Enabled + mode) | Win / mac | `tests/regress_exclusions.py` (12) wcsicmp vectors | `behaviour-verified` — **Win only** |
| **Source-language arg (auto vs selected)** | dispatcher `FUN_00404A12`; per-service `usesAutoDetectCode` hook (`FUN_0045f6c1` → `request+0x50`, consumed by `FUN_004606ba`) | `qtranslate/engine.py:translate`: echo on `src == target`; `_USES_AUTO_DETECT` declares auto-capability per provider | **decided 2026-10-10:** the rule is *capability-dependent and per-service* — the dispatcher echoes when source == destination and skips the service; detect runs only when the service does not answer `usesAutoDetectCode`, or when the destination is also unset. It is neither "all paths honor the selected source" nor "only the popup hotkey" | Win+mac | `tests/regress_source_language.py` (30) | `behaviour-verified` — **Win only** |

> **This row's "decide one rule" is closed as of 2026-10-10** — it was neither
> option it offered. Evidence and the exact branch conditions:
> `docs/review/SOURCE_LANGUAGE_RULE_2026-10-10.md`, decompiled from the
> recovered image in the full-analysis project `QT_FULL`.
>
> **One caveat that must travel with this row.** Native's rule is a *query* —
> it calls the service's `usesAutoDetectCode` JS hook — and those `Service.js`
> files are runtime-loaded, absent from the artifact
> (`docs/review/PLUGIN_LOADER_FOUND_2026-10-10.md`). So the port's
> `_USES_AUTO_DETECT` table is a **declared port-side capability, explicitly
> not native-derived**, and the per-service truth table is unverifiable here.
> Reading this row as "the auto-detect set is native-verified" would be wrong.

## C. Translation engine + providers

> **Coverage note:** the authoritative per-service inventory (19 services, one
> checklist row each) lives in `RE_COVERAGE_CHECKLIST.md` §E. This matrix
> section lists them as a *compatibility* subset; **no service present in the
> checklist may be missing here** (reconciliation rule, `TEST_STRATEGY.md`).

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| Orchestrator (pick→exec→render) | `FUN_00404A12`, `NATIVE_ARCH.md:442` | `qtranslate/engine.py:translate` | behavior | Win+mac | `tests/regress_translate_response_chain.py` (45) + `regress_app_reliability_e2e.py` (10) | `behaviour-verified` — **Win only** |
| Provider priority (ServicesOrder) | `FUN_0045CEDE` | `config.services_order` | exact order `[1,5,12,13,11,26,28,30,31]` | Win+mac | `tests/regress_router_order.py` (10) | `behaviour-verified` — **Win only** |
| Auto-detect (6-provider loop) | `FUN_00460354` | `qtranslate/registry.py:detect_language` | order + fallthrough | Win+mac | `tests/regress_auto_detect_capability.py` (26) + `regress_provider_auto.py` | `behaviour-verified` — **Win only** |
| Back-translation | `FUN_004606BA` | `qtranslate/engine.py:translate` (back_translate path) | yes | Win+mac | `tests/regress_translate_response_chain.py` (45) | `behaviour-verified` — **Win only** |
| Google translate | — | `google_translate.py` | yes | Win+mac | live EN→VI (Win) | `behaviour-verified` — **Win only** (mac untested) |
| Microsoft/Bing | — | `session.bing_translate` | yes | Win+mac | live EN→VI (Win) | `behaviour-verified` — **Win only** (mac untested) |
| DeepL | — | `deepl.py` | yes | Win+mac | live EN→VI (Win) | `behaviour-verified` — **Win only** (mac untested) |
| Yandex | — | `yandex.py` (android) | yes | Win+mac | live EN→RU (Win) | `behaviour-verified` — **Win only** (mac untested) |
| Naver/Papago | — | `naver.py` (new API) | yes | Win+mac | live EN→VI (Win) | `behaviour-verified` — **Win only** (mac untested) |
| Baidu translate | — | `baidu.py` | see status | Win+mac | detect live | `dead:needs-session-token` |
| Youdao translate | — | `youdao.py` | see status | Win+mac | translate_web live | `ported` — live verify needs a key/session, unpinned |
| Promt | `ghcs` verified | `promt.py` | see status | Win+mac | signing vectors | `dead:needs-session-token` |
| Babylon translate (ID13) | `NATIVE_ARCH.md` | `babylon.py` | see status | Win+mac | — | `dead:host-retired` |
| ImTranslator (ID18) | — | ported | no | — | — | `dead:host-retired` |
| **Fallback on failure** | backtrans/detect retry | `reliability.FallbackRouter` via `qtranslate/engine.py:translate` via `reliability.FallbackRouter` | yes (D12) | Win+mac | `regress_reliability.py` §5 + `regress_app_reliability_e2e.py` (10, drives `app.on_go()`) | `behaviour-verified` — **Win only** |
| **Bounded retry + timeout** | `FUN_0045BCED/0045BF7D` | `reliability.RetryPolicy` (base/max delay, `Retry-After`, shared budget) + `session.py` timeout | yes | Win+mac | `regress_reliability.py` §2–4 | `behaviour-verified` — **Win only** |
| **Error classification** | — | `reliability.ErrorKind` (9 kinds) + `classify()` `reliability.py:136` | yes | Win+mac | `regress_reliability.py` §1 (taxonomy, incl. SSL → `PROVIDER_DEAD`) | `behaviour-verified` — **Win only** |

**Reconciliation vs `RE_COVERAGE_CHECKLIST.md` §E (19 services + Common.js).**
This matrix does not list every service as its own row; the mapping is:

| Matrix row | Checklist items it covers |
|------------|---------------------------|
| Google translate / Bing / DeepL / Yandex / Naver-Papago | E2, E3, E4, E5, E6 (1:1) |
| Baidu translate · Youdao translate · Promt · Babylon · ImTranslator | E7, E9, E8, E10, E12 |
| Oxford/Lingvo/Urban/Wikipedia/Multitran/WordReference | E14, E15, E16, E17, E18, E19 (dict) |
| Reverso translate | E13 |
| ImTranslator/Babylon dict/Google Search | E11 (Babylon Dictionary), E12, E20 |
| (shared) | E1 `Common.js` → covered by `common.py` behavior |

No checklist §E service is absent from a matrix row. **Reconcile-or-journal rule:**
if a future inventory bump adds a service, it must be added here or the gap
recorded — a service may never quietly disappear between the two docs.


## D. Rendering · popup · theme

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| Popup window (borderless, topmost) | `FUN_0040C393`, `NATIVE_ARCH.md:1476` | `qtranslate/qt/popup.py:PopupWindow` + `QtApp.show_translation` | behavior | Win+mac | `tests/regress_popup_smoke.py` (20) + `ui_match.py` popup-* + 2162/2163 captures | `behaviour-verified` — **Win only** |
| Auto-fit layout engine | `FUN_0044B4F4`, `NATIVE_ARCH.md:1476` | `qtranslate/qt/popup.py` (content-sized; MIN/MAX bounds) | behavior | Win+mac | `tests/ui_match.py` popup-size-bounded/grows/clamped + content-driven sizing | `behaviour-verified` — **Win only** |
| RichEdit link tagging (`qtdp:`) | `FUN_004266C6`, `FUN_00465574` | dictionary-card link handling | yes | Win+mac | `tests/regress_dictionary_html.py` (qtdp: left alone) + `regress_plugin_js_recovered.py` (Oxford qtdp: rewrite) | `behaviour-verified` — **Win only** |
| 8+ themes (JSONC) | `FUN_0044C4CA`, `NATIVE_ARCH.md:926` | `theme.py` | load + roundtrip | Win+mac | `tests/regress_theme_all.py` (308, 8 themes) + `regress_theme_loader_jsonc.py` | `behaviour-verified` — **Win only** |
| Theme brightness shift | `FUN_0044A163` | `theme.adjust_brightness` | yes | Win+mac | `tests/regress_theme_colors.py` (303) vector table | `behaviour-verified` — **Win only** |
| Popup state colors | `FUN_0044FE1B` | `theme.window_colors` + `state_name` (0 Normal, 1 Hover, 2 Pressed, 3 Disabled, 4→Normal palette; Blue verified all 5) | states 0/1/2/3/4 (4→Normal: focus is a flag, not a palette) | Win+mac | `tests/regress_theme_colors.py` (303, state table + window_colors roundtrip) | `behaviour-verified` — **Win only** |
| **Visual fidelity to native** | screenshots | low (user) | target | Win+mac | screenshot diff | `not-started` |

## E. Dictionary · history · XDXF

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| 11 dictionary providers | `NATIVE_ARCH.md:801` | `dictionary.py` | working ones | Win+mac | `smoke_dict` + live | mixed |
| Oxford/Lingvo/Urban/Wikipedia/Multitran/WordReference | — | ported | yes | Win+mac | live OK (Win) | `behaviour-verified` — **Win only** |
| Reverso translate | — | ported | yes | Win+mac | live OK (Win) | `behaviour-verified` — **Win only** |
| ImTranslator/Babylon dict/Google Search | — | ported | no | — | — | `dead:host-retired` / `dead:bot-walled` |
| XDXF offline dict | `FUN_00445BB9`, `NATIVE_ARCH.md:1382` | `xdxf.py` | yes | Win+mac | `tests/regress_xdxf_passthrough.py` (25) + `regress_xdxf_render.py` + `regress_xdxf_vs_xslt.py` | `behaviour-verified` — **Win only** |
| dict template RT_HTML-192 | `qtranslate/dict_template.html` + `tests/regress_dict_template.py` (the `NATIVE_ARCH.md:1392` line previously cited here is the Youdao `Utils.md5` note — wrong reference, corrected 2026-10-16) | `dict_template.html` | byte-identical | Win+mac | MD5 (Win) | `behaviour-verified` (artifact, OS-independent) |
| History (DLG164) JSON+CSV order | `FUN_004638D8` **loader** / `FUN_00463B04` **saver** | `history.py` | col order `[a,c,b,e,d]` | Win+mac | `tests/regress_history_export.py` (JSON comma + CSV order) + `regress_history_dispatch.py` | `behaviour-verified` — **Win only** |
| History favorites | — | `qtranslate/history.py` (favorites pending; lifecycle wired) | yes | Win+mac | `tests/regress_history_dispatch.py` (lifecycle only, not the star) | `ported` — favorites unpinned |
| Export Csv/Html/Json/Txt | `Plugins/History/*.js` | `history.py` | 1:1 | Win+mac | `tests/regress_history_export.py` (native parity) | `behaviour-verified` — **Win only** |

## F. TTS · speech-in · OCR · spell · layout

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| TTS online mp3 | `FUN_004614BB` | `tts.py` | yes | Win+mac | live mp3 (Win) | `behaviour-verified` — **Win only** (Google) |
| BASS playback | `FUN_00461642`, `NATIVE_ARCH.md:1603` | `player.py` (real bass.dll) | behavior | Win / mac(no bass.dll) | `tests/regress_player.py` (8, backend selection) + `tests/live_bass.py` (manual, audio hardware) | `ported` — request path pinned, audible output needs hardware |
| Offline TTS fallback | **no native SAPI found** — `FUN_00448BEC` is the MSXML DOMDocument engine (see `RE_PROGRESS.md` §Tensions #5) | `sapi.py` (our fallback only) | mac replacement | Win / mac | `tests/regress_sapi_and_keyboard.py` (19, contract + key grid) | `ported` — contract pinned, audible output needs hardware |
| Slow TTS flag | `Advanced.EnableSlowerListening` | `qtranslate/player.py:play_text` (slow passthrough) | yes | Win+mac | `tests/regress_tts_slow.py` (7) | `behaviour-verified` — **Win only** |
| Read-phonetically (display) | `FUN_0042ED3F` appends `"\r\r"`+res186("Romanization: ")+`entry[5]` to the result when flag on AND `"<Error>"` absent (gate `FUN_00403897`) — an annotation on a *successful* result, never a replacement (J7) | `qtranslate/engine.py:translate` → `phonetics.append_phonetics` | preserve | Win+mac | `tests/regress_phonetics.py` (35) + `tests/regress_google_romanization.py` (19, 4 live langs) | `behaviour-verified` — **Win only**, phonetics **display** not TTS; Google `dt=rm` only, as natively |
| Speech input (mic → FLAC) | `FUN_0044555D`, `NATIVE_ARCH.md:1627` | `comtypes` SAPI | mac replacement | Win / mac | — | `dead:native-unavailable` |
| OCR (ocr.space) | `OcrSpaceProvider`, `NATIVE_ARCH.md:993` | `services/ocr.py` | yes | Win+mac | `tests/regress_ocr_multipart.py` (20, request shape) + `regress_ocr_languages.py` (72) — live OCR needs key | `behaviour-verified` — **Win only**, request shape only |
| OCR region select overlay | `ScreenCaptureWindow` | `qtranslate/qt/ocr_pick.py:RegionPicker` (`QScreen.grabWindow`) + `qtranslate/qt/ocr_window.py` (menu 10 host) | yes | Win+mac | `tests/regress_menu_slots.py` (37, slot host) | `behaviour-verified` — **Win only**, overlay + window only |
| Spell (Google suggest + Yandex) | `NATIVE_ARCH.md:982` label is wrong — `FUN_0042C909` is a destructor (see `RE_PROGRESS.md` §Tensions #3); real spell entry not read | `services/spell.py` | yes | Win+mac | live OK (Win) | `behaviour-verified` (port); native spell entry `INFERRED` — **Win only** |
| Keyboard-layout convert | `FUN_00404E09`, `NATIVE_ARCH.md:1282` | `layout.py` | yes | Win+mac | `tests/regress_layout_pairs.py` (13) | `behaviour-verified` — **Win only** |

## G. Options · i18n · tray · system

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| 9 Options pages | `FUN_004561F0`, `NATIVE_ARCH.md:781` | `qtranslate/qt/options/` (single shell, `OptionsBase._show_page` rebuilds in place) | 9/9 on real Options.json | Win+mac | `tests/ui_match.py` pages-9/order/ids + `regress_qt_features.py` (each page builds, swap keeps winId) | `behaviour-verified` — **Win only** |
| Options.json 20 sections R/W | `NATIVE_ARCH.md:398` | `config.py` | full roundtrip | Win+mac | `tests/regress_options_roundtrip.py` (5, live 20-section + Ocr + stable dump) | `behaviour-verified` — **Win only** |
| Hotkey rebind UI | `FUN_00408456` | `qtranslate/qt/options/hotkeys.py` (single-shell page) | yes | Win+mac | `tests/regress_qt_features.py` (HotkeysPage builds, 17-key codec in hotkeys.py) | `behaviour-verified` — **Win only** |
| Proxy / Internet.Timeout | `NATIVE_ARCH.md:1303` | `session.net_options` | yes | Win+mac | `tests/regress_proxy_options.py` (10) | `behaviour-verified` — **Win only** |
| i18n lang.json (36 strings, 14 win) | `FUN_0045B716`, `NATIVE_ARCH.md:1071` | `locale.py` | vi verified + en fallback | Win+mac | `tests/regress_locale_all_packs.py` (148, 35 packs) + `regress_locale.py` | `behaviour-verified` — **Win only** |
| Tray states | `FUN_00405C42`, `NATIVE_ARCH.md:1214` | `qtranslate/qt/tray.py:Tray` (QSystemTrayIcon; pystray gone with tkinter) | behavior | Win+mac | `tests/regress_tray_menu.py` (8) + `regress_tray_state.py` (12) | `behaviour-verified` — **Win only**, order + state |
| Start-with-system (Run key) | `NATIVE_ARCH.md` | `winreg` Run-key write (startup entry; UI-independent, still present where applicable) | mac replacement | Win / mac | `tests/regress_startup_entry.py` | `behaviour-verified` — **Win only** |
| Crash once-reporter | `FUN_00462C03`, `NATIVE_ARCH.md:413` | `qtranslate/crash.py:install_crash_hook` | behavior | Win+mac | `tests/regress_crash_failfast.py` (21) + `regress_crash_reporter.py` (9) | `behaviour-verified` — **Win only** |
| Updater | `FUN_00461A26` | flag only | **drop** (dead) | — | — | `dead:host-retired` (2022) |
| Fonts (Tahoma/Segoe UI) | `NATIVE_ARCH.md:1086` | `qtranslate/qt/main_window.py:PANE_FONT` (9pt panes) + `qtranslate_style.py` (11px UI) | mac mapping | Win+mac | `tests/regress_fonts.py` | `behaviour-verified` — **Win only** |

## H. New capabilities (no native equivalent)

| Feature | Evidence | Status | Notes |
|---|---|---|---|
| Extension SDK (provider/workflow/theme/UI) | design only | `not-started` | `EXTENSION_SDK.md` |
| Extension override + fail-open | design only | `not-started` | §Override rules |
| Reliability layer (classify/retry/fallback) | `FUN_004606BA` route + per-call retry | `reliability.ProviderRouter` via `qtranslate/engine.py:translate` | yes | Win+mac | `regress_wiring.py` + `regress_reliability.py` | `behaviour-verified` — **Win only** |
| macOS adapters (hotkey/clipboard/capture/audio) | none | `not-started` | macOS never tested |
| Stable-id registry (unify 3 sources) | audit | `not-started` | `ARCHITECTURE.md` §3.2 |

## Summary counts (this matrix, honest)

> **Reconciled 2026-10-14** to the machine tally (`tools/coverage_tally.py`:
> `ported 125` · `behaviour-verified 14` · `not-started 4` · `dead:* 9`).
> The 2026-10-09 figures this table used to carry (`ported 121`,
> `behaviour-verified 11`, `not-started 11`) were stale by three rows in
> section C alone: **Fallback on failure**, **Bounded retry + timeout**, and
> **Error classification** all landed with the reliability layer on
> 2026-10-10 and none of them was ever re-marked here. Updated by reading
> `reliability.py` + `regress_reliability.py`, not by copying the tally.

| Implementation status | Rows | Note |
|-----------------------|------|------|
| `behaviour-verified` | 14 | **all Win-only** (Test-on = Windows); none mac-verified |
| `ported` | 125 | "Python exists", not "proven equivalent" |
| `dead:*` | 9 | endpoint/feature cannot run; reason slug + citation recorded |
| `not-started` | 4 | C10, F13, G9, J6 — all four re-verified as correct negatives/none (`docs/review/FOUR_NOT_STARTED_REVERIFIED_2026-10-12.md`) |

Product decision (not a port state): the **Updater** is a conscious `drop` — its
server retired in 2022 — so its Port state is `dead:host-retired`.

> These counts are the **implementation axis** only and are per-row/coarse;
> they are **not** a "% of QTranslate reverse-engineered". Native **RE coverage**
> is tracked separately in `RE_COVERAGE_CHECKLIST.md`: as of 2026-10-15 it is
> **151 VERIFIED / 1 UNKNOWN (G9) of 152**, Gate **BLOCKED (1)**.
> Neither number opens the Gate; only the checklist does.
> Many rows here are `ported` — meaning "Python exists", **not** "proven
> equivalent". `behaviour-verified` always means "tested on the platforms in
> Test-on", which today is **Windows only**.
