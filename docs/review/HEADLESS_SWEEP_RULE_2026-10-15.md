# Headless sweep rule (2026-10-15) — no-tkinter compliance

> The user ordered: no screenshots, no opening tkinter. An audit of the
> sweep found two suites really create a Tk root:
> `tests/regress_tray_menu.py:39` (`tk.Tk()`) and
> `tests/regress_screens.py:87` (`tk.Tk()` + `withdraw`). Earlier "ALL_GREEN"
> claims ran them, so those claims implicitly opened a hidden Tk root.
> That was a violation, now corrected.

## Rule

The order is "don't **open** tkinter" (create a window), not "don't
import it". Importing `tkinter` — or `qtranslate.app`, which imports it
at module level — does not create a window. Only a `tk.Tk()` /
`mainloop()` call does.

The headless sweep **excludes** exactly the suites that create a window:

- `tests/regress_screens.py` (`tk.Tk()` + `withdraw`)
- `tests/regress_tray_menu.py` (`tk.Tk()`)
- `tests/ui_match.py` (`tk.Tk()`)

Every other `regress_*` suite is headless (import-only), including those
that import `qtranslate.app` (`regress_engine`, `regress_registry`,
`regress_source_language`, …) — they construct no root. The 3 excluded
suites are **not claimed green or red** — out of scope for a no-GUI
session until the user allows a GUI run.

## Correction (same day)

An earlier version of this note excluded 5 suites by "imports tkinter or
app" — too broad. Importing a module is not opening a window; the grep
for an actual `Tk()` call leaves 3 suites. Re-verified 2026-10-15.
