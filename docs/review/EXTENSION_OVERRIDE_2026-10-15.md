# Override consistency across aliases + runtime-fallback policy (2026-10-15)

> Makes an override **alias-consistent** and pins the **runtime-fallback
> policy** before any override UI is built. **No RE row changed**; the RE Gate
> is still `151 VERIFIED / 1 UNKNOWN (G9)`, `BLOCKED (1)`.

## 1. Why this slice exists

The Slice 8 review found one real gap and one open policy question.

**F1 — alias divergence.** `registry.TRANSLATORS` holds `"bing"` and
`"microsoft"` as the *same* callable (`_t_bing`), and `router_order()` dedupes
by callable identity (rule (b)). But `commit()` applied a declared override
only to the exact `replaces` id. A probe overriding `microsoft` showed:

```
microsoft is ext: True
bing is microsoft: False      # still the built-in
order microsoft=True bing=True  # both in the fallback chain
active(bing) is ext: True     # manager said the opposite
```

So the manager (`active`), the dispatch table, and `router_order()` disagreed,
and the built-in leaked back as a second fallback entry — exactly what rule (b)
exists to prevent.

**F2 — runtime failure of an override.** The built-in callable is overwritten
in `TRANSLATORS`, so a loaded overriding extension that fails at translate time
has no built-in to fall back to. That is a *semantics* choice, not a bug, so it
was made explicit rather than changed silently.

## 2. What landed

- **F1 — identity propagation in `ExtensionManager.commit()`.** `before =
  dict(table)` is snapshotted; for each `_replaces[base] → winner`, every table
  key whose callable `is` the replaced built-in is updated too (and the
  manager's own `_providers`, so `active()` agrees). Identity, not name: only
  names that truly shared the callable change, so unrelated providers are
  untouched. Works in **both directions** (`microsoft` → `bing` and reverse),
  and is idempotent on a repeated commit.
- **F1 — alias conflicts fail safe.** Two extensions claiming aliases of one
  provider (`replaces="microsoft"` vs `replaces="bing"`) are one claim on one
  implementation. `load_dir()` now resolves this **after** the scan and
  **before** any commit: no override is applied, the built-in stays, and both
  extensions are reported `disabled` with a "pick the winner" reason. The
  outcome does not depend on discovery order. `commit()` carries the same
  guard, so a direct `register()` + `commit()` (no `load_dir`) is protected
  too.
- **F2 — policy recorded, behavior unchanged (PA-B).** A *loaded* override
  that raises or returns an unusable result at translate time falls through the
  normal provider chain (`reliability.FallbackRouter`); the replaced built-in
  is **not** revived, and the failure stays traceable via
  `Result.failures` / `provider_used`. Only a *load-time* failure falls back to
  the built-in (rule 4, unchanged).

## 3. Decisions

| # | Choice | Why |
|---|--------|-----|
| F1 | Propagate by **callable identity**; no canonical alias map | Rule (b) already defines an alias as identity; `router_order()` depends on it. A second mapping would be a duplicate source of truth. |
| F1 | Alias conflict applies **no** override, keeps the built-in | No winner-selection UI yet (D18); discovery order must not pick a winner among two *different* declared claims. |
| F2 | Keep **PA-B** (fall through; do not revive the built-in) | Rule 4 is load-time by design. Reviving silently would hide a broken extension behind the built-in. |

Note: an *identical-id* conflict (`replaces="google"` twice) keeps the
pre-existing D18 behavior — first loaded wins, loser disabled + reported
(pinned by `regress_extension_loading.py`). This slice only changes the
*alias-equivalent* case, which was previously undetected.

## 4. Evidence

`tests/regress_extension_override.py` (37 checks, offline, temp folders +
fake providers only), mutating the live table on purpose and restoring it:

- overriding `microsoft` makes `TRANSLATORS["microsoft"] is
  TRANSLATORS["bing"]`, `active()` agrees for both names, `router_order()`
  keeps `microsoft` and drops `bing`, and `engine.translate("bing", …)` calls
  the extension;
- the reverse override (`bing`) updates `microsoft` too;
- an alias conflict (`microsoft` vs `bing`) disables **both** extensions with
  a reported reason, registers neither provider, keeps the built-in under both
  names, and commits nothing — with the same outcome when the folder order is
  reversed;
- a repeated load does not accumulate registrations and keeps the same
  `router_order()`;
- a **raising** override falls through to the next provider with
  `provider_used == "alt"` and the replaced built-in **not** called;
- an **empty-result** override is reported `malformed-response` and also falls
  through.

An independent probe (direct `register()` + `commit()`) confirms both
directions and the fail-safe conflict with no `load_dir` involved.

## 5. Still out of scope (unchanged)

> **The first item has landed.** The winner-selection UI is
> `qtranslate/override_ui.py`'s `pick_override_winners(root, conflicts)`,
> called from the app's extension menu; the winners go to
> `write_saved_overrides()` (`Options.json` → `ExtensionOverrides`) and are
> read back on the next load. Alias-equivalent claims are merged **by
> callable identity** before the dialog opens, so the user sees one row per
> provider — the "canonical id" this section asked for is the provider's
> own callable identity, which is rule (b)'s definition of an alias.
> Pinned by `tests/regress_override_persistence.py` and
> `tests/regress_packaging.py`.

- **True D17 isolation** — unchanged from Slice 7 (an import-path
  mechanism only).
- **macOS adapters** — the non-Windows adapter still reports every
  platform capability as unavailable (honestly, and by design).
