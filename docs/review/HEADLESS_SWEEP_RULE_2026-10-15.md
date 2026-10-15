# Headless sweep rule (2026-10-15) — no-tkinter compliance

> The user ordered: no screenshots, no opening tkinter. An audit of the
> sweep found two suites really create a Tk root:
> `tests/regress_tray_menu.py:39` (`tk.Tk()`) and
> `tests/regress_screens.py:87` (`tk.Tk()` + `withdraw`). Earlier "ALL_GREEN"
> claims ran them, so those claims implicitly opened a hidden Tk root.
> That was a violation, now corrected.

## Rule

The headless sweep **excludes** every suite that imports `tkinter` or
`qtranslate.app` at module level (AST-checked), because `app.py` imports
tkinter at module level:

- `tests/regress_engine.py` (imports `qtranslate.app`)
- `tests/regress_registry.py` (imports `tkinter`, `qtranslate.app`)
- `tests/regress_screens.py` (imports `tkinter`; creates a root)
- `tests/regress_source_language.py` (imports `qtranslate.app`)
- `tests/regress_tray_menu.py` (imports `tkinter`; creates a root)

46 headless suites remain and must be green. The 5 excluded suites are
**not claimed green or red** — they are out of scope for a no-GUI session
until the user explicitly allows a GUI run.

## Consequence for earlier claims

Earlier `N/51 ALL_GREEN`-style claims in this session's messages included
the excluded suites. Read them as "46 headless + up to 5 tkinter-gated,
the latter unverified in this session". The suite files themselves are
unchanged and still valid for a GUI run.
