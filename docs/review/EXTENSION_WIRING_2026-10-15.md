# Extension wiring + provider integration — Slice 8 (2026-10-15)

> Turns the Slice 7 loader from a tested-but-unused library into the live
> feature the architecture promised: **loaded extensions serve
> translations**, and a declared override actually replaces a built-in in
> the real call path. **No RE row changed**; the RE Gate is still
> `151 VERIFIED / 1 UNKNOWN (G9)`, `BLOCKED (1)`.

## 1. Why this slice exists

A review point flagged the gap precisely: `ExtensionManager` existed, but
`register_provider()` only mutated the manager's private `_providers`
dict. `grep ExtensionManager` across the repo matched only `tests/`.
`app.py:4418` built the window with no extension call, and the engine
dispatches through `registry.TRANSLATORS` / `registry.build_router()` —
neither of which the manager touched. So "load a valid extension" would
have succeeded while the engine kept calling built-ins. Startup wiring
alone would have shipped a green-but-vacuous end-to-end story.

## 2. What landed

- **`ExtensionManager.commit(registry=None)`** — writes the registered set
  into `registry.TRANSLATORS` **in place** (the app's and engine's aliases
  are the same dict object), maps each declared override onto the built-in
  id it replaces, and calls `registry.reset_router()`.
- **`registry.reset_router()`** — drops the cached `ProviderRouter`
  singleton, whose `callables`/`order` were captured at build time; the next
  `build_router()` re-reads the table and appends extension-only names to
  the fallback chain, exactly as `router_order` already does for any
  table-only name.
- **`extensions.load_user_extensions(manager, extensions_dir, registry)`** —
  resolves the D16 folder through `Paths`, loads fail-open, commits when
  anything loaded, and returns the report. tkinter-free.
- **`app.main()`** now calls `load_user_extensions()` once at startup,
  wrapped fail-open; a bad folder or extension cannot block launch.

## 3. The bug the end-to-end pin found (and the fix)

The first run of the e2e pin failed: selecting the overridden built-in
`google` returned a **real Google translation**, not the extension's.
Cause: `registry.build_router()`, when a call passes the J7 phonetics sink
(the engine always does), cloned the singleton and **unconditionally
replaced `google` with `_google_for_call`** — the built-in adapter. Any
extension overriding `google` was silently reverted.

Fix: the clone now wraps google **only when the table's google entry is
still the canonical `_t_google`**:

```python
if callables.get("google") is _t_google:
    callables["google"] = _g   # per-call phonetics sink
```

An overriding extension keeps its callable; it simply supplies no `dt=rm`
romanization (which only the real Google endpoint has). Normal (non-override)
calls are byte-identical: the table's google *is* `_t_google`.

This is the concrete reason the reviewer insisted on an end-to-end pin:
unit-level "load_dir returned ok" could not see this.

## 4. End-to-end evidence

`tests/regress_extension_e2e.py` (17 checks, offline, temp folders only),
mutating the live table on purpose and restoring it:

- a loaded provider `ext.e2e` is committed into `registry.TRANSLATORS`,
  joins `router_order()`, and **`engine.translate("ext.e2e", …)` returns
  the extension's own text with `provider_used == "ext.e2e"`** — also via
  the public `sdk.translate`;
- a declared override replaces the built-in under its id
  (`TRANSLATORS["google"] is TRANSLATORS["ext.goog"]`), **selecting
  `google` calls the extension**, and the overriding callable is not a
  duplicate fallback entry (rule b dedupe);
- a broken override leaves the built-in callable behind its id untouched
  (rule 4);
- `app.main` is wired to `load_user_extensions` (static pin; `main()` is
  not run).

`tests/regress_wiring.py` updated: `extensions` and `platforms` left the
known-unwired set and a positive pin asserts extension loading stays wired.

## 5. Still out of scope

- **Override UI** (D18 winner selection) — conflicts are still only
  reported.
- **True D17 isolation** — unchanged from Slice 7 (import-path mechanism
  only).
- **Packaging** — bundler decision still open; the loader is now callable
  from a bundle's startup, which was the prerequisite.
