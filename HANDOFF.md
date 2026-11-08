# HANDOFF

What the last sessions did, what the tree looks like now, and what the
next session should pick up. Updated **2026-11-09** at the tip of
`main` (see §0), working tree clean, pushed.

The standing rules still apply: the GitHub push token is used
transiently in a push URL only (never in a file, never in
`.git/config`; the helper authenticates as `qdang46`, which gets 403 on
`quangdang46/QTranslate`, so the operator supplies a session token);
the native's installer is never run (the installed copy at
`C:/Program Files (x86)/QTranslate/` is read only -- currently absent
on this machine; only `%APPDATA%\QTranslate` user config remains); `docs/NATIVE_ARCH.md`
is frozen; every Python run uses `python -I`; downloaded files are
untrusted.

## 0. The state of the tree right now

| What | Value |
|---|---|
| Branch / commit | `main`, tip `27484ee`, pushed |
| Working tree | clean (except known `.beads` vacuum artifacts) |
| Suites | **198 suites, 0 failed, ~325s on Windows** (`QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe tools/run_suites.py`) -- re-run 2026-11-09 after a full-tree audit; one stale expectation fixed in `27484ee` (`regress_ui_parity_fixes` expected history-menu ids 10/20/30/50/40, native menu 3 in `lang.json` actually carries 10/15/20/30/40 -- the code was right, the test was wrong). 22 suites still SKIP honestly here for the same environmental reasons as before |
| Pixel measure | mean ink diff **0.0037** over 12 screens (re-run 24/10; macOS re-measure not done) |
| Docs consistency | 0 findings |
| Live providers | **30/31 LIVE-OK** re-run 2026-11-09 (`tests/live_providers.py`): `dict.lingvo` timed out repeatedly and curl to `lingvolive.com` reset after ~31s — the host is unstable/down server-side right now, request shape unchanged and previously LIVE-OK. All other 30 checks pass incl. mymemory/mozhi/yandex_web/commons_images, spell backends, reverso.lookup idx-pair, google_dict; PROMT still returns its own "temporarily unavailable" (session scrape healthy, re-probed 2026-11-09), Babylon/Baidu-translate dead, recorded |
| Bundle | rebuilt on Windows after every wave; latest `SELFTEST PASS 29/29`, `_missing_deps`/`_frozen_gap` clean, `pdfium.dll` in `_internal`; `dist\QTranslate\` current with `main` |
| Front end | Qt only. tkinter was deleted on 2026-10-23 |
| Platform focus | This machine is **Windows** (was macOS on 2026-11-08 morning) — `macos_*` backends live-tested earlier; Windows backends now suite-verified, still need real-device audio/hook checks (see §4) |

**The operator CONFIRMED the GUI matches native** (2026-10-24, running
the real bundle, Windows). Recorded in `docs/review/FEATURE_CHECKLIST_2026-10-23.md`.

## 0.5. macOS parity session (2026-11-08, this machine) -- what landed

A full `.tmp` parity pass ran here: ~20 beads, 5 commit waves, all
pushed. Headline items (details in `docs/GAP_AUDIT_2.md`,
`docs/GAP_AUDIT_3.md`, `docs/RE_COVERAGE_CHECKLIST.md`):

- **Quick popup parity**: language row (src/swap/target combos +
  retranslate), inline dictionary gloss, comparison + provider strips,
  pin/auto-hide/placement, Ctrl+C/E/S/P, listen reads SOURCE text.
- **Core**: DoubleCtrl detector (CGEventTap key observer), hotkey
  presets LEGACY/MODERN/CUSTOM, LOCAL hotkeys, selection
  restore-fail-closed, clipboard seq DWORD wrap, auto-lookup
  main-visible guard + settings retrigger, `prepare_input_text` \r
  semantics, instant translate, auto-copy, close-action ASK, status bar.
- **Options**: SettingsSearch, summary/rewrite, service presets,
  per-role service prefs, pinned languages, translation rules, UI i18n
  chrome, editor font split, toolbar visibility + selector appearance,
  NetworkConfig retry/backoff/Retry-After/host-timeouts.
- **Services**: Windows (SAPI TTS, ISpellCheckerFactory spell) and
  Linux (espeak, aspell, mpv/ffplay) backends WRITTEN — untested off
  their OSes. Proxy password moved to `qtranslate/secrets.py` (was
  plaintext in Options.json — real leak fixed).
- **Extensions**: data_dir, secrets, `tr()` + `localization/*.toml`,
  notify bridge, lifecycle hooks, scoped http, install-folder.
- **Update dialog**: platform asset download URL + Download button
  (asset naming convention: `QTranslate-<ver>-<platform>.<ext>`).
- **Docs**: `docs/PDF_LAYOUT.md` (layout-aware PDF design),
  `docs/GAP_AUDIT_2/3.md`.
- **191 suites / 0 failed.** `AGENTS.md` records workflow prefs:
  push after each wave, kill app+stray Qt processes after testing.

## 0.7. Windows session (2026-11-08, this machine) -- what landed

- **PROMT request shape FIXED** (`f26fdc7`): the site's page bundle
  changed the `h=` hash -- UTF-16 code units, forward+backward
  accumulation (h1+h2), and `#Gener\u0430l#` with a CYRILLIC a. The old
  native-Service.js hash got HTTP 400. `ghcs`/`ghcd` now mirror the
  live client, `translate()` sends the session opener (cookies it used
  to drop) and trims/strips U+0301 like the web client. Backend still
  answers "service temporarily unavailable" -- request accepted again
  (HTTP 200 + schema). Details in `tests/LIVE_RESULTS.md` top entry.
- **`secrets.py` Windows ACLs**: `os.chmod(0600)` is a no-op on nt;
  `_chmod_private` now strips inheritance + grants only the current
  user via `icacls` (proxy password file).
- **8 suite portability fixes** so the sweep is green on Windows:
  platform pinned in system_tts/speech_macos/system_backends_win/
  role_prefs/player tests, utf-8 explicit in contents_persist,
  ImageSearch added to options_roundtrip whitelist.
- **venv recreated** at `.venv` (uv, py3.12): `uv pip install -r
  requirements.txt PySide6 Pillow pystray comtypes`.
- **Push**: `gh auth token` works (account quangdang46, repo scope);
  GCM `git push` hangs waiting on a credential dialog -- confirmed
  again 2026-11-08 (stale `git-credential-manager.exe` zombies had to
  be taskkilled). Cleanest workaround, no token in URL/args:
  `git -c credential.helper= -c credential.helper="!gh auth git-credential" push origin main`.
- **PDF layout-aware translation LANDED** (`34585f7`): the largest
  remaining feature, MVP per `docs/PDF_LAYOUT.md` strategy A --
  `qtranslate/pdf_layout.py` (pdfplumber blocks → per-block translate →
  pypdfium2 216 DPI raster bg + reportlab vector overlay). New deps in
  requirements.txt (pdfplumber, pypdfium2, reportlab). Missing deps +
  odd-angle pages fail honestly. `tests/regress_pdf_layout.py` (20+).
  Document dialog's Layout-aware combo enabled.
- **Bundle rebuilt** on Windows after all of the above (again after
  the recorder + CJK waves): first pass exposed that the isolated
  `uv tool run` builder env dropped ALL document deps
  (pypdf/docx/pdfplumber/pypdfium2/reportlab/PIL) -- fixed in `627688d`
  by injecting pinned `--with` deps + a `_missing_deps` warn-file gate.
  Final: `SELFTEST PASS 29/29`, pdfium.dll + pdfminer + reportlab in
  `_internal`, `dist\QTranslate\` current.
- **192 suites / 0 failed** on Windows (~172s).
- **Hotkey recorder capture landed** (`0edb8c7`):
  bit15 double-press (500 ms same-chord), Double-Ctrl tap -> 0x8000
  on HotKeyMainWindow via per-capture DoubleCtrlDetector, armed-state
  chip strip (mod toggles + special keys + Cancel) and live modifier
  preview. `tests/regress_hotkey_recorder.py` (38 checks).
  `options/base.py` `_clear`/`closeEvent` now reset the new capture
  state so nothing leaks across page swaps.
- **PDF geometry hardening** (`34585f7`..`3438d39`): layout-aware PDF
  now handles 90/180/270 `/Rotate` pages, multi-column layouts
  (char-gap line splitting + low-coverage gutter column bands),
  CropBox-relative coordinates (pdfium renders the crop, pdfplumber
  reports mediabox), CJK font fallback via glyph coverage, and
  intrinsically-sideways text runs left raster-only. Odd angles
  refuse honestly. Latent A4-page-size bug fixed. 22+ rotated checks
  + column/cropbox checks in `tests/regress_pdf_layout.py`.
- **Windows portability + dialog coverage** (`16d42cc`..`65ab4a2`):
  document dialog's Open button used macOS `open` (silent no-op on
  Windows) -> `QDesktopServices.openUrl`; `_finished(None)` crash
  fixed; new suites `regress_document_dialog.py` (25) and
  `regress_loading_indicator.py` (15); audit docs de-staled.
- **Live provider sweep 21 -> 31 checks** (`f45a36f`..`034e07d`):
  every keyless provider surface now probed (mymemory/mozhi/
  yandex_web translates, commons_images, spell backends,
  reverso.lookup + reverso.svc.translate, google_dict). Fixed
  `reverso_lookup` index-leg bug (`_api_leg` resolves int language
  ids via REVERSO_LANGS). `tests/regress_reverso_fallback.py` (6).
- **OCR multipart body fixed** (`abc6e22`): field parts carried a
  leading `\r\n` on top of the previous part's trailing CRLF, so
  values reached ocr.space with a trailing CRLF (`apikey` parsed as
  `"helloworld\r\n"`) -> intermittent E555/403. Parts now join exactly
  per the recovered format strings. Demo key is also rate-limited
  (429); real OCR wants `Advanced.OcrApiKey`. New no-double-CRLF
  check in `regress_ocr_multipart.py`.
- **J6 FLAC encoder landed** (`qtranslate/flac_encode.py`): int16 PCM
  -> `fLaC` stream via soundfile's bundled libsndfile, one-shot +
  block-wise `FlacEncoder`; `speech_input.flac_payload` is the chain
  link. soundfile is an OPTIONAL dep (commented in requirements.txt)
  -- absent it raises `FlacUnavailableError`. Upload half stays
  dead:native-unavailable upstream. `tests/regress_flac_encode.py`
  (13 assertions, bit-exact round-trip).
- **Operator decisions landed**: `qtranslate-sdk` name confirmed
  (D19 resolved -- EXTENSION_SDK/IMPLEMENTATION_PLAN updated); J6
  FLAC implemented per operator call; extension-API additions left
  unanswered (no new exposure added).
- **Audit waves after that** (all pushed, `6c8c899`..`176fcdd`):
  caller-provided openers now reach `common.http_open` in youdao
  (translate/dictionary/translate_web) and yandex Disk public-link
  resolution (`6c8c899`); dead-store cleanup -- baidu's unused
  sl_idx/tl_idx (`4d502fa`), last six F841s (`eb21799`); extension
  `replaces` documented as inert on the five dispatch tables
  (`9916a94`). **Two real UI bugs found by ruff bugbear**:
  the tray Extensions on/off switch persisted the build-time state
  so it could never toggle (`d9846af`), and the OCR-language +
  extra-options pickers allowed multiple checks -- now exclusive
  QActionGroups, menu builders split for testability (`176fcdd`).
  Static analysis is now clean: F821/F841/E711/E712 = 0, B/RUF
  findings all classified benign. Full sweep re-verified **198/0**.

## 1. Windows session (2026-10-24) -- what landed, newest last

| Commit | What |
|---|---|
| `362344a` | **test isolation**: three suites read the real `%APPDATA%` Options.json; the operator's live session (`From=auto, To=auto`) made the engine echo instead of calling the rigged provider. The suites pin `en → vi` now. |
| `89e9e68` | **Bing FIXED**: bing.com moved the credentials into `params_AbusePreventionHelper = [<expiry-ts>,"<token>",<TTL>]` and the POST's `key=` is the EXPIRY, not the TTL (`statusCode:205` vs translation, both verified live). EN→VI and VI→EN translate; sweep 21/21. PROMT re-probed: scrape OK, backend "temporarily unavailable" (`dead:service-unavailable`). Babylon still dead (SSL chain). |
| `bb86d3e` | **`examples/extensions/power_suite/`** -- a worked extension with ALL EIGHT capabilities: language-gated provider that raises on a miss (fallback answers), a deliberately broken sibling proving fail-open, workflow step, partial theme, popup-body/tray/panel slots, restart-safe state in its OWN file (D16). Pinned by `regress_extension_power_suite.py` (28) through the real loader. |
| `775b38b` | **The user's extension switch + settings API + the Options Extensions page**: `Extensions.Disabled` in Options.json skips the folder at load (no import, no tables); `api.get_setting`/`set_setting` persist per-extension under `Extensions.Settings.<ext id>` (schema-declared keys only, fail-open reads); the Options dialog's tenth page **Extensions** lists installed folders with an on/off checkbox each, the load status, an Open-folder button and a restart hint. Pinned by `regress_extensions_options.py` (21). |
| `a7e207a` | the operator's GUI-match confirmation recorded in the checklist. |
| `359b834` | 15 surface captures of the running app (main/popup/dict/history/keyboard + all ten Options pages) under `docs/review/screenshots_2026-10-24/`. |
| `4ecac33` | **popup strip selects**: clicking a provider cell highlights it (selection blue, white text) and re-translates through the chosen provider on the worker. `regress_popup_strip.py` (10). |
| `599c32f` | **history rows no longer overlap; dictionary strip fits**: the history list is a QScrollArea at a 34px pitch (12 entries needed 360px in a 228px panel and painted over each other); the strip's cell width is computed from the service count. |
| `f35b6da` | **history persists** to `History.json` (the port held it in memory only -- every restart emptied the window); the main strip's highlight MOVES with the clicked provider and follows the restored service at boot. `regress_history_persist.py` (9). |
| `4cf4f71` | **history/dictionary match the native captures** 2133/2132: header band + bold source + white translation row; the strip runs the full window width with the last cell stretched, and the SELECTED cell is the light one (the port had it inverted). |

## 2. The extension platform (current shape)

All eight capabilities are live and proven through the app's own call
paths (`EXTENSION_SDK.md` §9 has the table). On top of that:

- **On/off**: Options → Extensions, one checkbox per folder, persisted
  as `Extensions.Disabled`; the loader reports
  `user-disabled (Options → Extensions)` and never imports the folder.
- **Settings**: `api.get_setting/set_setting`, per-extension sections,
  `settings_schema` enforced on write.
- **Examples**: `hello_provider`, `custom_ui`, `custom_theme` (one path
  each) and `power_suite` (everything at once).
- Two extensions are INSTALLED on this machine
  (`%APPDATA%\QTranslate\extensions\`): hello_provider, power_suite.

## 3. Bugs fixed this session (summary)

| Bug | Root cause |
|---|---|
| 3 suites failed on a tree whose previous record was green | suites read the real Options.json; the live session echoed inputs |
| Bing dead | page moved the credentials; `key=` must be the expiry ts |
| popup strip clicks did nothing | cells had no click handler; the active mark was a slightly darker grey |
| history rows painted over each other | 12 entries x 30px = 360px in a 228px panel, no scroll |
| history empty after every restart | in-memory only, never persisted |
| main strip highlight never moved | `selected` set on button 0 at build, never updated |
| dictionary strip's last cells cut | fixed 42px cells ran under the scrollbar; selection colour inverted vs native |

## 4. What is NOT done -- the next session's queue

**Agent-doable, no new decisions needed:**
- PROMT: request shape fixed 2026-11-08 (was HTTP 400, now HTTP 200 +
  schema); backend still "temporarily unavailable" -- re-probed again
  later same day (session -> pageLoad -> translate en->ru still
  returns the provider's own unavailable string); if it comes back,
  the scrape+hash are already working.
- Rebuild the bundle after any change
  (`python tools/build_bundle.py`, selftest 29/29) -- the operator runs
  the bundle, not the repo. NOTE: bundle was built on Windows; rebuild
  on whichever OS ships.
- More customisation APIs along the same seam (e.g. exposing the
  hotkey table or the tray icon set to extensions) -- ask the operator
  which he wants first.
- ~~Hotkey recorder cannot SET the double-Ctrl bit15~~ -- DONE
  2026-11-08: same-chord double-press inside 500 ms re-saves with
  bit15 on every row, and two Ctrl taps on the Show-main-window row
  save bare 0x8000 via a per-capture DoubleCtrlDetector. Chips +
  live modifier preview also landed (armed-state chip strip replaces
  the hint line; modifier toggles compose chords by mouse).
- ~~PDF layout-aware translation~~ -- DONE 2026-11-08 (MVP, strategy A).
  Follow-up polish also landed same day: CJK font fallback
  (`_font_for_text` + `_CJK_CANDIDATES` glyph-coverage swap) and
  quarter-turn page support (visual->natural frame un-rotation of
  lines + raster, `/Rotate` carried to output; arbitrary angles still
  refuse), same-baseline char-gap line splitting + low-coverage
  vertical-gutter column bands (two-column pages group per column),
  CropBox-aware coordinates (`_crop_frame` -- pdfium renders only the
  crop region, pdfplumber reports mediabox frames), intrinsically
  sideways text runs on rotated pages skipped via `_raw_orientation_ok`
  (matrix angle vs expected `(-rot)%360`; they stay raster-only), and a
  latent bug fix: reportlab's default A4 page size was never overridden,
  so output pages were A4 regardless of source.
- **Document dialog Open button fixed** (`16d42cc`): `_open_output`
  shelled out to macOS `open` and silently did nothing on Windows; now
  `QDesktopServices.openUrl` like the rest of the app.

**Needs the operator / real device:**
- Behaviour NEEDs in `docs/review/FEATURE_CHECKLIST_2026-10-23.md`:
  Ctrl+Q / Replace Selection against real foreign apps, each Options
  page changed + app restarted + value still in effect, TTS audible,
  microphone, OCR live (needs an API key). The GUI itself is confirmed
  (Windows bundle).
- **Alt+W replace-selection on a normally-launched app** (`qt-z33`,
  P1) -- verified in tests, needs one real-machine run.
- **G9**: review `native.png`/`port.png`/`diff.png` and write the
  waiver token -- no agent may self-assign it (`qt-fj5`).
- Options → Basics and the tray menu have NO native capture
  (BLOCKERS B4) -- pixel parity there is unverifiable without them.
- **Windows real-device pass** (partially DONE 2026-11-08 on this
  machine): ISpellCheckerFactory spell VERIFIED live -- fixed a
  fatal vtable bug (`IEnumSpellingError::Next` takes ONE out param,
  not the standard 3-arg enumerator; wrong signature AV'd and
  `check()` swallowed it to None). SAPI voice discovery + locale
  mapping verified -- fixed SAPI `Language` attr being a HEX LCID
  string and `LocaleNameFromLCID` missing on some kernels
  (`LCIDToLocaleName` fallback added). DoubleCtrl `keyboard.hook`
  feed VERIFIED live too -- fixed a real bug: `keyboard.hook()` is
  not a context manager (returns a remove fn), the `with` form killed
  the feed thread so the gesture never bound on Windows; end-to-end
  verified with injected Ctrl taps -> detector fires once. Mouse
  hook install + MSAA `cursor_text` + clipboard snapshot/restore
  also verified live on Windows, and `keyboard.add_hotkey` global
  combos fire on injected chords (needs real scan codes --
  keybd_event with sc=0 produces unmatchable events). SAPI
  `speak()` executed clean on both paths (system_tts comtypes +
  sapi.py) -- operator can confirm audibility. Single-instance guard
  FIXED (`_default_find`/`_default_activate`): the Qt window's Win32
  class is Qt's own, never `QTranslate_ApplicationWindow`, so
  `FindWindowW` could never find it and every second launch started
  a full copy; now falls back to the stable "QTranslate" caption and
  activates via ShowWindow/SetForegroundWindow (Qt ignores the
  native WM_COMMAND 0x8009). Verified live against a real titled
  window. Still human-bound: real-hardware hotkey delivery to
  foreign apps (Alt+W, Ctrl+Q). Clipboard sequence counter verified
  live (increments on writes); the Alt+W capture chain's every
  Windows link is now exercised -- only foreign-app delivery
  itself remains human-bound. Virtual-keyboard bug fixed
  (`be14ae4`/`b5498d6`): `_key_pressed` used `keyboard.press()`
  which holds keys forever -- now taps via the `sendkeys` wrapper.
  Offscreen startup smoke (2026-11-08): `start_qt.py` ran 15s clean
  under `QT_QPA_PLATFORM=offscreen`; the hotkeys diagnostic log
  shows `install()` bound the operator's real config live
  (`HotKeyPopupWindow=ctrl+q`, `HotKeyReplaceSelection=ctrl+shift+t`,
  `HotKeyMainWindow=double-ctrl`, etc.) -- registration path
  verified end-to-end with real settings. SAPI PowerShell fallback
  stdin-encoding bug fixed (`573cc5b`). Hardening waves after that:
  every persisted state file now writes atomically (tmp+os.replace) --
  History.json writers, exceptions.json, and two Options.json writers
  that bypassed config.save entirely (`dd4725c`); diagnostic logs
  rotate at 1MB (`2288b9c`/`11e9f12`); winreg handles closed
  (`efb393a`); swallowed UI-invoke exceptions now logged (`ed04f8e`).
  Lint audits: `uv run --with pyflakes python -m pyflakes qtranslate/`
  and `uv run --with ruff ruff check . --select F821` -- the F821
  (undefined-name) class caught two real Options-page NameErrors
  (`2df787c`); unused-import noise is expected from lazy platform
  imports.
- **macOS real-device pass**: DoubleCtrl CGEventTap flagsChanged feed
  (needs Accessibility grant), Vision mixed-direction OCR ordering
  (UNVERIFIED).
- **PyPI**: `qtranslate-sdk` CONFIRMED by the operator 2026-11-08
  (D19 resolved); publishing rights are still a release-time check.
- **Release assets**: name them `QTranslate-<ver>-<platform>.<ext>`
  (e.g. `-windows-x64.zip`, `-macos-arm64.dmg`) or the update dialog's
  Download button falls back to the release page.

## 5. How to run it

Windows (this machine, 2026-11-08 — venv recreated at `.venv`):

```
.venv/Scripts/python.exe -I start_qt.py google vi
QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe tools/run_suites.py
```

The venv was created with uv (the PATH Python refuses `pip install`):

```
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt \
    PySide6
```

Sweeps: `python -I tools/run_suites.py`. Pixel: `python -I
tools/render_qt.py --compare`. Docs: `python -I tools/docs_consistency.py`.
Live: `python -I tests/live_providers.py`. Bundle:
`python tools/build_bundle.py` (writes the spec, builds, selftests).

## 6. A note on mass suite failures

A sweep once came back with 82 suites failing, every one with exit code
`0xC0000142` (`STATUS_DLL_INIT_FAILED`). Every one of them passed on
its own, and the next full sweep was clean. The machine was out of
resources (12 unrelated Python processes running). Check the process
count and re-run before believing a mass failure. Also: the running
bundle writes the REAL Options.json -- a suite that reads it must pin
what it needs (see commit `362344a`).
