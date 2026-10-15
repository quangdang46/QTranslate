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

## Sweep detection must use the exit code, not a text grep

A grep for "FAIL"/"failed" both **misses** suites that print `FAIL 4/25`
(no colon — `regress_google_romanization`, `regress_source_language`,
`regress_wiring` all used that form) and **false-positives** on suites
whose log contains the word (e.g. `regress_player` prints "online TTS
failed" on its deliberate fallback path). The reliable check is the
process exit code: every suite `raise SystemExit(1)` / `sys.exit(1)` on
failure and 0 on success.

Found 2026-10-15: three suites were failing (`regress_google_romanization`
4/25, `regress_source_language` 5/17, `regress_wiring` 4/7) and a
text-grep sweep had reported ALL_GREEN. All three were stale assertions
pointing at `app.py` after Slice 2 moved the orchestration to
`engine.py`; fixed to read the engine body.

## Correction (same day)

An earlier version of this note excluded 5 suites by "imports tkinter or
app" — too broad. Importing a module is not opening a window; the grep
for an actual `Tk()` call leaves 3 suites. Re-verified 2026-10-15.
