# CONTRACT-TO-CODE AUDIT

A row-by-row check of what `PROJECT_VISION.md`, `COMPATIBILITY_MATRIX.md`
and `EXTENSION_SDK.md` promise, against what the code does. Written
2026-10-23 at `6636686`, after the tkinter front end was deleted.

Every row carries one of five states, and they are NOT interchangeable:

| State | Means |
|---|---|
| **Implemented** | the code exists |
| **Wired** | the running app actually reaches it |
| **Behaviour-verified** | a test proves the behaviour (not just the call) |
| **Platform-verified** | the behaviour was run on the named OS |
| **Missing / partial** | absent, or only half built |

A row is never promoted because a neighbouring row passed. The point of
this file is that "there is code" and "the app does it" are different
claims, and this project has been burned by the gap once already (the
extension registry existed and nothing read it).

## P0 -- the working tree builds and runs

Done on 2026-10-23 at `6636686`, on this machine.

| Check | Result | Evidence |
|---|---|---|
| Working tree clean at the audited revision | yes | `git status` |
| The tkinter import graph is gone | yes | no `qtranslate.app` / `qtranslate.windows` import outside scratch tools |
| The live selftest | `SELFTEST PASS 29/29` | `python -I start_qt.py --selftest` |
| The bundle builds | yes | `tools/build_bundle.py`, exit 0 |
| The FROZEN bundle's selftest | `SELFTEST PASS 29/29` | `dist/QTranslate/QTranslate.exe --selftest` |
| The frozen-module gap check | clean | the build fails on a module Analysis missed |
| The full suite | **130 suites, 0 failed, 64.4s** | `python -I tools/run_suites.py` |
| Docs consistency | 0 findings | `tools/docs_consistency.py` |

**Two defects the build found, both fixed:**

1. `build_bundle.py` passed `"--with keyboard==0.13.5"` as ONE argv entry
   instead of two, so `uv` read the value as `" keyboard==0.13.5"` and the
   build died with "unexpected argument '--with keyboard' found". The
   build had not been run since the argument was written.
2. Five Core modules (`clipboard`, `fonts`, `override_ui`, `screens`,
   `updater`) were reached only through the deleted tkinter code. The
   frozen-gap check caught them, they are `hiddenimports` now, and the
   bundle carries them.

## P1 -- the extension contract vs the runtime

This is the section the C2C audit asked for, and it found a real gap.

### The `capabilities` field is broader than the API

A manifest may declare eight capabilities. `ExtensionAPI` has **three**
`register_*` methods.

| Capability | `register_*` in `ExtensionAPI` | Host consumes it | State |
|---|---|---|---|
| `provider` | `register_provider` | yes -- committed into `registry.TRANSLATORS`, reached by `engine.translate` | **Behaviour-verified** |
| `theme` | `register_theme` | yes -- `QtApp.apply_theme` resolves through the manager and `apply_style` paints it | **Behaviour-verified** |
| `ui` | `register_ui` | yes -- every published menu/panel/popup slot has a host | **Behaviour-verified** |
| `workflow` | `register_workflow` | yes -- `engine.translate` runs the step on the finished text | **Behaviour-verified** |
| `dictionary` | `register_dictionary` | yes -- `sdk.dict_lookup` reads `registry.DICT_EXT` | **Behaviour-verified** |
| `tts` | `register_tts` | yes -- `player.play_text` tries the extension backend first | **Behaviour-verified** |
| `ocr` | `register_ocr` | yes -- `services.ocr.ocr_text` asks it before the endpoint | **Behaviour-verified** |
| `spell` | `register_spell` | yes -- `registry.google_suggest` prefers it | **Behaviour-verified** |

**Measured, not inferred.** When the audit was written, an extension
declaring ANY of the eight loaded with `status: "loaded"` -- including
the five the runtime could not host -- so `capabilities` was a lie.

**Closed the same day, both ways.** A capability outside the hostable
set is refused at manifest validation with a defined error (so the
field can never lie again), AND the five now exist: each has its
`register_*` method, a live table on `registry` (`DICT_EXT`, `TTS_EXT`,
`OCR_EXT`, `SPELL_EXT`, `WORKFLOW_EXT`), and a call site in the app that
uses it. `tests/regress_extension_capabilities.py` proves each by
driving the REAL app path -- `engine.translate`, `sdk.dict_lookup`,
`player.play_text`, `ocr_text`, `google_suggest` -- and getting the
extension's own answer back. A capability that raises falls through to
the built-in instead of taking the call with it.

### The UI slots: three kinds, not every slot name

`ui_slots` publishes nine menu names, three panel names and two popup
names. The host consumes:

| Kind / slot | Consumer | State |
|---|---|---|
| `menu` / `tray` | the Qt tray menu adds one action per contribution | **Behaviour-verified** |
| `panel` / `top`, `middle` | the main window docks a strip in that pane | **Behaviour-verified** |
| `popup` / `body` | the popup lets the contribution render its text | **Behaviour-verified** |
| `menu` / the other eight names | every menu reads its own slot (`extension_menu_entries`) | **Wired** (main and history_ctx pinned; the reader is one function) |
| `panel` / `services` | the main window docks a strip above the provider buttons | **Behaviour-verified** |
| `popup` / `icons` | the popup places a contributed label in its icon row | **Behaviour-verified** |

The three that work are the ones with a test
(`regress_qt_extension_ui.py`). The rest are published names with no
host, which is the same shape as the capability gap above.

### The SDK package

| Claim | State | Evidence |
|---|---|---|
| `qtranslate-sdk` is a standalone distribution | **Implemented** | `sdksrc/pyproject.toml` |
| It imports with no desktop app on `sys.path` | **Behaviour-verified** | `regress_sdk_package.py` |
| Its contracts match the host's | **Behaviour-verified** | field-for-field comparison in the same suite |
| Its wheel builds and installs into a clean virtualenv | **Behaviour-verified** | the same suite, `--no-index` |
| Publishing to PyPI | **Missing (human)** | D19: the name and its rights need verifying |

## P2 -- the product claims

### Feature parity

| Claim | State | Why |
|---|---|---|
| The twelve captured native screens are reproduced | **Behaviour-verified** | mean ink diff 0.0037 over twelve screens |
| Every feature row has a test behind it | **Behaviour-verified** | every row that was `ported` now names a suite that runs; three of those rows (speech, the virtual keyboard, themes) had NO suite at all and one (`regress_sapi.py`) did not exist -- `regress_sapi_and_keyboard.py` and the existing theme/locale/OCR suites back them now |
| Every native BEHAVIOUR is reproduced | **partly verified, and the remainder is named** | What IS proven: the twelve windows' pixels (0.0037), the strip's real icons and 56px geometry, the mouse mode's gates in native's order, the hotkeys' 17-key codec, the history's lifecycle, the nine Options pages' control sets, the fallback chain and its error strings. What is NOT proven and is not claimed: native's behaviour on the screens with no capture (the Basics page), the tray menu's live menu (no capture), and every endpoint that is dead by evidence. The audit's job is to keep that list true, not to shorten it by relabelling. |
| The Basics Options page matches native | **Missing** | no native capture of it exists (BLOCKERS B4) |
| The tray menu matches native item-for-item | **partial, and the evidence is exhausted** | the menu is the OS's own, and NO native capture of it exists. The 13 captures were checked: 2126/2135-2141/2144 are Options pages, 2130 is the popup, 2131-2134 are the four windows. The item list comes from the locale pack's `Menus[].Id 5` block plus the reference renderer's markup, which is two independent transcriptions but not a picture. Recording it as partial is the honest state; a capture needs a person at the native. |
| Dead endpoints behave like native's dead endpoints | **missing** | Babylon, ImTranslator, Google Search, Yandex TTS and Baidu TTS are `dead:` by evidence, which is honest, but they are not "working features" |

### Reliability

| Claim | State | Why |
|---|---|---|
| Fallback router, error classes, health tracking | **Implemented + Behaviour-verified** | `reliability.py`, `regress_reliability.py` |
| The app tells the user which provider answered | **Wired** | the result pane shows `res.provider_used` |
| Every provider holds up live | **Missing** | `TEST_RESULTS.md`: 19/21 live, Bing session scrape broken, WordReference needs Playwright |
| End-to-end under consecutive failures | **Behaviour-verified** | `regress_app_reliability_e2e.py` drives `app.on_go()` with a rigged provider table |

### Platforms

| Claim | State | Why |
|---|---|---|
| Windows | **Platform-verified** | every suite and the bundle ran here |
| macOS - clipboard and paths | **Implemented, not platform-verified** | `MacOSAdapter` exists and now resolves its own home-based path; no macOS host ran it. **A defect was found and fixed here:** the adapter called `app_data_dir()`, which reads `%APPDATA%` first, so on a Windows host it returned the WINDOWS path -- a test asserting it "passed" while proving nothing about macOS. It resolves from `~` now, and the test says so. |
| macOS - hotkeys, mouse hook, SAPI | **Missing, honestly reported** | the adapter returns `UNAVAILABLE` rather than faking it |

The last row is the right shape: an unavailable capability that reports
itself unavailable is honest. Claiming macOS support without a macOS run
is not.

### The gates

| Gate | State |
|---|---|
| G0-G8 | DONE, with the evidence `IMPLEMENTATION_PLAN.md` names |
| G9 | **BLOCKED** -- a human reviews the screenshots; a human writes the waiver |
| G10 | the suite is green; final acceptance waits on G9 |

Neither G9 item may be self-assigned. `qt-fj5` is exactly those two.

## What this audit changes

Nothing in the product claims above may be upgraded without the evidence
column changing. The two things it found that are fixable now:

1. **The capability gap** (P1). The runtime accepts eight capabilities
   and hosts three. This is the highest-value fix: it is a contract lie
   today, and the fix is small.
2. **The missing UI slots** -- closed the same day. Every published
   slot now has a host: each menu draws its own slot through one shared
   reader, the services pane has its strip, and the popup has its icon
   row. `regress_qt_extension_ui.py` grew to 34 assertions, and the
   pixel measure is unchanged (0.0037) because a window with no
   extension draws exactly what native draws.

The capability gap is closed in both halves: the five are BUILT (each
with a table and a call site, proven end to end) and the validator still
refuses a name it does not know, so a manifest cannot claim a capability
that does not exist.

**A real bug fell out of the end-to-end reliability case.** When every
provider failed, the engine still put the REQUESTED service into
`Result.provider_used`, and `Result.ok` is `bool(provider_used)` -- so a
total failure reported `ok=True`. The unit suite could not see it (it
asks the router, not the engine); driving `app.on_go()` did. Fixed:
`provider_used` stays empty on that branch and `requested` carries which
service was asked.
