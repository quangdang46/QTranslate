# HANDOFF

What the last sessions did, what the tree looks like now, and what the
next session should pick up. Updated **2026-10-23** at `b76889e`, on
`main`, working tree clean.

The standing rules still apply: the GitHub token is used transiently in
a push URL only (never in a file, never in `.git/config`, output
redacted); the native's installer is never run (the installed copy at
`C:/Program Files (x86)/QTranslate/` is read only); `docs/NATIVE_ARCH.md`
is frozen; every Python run uses `python -I`; downloaded files are
untrusted.

## 0. The state of the tree right now

| What | Value |
|---|---|
| Branch / commit | `main` at `b76889e`, pushed |
| Working tree | clean |
| Suites | **135 suites, 0 failed, 64.6s** (`python -I tools/run_suites.py`) |
| Pixel measure | mean ink diff **0.0037** over 12 screens (rgb 0.0358) |
| Docs consistency | 0 findings, 120 files scanned |
| Live selftest | `SELFTEST PASS 29/29` (`python -I start_qt.py --selftest`) |
| Front end | Qt only. tkinter was deleted on 2026-10-23 |

The per-feature checklist (what is proven, what needs a human, what is
blocked) is `docs/review/FEATURE_CHECKLIST_2026-10-23.md`. The
contract-by-contract table is `docs/CONTRACT_AUDIT.md`.

## 1. Ctrl+Q now translates the SELECTION

`hotkey_popup()` used to call `pyperclip.paste()` directly -- no Ctrl+C,
so a user who selected new text and pressed Ctrl+Q got the OLD clipboard
translated. The native's own `help.txt` says "Translate **selected**
text".

The fix is native's copy-capture engine (`FUN_0043BF30`,
`NATIVE_ARCH.md` item 4), as `qtranslate/selection.py`: snapshot the
clipboard sequence number, synthesize Ctrl+C, poll with the native
8ms..320ms backoff until the number CHANGES -- that change is the proof
the copy landed, not a guess. The same engine now serves Alt+W
(`hotkey_replace_selection`) and the mouse modes' `_capture_selection`,
which had a fixed `sleep(0.15)` that read the clipboard before a slow
copy arrived.

**Pinned by** `tests/regress_selection_capture.py` (15): the backoff
shape, a slow copy, a refused Ctrl+C, no sequence counter at all, a held
modifier.

## 2. The popup matches the operator's two captures

Rebuilt against `2162.png` (resting) and `2163.png` (hover), with fully
content-driven sizing -- `MIN_WIDTH`/`MAX_WIDTH` bounds, never a fixed
pixel count.

| What was wrong | What the captures show |
|---|---|
| body painted white | same `#f0f0f0` field as the header |
| hardcoded `#d0d0d0` background | that field is `COLOR_BTNFACE`; 2162's apparent `#cccccc` is the same colour at the default 217 transparency (`240 * 217/255 = 204`) |
| two header glyphs drew as tofu boxes | all five are `RT_ICON` pixmaps recovered from the binary (`book`/`copy`/`translit` joined `star`/`headphone` in the assets manifest, with match distances) |
| the strip's height was added on hover | the strip's ROW is always reserved; only the cells appear |
| labels cut at 4 chars | native cuts at 3 (`Bab...`, `Yan...`) |

The header pair now reads `Vietnamese to English (Google)` from the live
settings, not a literal.

**Pinned by** `ui_match.py` and `regress_popup_smoke.py`, whose old
fixed `(200, 68)` pins became bounds + growth checks.

## 3. Every published menu slot now has a window

`ui_slots` publishes nine menu names. Only `tray`, `main` and
`history_ctx` had a host, so an extension targeting `menu`/`ocr`
registered without error and appeared nowhere -- the same shape as the
eight-capability lie the audit caught earlier.

Six hosts built (`qtranslate/qt/context_menus.py` plus the windows),
each drawing NATIVE's menu from the shipped locale packs by id:

| slot | native menu | items |
|---|---|---|
| `source_context` | 2 | Undo / Cut / Cut all / Copy / Copy all / Paste / Select all / Translate / Dictionary search for / Listen |
| `result_context` | 3 | Open / Copy text / Copy translation / Delete / Listen |
| `language` | 4 | Reset / Edit... / Always detect language |
| `dict_header` | 7, 8 | Show Full History; plus the strip's Show info / Remove dictionary |
| `history_menu` | 9 | Clear history / Show services pane / Exact search / Options |
| `ocr` | 10 | the new `OcrResultWindow`, nine native items |

An id the port has no operation behind is drawn DISABLED, never faked.

**Two real defects fell out of the wiring:**

1. `open_service_page()` called `open_options()` with no page, so every
   "go to that page" entry opened Basics. `open_options(page)` takes a
   page now.
2. `General.ShowServicesPane` saved and did nothing -- the main window
   drew all three panes always. `MainWindow.apply_pane_visibility()`
   hides them now.

**Pinned by** `tests/regress_menu_slots.py` (37).

## 4. The extension platform is fully connected

All eight capabilities are real and proven through the app's own paths
(`engine.translate`, `sdk.dict_lookup`, `player.play_text`,
`services.ocr.ocr_text`, `registry.google_suggest`), each with a
`register_*` method, a live table on `registry`, and a call site. A
capability the host cannot serve is REFUSED at manifest validation.

`tests/regress_extension_capabilities.py` proves each by getting the
extension's own answer back. `regress_qt_extension_ui.py` (33) covers
the UI slots, the override picker, and capability refusal.
`regress_sdk_package.py` (22) builds the wheel and installs it into a
clean virtualenv.

## 5. Bugs found and fixed along the way

| Bug | Where it was hiding | Suite that caught it |
|---|---|---|
| a total provider failure reported `Result.ok == True` | `engine.translate` put the REQUESTED service into `provider_used`; `ok` is `bool(provider_used)` | `regress_app_reliability_e2e.py`, which drives `app.on_go()` rather than the router |
| the macOS adapter returned the WINDOWS path | `MacOSAdapter.app_data()` called `app_data_dir()`, which reads `%APPDATA%` first -- so the "macOS" test passed while proving nothing | `regress_platforms.py` now asserts the path does NOT come from `%APPDATA%` |
| `KeyError: 0` on Microsoft/Bing | the live endpoint returns `{"statusCode": 400}` where native's shape is a list | `regress_microsoft_chain.py`; the port reports an empty translation and the chain falls through |
| the bundle's `--with keyboard==0.13.5` was one argv entry | `build_bundle.py` | the build itself |
| five Core modules were unreachable in a frozen build | reached only through the deleted tkinter code | the frozen-gap check |

## 6. What is NOT done -- and why it needs someone else

Read `docs/review/FEATURE_CHECKLIST_2026-10-23.md` §"Tổng hợp NEED/BLOCKED"
for the full list. The short version:

**Needs a human at a desktop** (nothing automatic can substitute):
- press Ctrl+Q in a real app with a real selection, repeatedly, and
  confirm no crash and the popup lands beside the pointer;
- Replace Selection against a real foreground window;
- each Options page changed, app restarted, value still in effect;
- TTS actually audible; microphone actually captured;
- live providers and live OCR (the latter needs an API key).

**Blocked on evidence that does not exist:**
- Options → Basics has NO native capture (BLOCKERS B4), so its pixel
  parity cannot be measured -- only its control set is verified;
- the tray menu's live item list has no native capture either; the 13
  captures were all checked and none shows it. Recording it as
  `partial` is the honest state.

**Blocked on hardware:**
- macOS has an adapter (`MacOSAdapter`, clipboard + paths, resolving
  `~/.config/QTranslate`) but no macOS host has run it. Hotkeys, the
  mouse hook and SAPI report themselves `UNAVAILABLE` there rather than
  faking support.

**Human-only gates:**
- G9 needs a person to review the screenshots and a person to write the
  waiver. Neither may be self-assigned. `qt-fj5` is exactly those two.

## 7. Translation speed -- measured, not yet optimised

The user's question "why is it slow" is not answered by a number yet.
Two facts are established by reading the code:

- `QtApp.on_go()` / `_translate()` call `engine.translate()` on the UI
  thread, so a slow provider freezes the window for the duration.
- `engine.translate` runs pick -> detect -> router -> (retry, fallback,
  back-translation, workflow) synchronously.

**The next step is to MEASURE each stage before changing anything.**
Do not shorten timeouts or drop the fallback to make it look faster --
`docs/TEST_STRATEGY.md` and the reliability suites exist because a fast
wrong answer is worse than a slow right one.

## 8. How to run it

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

## 9. A note on mass suite failures

A sweep once came back with 82 suites failing, every one with exit code
`0xC0000142` (`STATUS_DLL_INIT_FAILED`). Every one of them passed on its
own, and the next full sweep was clean. The machine was out of
resources (12 unrelated Python processes running). Check the process
count and re-run before believing a mass failure.
