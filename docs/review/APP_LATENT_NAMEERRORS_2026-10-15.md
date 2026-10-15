# Latent `NameError`s in `app.py` + `tests/` import cleanup (2026-10-15)

> Fixes three latent `NameError`s — each swallowed by a bare
> `except Exception: pass`, so they never crashed the app, they silently
> disabled a feature — and removes dead imports from `tests/`. **No RE row
> changed**; the Gate stays `151 VERIFIED / 1 UNKNOWN (G9)`, `BLOCKED (1)`.

## 1. How these were found

A read-only `pyflakes` pass (via `uv run --with pyflakes`; no repo install)
over `qtranslate/` reported **four** undefined names, all in `app.py`, and
**zero** import redefinitions:

```
qtranslate\app.py:630:20: undefined name '_gp'
qtranslate\app.py:633:20: undefined name '_gp'
qtranslate\app.py:1299:62: undefined name 'e'
qtranslate\app.py:4047:64: undefined name 'src'
```

Every one sat behind a `try/except Exception: pass`, so each was a silent
feature loss rather than a crash — exactly the class of bug the headless
suites cannot see (a windowed suite would exercise the path; a static pin is
the honest headless substitute).

## 2. The three bugs and their fixes

### 2.1 `_gp` read before assignment — ShowTopPane / ShowMiddlePane never hid

`_build_main` read `_gp.get("ShowTopPane"/"ShowMiddlePane")` near line 630,
but `_gp` was assigned ~48 lines later (~677). Because `_gp` is a function
local assigned later in the body, Python binds it as a local for the whole
function, so the early read raised `UnboundLocalError` — swallowed by the
`except`, so the top/middle panes never hid.

**Fix:** moved the `_gp` binding (`from qtranslate import config as _CP` /
`_CP.load().get("General", {})`) above the pane-hiding block.

### 2.2 `except as e` read inside a deferred lambda

```python
except Exception as e:
    self.root.after(0, lambda: self.render(f"[speech error] {e}"))
```

Python 3 deletes `e` at the end of the `except` block; the deferred lambda
referenced it later, raising `NameError` inside the Tk callback.

**Fix:** capture the message eagerly while `e` is bound —
`_speech_err = f"[speech error] {e}"` — and have the lambda close over that.

### 2.3 undefined `src` in the clipboard popup

`start_clipboard_monitor`'s `_poll` discarded the source
(`svc, _, tgt, _ = app.current()`) yet passed `src` to `show_popup`:
`show_popup(..., res.source_language_code or src)`. The other two call sites
(`on_hotkey`, `_translate_text`) bind `src` legitimately from
`app.current()`; `_poll` alone dropped it.

**Fix:** fall back to the request's `"auto"` — consistent with the
`do_translate(..., "auto", ...)` call in the same block. No call site
changed; `src` was never a provider.

## 3. `tests/` import cleanup

Removed ~20 unused imports across 13 suites. Three intentional imports
**kept** — they are the test, not dead weight:

- `regress_registry.py` `import tkinter` / `regress_tray_menu.py`
  `import pystray` — availability probes (the import *is* the check).
- `smoke_dict.py` `import qtranslate.services.promt` — a syntax-regression
  guard.

## 4. Evidence

`tests/regress_app_undefined_names.py` (5 checks, offline) — an AST pin
over `app.py` that asserts:

- `_gp` is stored before it is loaded within `_build_main`;
- no deferred lambda inside an `except … as e` handler references `e`;
- no `show_popup` call passes an unbound `src` — resolving through the whole
  enclosing-scope chain, since a lambda is a closure over the function that
  defines it.

It **fails on the committed `app.py` (4 failures) and passes on the fixed
one** — verified by restoring `HEAD` and re-running (a real fail-before /
pass-after pin, per `TEST_STRATEGY.md` rule 6).

Headless regress sweep **67/67** by exit code; `coverage_tally --check`
unchanged at `151 VERIFIED / 1 UNKNOWN (G9)`, `BLOCKED (1)`.

## 5. Scope

The fixes are in `qtranslate/` (src scope); their regression coverage is in
`tests/` (test scope) — the cross-scope handoff the two-agent split
requires. No RE row changed; the Gate stays `BLOCKED (1)` on G9.
