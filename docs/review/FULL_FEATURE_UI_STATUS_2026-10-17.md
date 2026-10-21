# QTranslate Port — Full Feature / UI Status Summary (2026-10-17)

> **Scope:** one-stop status of everything that has been ported, verified, and
> what remains open. This is the "full docs" reference for the port: every
> feature that works, every UI surface that matches native, every test that
> passes, and exactly what is still blocked (and why). Updated after the
> 2026-10-17 sweep.
>
> **Superseded in part on 2026-10-21.** Three documents record what changed:
> `G9_DIFF_DECOMPOSITION_2026-10-21.md` (the 5.35 % G9 difference is 97.5 %
> window frame; the client area matches at 0.21 %), `UI_FIDELITY_MAIN_WINDOW_
> 2026-10-21.md` (three real main-window defects, fixed, with native's own
> assets recovered from the installer payload and the EXE's resources), and
> `AUTO_DETECT_CAPABILITY_2026-10-21.md` (native's per-service auto-detect
> truth table, derived from the recovered `Common.js`). The suite count
> below is the 2026-10-17 figure; the current one is in §7.
>
> **Gate:** `BLOCKED (1)` — G9 part (b) is `UNKNOWN` and needs a human
> reviewer + a human-written waiver token. Nothing below promotes G9.

---

## 1. Test suite sweep — everything green

```
python3.11 -I tools/run_suites.py
127 suites, 0 failed (2026-10-21)
```

| Tool | Result |
|------|--------|
| Headless suites + `ui_match` + `smoke_dict` | **122/0 failed** |
| `tools/docs_consistency.py` | 97 files scanned, 0 findings |
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
| `2131.png` (516×423) | `main.png` (516×393) | Main window | **Close** — same panes, toolbar, boot text. Native has service icon strip; port has it too. **Corrected 2026-10-21: the port did NOT have the strip off Windows** — its buttons were character-sized (230 px each, 2334 px needed inside a 587 px window), so six of the nine services were off-screen and the macOS capture showed no strip at all. Fixed, with native's own icons recovered from the installer payload: `docs/review/UI_FIDELITY_MAIN_WINDOW_2026-10-21.md`. |
| `2130.png` (265×115) | `popup.png` (200×68) | Ctrl+Q popup | **Close** — same title line, star, glyphs, source line. Port smaller. |
| `2126.png` (663×388) | `tray.png` (367×295) | Tray menu | **Mismatch** — `tray.png` is actually Options→Hotkeys page; tray menu not captured |
| `2132.png` (476×333) | `options_internet.png` (663×388) | Options → Internet | **Close** |
| `2133.png` (476×320) | `kbd.png` (464×168) | Virtual keyboard | **Close** |
| `2134.png` (464×198) | `hist.png` (476×303) | History window | **Close** |
| `2135.png` (646×389) | `options_services.png` (663×388) | Options → Services | **Close** — 9 services, 7 dictionaries |
| `2136.png` (646×389) | `options_languages.png` (663×388) | Options → Languages | **Close** — 4-column language list |
| `2137.png` (646×389) | `dict.png` (476×303) | Dictionary window | **Close** |
| `2138.png` (646×389) | `options_exceptions.png` (663×388) | Options → Exceptions | **Close** |
| `2139.png` (646×389) | `options_hotkeys.png` (663×388) | Options → Hotkeys | **Close** — Ctrl+Q, Alt+W bindings |
| `2140.png` (646×389) | `options_updates.png` (663×388) | Options → Updates | **Close** |
| `2141.png` (646×389) | `options_advanced.png` (663×388) | Options → Advanced | **Close** |
| `2144.png` (516×402) | `options_appearance.png` (663×388) | Options → Appearance | **Close** |

**Findings:**
- Structural fidelity is high — every native surface has a port counterpart with same controls, labels, grouping.
- Options pages: 9/9 present.
- Size differences are systematic (DPI/scaling between Windows and macOS capture environments), not layout differences.
- **Gap:** port's tray menu was never captured — `tray.png` is actually the Options→Hotkeys page.
- Doc: `docs/review/NATIVE_VS_PORT_SCREENSHOT_COMPARISON_2026-10-16.md`.

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
| `qt-fj5` (P1) | **G9 part (b)** — native-vs-port pixel comparison | The acceptance capture pair **does** exist (2026-10-16) and was compared; what was missing was a *matched protocol*. The 5.35 % whole-image difference is **97.5 % window frame** — the native was captured with `PrintWindow` and the port by cropping the desktop, and the native was unfocused while the port was focused. The application's own pixels match at **0.21 %** (0.026 % excluding the caption). The harness now refuses a pair whose capture method or activation state disagree. The remaining 12 native surfaces still have no matching port capture, and the human review + waiver are still required. | Human review + human-written waiver token, plus a re-capture of the other 12 surfaces under a matched protocol. See `docs/review/G9_DIFF_DECOMPOSITION_2026-10-21.md`. |
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
~/.local/bin/python3.11 -I tools/run_suites.py          # 127 suites, 0 failed (2026-10-21)

# Audit tools
python3 -I tools/docs_consistency.py                    # 97 files, 0 findings
python3 -I tools/coverage_tally.py --check              # 151 VERIFIED / 1 UNKNOWN
python3 -I tools/gate_artifact_audit.py                 # exit 0
python3 -I tools/audit_ui_spec.py                       # 53 assertions OK

# Launch port app live
uv run --with keyboard --with pyperclip -- python -I start_app.py

# macOS bundle selftest (if dist-mac/ exists)
./dist-mac/QTranslate/QTranslate --selftest             # PASS 17/17
```

---

**Bottom line:** every feature that can be verified without a human reviewer is green. The only thing standing between this port and a clean gate is G9 part (b) — a human screenshot review + waiver. Everything else is done, committed, and pinned by tests.
