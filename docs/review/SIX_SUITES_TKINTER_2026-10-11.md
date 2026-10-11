# Six suites are red on this host for one reason, and it is not the code

> Read-only. Running all 22 `tests/regress_*.py` suites on this machine gives
> **16 pass / 6 fail**, and every one of the six failures has the same single
> cause: `qtranslate/app.py:30` does `import tkinter as tk`, and this host's
> Python cannot load `_tkinter`.
>
> This is recorded because a red suite is read as "the port is broken", and
> all six are telling us something about the *environment* instead. The
> honest statement is that those six are **not runnable here**, not that
> they fail.
>
> **Corrected while writing this document, because the first two numbers I
> got were both wrong.** My first run reported `16/6` including
> `regress_plugin_js_recovered.py` among the failures; a later run reported
> `15/7`. Neither was a measurement of the code. The peer was editing that
> suite and `dictionary.py` at the same time, and I was sampling a moving
> target: across four runs in ten minutes the same suite reported
> `FAIL 2/97`, `FAIL 1/121`, `FAIL 1/118`, then `all checks ok (118)` — and
> the *text of the failing assertion* changed between reads. I chased three
> of those failures into `dictionary.py` and each time found the port
> correct and the assertion mid-edit. The stable numbers are below, taken
> after the edits settled. Running another session's uncommitted work as
> though it were the baseline measures their keystrokes.

## 1. The measurement

```
$ for t in tests/regress_*.py; do python3 "$t" >/dev/null 2>&1 || echo "$t rc=$?"; done
regress_dict_args.py          rc=1
regress_enable_history.py     rc=1
regress_exact_search.py       rc=1
regress_provider_auto.py      rc=1
regress_reliability.py        rc=1
regress_translate_errors.py   rc=1
```

All six reach `app.py` and die at the same import. Two of them fail *inside*
a `try` that turns the import error into an assertion, so they report it as
a check rather than a traceback:

| suite | how it reports |
|---|---|
| `regress_dict_args.py` | `FAIL: app import for call-site check -- ModuleNotFoundError("No module named '_tkinter'")` |
| `regress_exact_search.py` | same shape — the `except Exception as e:` at `:84` converts it to a failed check |
| `regress_enable_history.py` | traceback at import |
| `regress_provider_auto.py` | traceback at import |
| `regress_reliability.py` | traceback at import |
| `regress_translate_errors.py` | traceback at import |

The environment facts, on this host:

```
python                3.14.6 (Homebrew, the only Python present)
_tkinter              No module named '_tkinter'
/Library/Frameworks/Tcl.framework
                      does not exist
```

Homebrew's `python@3.14` keg is built without Tk unless `python-tk` is
installed, and there is exactly one Python on this machine, so there is no
alternate interpreter to fall back to. `brew list | grep python-tk` is
empty.

## 2. Why this is the same class as G9 part (b)

`G9_RESULT_2026-10-09.md` records the native side of G9 as blocked because
the native binary is i386 and this host is arm64. This is the same shape one
layer up: the *port's GUI layer* cannot be exercised here because the GUI
toolkit cannot be imported here. G9's part (b) needs a Windows host; these
six suites need a Python with `_tkinter`.

**Neither is an RE gap and neither is a code defect.** Both are "the
artefact this check needs is not obtainable on this host", which is the
distinction the project's vocabulary already has and which I did not apply
the first time I saw the red.

## 3. What would unblock it, in order of least invasive

1. **A Python built with Tk.** `brew install python-tk@3.14` provides
   `_tkinter` for the keg. Unverified here — I am not installing it, since
   adding a system package is the user's call, not mine.
2. **A stubbed `tkinter` in the harness.** Importing a fake module before
   `app` would let the non-GUI assertions in these suites run. It is worth
   knowing that `apps.regress_exact_search.py:84`'s `except Exception`
   already *looks* like graceful degradation, so a stub would silently turn
   a skipped check into a passed one unless the stub is detected and the
   check is marked skipped. That is a trap, not a fix.

## 4. What is green

The other **16** suites pass, including the one carrying the most recent
consequential work:

- `regress_plugin_js_recovered.py` — **118/118**, the suite that pins the
  recovered `Service.js` files, `Common.js`, the framework's
  `codeFromLanguage`/`isLanguage` semantics, and every URI builder against
  real native source.
- `regress_dict_args.py` — its own argument-shape assertions agree with the
  peer's URI-builder fix; it fails only on the `app` import. Independently
  spot-checked against the recovered JS: `lingvo_build_uri('hello',17,46)`
  → `/en-us/translate/en-ru/hello`, `reverso_build_uri` → `/english-russian/hello`,
  `gsearch_build_uri('hello',46)` → `/search?q=hello&ie=UTF-8&hl=ru`. All three
  match the recovered `buildUri` bodies exactly, `langToUiLang`'s `en-us`
  default included.

## 5. Reproduce

```sh
python3 -c "import _tkinter" 2>&1 | tail -1     # No module named '_tkinter'
for t in tests/regress_*.py; do
  python3 "$t" >/dev/null 2>&1 || echo "$t"
done
```

Six names print, and `python3 -c "import _tkinter"` explains all of them.
