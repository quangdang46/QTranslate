# HANDOFF

What the last sessions did, what the tree looks like now, and what the
next session should pick up. Updated **2026-10-24** at the tip of
`main` (see §0), working tree clean, pushed.

The standing rules still apply: the GitHub push token is used
transiently in a push URL only (never in a file, never in
`.git/config`; the helper authenticates as `qdang46`, which gets 403 on
`quangdang46/QTranslate`, so the operator supplies a session token);
the native's installer is never run (the installed copy at
`C:/Program Files (x86)/QTranslate/` is read only); `docs/NATIVE_ARCH.md`
is frozen; every Python run uses `python -I`; downloaded files are
untrusted.

## 0. The state of the tree right now

| What | Value |
|---|---|
| Branch / commit | `main`, tip = the HANDOFF commit itself, pushed |
| Working tree | clean |
| Suites | **140 suites, 0 failed, ~53s** (`python -I tools/run_suites.py`) |
| Pixel measure | mean ink diff **0.0037** over 12 screens (re-run 24/10) |
| Docs consistency | 0 findings, 120 files scanned |
| Live providers | **21 checks LIVE-OK** (`tests/LIVE_RESULTS.md`); PROMT/Babylon/Baidu-translate dead, recorded |
| Bundle | rebuilt on this tree, `SELFTEST PASS 29/29`, runs from `dist\QTranslate\` |
| Front end | Qt only. tkinter was deleted on 2026-10-23 |

**The operator CONFIRMED the GUI matches native** (2026-10-24, running
the real bundle). Recorded in `docs/review/FEATURE_CHECKLIST_2026-10-23.md`.

## 1. This session (2026-10-24) -- what landed, newest last

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
- PROMT: the backend answers "temporarily unavailable" -- re-probe
  periodically; if it comes back, the scrape is already working.
- Rebuild the bundle after any change
  (`python tools/build_bundle.py`, selftest 29/29) -- the operator runs
  the bundle, not the repo.
- More customisation APIs along the same seam (e.g. exposing the
  hotkey table or the tray icon set to extensions) -- ask the operator
  which he wants first.

**Needs the operator:**
- Behaviour NEEDs in `docs/review/FEATURE_CHECKLIST_2026-10-23.md`:
  Ctrl+Q / Replace Selection against real foreign apps, each Options
  page changed + app restarted + value still in effect, TTS audible,
  microphone, OCR live (needs an API key). The GUI itself is confirmed.
- **G9**: review `native.png`/`port.png`/`diff.png` and write the
  waiver token -- no agent may self-assign it (`qt-fj5`).
- Options → Basics and the tray menu have NO native capture
  (BLOCKERS B4) -- pixel parity there is unverifiable without them.
- **macOS**: the adapter exists; no macOS host has run it (`qt-3ro`).
- **PyPI**: `qtranslate-sdk` is provisional (D19) -- a human must
  verify the name and rights before publishing.

## 5. How to run it

```
.venv/Scripts/python.exe -I start_qt.py google vi
```

The venv was created with uv (the PATH Python refuses `pip install`):

```
uv venv C:/Users/ADMIN/qtranslate-re/.venv --python 3.12
uv pip install --python C:/Users/ADMIN/qtranslate-re/.venv/Scripts/python.exe \
    PySide6 keyboard pyperclip Pillow
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
