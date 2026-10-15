# Override winner persistence + saved-winner veto (D18) (2026-10-15)

> Persists the user's override winner selection and applies it at startup.
> **No RE row changed**; the Gate stays `151 VERIFIED / 1 UNKNOWN (G9)`,
> `BLOCKED (1)`.

## 1. Why this slice exists

The override-consistency slice (F1/F2) made overrides alias-safe and made an
alias conflict fail safe — but it only *reported* conflicts
(`conflicts()`/`active()`); it did not let the user *pick* a winner, and a
picked winner did not survive a restart. D18 ("the user picks the winner")
needs persistence: a selection stored in `Options.json`, applied
deterministically at startup, and cleared when it no longer applies.

## 2. What landed

- **Persistence** (`qtranslate/extensions.py` + `qtranslate/config.py`):
  `read_saved_overrides` / `write_saved_overrides` round-trip the selection
  through a new `Options.json` section `ExtensionOverrides`
  (`{base_id: ext_id}`). Both fail open (no file / bad shape → `{}`).
- **Saved-winner veto** (`ExtensionManager._saved_veto`): a saved winner
  pre-empts discovery-order conflict resolution. Any *other* extension claiming
  the same provider — by the same id **or an alias** (rule (b) callable
  identity) — is disabled with a "saved winner" reason before it reaches
  auto-resolution. The saved winner is never disabled.
- **Startup wiring** (`load_user_extensions`): reads the selection, applies it
  to `load_dir`, and clears a saved winner whose extension is no longer
  installed (the built-in stays; no provider is pinned to a missing folder).
- **Conflict exposure** (`ExtensionManager.override_conflicts`): providers
  claimed by more than one loaded extension, with alias-equivalent claims
  merged into one row — what the UI presents.
- **UI** (`qtranslate/override_ui.py` + `App.show_override_conflicts`): a thin
  tkinter dialog that lists the conflicts and returns the user's choice. The
  dialog opens no window on import; the *policy* lives in `extensions.py` so
  it stays headless-testable.

## 3. Design decisions

| # | Choice | Why |
|---|--------|-----|
| 1 | Key the selection by **canonical `base_id`** (not alias) | The `replaces` field already names a built-in id; the alias group is resolved by callable identity at apply time. |
| 2 | Apply the veto **before** auto-resolution | A post-hoc "re-enable the saved winner" would require undoing the auto-disable; a pre-filter keeps the saved winner from ever being dropped. |
| 3 | Alias-aware veto (callable identity) | Overriding `microsoft` must also veto a `bing` claimant — they are one provider (rule (b)). |
| 4 | Clear a winner whose extension is gone | A saved id that no longer resolves must not pin a provider to a missing folder; fall back to the built-in. |

## 4. Evidence

`tests/regress_override_persistence.py` (21 checks, offline, no window):

- persistence round-trip via the dict path and the file path
  (`config.load`/`save` monkeypatched so the real `Options.json` is untouched);
- alias-aware veto: an alias-equivalent different winner is vetoed, the saved
  winner itself is not;
- `load_dir` with a saved winner: the winner loads, the other claimant is
  vetoed with a reason;
- `override_conflicts` merges alias-equivalent claims into one row;
- `load_user_extensions` applies the saved winner and clears a stale one;
- structural: the dialog opens no window on import and `App.show_override_conflicts`
  is wired.

Headless regress sweep **68/68** by exit code; `coverage_tally --check`
unchanged.

## 5. Still out of scope

- Wiring the dialog into a menu/tray action (a UI-host slice).
- **Packaging**, **true D17 isolation**, **macOS adapters**, **Phase 7** —
  unchanged (see `IMPLEMENTATION_PLAN.md`).
- **G9** — the Gate blocker; uncapturable here (native i386 unrunnable on
  arm64, port capture denied, screenshots banned).
