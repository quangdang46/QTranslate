# Off-Windows suite failures — triage (2026-10-17)

> The headless sweep (`python3.11 -I tools/run_suites.py`) showed **122
> suites, 6 failed** on macOS. This document records what each failure
> was, what was fixed, and what was deliberately left Windows-only.
> Sweep after: **122 suites, 0 failed**. Gate unchanged `BLOCKED (1)`.

## 1. Real defects (fixed)

| # | Suite | Defect | Fix |
|---|---|---|---|
| 1 | `regress_dict_template` | `dict_template.html` was 2985 bytes vs native RT_HTML-192's 3062. The 77-byte gap was line endings only (LF vs CRLF, 77 newlines) — no content lost. | Converted file to CRLF (commit `9893eb8`). Suite passes (6 assertions). |
| 2 | `regress_options_roundtrip` | Called `C.load()` unconditionally (line 37) despite its own docstring promising "reads the live Options.json when present; otherwise exercises a synthetic 20-section document". Crashed `FileNotFoundError` off-Windows. | Wrapped in `try/except (FileNotFoundError, OSError) → None` so the synthetic path runs (commit `440ad81`). |
| 3 | `regress_windows` (pin, not product) | The byte-identity pin compared against the pre-split body byte-for-byte, so the two trailing `return` lines the runtime fix added (see §2) failed it. | Allowed the trailing returns for PopupHost (`return win`) and OptionsDialog (`return w`), same allowance DictionaryView already had (commit `440ad81`). 41 assertions. |

## 2. Real product defects (fixed, in `windows.py`)

Found by **opening the windows live**, not by reading code. All three
came from the Phase 7 transcription:

| # | Defect | Evidence | Fix |
|---|---|---|---|
| 1 | `OptionsDialog.open`'s entire body (lines 1010–2209) was indented inside the `except Exception:` branch of `if self.win is not None:`. On first open (`self.win is None`) the body was skipped and `open()` returned `None` — the Options window **never opened**. | `app.open_options()` returned `NoneType`, 0 Toplevels | Dedented 8 spaces to match the pre-split `app.py` guard (`ef90f14^`, `open_options` at `app.py:1876`) |
| 2 | Missing imports the split dropped: `startup_entry`, `SRC_LANG_NAMES`, `TO_LANG_NAMES` (module constants in `app.py`, used by `show_basics`). `open_options` raised `NameError`. | `NameError: name 'startup_entry' is not defined`, then `TO_LANG_NAMES` | Added to the `from qtranslate.app import (...)` list |
| 3 | `PopupHost.open` and `OptionsDialog.open` never returned the window — both opened live (Toplevel exists) but callers got `None`. | `popup: WARN exists=False` (wrong probe — the window existed, the return was `None`) | Added `return win` / `return w` |

Live-verified after fix: history/dict/options/popup all open
(`exists=1`). Commit `a542659`.

## 3. Host-specific (skipped off-Windows, not defects)

| Suite | Why it fails on macOS | Handling |
|---|---|---|
| `smoke_dict` | Reads `~/AppData/Roaming/QTranslate/Options.json` (Windows-only path) unconditionally | Skips that section when the file is absent; import/entry-point checks still run |
| `regress_packaging` ("passes as shipped") | Demands `keyboard`/`pyperclip`/`PIL` importable, but `keyboard` crashes on import under macOS Cocoa (`__CFDataValidateRange`), and `-I` hides the user site-packages where PIL/pyperclip live | Skipped unless frozen (`sys.frozen`) or deps present; part B (missing dep turns FAIL, host-independent via fake importer) still runs. 30 assertions. |
| `ui_match` | Reads `C:/Program Files (x86)/QTranslate/.../help.txt` and `C.load()` (live native install) | `SKIP` exit 0 when the native install is absent (Windows-only suite by design; `run_suites` already reports it separately as `(gui)`) |
| `regress_g9_part_a_complete` (2 checks) | (a) "no capture pair exists" went stale when `b60b120` landed `native.png` + `port.png`; (b) "this host is AMD64 Windows" demands `sys.platform == "win32"` | (a) Now pins the pair's **presence**; (b) skipped off-Windows. 19 assertions. |

## 4. What was NOT touched

- `regress_dict_template`'s byte-identity half still requires `pefile`
  (skipped when absent) — unchanged.
- The G9 row stays `UNKNOWN`, the Gate stays `BLOCKED (1)` — none of
  these fixes is fidelity evidence.
- No `docs_consistency` findings (97 files, 0); `coverage_tally --check`
  unchanged (`151 VERIFIED / 1 UNKNOWN`); `gate_artifact_audit` exit 0;
  `audit_ui_spec` 53 assertions OK.

## 5. Reproduce

```
~/.local/bin/python3.11 -I tools/run_suites.py   # 122 suites, 0 failed
```
