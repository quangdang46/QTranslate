# Extension loading — Slice 7 (2026-10-15)

> Records the slice that closed the scoped-out gap named in
> `CORE_EXTENSIONS_SLICES_1_5_2026-10-15.md` §7 and Phases 3/6 of
> `IMPLEMENTATION_PLAN.md`: **extension-directory discovery, manifest
> validation, and fail-open loading**. Design source of truth is
> `EXTENSION_SDK.md` §3/§4/§6/§7. **No RE row changed** and this work does
> **not** open the RE Gate (still `151 VERIFIED / 1 UNKNOWN (G9)`,
> `BLOCKED (1)`).

## 1. What landed

All in `qtranslate/extensions.py` (tkinter-free, never imports `app`):

| Symbol | Role |
|--------|------|
| `SDK_VERSION` / `SDK_MAJOR` | Host contract version; only the major must match a manifest's `sdk_version`. |
| `KNOWN_CAPABILITIES` | The §2 kinds; an unknown kind is rejected. |
| `ManifestError` | Raised by validation; the loader turns it into a disabled extension. |
| `validate(data)` | Minimum §4 schema + the Phase-3 matrix. |
| `read_manifest(folder)` | Reads + validates `folder/manifest.json`. |
| `discover(extensions_dir)` | Manifest-bearing folders, sorted; missing dir → `[]`. |
| `import_entrypoint(folder, manifest)` | Imports `module:callable`, folding the folder onto `sys.path` for the import only (D17 mechanism, not isolation). |
| `ExtensionAPI` | Provisional host API handed to `entrypoint.register`: `register_provider(name, fn, replaces=…)`. |
| `ExtensionManager.load_dir(dir)` | Discover → validate → import → register, fail-open with rollback. |

`qtranslate/platforms.py`: `WindowsAdapter.app_data()` and
`WindowsAdapter.extensions_dir()` resolve the D16 per-user folder
(`%APPDATA%/QTranslate/extensions`); `UnavailableAdapter` still reports
`unavailable` and raises on use (honest, not faked).

## 2. Validation rules (the Phase-3 matrix)

`TEST_STRATEGY.md` §3 asks for missing/short/bad `sdk_version`, broken
entrypoint, and unimportable module. Each is pinned:

| Case | Rule |
|------|------|
| missing field | any of `id`/`name`/`version`/`sdk_version`/`entrypoint`/`capabilities` absent → error |
| short `sdk_version` | `""` → no numeric major → error |
| bad `sdk_version` | non-string or `"abc"` → error |
| wrong major | `"2.0"` vs host `1.0` → error; `"1.7"` is compatible |
| broken `entrypoint` | not exactly one `:`; empty module or callable → error |
| bad `capabilities` | empty, or an unknown kind → error |
| bad `replaces` | non-list, or a non-string / empty id → error |
| unimportable module | import raises → extension disabled, app continues |
| broken callable | entrypoint has no such callable / not callable → disabled |

## 3. Fail-open + rollback (rules 3 and 4)

`load_dir` snapshots the registry before loading each extension and restores
it if anything raises. Consequences pinned by the suite:

- a half-applied override never wins — the built-in stays active
  (rule 4);
- an override conflict raises `OverrideConflict`, so the **second**
  extension is disabled and its provider is **not** registered, with the
  reason `"… pick the winner"` (D18) surfaced in the outcome and in
  `conflicts()`;
- a rolled-back override is **not** left in `conflicts()`.

Outcome shape per discovered folder:
`{"path", "id", "status": "loaded"|"disabled", "reason"}`.

## 4. What is deliberately NOT here

> **The first item has since landed** (`qtranslate/override_ui.py`, wired
> from the app's extension menu, with the winner persisted in
> `Options.json` → `ExtensionOverrides`; see
> `EXTENSION_OVERRIDE_2026-10-15.md` and
> `EXTENSION_WIRING_2026-10-15.md` §5). This slice only *reported* the
> conflict, as it says below.

- **Override UI** — who picks the D18 winner is a UI slice; this slice only
  *reports* the conflict (`conflicts()` + the disabled reason).
- **True D17 isolation** — `import_entrypoint` puts the extension folder on
  `sys.path` for the duration of the import, so a vendored dep inside the
  folder is importable. Two extensions (or an extension and Core) can still
  collide; subprocess isolation remains designed-for.
- **Startup wiring** — landed in the next slice (Slice 8,
  `EXTENSION_WIRING_2026-10-15.md`): `app.main` now calls
  `load_user_extensions()`, which loads and **commits** the winners into
  `registry.TRANSLATORS`. Kept out of Slice 7 so it stayed headless and
  import-only.
- **Register API freeze** — `ExtensionAPI.register_provider` is the MVP
  shape; `EXTENSION_SDK.md` §5/§9 says signatures freeze before release.

## 5. Verification

- New suite: `tests/regress_extension_loading.py` — **39 checks, 0 failed**
  (offline, temp folders only, no window, no network).
- Existing pins unaffected: `regress_extensions` 12/12,
  `regress_platforms` 15/15.
- Headless regress sweep: **64/64 suites PASS** by exit code (the two
  window-opening suites excluded; the count grew by one — this suite).
- `tools/coverage_tally.py --check`: `151 VERIFIED / 1 UNKNOWN (G9)`,
  `gate=BLOCKED (1 unresolved)` — unchanged.

> **Follow-up (Slice 8, same day):** startup wiring + provider integration
> landed — see `EXTENSION_WIRING_2026-10-15.md`. That slice took the
> headless sweep to **65/65** and fixed a real bug the end-to-end pin found
> (an override of `google` was silently reverted by the router's
> phonetics clone).
