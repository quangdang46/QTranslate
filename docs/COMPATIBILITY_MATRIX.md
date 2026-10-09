# Compatibility Matrix — QTranslate 6.10.0 → new Core

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
| Single-instance guard | `FUN_00435005`, `docs/NATIVE_ARCH.md:367` | absent | yes (bring existing window forward) | Win+mac | launch twice → one window | `analysed` |
| Main window (DLG129, 526×366, Tahoma) | `FUN_00411DEB`, `NATIVE_ARCH.md:1086` | `app.py:634` Tk | layout + control ids | Win+mac | `ui_match` structure | `ported` |
| WINDOWPLACEMENT restore | `NATIVE_ARCH.md:1086` | `app.py:264-346` | yes | Win+mac | reopen → same geom | `ported` |
| 17 global hotkeys | `FUN_00405A17`, `NATIVE_ARCH.md:677` | `app.py:3550` (`keyboard`) | all 17, from Options.json | Win ✓ / mac needs perm | registry == Options.json | `ported` |
| Hotkey display string | `FUN_00403B48/D3C` | `config.format_hotkey` | "Double Ctrl + Q" form | Win+mac | known-answer vectors | `ported` |
| Double-press detection | `FUN_0041786B`, `NATIVE_ARCH.md:915` | partial | Ctrl+C+C / Ctrl+Q+Q | Win+mac | manual | `ported` |
| Menu accelerators / help.txt default | `NATIVE_ARCH.md:404` | `app.py` | yes | Win+mac | `ui_match` | `ported` |
| Cursor-hook mouse icon | `NATIVE_ARCH.md:121` | **none** | decide | Win | — | `not-started` |

## B. Capture (3 modes)

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| Mode 3 clipboard capture | viewer `FUN_0043EBE0` | `app.py:3407` monitor | yes | Win+mac | copy→hotkey→translate | `ported` |
| Mode 2 mouse (OLEACC) | `FUN_00404901`, `NATIVE_ARCH.md:189` | **none** | yes (native core UX) | Win | select→hotkey→translate | `not-started` |
| Mode 1 reuse-text | `FUN_004052E4` | partial | yes | Win+mac | — | `ported` |
| SendInput synth (Ctrl+C) | `FUN_0043BD5C` | `keyboard.send` `app.py:3598` | yes | Win / mac perm | — | `ported` |
| Replace-selection write-back | `FUN_0043BE56`, `NATIVE_ARCH.md:650` | `_replace` `app.py:3592` | yes | Win / mac perm | — | `ported` |
| Foreground exclusion list | `FUN_004631DE/004470B7` | `exclusions.py` | yes (Disabled/Enabled + mode) | Win / mac | wcsicmp vectors | `ported` |
| **Source-language arg (auto vs selected)** | dispatcher `FUN_00404A12` | **inconsistent** (`app.py:3356`=src, `:3449/3593/3514`=auto) | **decide one rule** | Win+mac | matrix row + test | `ported` (uncommitted) |

> The source-language row is the live uncommitted change. It is listed here so
> the migration cannot silently regress it. Decision needed before Phase 5:
> should *all* capture paths honor the selected source language, or only the
> popup hotkey?

## C. Translation engine + providers

> **Coverage note:** the authoritative per-service inventory (19 services, one
> checklist row each) lives in `RE_COVERAGE_CHECKLIST.md` §E. This matrix
> section lists them as a *compatibility* subset; **no service present in the
> checklist may be missing here** (reconciliation rule, `TEST_STRATEGY.md`).

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| Orchestrator (pick→exec→render) | `FUN_00404A12`, `NATIVE_ARCH.md:442` | `do_translate` `app.py:537` | behavior | Win+mac | end-to-end mock | `ported` |
| Provider priority (ServicesOrder) | `FUN_0045CEDE` | `config.services_order` | exact order `[1,5,12,13,11,26,28,30,31]` | Win+mac | order test | `ported` |
| Auto-detect (6-provider loop) | `FUN_00460354` | `app.py:496-503` | order + fallthrough | Win+mac | detect test | `ported` |
| Back-translation | `FUN_004606BA` | `do_translate` | yes | Win+mac | flag test | `ported` |
| Google translate | — | `google_translate.py` | yes | Win+mac | live EN→VI (Win) | `behaviour-verified` — **Win only** (mac untested) |
| Microsoft/Bing | — | `session.bing_translate` | yes | Win+mac | live EN→VI (Win) | `behaviour-verified` — **Win only** (mac untested) |
| DeepL | — | `deepl.py` | yes | Win+mac | live EN→VI (Win) | `behaviour-verified` — **Win only** (mac untested) |
| Yandex | — | `yandex.py` (android) | yes | Win+mac | live EN→RU (Win) | `behaviour-verified` — **Win only** (mac untested) |
| Naver/Papago | — | `naver.py` (new API) | yes | Win+mac | live EN→VI (Win) | `behaviour-verified` — **Win only** (mac untested) |
| Baidu translate | — | `baidu.py` | see status | Win+mac | detect live | `dead:needs-session-token` |
| Youdao translate | — | `youdao.py` | see status | Win+mac | translate_web live | `ported` (translate_o needs bv) |
| Promt | `ghcs` verified | `promt.py` | see status | Win+mac | signing vectors | `dead:needs-session-token` |
| Babylon translate (ID13) | `NATIVE_ARCH.md` | `babylon.py` | see status | Win+mac | — | `dead:host-retired` |
| ImTranslator (ID18) | — | ported | no | — | — | `dead:host-retired` |
| **Fallback on failure** | backtrans/detect retry | **none shared** | yes (D12) | Win+mac | fail→next provider test | `not-started` |
| **Bounded retry + timeout** | `FUN_0045BCED/0045BF7D` | timeout only (`session.py`) | yes | Win+mac | retry policy test | `ported` (timeout only) |
| **Error classification** | — | **none** | yes | Win+mac | taxonomy test | `not-started` |

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
| Popup window (borderless, topmost) | `FUN_0040C393`, `NATIVE_ARCH.md:1476` | `show_popup` `app.py:3962` | behavior | Win+mac | popup test | `ported` |
| Auto-fit layout engine | `FUN_0044B4F4`, `NATIVE_ARCH.md:1476` | `app.py` layout | behavior | Win+mac | geometry test | `ported` |
| RichEdit link tagging (`qtdp:`) | `FUN_004266C6`, `FUN_00465574` | `tag_links` | yes | Win+mac | link test | `ported` |
| 8+ themes (JSONC) | `FUN_0044C4CA`, `NATIVE_ARCH.md:926` | `theme.py` | load + roundtrip | Win+mac | theme hex test | `ported` |
| Theme brightness shift | `FUN_0044A163` | `theme.adjust_brightness` | yes | Win+mac | vector test | `ported` |
| Popup state colors | `FUN_0044FE1B` | `theme.window_colors` | states 0/1/3/4 | Win+mac | — | `ported` |
| **Visual fidelity to native** | screenshots | low (user) | target | Win+mac | screenshot diff | `not-started` |

## E. Dictionary · history · XDXF

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| 11 dictionary providers | `NATIVE_ARCH.md:801` | `dictionary.py` | working ones | Win+mac | `smoke_dict` + live | mixed |
| Oxford/Lingvo/Urban/Wikipedia/Multitran/WordReference | — | ported | yes | Win+mac | live OK (Win) | `behaviour-verified` — **Win only** |
| Reverso translate | — | ported | yes | Win+mac | live OK (Win) | `behaviour-verified` — **Win only** |
| ImTranslator/Babylon dict/Google Search | — | ported | no | — | — | `dead:host-retired` / `dead:bot-walled` |
| XDXF offline dict | `FUN_00445BB9`, `NATIVE_ARCH.md:1382` | `xdxf.py` | yes | Win+mac | template test | `ported` |
| dict template RT_HTML-192 | `NATIVE_ARCH.md:1392` | `dict_template.html` | byte-identical | Win+mac | MD5 (Win) | `behaviour-verified` (artifact, OS-independent) |
| History (DLG164) JSON+CSV order | `FUN_004638D8` **loader** / `FUN_00463B04` **saver** (see `RE_PROGRESS.md` §Tensions #4) | `history.py` | col order `[a,c,b,e,d]` | Win+mac | order test | `ported` |
| History favorites | — | `app.py` | yes | Win+mac | — | `ported` |
| Export Csv/Html/Json/Txt | `Plugins/History/*.js` | `history.py` | 1:1 | Win+mac | exporter test | `ported` |

## F. TTS · speech-in · OCR · spell · layout

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| TTS online mp3 | `FUN_004614BB` | `tts.py` | yes | Win+mac | live mp3 (Win) | `behaviour-verified` — **Win only** (Google) |
| BASS playback | `FUN_00461642`, `NATIVE_ARCH.md:1603` | `player.py` (real bass.dll) | behavior | Win / mac(no bass.dll) | live audio | `ported` (Win) |
| Offline TTS fallback | **no native SAPI found** — `FUN_00448BEC` is the MSXML DOMDocument engine (see `RE_PROGRESS.md` §Tensions #5) | `sapi.py` (our fallback only) | mac replacement | Win / mac | — | `ported` (Win) |
| Slow TTS flag | `Advanced.EnableSlowerListening` | wired | yes | Win+mac | — | `ported` |
| Read-phonetically (display) | `FUN_0042ED3F` appends `"\r\r"`+res0xBA+phonetics to the result when flag on (J7) | `layout.py`/render flag | preserve | Win+mac | — | `ported` — phonetics **display**, not TTS |
| Speech input (mic → FLAC) | `FUN_0044555D`, `NATIVE_ARCH.md:1627` | `comtypes` SAPI | mac replacement | Win / mac | — | `dead:native-unavailable` |
| OCR (ocr.space) | `OcrSpaceProvider`, `NATIVE_ARCH.md:993` | `services/ocr.py` | yes | Win+mac | endpoint smoke | `ported` |
| OCR region select overlay | `ScreenCaptureWindow` | `app.py:3185` (`ImageGrab`) | yes | Win+mac | — | `ported` (Win) |
| Spell (Google suggest + Yandex) | `NATIVE_ARCH.md:982` label is wrong — `FUN_0042C909` is a destructor (see `RE_PROGRESS.md` §Tensions #3); real spell entry not read | `services/spell.py` | yes | Win+mac | live OK (Win) | `behaviour-verified` (port); native spell entry `INFERRED` — **Win only** |
| Keyboard-layout convert | `FUN_00404E09`, `NATIVE_ARCH.md:1282` | `layout.py` | yes | Win+mac | known pairs | `ported` |

## G. Options · i18n · tray · system

| Feature | Native evidence | Python today | Must keep | Platforms | Test | Status |
|---|---|---|---|---|---|---|
| 9 Options pages | `FUN_004561F0`, `NATIVE_ARCH.md:781` | `app.py:1742` (1 method) | 9/9 on real Options.json | Win+mac | `ui_match` | `ported` |
| Options.json 20 sections R/W | `NATIVE_ARCH.md:398` | `config.py` | full roundtrip | Win+mac | roundtrip test | `ported` (123/124 keys) |
| Hotkey rebind UI | `FUN_00408456` | `app.py` | yes | Win+mac | — | `ported` |
| Proxy / Internet.Timeout | `NATIVE_ARCH.md:1303` | `session.net_options` | yes | Win+mac | — | `ported` |
| i18n lang.json (36 strings, 14 win) | `FUN_0045B716`, `NATIVE_ARCH.md:1071` | `locale.py` | vi verified + en fallback | Win+mac | vi test | `ported` |
| Tray states | `FUN_00405C42`, `NATIVE_ARCH.md:1214` | `app.py:3842` (`pystray`) | behavior | Win+mac | — | `ported` |
| Start-with-system (Run key) | `NATIVE_ARCH.md` | `app.py:1788` (`winreg`) | mac replacement | Win / mac | — | `ported` (Win) |
| Crash once-reporter | `FUN_00462C03`, `NATIVE_ARCH.md:413` | `app.py:3696` hook | behavior | Win+mac | — | `ported` |
| Updater | `FUN_00461A26` | flag only | **drop** (dead) | — | — | `dead:host-retired` (2022) |
| Fonts (Tahoma/Segoe UI) | `NATIVE_ARCH.md:1086` | hardcoded `app.py:678` | mac mapping | Win+mac | — | `ported` (Win) |

## H. New capabilities (no native equivalent)

| Feature | Evidence | Status | Notes |
|---|---|---|---|
| Extension SDK (provider/workflow/theme/UI) | design only | `not-started` | `EXTENSION_SDK.md` |
| Extension override + fail-open | design only | `not-started` | §Override rules |
| Reliability layer (classify/retry/fallback) | design only | `not-started` | `RELIABILITY.md` |
| macOS adapters (hotkey/clipboard/capture/audio) | none | `not-started` | macOS never tested |
| Stable-id registry (unify 3 sources) | audit | `not-started` | `ARCHITECTURE.md` §3.2 |

## Summary counts (this matrix, honest)

> **Reconciled 2026-10-09** to the machine tally (`tools/coverage_tally.py`).
> Port-axis counts (152 items): `ported 121` · `behaviour-verified 11` ·
> `not-started 11` · `dead:* 9`.

| Implementation status | Rows | Note |
|-----------------------|------|------|
| `behaviour-verified` | 11 | **all Win-only** (Test-on = Windows); none mac-verified |
| `ported` | 121 | "Python exists", not "proven equivalent" |
| `dead:*` | 9 | endpoint/feature cannot run; reason slug + citation recorded |
| `not-started` | 11 | incl. all macOS adapters, reliability, extension system |

Product decision (not a port state): the **Updater** is a conscious `drop` — its
server retired in 2022 — so its Port state is `dead:host-retired`.

> These counts are the **implementation axis** only and are per-row/coarse;
> they are **not** a "% of QTranslate reverse-engineered". Native **RE coverage**
> is tracked separately in `RE_COVERAGE_CHECKLIST.md`: as of 2026-10-09 it is
> **140 VERIFIED / 9 INFERRED / 3 UNKNOWN of 152**, Gate **BLOCKED (12)**.
> Neither number opens the Gate; only the checklist does.
> Many rows here are `ported` — meaning "Python exists", **not** "proven
> equivalent". `behaviour-verified` always means "tested on the platforms in
> Test-on", which today is **Windows only**.
