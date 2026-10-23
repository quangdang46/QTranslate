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
| `ui` | `register_ui` | partly -- the tray menu, the top/middle panels and the popup body | **partial** |
| `workflow` | none | none | **Missing** |
| `dictionary` | none | none | **Missing** |
| `tts` | none | none | **Missing** |
| `ocr` | none | none | **Missing** |
| `spell` | none | none | **Missing** |

**Measured, not inferred.** An extension declaring ANY of the eight loads
with `status: "loaded"` -- including the five the runtime cannot host.
`extensions.py`'s own comment says the opposite ("silently accepting a
kind the runtime cannot host would make `capabilities` a lie"), so the
code contradicts its comment.

**This is a contract bug, not a missing feature.** The fix is one of:

- (a) give the five a `register_*` and a host consumer, or
- (b) reject a manifest whose capabilities include one the runtime cannot
  host, with a defined error the author can see.

(b) is the smaller, honest change and it is what `EXTENSION_SDK.md`
already promises; (a) is the bigger one the vision describes. Until one
of them lands, a manifest's `capabilities` must not be read as a
statement that the app supports them.

### The UI slots: three kinds, not every slot name

`ui_slots` publishes nine menu names, three panel names and two popup
names. The host consumes:

| Kind / slot | Consumer | State |
|---|---|---|
| `menu` / `tray` | the Qt tray menu adds one action per contribution | **Behaviour-verified** |
| `panel` / `top`, `middle` | the main window docks a strip in that pane | **Behaviour-verified** |
| `popup` / `body` | the popup lets the contribution render its text | **Behaviour-verified** |
| `menu` / the other eight names | none | **Missing** |
| `panel` / `services` | none | **Missing** |
| `popup` / `icons` | none | **Missing** |

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
| Every native feature is reproduced | **Missing** | `FEATURE_MATRIX` still carries `ported` rows that are not `behaviour-verified` |
| The Basics Options page matches native | **Missing** | no native capture of it exists (BLOCKERS B4) |
| The tray menu matches native item-for-item | **partial** | the menu is the OS's own; the item list was transcribed, not measured |
| Dead endpoints behave like native's dead endpoints | **missing** | Babylon, ImTranslator, Google Search, Yandex TTS and Baidu TTS are `dead:` by evidence, which is honest, but they are not "working features" |

### Reliability

| Claim | State | Why |
|---|---|---|
| Fallback router, error classes, health tracking | **Implemented + Behaviour-verified** | `reliability.py`, `regress_reliability.py` |
| The app tells the user which provider answered | **Wired** | the result pane shows `res.provider_used` |
| Every provider holds up live | **Missing** | `TEST_RESULTS.md`: 19/21 live, Bing session scrape broken, WordReference needs Playwright |
| End-to-end under consecutive failures | **partial** | unit-tested through the router; not driven through the running app |

### Platforms

| Claim | State | Why |
|---|---|---|
| Windows | **Platform-verified** | every suite and the bundle ran here |
| macOS - clipboard and paths | **Implemented, not platform-verified** | `MacOSAdapter` exists; no macOS host ran it in this session |
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
2. **The five missing UI slots.** Published, no host.

Both are recorded here rather than fixed in the same pass, so the audit
is a measurement and not a rewrite.
