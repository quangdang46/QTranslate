# QTranslate Port — Full Feature / UI Status Summary (2026-10-17)

> **Scope:** one-stop status of everything that has been ported, verified, and
> what remains open. This is the "full docs" reference for the port: every
> feature that works, every UI surface that matches native, every test that
> passes, and exactly what is still blocked (and why). Updated after the
> 2026-10-17 sweep.
>
> **Superseded in part on 2026-10-21.** Five documents record what changed:
> `G9_DIFF_DECOMPOSITION_2026-10-21.md` (the 5.35 % G9 difference is 97.5 %
> window frame; the client area matches at 0.21 %), `UI_FIDELITY_MAIN_WINDOW_
> 2026-10-21.md` (three real main-window defects, fixed, with native's own
> assets recovered from the installer payload and the EXE's resources),
> `AUTO_DETECT_CAPABILITY_2026-10-21.md` (native's per-service auto-detect
> truth table, derived from the recovered `Common.js`),
> `UI_FIDELITY_OPTIONS_2026-10-21.md` (the Options window rebuilt against
> native's nine dialog templates) and `UI_FIDELITY_SURFACES_2026-10-21.md`
> (the other five surfaces, captured and compared under one protocol).
> The suite count below is the 2026-10-17 figure; the current one is in §7.
>
> **Gate:** `BLOCKED (1)` — G9 part (b) is `UNKNOWN` and needs a human
> reviewer + a human-written waiver token. Nothing below promotes G9.

---

## 1. Test suite sweep — everything green

```
python3.11 -I tools/run_suites.py
129 suites, 0 failed (2026-10-21)
```

| Tool | Result |
|------|--------|
| Headless suites + `ui_match` + `smoke_dict` | **129/0 failed** |
| `tools/docs_consistency.py` | 106 files scanned, 0 findings |
| `tools/coverage_tally.py --check` | `151 VERIFIED / 1 UNKNOWN (G9)`, Gate `BLOCKED (1)` |
| `tools/gate_artifact_audit.py` | exit 0 — **and now true**: 2026-10-21 taught it to resolve a citation against the *recovered* native copies (147 VERIFIED rows cite a concrete artifact, 0 cite only a doc pointer; it was 128/19 and exit 1 on the 2026-10-17 baseline) |
| `tools/audit_ui_spec.py` | 53 assertions OK |

**The single remaining blocker is G9 part (b)** — a real native-vs-port pixel
comparison that a human must review. It cannot run here because screenshots
are banned on this host. See §6.

---

## 2. Runtime features — all live-verified on macOS

The port app was opened live on this host (macOS, Python 3.11, Tk 9.0).
Main window: title `QTranslate`, geometry `595×376`, source pane shows the
expected boot text (`QTranslate Version 6.10.0` + hotkey help).

| Surface | Status | Evidence |
|---------|--------|----------|
| History window | **Opens** | `app.open_history_window()` → Toplevel, exists=1, children=3 |
| Dictionary window | **Opens** | `app.open_dict_window()` → Toplevel, exists=1, children=3 |
| Options window | **Opens** | `app.open_options()` → Toplevel, exists=1, children=3 |
| Ctrl+Q popup | **Opens** | `show_popup(...)` → Toplevel, exists=1, children=1 |
| Frozen bundle `--selftest` | **PASS 17/17** | `dist-mac/QTranslate/QTranslate --selftest` on macOS arm64 |

**Real product defects found by opening windows live (not by reading code), all fixed:**

| # | Defect | Evidence | Fix |
|---|--------|----------|-----|
| 1 | `OptionsDialog.open()` body indented inside `except` — returned `None`, Options window never opened | `open_options()` returned `NoneType`, 0 Toplevels | Dedented 8 spaces to match pre-split `app.py` guard |
| 2 | Missing imports after Phase 7 split: `startup_entry`, `SRC_LANG_NAMES`, `TO_LANG_NAMES` | `NameError` on `show_basics()` | Added to `from qtranslate.app import (...)` |
| 3 | `PopupHost.open()` / `OptionsDialog.open()` never returned the window | Window opened but callers got `None` | Added `return win` / `return w` |
| 4 | `keyboard` import crashes macOS Cocoa process (not a catchable exception) | `import keyboard` → `__CFDataValidateRange` abort | Gate behind `sys.platform == "win32"` everywhere at module level (`app.py`, `start_app.py`, `_frozen_selftest()`, `build_bundle.py`) |

Commits: `9893eb8` (dict template CRLF), `440ad81` (suite skips + pin), `a542659` (windows.py defects), `91d454b` (macOS bundle fixes).

---

## 3. UI — native vs port screenshot comparison

All 13 native captures in `docs/review/native_screens/` (2126–2144) were
opened and compared against `screenshots/screens/*.png`. This is a
**human-reviewed visual pass**, not a pixel diff — G9 stays `UNKNOWN`.

| Native | Port | Surface | Verdict |
|--------|------|---------|---------|
| `2131.png` (516×423) | `main.png` (595×404) | Main window | **Close** — same panes, same toolbar, same boot text, same service strip with the same truncated labels. **Corrected 2026-10-21: the port did NOT have the strip off Windows** — its buttons were character-sized (230 px each, 2334 px needed inside a 587 px window), so six of the nine services were off-screen and the macOS capture showed no strip at all. Fixed, with native's own icons recovered from the installer payload: `docs/review/UI_FIDELITY_MAIN_WINDOW_2026-10-21.md`. |
| `2130.png` (265×115) | `popup.png` (265×79) | Ctrl+Q popup | **Close** — same caption row, star and four glyphs, same result line. **2026-10-21:** the port drew a fixed 60-column text area (616 px) where native sizes the popup to its content and truncates the caption ("English to Viet…"), it had no close button, and its fourth glyph was a refresh arrow where native's is the romanization mark. All three fixed. |
| `2126.png` (663×388) | -- | Tray menu | **Not capturable** — the tray menu is a Tk menu, not a window, so a window capture cannot see it; the native's is a bitmap. |
| `2132.png` (476×333) | `dict.png` (553×374) | Dictionary window | **Close on the row, open on the strip** — **2026-10-21:** native's DLG184 row is `[language v] [<][>] [field] [q] [d] [v]`, and the port now draws exactly that (the language combo, the history arrows, the magnifier, the clock and the ':' menu). Native still draws a strip of twelve dictionary-service icons along the bottom; the port has no such strip (the dictionary-service icons are not in the recovered asset set — the nine bundled icons are the *translation* services'). |
| `2133.png` (476×320) | `keyboard.png` (539×219) | Virtual keyboard | **Close** — same key layout, same language dropdown. The port is 63 px wider (the template's 539 px against the captured instance's 476 px). |
| `2134.png` (464×198) | `history.png` (553×359) | History window | **Close** — same tree, same buttons. The port is 89 px wider and 161 px taller (the template's 553×331 against the captured instance's 464×198). |
| `2135.png` (646×389) | `options_Internet.png` (751×445) | Options → Internet | **Close** — the Connection and Proxy group boxes, the seconds combo over the millisecond value, the proxy fields. |
| `2136.png` (646×389) | `options_Services.png` (751×445) | Options → Services | **Close** — one list with the Translation and Dictionary groups, the service icons, 'Add dictionary...' / 'Remove dictionary'. **2026-10-21: the port's two lists were EMPTY on a fresh config** (they were filled from `ServicesOrder` alone, a key that does not exist until the user reorders something). Fixed. |
| `2137.png` (646×389) | `options_Languages.png` (751×445) | Options → Languages | **Close** — native's four-column checklist of 72 languages and 'Check / Uncheck all'. **2026-10-21: the port's page was a page native does not have** ('Default languages' with Translate from/to, Dictionary, Virtual keyboard, Always detect, Smart detection, Language pairs, Disabled languages). Replaced. |
| `2138.png` (646×389) | `options_Appearance.png` (751×445) | Options → Appearance | **Close** — the General and Popup window group boxes, native's control order, the seconds unit, the four icon buttons and the three colour swatches. **2026-10-21: the page raised `NameError` and rendered nothing** (the Phase 7 split had dropped six names from `app.py`'s scope). Fixed. |
| `2139.png` (646×389) | `options_Exceptions.png` (751×445) | Options → Exceptions | **Close** — the mode combo, the one two-column table, Add/Modify/Delete (which now open native's DLG178 entry dialog), 'Enable smart detection'. |
| `2140.png` (646×389) | `options_Advanced.png` (751×445) | Options → Advanced | **Close** — the Advanced, Mouse mode and API keys group boxes, the four native ComboBoxes, the OCR API key and its link. **2026-10-21: the port drew two captions for one config key and overflowed the window**, pushing Apply off the bottom edge. Fixed. |
| `2141.png` (646×389) | `options_Updates.png` (751×445) | Options → Updates | **Close** — 'Automatically check for updates', the changelog area, 'Check now' and 'Install'. |
| -- | `options_Basics.png` (751×445) | Options → Basics | **No native capture**, but the page matches DLG171: the General / Auto-detect languages / History group boxes and native's control order. |
| -- | `options_Hotkeys.png` (751×445) | Options → Hotkeys | **No native capture**, but the page matches DLG179: 'Enable hotkeys' and the action list. |
| `2144.png` (516×402) | `options_Appearance.png` | Options → Appearance (crop) | **Close** — the same page as 2138, cropped. |

> **2026-10-21: the native screen numbers in this table were wrong** and
> have been corrected. `2132` is the **Dictionary window** (it had been
> read as the Internet page), and `2135`/`2136`/`2137` are
> **Internet / Services / Languages** (they had been read as
> Services / Languages / Dictionary). The numbering was re-derived by
> reading each capture's highlighted nav row and its body; the two
> documents that carried the wrong numbers are corrected too.

> **And the capture harness itself was wrong.** `CGWindowListCreateImage`
> returns 32-bit **BGRA** and the harness read it as RGB, so red and
> blue came out swapped in every port screenshot taken before
> 2026-10-21 (a canvas filled `#0000ff` captured as `f60e00`, `#ff0000`
> as `142eee`, `#00ff00` unchanged). Every colour claim made against
> those screenshots was an artifact of the harness and does not survive
> it. All the comparisons above are from the fixed harness.

**Findings:**
- Structural fidelity is high — every native surface has a port counterpart with the same controls, labels and grouping. **2026-10-21: the Options window was the exception and had been rebuilt against native's nine dialog templates** (`UI_FIDELITY_OPTIONS_2026-10-21.md`); the six defects it took are listed there.
- Options pages: 9/9 present, each matching its DLG (171/172/173/174/175/176/179/185/205).
- Size differences are systematic (the template's size against the captured instance's), not layout differences.
- **Gap:** the tray menu cannot be captured by a window capture (it is a Tk menu, not a window).
- **Gap:** native's dictionary window draws a strip of twelve dictionary-service icons along the bottom; the port has no such strip, because the nine icons recovered from the installer payload are the *translation* services'.
- Docs: `NATIVE_VS_PORT_SCREENSHOT_COMPARISON_2026-10-16.md` (corrected), `UI_FIDELITY_OPTIONS_2026-10-21.md`, `UI_FIDELITY_SURFACES_2026-10-21.md`.

---

## 4. Packaging — Windows + macOS

| Platform | Status | Details |
|----------|--------|---------|
| Windows | **Built & verified** | PyInstaller onedir, `tools/build_bundle.py`, frozen exe selftest 18/18 |
| macOS | **Built & verified** | Built on this host (macOS arm64), `QTranslate --selftest` → `PASS 17/17` |

**macOS bundle note:** bead `qt-3ro` claimed "cannot be produced or verified on this host" — that premise was wrong. This host **is** macOS arm64, and the bundle builds + verifies here. Fixed defects:
- `qtranslate.unavailable_adapter` hidden import didn't exist → changed to `qtranslate.platforms`.
- `keyboard` import crashes macOS Cocoa → gated behind `sys.platform == "win32"`.
- `start_app.py` module-level `import keyboard` → same gate.

Doc: `docs/review/OFF_WINDOWS_SUITE_FAILURES_2026-10-17.md`.

---

## 5. What remains open (requires human decision — not agent-tractable)

| Bead | Item | Why it's blocked | What's needed |
|------|------|------------------|---------------|
| `qt-fj5` (P1) | **G9 part (b)** — native-vs-port pixel comparison | The acceptance capture pair **does** exist (2026-10-16) and was compared; what was missing was a *matched protocol*. The 5.35 % whole-image difference is **97.5 % window frame** — the native was captured with `PrintWindow` and the port by cropping the desktop, and the native was unfocused while the port was focused. The application's own pixels match at **0.21 %** (0.026 % excluding the caption). The harness now refuses a pair whose capture method or activation state disagree. The human review + waiver are still required. **2026-10-21: the port-side re-capture of the other surfaces is DONE** — every native surface now has a port capture and a side-by-side under one protocol (`UI_FIDELITY_SURFACES_2026-10-21.md`). The *native* side still has to be re-captured on the Windows host, because the harness expects near-pixel parity and a macOS capture can never meet it. | Human review + human-written waiver token, plus a re-capture of the **native** side on the Windows host under the same protocol. See `docs/review/G9_DIFF_DECOMPOSITION_2026-10-21.md`. |
| `qt-o7p` (P2) | **MainWindow split** (6th of 6 classes) | MainWindow *is* the app (panes, orchestration, hotkey routing, clipboard monitor); no fidelity signal under screenshot ban | Scoping decision: is a 1,789-line restructure worth the risk? |

**Gate arithmetic:** G9 stays `UNKNOWN` → Gate stays `BLOCKED (1)`. A waiver would close the row, but the validator never assigns one — it only validates a token a human put in the document.

Doc: `docs/review/OFF_WINDOWS_SUITE_FAILURES_2026-10-17.md`.

---

## 6. What was deliberately NOT done (recorded, not claimed)

- **G9 part (b):** not a code change, not a pixel diff. The G9 harness (`tools/g9_screenshot_diff.py`) exists and works mechanically (`selftest` 15/15), but `compare` needs genuine native+port captures under identical protocol (`ui_state`, `input`, `size_origin`).
- ~~**MainWindow (Phase 7, 6th class):**~~ done 2026-10-21 — `qtranslate.windows.MainWindow` holds the 50 moved methods, `app.py` keeps a thin delegator each; the widget geometry before and after the split is identical band for band.
- **macOS adapters (Phase 4):** scoped out — no macOS machine to wrap yet; `platforms.py` already reports `unavailable` honestly off-Windows.
- **Override UI (Phase 3):** the policy lives in `extensions.py` (headless); the thin tkinter dialog (`override_ui.py`) exists but the winner-picking UI is scoped out.
- **Vendored-dep isolation (D17):** loader puts the extensions folder on `sys.path`; collisions remain possible — a product decision, not RE work.

---

## 7. Reproduce

```bash
# Full suite sweep
~/.local/bin/python3.11 -I tools/run_suites.py          # 129 suites, 0 failed (2026-10-21)

# Audit tools
python3 -I tools/docs_consistency.py                    # 106 files, 0 findings
python3 -I tools/coverage_tally.py --check              # 151 VERIFIED / 1 UNKNOWN
python3 -I tools/gate_artifact_audit.py                 # exit 0
python3 -I tools/audit_ui_spec.py                       # 53 assertions OK

# Launch port app live
uv run --with keyboard --with pyperclip -- python -I start_app.py

# macOS bundle selftest (if dist-mac/ exists)
./dist-mac/QTranslate/QTranslate --selftest             # PASS 17/17
```

---

**Bottom line:** every feature that can be verified without a human reviewer is green, and the UI check is done surface by surface against the native captures with the defects fixed and pinned by tests. The only thing standing between this port and a clean gate is G9 part (b) — a human screenshot review, a human-written waiver, and a re-capture of the *native* side on the Windows host. Everything else is done, committed, and pinned by tests.
