# Phase 7 — the `App` split, as a transcription with mechanical proof

> Status: **5 of 6 classes landed 2026-10-16; `MainWindow` deliberately not
> started.** No runtime behavior changed — every moved body is proven
> identical, not reviewed as identical.

## 1. Why this needed a discipline, not a go-ahead

Phase 7 asked for `App` split into `MainWindow`, `OptionsDialog`,
`HistoryView`, `DictionaryView`, `TrayController`, `PopupHost`. The
recorded blocker was that this needs a decision ("UI đã settled", no
verification signal under the screenshot ban). The instruction was to
decide it and do it, so the decision was made:

> **Extract the five windows that hang off `App`, as a transcription, with
> a test that proves each body is unchanged. Do not restructure the main
> window itself.**

That is not a hedge. "Move and review" is not available for a 3,400-line
class, and the first attempt proved it.

### The first attempt rewrote the code it claimed to move

`HistoryView` was written by *reading* `open_history_window` and
reproducing it. It diverged in at least four ways:

| What native/port does | What the first attempt did |
|---|---|
| Menu labels come from the locale packs (`_T("Menus", 10, "Open", menu=3)`) | Invented `"Open service page"` |
| All five menu entries carry `state="normal" if _ent else "disabled"` | Dropped — every item stayed clickable with nothing selected |
| `HistoryFilter` is a substring match on the **source** | Searched source **and** translation |
| `_sel_entry()` returns `(idx, entry)` | Returned a scalar, so `_pcopy(_ent[1])` read the wrong thing |

Three assertions went red. **That is the entire risk of a blind split: the
code looks moved, and nothing else notices.** A reviewer skimming a diff
would have seen "HistoryView: new file, 271 lines" and moved on.

## 2. The discipline

Each class is a **transcription** with exactly these permitted edits:

1. `self.` → `self.app.` (the live `App` is reached through a field)
2. one level of indentation (method-in-`App` → method-in-`Class.open`)
3. a `self.win =` alias on the window-creation line, so `open()` can be
   idempotent

`tests/regress_windows.py` (39 assertions) enforces it mechanically. For
every class it asserts:

- every closure the original body defined exists in the extracted class,
  and **no new ones**;
- each moved closure's body is **identical** after applying (1)–(3),
  reporting the first differing line — so a rewrite cannot pass;
- the window's own top-level statements match in count, order and shape,
  excluding only the extraction's scaffolding (docstring, the idempotency
  guard, the `return` a delegator needs);
- `app.py` no longer contains the old body — a leftover copy would
  silently diverge.

### Why the baseline is the split commit's *parent*

The comparison reads `git show <pre-split>:qtranslate/app.py`, resolved by
searching for the split commit's subject and taking `^`. Two naive choices
were both wrong:

- **`HEAD`** stops being the pre-split state the moment the split lands.
  This bit the suite's own first run: it failed with
  `HEAD has 3, windows.py has 25` against a body that had already moved.
- **a fixed `-20` commit window** would have silently *skipped* the checks
  once enough commits accrued — which is worse than failing, because a
  green run would mean nothing.

The same staleness class as the three known-answer vectors this repo
already hit: a check that quietly compares against the wrong thing.

### Why the window variable stays `w`

`DictionaryView` and `OptionsDialog` both use the literal `"w"` as a
**file mode** — a dozen `open(path, "w")` calls — plus `anchor="w"`. A
regex that renames `w` has to be taught to skip those, and a rename
capable of corrupting a file write is not worth the tidiness. So `w`
stays, and `tests/regress_windows.py` pins that the ≥10 `"w"` literals
survived — the check that would catch the day someone "cleans up" the
alias into a rename.

## 3. What landed

| Class | Source | Statements | Substitutions |
|---|---|---|---|
| `HistoryView` | `App.open_history_window` | ~132 (10 closures) | `self.`→`self.app.`, `w`→`self.win` |
| `DictionaryView` | `App.open_dict_window` | 249 (5 closures) | `self.`→`self.app.` only; `w` kept |
| `TrayController` | `_make_tray` (plain function) | 126 (8 closures) | **none**; a `self.icon` alias |
| `PopupHost` | `show_popup` (plain function) | 122 (2 closures) | **none** |
| `OptionsDialog` | `App.open_options` | 1,056 (9 pages) | `self.`→`self.app.`; `w` kept |

`qtranslate/windows.py`: 2,209 lines. `qtranslate/app.py`: 4,868 → 3,083.
`class App`: ~3,400 → 1,789 lines / 62 methods.

`app.py` keeps a delegator for each with the original signature, so every
existing suite still exercises the same behavior through the same entry
point — which is why the extraction could be done at all without a GUI
session.

### Structural pins that had to follow the code

Nine suites read `app.py`'s source or `inspect.getsource` directly. Each
going red was the correct signal, and each fix followed the same shape:
search **both** modules, and additionally assert the wiring is now in
`windows.py` — so a pin cannot silently stop covering the thing it exists
to cover.

| Suite | What it pins |
|---|---|
| `regress_windows` | the byte-identity comparison itself |
| `regress_ui_parity_fixes` | the I6 five-entry history menu; the per-key `_defs` language defaults |
| `regress_dict_lang` | `go_all` reads `LanguageDictionary` |
| `regress_exact_search` | `DictionaryExactSearch` is threaded into `xdxf.lookup` |
| `regress_packaging` | `_sync_icon` routes through `tray_state.select_state` |
| `regress_tray_menu` | the native tray menu order; the handler writes `EnableHotKeys` |
| `regress_popup_smoke` | `PopupAutoPos`/timeout/transparency/placement defaults |
| `regress_proxy_options` | the four proxy labels in native order |
| `ui_match` | `_PAGES` — the nine Options pages, ids 10–18 |

Two of these were verified by re-breaking the code: reverting the
`tray_state` fix makes `regress_packaging` fail, and breaking
`DictionaryExactSearch` in `windows.py` makes `regress_exact_search` fail.
A pin that cannot go red is noise.

### A bug fixed in the suite itself

`regress_windows`' "creates no window at import" check was a text search
for `"tk.Tk("` against a slice of the docstring split — which happened to
miss a comment containing `tk.Tk()` **by luck, not by correctness**. It
went false-positive on `PopupHost`. Replaced with an AST walk that only
flags a `Tk()` call sitting outside every `FunctionDef`, so a comment or a
string cannot fool it.

## 4. What did *not* land, and why it is not a small remainder

`MainWindow` — the 6th class — is deliberately not started.

It is not a window hanging off the app. It *is* the app: the source/result
panes, translation orchestration, hotkey routing, the clipboard monitor,
and the nav menu, cross-referenced far more tightly than the five
extracted windows were (which is why those took one mechanical
substitution each). Cutting it out is a restructure of the code the UI is
built **from**, not from windows that hang off it.

Second, with the screenshot ban there is no fidelity signal to verify a
restructure by — so the honest position is "recorded", not "claimed".

Recorded in `IMPLEMENTATION_PLAN.md` Phase 7 rather than left implicit.

## 5. Verification

```
122 suites, 0 failed                    # 120 regress + ui_match + smoke_dict
ui_match: 103 passed, 0 failed
tools/gate_artifact_audit.py            # 147/147
tools/docs_consistency.py               # 93 files, 0 findings
tools/audit_ui_spec.py                  # 48 assertions
tools/coverage_tally.py                 # gate=BLOCKED (1) -- unchanged
tools/build_bundle.py                   # frozen exe SELFTEST PASS 18/18
```

The bundle rebuild matters: `windows.py` is a **new** module, and
`tools/build_bundle.py`'s `_frozen_gap()` check would have failed the build
if PyInstaller's Analysis could not reach it. It can (verified: gap is
empty), because `app.py` imports it at each delegator.

## 6. What to check in review

1. **The byte-identity claims.** `python -I tests/regress_windows.py` — 39
   assertions, each class compared against the pre-split commit. If any
   body is not identical, this suite is wrong, not the extraction.
2. **The nine pins that moved.** Each now reads both modules; confirm the
   added "and it's in windows.py" assertion is not vacuous.
3. **That `MainWindow`'s absence is a decision, not an omission** — Phase 7
   in `IMPLEMENTATION_PLAN.md`.
