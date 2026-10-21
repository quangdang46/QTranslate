# Current State — Audit of `qtranslate-re`

> **SUPERSEDING NOTE (2026-10-15, commit `7b8ea7a`).** The audit below is a
> point-in-time snapshot at `0cb0e78` (2026-10-09). Since then the Core/
> Extensions slices landed: `qtranslate/registry.py` (single dispatch source),
> `qtranslate/providers/` (Provider contract), `qtranslate/engine.py`
> (orchestration out of `app.do_translate`), `qtranslate/extensions.py`,
> `qtranslate/platforms.py`, `qtranslate/sdk.py`, `qtranslate/placement.py`.
> So §3's "one class owns everything / hardcoded dict" description no longer
> holds for dispatch or orchestration — see
> `docs/review/CORE_EXTENSIONS_SLICES_1_5_2026-10-15.md`. A follow-up slice
> added extension **discovery + manifest validation + fail-open loading**
> (`ExtensionManager.load_dir`) and the `Paths` adapter's extensions-folder
> resolution — see `docs/review/EXTENSION_LOADING_2026-10-15.md`. Startup
> **wiring + provider integration** then landed (Slice 8): `app.main` calls
> `load_user_extensions()`, which commits loaded providers into
> `registry.TRANSLATORS`, so an extension actually serves translations —
> see `docs/review/EXTENSION_WIRING_2026-10-15.md`. **Override consistency**
> then landed: an override now propagates across aliases (`microsoft`/`bing`)
> in both directions, an alias conflict applies no override and keeps the
> built-in (never decided by discovery order), and the runtime-fallback policy
> (PA-B) is pinned — see `docs/review/EXTENSION_OVERRIDE_2026-10-15.md`.
> Three latent `NameError`s in `app.py` were also fixed (a `_gp` read before
> assignment, an `except as e` read inside a deferred lambda, and an undefined
> `src` in the clipboard popup) and `tests/` unused imports cleaned — pinned by
> `tests/regress_app_undefined_names.py`. **Override persistence** then
> landed: a saved winner pre-empts conflict resolution, startup applies saved
> winners and clears stale ones, and a thin tkinter dialog picks the winner —
> pinned by `tests/regress_override_persistence.py`. The RE Gate is unchanged:
> `151 VERIFIED / 1 UNKNOWN (G9)`, `BLOCKED (1)`.
>
> **SUPERSEDING NOTE (2026-10-21).** The **sixth** window class,
> `MainWindow`, was extracted last (the Phase 7 `6/6` slice), so §1's
> "the 6th, `MainWindow`, remains in `app.py`" no longer holds. The
> 2026-10-21 UI-fidelity pass then rebuilt the surfaces against native's
> own captures — the main window's band structure, the dictionary
> window's service strip, the virtual keyboard's key grid, the history
> window's bottom row — and fixed the defects that pass exposed, among
> them `render()` being unable to fill the result pane at all (a
> `@staticmethod` delegator whose body used `self`). See
> `docs/review/UI_FIDELITY_*.md` and
> `docs/review/G9_DIFF_DECOMPOSITION_2026-10-21.md`. The RE Gate is still
> `151 VERIFIED / 1 UNKNOWN (G9)`, `BLOCKED (1)`.

> Status: **PLANNING / READ-ONLY AUDIT.** Grounded in direct reads of the
> repository at commit `0cb0e78` (branch `main`) on 2026-10-09. No files were
> modified to produce this audit. Claims are tagged **[verified]** (read from
> code/tests now), **[doc-claimed]** (asserted by a repo doc, not re-run here),
> or **[assumed]** (inference, flagged as such).

## 1. Repository shape

| Path | Lines/Size | Role |
|------|-----------|------|
| `qtranslate/app.py` | 2,088 lines | Tkinter UI + hotkey + clipboard + orchestration (see §3). **All six** window classes Phase 7 names were extracted out of it on 2026-10-16 — see `qtranslate/windows.py` below |
| `qtranslate/windows.py` | 5,016 lines | The Phase 7 split: `HistoryView`, `DictionaryView`, `TrayController`, `PopupHost`, `OptionsDialog` and `MainWindow` (the 6th, extracted last, on 2026-10-16). Each class is a transcription of the pre-split body, proven identical by `tests/regress_windows.py` (53 assertions, compared against the split commit's *parent*) |
| `qtranslate/common.py` | 356 lines | 1:1 port of `Common.js` (RequestData/ResponseData, capability bitmask, helpers) |
| `qtranslate/config.py` | 247 lines | `Options.json` model, hotkey decode, service ids/order |
| `qtranslate/session.py` | 179 lines | Session/token scrape (Bing, Promt), net timeout/proxy |
| `qtranslate/services/` | 12 provider modules + `dictionary.py` + `ocr.py` + `spell.py` | provider ports |
| `qtranslate/win32app.py` | 203 lines | Native Win32 DLG129 re-creation (pywin32) |
| `qtranslate/{theme,locale,history,layout,xdxf,tts,player,sapi,headless,exclusions}.py` | small | feature modules |
| `docs/NATIVE_ARCH.md` | 1649 lines | native binary RE analysis |
| `tests/` | 134 files | 130 `regress_*.py` suites (headless unless named), plus `ui_match.py`, `smoke_dict.py`, `live_providers.py`, `live_bass.py`. Sweep them with `python -I tools/run_suites.py` (exit-code judged, not grep) — see §Test suites in `README.md` |

**[verified]** Language: Python, Tkinter UI, stdlib `urllib` for HTTP; optional
deps only (`keyboard`, `pyperclip` required; `pystray`, `Pillow`, `comtypes`,
`playwright` optional — `requirements.txt`).

**License [verified]:** MPL-2.0 (`README.md:69`). Clean-room RE for education.

## 2. What actually works today

### 2.1 Providers [doc-claimed, from `tests/LIVE_RESULTS.md` + README]
- **LIVE-OK (verified against real endpoints on 2026-10-07/08):** Google
  translate + TTS, DeepL detect/translate, Microsoft/Bing (via shared cookie
  jar), Yandex (android variant), Baidu detect+suggest, Naver/Papago
  (text/tts/dictionary), Youdao (translate_web + dictionary), Reverso
  translate, and dictionaries Oxford / Lingvo / Urban / Wikipedia / Multitran /
  WordReference (headless). `21/21 live OK` (`LIVE_RESULTS.md:27`).
- **Known dead / token-walled** (`LIVE_RESULTS.md:57-72`): Babylon translate
  (SSL dead), ImTranslator (ASMX retired), Google Search (JS+consent wall),
  Baidu `/transapi`, Youdao translate_o, Promt `paft`, plus Yandex TTS and
  Baidu TTS hosts.
- These results were **not re-run during this audit** — treat as doc-claimed.

### 2.2 Test suites [verified as files; results doc-claimed]
- `tests/live_providers.py` — hits real endpoints (network-dependent).
- `tests/ui_match.py` — **structural** checks of `app.py`: it constructs
  `A.App(root)` and asserts strings/order/defaults by inspecting objects and
  even the source text of `app.py` (`ui_match.py:57-59`). It is a
  *string/structural* match, **not** pixel or screenshot comparison.
- `tests/smoke_dict.py` — import + offline helper assertions.
- README claims (as of 2026-10-15) `103/103 UI` (GUI session only — it
  builds a Tk root and was last green in a GUI run, not re-verified in
  this no-GUI session), 61/61 headless regress suites PASS (re-run here),
  live suites historical (2026-10-08). Earlier doc said `101/101 UI` /
  32/32 suites — counts differ across CHANGELOG entries (`82/82`,
  `40/40`, `46/46`…), a sign the suite grew over time. See README "Test
  suites" and `docs/review/HEADLESS_SWEEP_RULE_2026-10-15.md` (61 headless
  = 63 total minus the 2 window-opening suites).

> **Verified 2026-10-16 — the suite count is not stated here on purpose.**
> It is a number that rots the moment a suite is added, and this very
> paragraph had a hardcoded `113` that was wrong within the hour. Get it
> from the tool instead:
>
> ```
> python -I tools/run_suites.py
> ```
>
> That judges every suite by **exit code**, not by grepping for "FAIL".
> Several suites print `FAIL n/m` without a colon, so a grep-based check
> both over- and under-reports — the reason this tool exists.
>
> The dated notes in `docs/review/` record the count *as of their date*
> (95 on 2026-10-16, 61 on 2026-10-15, 32 earlier) and are historical
> records; this section and the README are the two meant to be current.

> **Honesty note:** "UI match" does **not** mean the UI looks like the
> native window. The user's own assessment is that the UI "chả giống tý nào"
> (doesn't look alike at all). The test verifies *structure/strings/order*, not
> visual fidelity. Any future UI claim must distinguish these.

## 3. `app.py` — where boundaries blur [verified]

Full structural audit (delegated, line-cited):

- **`class App` owns everything** (`app.py:440-2229`): main window, OCR,
  virtual keyboard, hotkey routing, the clipboard monitor, and the nav menu.
  **Partially relieved 2026-10-16 (Phase 7):** the popup, Options, History,
  Dictionary and tray have moved to `qtranslate/windows.py` — `open_options`
  was one ~1,056-statement method and is now a delegator; `show_popup`,
  `_make_tray`, `open_history_window` and `open_dict_window` likewise.
  `App` is down from ~3,400 to 1,789 lines. The remainder is the main window
  itself, which is not a window hanging off the app but the app, and is
  recorded rather than claimed (`IMPLEMENTATION_PLAN.md` Phase 7).
- **Provider dispatch is dict-based but hardcoded:** `TRANSLATORS` (`:221`),
  `DICTS` (`:234`); detection is a **hardcoded tuple** (`:496-503`). A separate
  `services/__init__.py` `REGISTRY` registers only 5 providers — **three
  sources of truth**, none complete.
- **Orchestration interleaved with widgets:** `on_hotkey` (`:3337`) reads
  `app.current()` then writes `app.src`/render/history; same for the clipboard
  monitor (`:3407`) and `_replace` (`:3592`). `PopupHost.open`'s
  `_to_main` (`qtranslate/windows.py:902`) builds a **second `tk.Tk()` +
  `App`** inside a popup callback — noted here again because the extraction
  *moved* that latent problem without fixing it, and `app.py`'s only
  remaining `tk.Tk()` is the legitimate `main()` one (`:2966`).
- **Windows coupling:** `ctypes.windll.user32` (`:3419`, `:3790`), `winreg`
  autostart (`:1788`), `comtypes` SAPI (`:1251`), `keyboard` global hooks
  (`:3668`), `PIL.ImageGrab` (`:3277`), hardcoded `C:/Program Files (x86)/…`
  (`:1806`). Note: the **native cursor-hook / SendInput capture path is not
  ported** at all (no `win32gui` here).

## 4. Working tree — do not overwrite

**One uncommitted file: `qtranslate/app.py`** (`git diff --stat`: 2 insertions,
2 deletions). The change is in `on_hotkey` (`app.py:3356-3359`):

```python
svc, _, tgt, src = app.current()          # was: svc, _, tgt, _ = app.current()
res = do_translate(svc, text[:5000], tgt, src,   # was: ... tgt, "auto",
                   app.opt_detect.get(), app.opt_backtr.get())
```

So the popup hotkey now forwards the **selected source language** instead of
forcing `"auto"` (auto-detect). Rationale per the planning thread: respect the
user's chosen source.

**[resolved 2026-10-10]** The "inconsistency — decide one behavior for all
capture paths" note that used to sit here is **closed, and the answer was
neither of the two options it offered.** Native is not consistent in the
port-side sense: `FUN_0045f6c1` asks the service's own `usesAutoDetectCode`
hook and stores the answer at `request+0x50`, and `FUN_004606ba` runs detect
only when that flag is false — or when the *destination* is also not a
concrete code. `FUN_00404A12` additionally echoes the source and skips the
service entirely when source == destination.

So the per-call-site variance the old note asked to unify was never a
divergence to eliminate. The port now implements both halves
(`_USES_AUTO_DETECT` declared per provider; the `src == target` echo) and
`docs/review/SOURCE_LANGUAGE_RULE_2026-10-10.md` carries the decompile.

**Do not reset or overwrite this change** — and do not "fix" the remaining
per-call-site variation by forcing one literal everywhere, which is what this
note used to ask for. The honest port-side caveat: the capability table is
declared, not native-derived, because the hook's answers live in the
runtime-loaded `Service.js` that
`docs/review/PLUGIN_LOADER_FOUND_2026-10-10.md` proves are absent from the
recovered artifact.

## 5. Native RE coverage [doc-claimed, from `docs/NATIVE_ARCH.md`]

`NATIVE_ARCH.md` (1649 lines) documents, with function addresses, RTTI classes
and dialog ids: startup/message-loop/hotkey, 3-mode capture, translate
orchestrator + provider executor, JS boundary (`IActiveScript` CLSIDs), render
(RichEdit/layout/popup), dictionaries/XDXF, TTS (BASS), speech-in
(BASS_RecordStart + FLAC), OCR, tray, Options/settings, history/export, crash
reporter, updater, spell, keyboard-layout convert, i18n, theme.

Ratio-style evidence it records (`NATIVE_ARCH.md`, doc-claimed): `123/124` live
Options.json keys matched (`:714`), `9/9` Options pages on real Options.json
(`:77`), `28/35` lang.json parse (`:1073`), 8 themes load (`:1527`), 17
providers (`:1648`).

## 6. Known gaps and dead ends

These are stated **where** they are true; several originate in `CHANGELOG.md` /
`README.md`, *not* in `NATIVE_ARCH.md` (verified by audit — do not misattribute).

| Gap | Where stated | Impact |
|-----|--------------|--------|
| Cursor-hook mouse icon not ported | `CHANGELOG.md` (Flags coverage) | mouse-mode hover UI |
| Drag-and-drop needs `tkinterdnd2` | `CHANGELOG.md` | file DnD |
| "Extended" feature absent in modern Options.json | `CHANGELOG.md` | legacy menu only (`NATIVE_ARCH.md:727` label) |
| TTS phonetic: no API | `CHANGELOG.md` | "Read phonetically" limited (`NATIVE_ARCH.md:736`) |
| Updater dead (server retired 2022) | `NATIVE_ARCH.md:1376` | update check is dead code |
| `tlookupv3` dictionary 401-walled | `NATIVE_ARCH.md:1454` | Bing standalone dict |
| `refresh_tkk()` not ported (defaults `"0.0"`) | `NATIVE_ARCH.md:1464` | Google token freshness |
| Speech endpoint needs key+FLAC | `NATIVE_ARCH.md:1638` | speech-input blocked |
| Native capture (mouse/mode 2, SendInput synth) not ported | `app.py` audit | core to native UX |
| UI visual fidelity low | user assessment | see §2.2 honesty note |

## 7. What is verified vs not — summary

- **[verified now]** file/module structure, dispatch tables, Windows couplings,
  the uncommitted diff, test files' existence and their *type*.
- **[doc-claimed]** all "N/ N green", "LIVE-OK", percentages, and native RE
  addresses — read from docs; not re-executed in this audit.
- **[assumed]** macOS behavior of adapters — never tested.

> **This audit is NOT an RE-completion artifact.** The `doc-claimed` bucket
> above is exactly the evidence that **cannot** be used to open the Gate
> (`PROJECT_VISION.md` §0). Structure and presence are not behavioral proof, and
> a line written in a document is not self-validating evidence. Native RE
> coverage lives in `RE_COVERAGE_CHECKLIST.md` and is tracked on its own axis;
> this file records the **Python-side** state only.

## 8. Implications for the redesign

1. The three-source-of-truth registry and hardcoded detect tuple **must** be
   unified (see `ARCHITECTURE.md` §3.2).
2. `app.py` cannot be the Core; it becomes UI host components.
3. The `"auto"` vs `src` inconsistency is a **real compatibility decision**,
   not just a diff to preserve.
4. Reliability is absent as a shared layer — the biggest user-facing gap.
5. Several providers are genuinely dead; the matrix must record dead-vs-fixable
   so the redesign doesn't promise to resurrect retired servers.
