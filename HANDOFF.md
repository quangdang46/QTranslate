# HANDOFF — QTranslate port (Python/PySide6)

**Goal:** Port QTranslate 6.10 (`.tmp/QTranslate`, Kotlin/Swing reference)
functionally + behaviorally to this repo — all logic and UX, core and
secondary features. User's standing instruction: "làm hết" — everything,
verified against `.tmp`, no feature left un-audited.

**Status:** Parity work is essentially COMPLETE on the agent-doable
surface. 191/191 test suites green, 0 failed. All work pushed to
`origin main` (latest: `5c31115`).

## Repo layout

- Port: `qtranslate/` (Python + PySide6), entry `start_qt.py`, config
  `Options.json` under `platforms.app_data_dir()`.
- Reference (READ-ONLY): `.tmp/QTranslate` — Kotlin/Swing upstream 6.10.
  `.tmp` has its own `AGENTS.md` (MPL-2.0 rules; never push to its
  main/develop).
- Docs: `docs/RE_COVERAGE_CHECKLIST.md` (port↔.tmp mapping + divergences),
  `docs/GAP_AUDIT_2.md`, `docs/GAP_AUDIT_3.md` (test-contract mining —
  12 gaps all fixed or documented), `docs/PDF_LAYOUT.md` (feasibility),
  `docs/CURRENT_STATE.md`, `docs/EXTENSION_SDK.md`.
- Tests: `tests/regress_*.py` (~190 files). Run ALL:
  `QT_QPA_PLATFORM=offscreen .venv/bin/python tools/run_suites.py`
  Single: `.venv/bin/python tests/regress_x.py`.
- Task tracking: `br list` / `br close <id> --reason "..."` (beads).

## Must-read conventions (AGENTS.md)

- Tests isolate `qtranslate.config.DEFAULT_PATH` to a temp file BEFORE
  any config load — pages write through; `config.load()` auto-migrates
  the real Kotlin DataStore only when `DEFAULT_PATH` is the builtin path.
- Options pages use screenshot coords via `put()`; grown pages need
  matching `CHROME` offsets.
- Quick popup must stay button-less (structural test greps raw source).
- Secrets: `qtranslate/secrets.py` (0600 JSON beside Options.json) —
  never in Options.json.
- Platform backends dispatch on `sys.platform`, lazy imports, honest
  fallback when binaries missing.
- **Push to origin main after each wave. Kill the app + stray Qt test
  processes after testing** (user preferences, in AGENTS.md).

## What's DONE (ported from .tmp)

Core UX: Ctrl+Q, mouse-icon mode (mutually exclusive), Alt+W
replace-selection, selection OFF/SHOW_ICON/TRANSLATE/TRANSLATE_AND_READ,
DoubleCtrl detector, LOCAL hotkeys (11 QShortcuts), single-instance,
startup (LaunchAgent on macOS), exclusions, history (persist/migrate/
export/nav), clipboard snapshot/restore fail-closed.

Quick popup: language row (src/target combos + swap), retranslates,
inline dictionary gloss, comparison strip, provider strip, pin/auto-hide/
placement, Ctrl+C/E/S/P shortcuts, listen reads SOURCE text.

Main window: instant translate (350ms debounce), spell-check debounce,
extra outputs (summary/rewrite/back-translation), translation rules,
auto-copy (off/quick/all), close-action ASK dialog, service presets,
pinned languages, status bar (notification chip + history), toolbar
visibility + selector appearance settings, i18n chrome (locale packs),
editor font split, settings search.

Services: google/deepl/microsoft/bing/llm-chain providers, MyMemory
(UTF-8 segmenter port), LibreTranslate, Yandex/Reverso web paths, Google
Dictionary, system TTS+spell on macOS (`say`/NSSpellChecker), Windows
(SAPI/ISpellCheckerFactory), Linux (espeak/aspell), OCR chain
(Vision→tesseract→ocr.space→Google Vision→AI), document translation
(docx/pdf-text/txt/srt/vtt), image search, extensions runtime
(manifest+ext.py, settings UI, lifecycle hooks, data_dir, secrets,
tr() localization, notify, scoped http, install-folder).

Network: proxy (password in secrets store), retry policy (429 any-method,
5xx idempotent-only, Retry-After delta+HTTP-date cap 600s, exponential
jitter), host-specific timeouts, provider API keys, Google endpoint
circuit breaker.

## Remaining work — pick up here

### Needs a human (beads qt-z33, qt-fj5 — P1)
- `qt-z33`: verify Alt+W replace-selection on a REAL launched app
  (needs GUI + Accessibility permission).
- `qt-fj5`: G9 part (b) needs human reviewer; waiver needs human sign-off.

### Windows-specific — THIS IS WHY HANDOFF TO WINDOWS DEV
Windows paths EXIST for most subsystems (hotkeys via `keyboard` pkg
Win32 hook, mouse_capture win32 branches, clipboard/selection win32,
startup HKCU Run key, `win32app.py` legacy window, Qt `mouse_icon.py`
cross-platform). What's WRITTEN but NEVER tested on real Windows:
- `services/system_tts.py` — SAPI `SpVoice` voice-matched speak +
  `GetVoices` discovery via comtypes (optional dep, commented in
  requirements.txt — may need enabling).
- `services/system_spell.py` `_check_win` — ctypes port of
  `ISpellCheckerFactory` COM (Win8+). Mirrors upstream JNA slot layout;
  untested on real Windows.
- `qt/hotkeys.py` DoubleCtrl — `keyboard.hook` observe-only feed for
  win32 (untested; degrades silently to unbound).
- `clipboard.py`/`selection.py`/`mouse_capture.py` win32 branches —
  need real-device verification (OpenClipboard retries, sequence-number
  polling, hook capture_allowed/exclusions).
- `requirements.txt` — check `keyboard`, `comtypes`, `pywin32` entries
  are installed on Windows (`win32app.py` needs pywin32).
- OCR: no Windows.Media.Ocr backend → RTL `OcrLineOrder` divergence;
  tesseract path works.
- **Smoke-test checklist for Windows:** install deps, run
  `start_qt.py`, verify Ctrl+Q (global hook), Alt+W replace-selection,
  mouse-icon drag mode, DoubleCtrl, TTS "system" pref, spell check,
  document translation, extensions, proxy+secrets store.

### Documented divergences (decide if worth doing)
- PDF layout-aware translation — design in `docs/PDF_LAYOUT.md`
  (pdfplumber + pypdf redact/merge + ReportLab overlay, ~2.5–4wk MVP).
- Layout presets, ENHANCED service selector (evaluated → redundant),
  iconSetId, donation nudge — architectural, see checklist.
- QuickDictionary popup vs window — evaluated, window kept (rationale
  in checklist).
- Extension JAR-trust/fingerprint/`validate()`/scoped-HTTP isolation/
  SettingType richness — Python-source extension model instead.
- Plugin validate-timeout formula, status-bar loading pipeline —
  minor residuals in GAP_AUDIT_3.
- macOS Vision mixed-direction OCR ordering — UNVERIFIED.
- Hotkey recorder can't SET double-Ctrl bit15 (detector works; recorder
  capture is a small follow-up). Recorder lacks .tmp's clickable
  special-key chips + live modifier preview (convenience).
- CI/release: update Download button expects asset names like
  `QTranslate-<ver>-windows-x64.zip` — name release assets accordingly.

## Workflow for next agent

1. `git pull`, read this file + AGENTS.md + GAP_AUDIT_3.md tail.
2. `br list` for open beads; create beads for new work (`br create`).
3. Work one concern at a time; regression test per fix; run focused
   tests then full suite before pushing.
4. Commit + push each wave; kill test processes after.
5. On Windows: prioritize real-device smoke of the untested backends
   above — that's the highest-value remaining work.
