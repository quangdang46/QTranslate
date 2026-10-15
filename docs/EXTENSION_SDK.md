# Extension SDK

> Status: **PARTIALLY LANDED (2026-10-15).** The built-in
> manager (`qtranslate/extensions.py`) and the public SDK surface
> (`qtranslate/sdk.py`: `translate`/`detect`/`speak`/`dict_lookup`/`Result`)
> landed at `7b8ea7a`. **Extension-directory discovery, manifest validation
> and fail-open loading landed next** (`ExtensionManager.load_dir`,
> `validate`/`read_manifest`/`discover`, plus `Paths.extensions_dir` on the
> Windows adapter). Startup wiring landed too (`app.main` calls
> `load_user_extensions()`), and `commit()` now makes an override **alias-
> consistent** (overriding `microsoft` updates `bing` and vice versa) and
> fails safe on an alias conflict. Still designed-for only: the override
> **UI** (who picks the D18 winner), vendored-dependency **isolation** (D17 is
> implemented as an import-path mechanism, not true isolation), and
> packaging. See `docs/review/CORE_EXTENSIONS_SLICES_1_5_2026-10-15.md`,
> `docs/review/EXTENSION_LOADING_2026-10-15.md`, and
> `docs/review/EXTENSION_OVERRIDE_2026-10-15.md`. Signatures here
> are design-level and **will be frozen before release**.

## 1. Concepts (do not conflate)

| Term | Meaning |
|------|---------|
| **SDK** (`qtranslate-sdk`) | The pip-installable package developers import. Ships contracts + a test harness. |
| **Extension** | A specific extension (a folder) a user installs. |
| **Extensions folder** | Where QTranslate looks for installed extensions. |
| **Built-in** | Extensions/features compiled into the shipped app. |
| **Core** (`qtranslate-core`) | The runtime the desktop app uses (engine, registry, config, storage, extension manager). |

The SDK and the extensions folder are not the same thing. The SDK is the tool;
the folder is where tools' output lives.

## 2. What an extension can be

An extension is a folder with a `manifest.json` and Python code. It may register
**one or more** of these capability kinds:

- **Provider** — a translation/detect backend.
- **Workflow** — code that composes providers (e.g. translate → post-process,
  or custom fallback order). *Code, not a UI.*
- **Theme** — colors, fonts, style values.
- **UI** — a panel / widget / menu / popup added through published slots.
- **Dictionary / TTS / OCR / Spell** — additional capability plugins.

An extension only imports the API groups it uses.

## 3. Folder layout

```
<extensions_dir>/
└── my_custom_workflow/
    ├── manifest.json         # required
    ├── __init__.py           # required entrypoint module
    ├── provider.py
    ├── workflow.py
    ├── ui.py
    └── theme.py
```

`<extensions_dir>` is resolved per OS by the `Paths` adapter
(`ARCHITECTURE.md` §4) to the **per-user app-data directory** (decision D16):
e.g. `%APPDATA%/QTranslate/extensions` on Windows,
`~/Library/Application Support/QTranslate/extensions` on macOS. Extensions are
**never** auto-loaded from the install directory. This avoids admin rights and
prevents losing extensions when the app updates.

## 4. Manifest schema (minimum)

| Field | Purpose |
|-------|---------|
| `id` | Stable extension id, e.g. `ext.acme.custom_google`. Never a number. |
| `name`, `version` | Display name + semver. |
| `sdk_version` | Required SDK contract version (compatibility gate). |
| `entrypoint` | Module + callable, e.g. `__init__:register`. |
| `capabilities` | List: `provider`, `workflow`, `theme`, `ui`, … |
| `replaces` | Optional explicit list of built-in ids this extension overrides. |
| `settings_schema` | Declarative settings for the Options UI. |
| `platforms` | `["windows","macos"]` — which the extension claims. |

Validation on load: manifest parses → `sdk_version` compatible → `entrypoint`
importable → registrations well-formed → override conflicts resolved. Any
failure = **extension disabled, app continues** (§7).

> **Landed (2026-10-15):** `extensions.validate()` enforces this gate —
> `sdk_version` must be a string whose **major** matches `SDK_VERSION`
> (`1.x`); `entrypoint` must be `module:callable`; `capabilities` must be a
> non-empty list of known kinds; `replaces` (if present) a list of ids. A
> manifest that fails raises `ManifestError`, which the loader turns into a
> disabled extension. Pinned by `tests/regress_extension_loading.py`.

## 5. Provider contract (illustrative, not final)

```python
from qtranslate_sdk import TranslationProvider, TranslationRequest, TranslationResult

class MyGoogle(TranslationProvider):
    id = "provider.my_google"
    capabilities = {"translate", "detect"}
    languages = ["en", "vi", "ja", ...]

    def translate(self, req: TranslationRequest) -> TranslationResult: ...
    def detect(self, text: str) -> str | None: ...
```

Design constraints:

- **Capability-scoped**, not one giant interface. OCR is not a translation
  provider.
- **Async-capable** so a future out-of-process provider fits
  (`ARCHITECTURE.md` §7). v1 may accept a sync wrapper Core runs off the UI
  thread.
- **Provider stays dumb:** no retry/fallback logic inside the provider — that
  is Core (`RELIABILITY.md`). The provider either returns a result or raises a
  classified error.
- Providers may reuse `common.py` (`RequestData`/`ResponseData`) internally, but
  that is an implementation detail, not the SDK contract.

## 6. Override rules (decision D8 = level C)

| Mode | Meaning | MVP |
|------|---------|-----|
| **Extend** | Add a provider/panel/theme without replacing anything. | yes |
| **Override (declared)** | Replace a *specific* built-in id; declared in `replaces`, enabled by the user. | yes |
| **Replace (deep)** | Replace the whole main UI. | designed-for, not required |

> **Landed 2026-10-15 (Slice 9a):** the **theme** capability is live.
> `ExtensionAPI.register_theme(name, record, replaces=None)` registers a
> theme-colour record in the same shape `theme.load_theme_at` returns (any
> subset of sections/slots -- `theme.slot()` reports `UNSET` for the rest,
> so a partial record inherits slot-by-slot exactly like a partial native
> theme file). A non-dict record raises `TypeError` (fail-open); a second
> claimant on the same built-in theme id raises `OverrideConflict` (D18).
> Resolution is `ExtensionManager.active_theme(name)`: extension name,
> then declared override, then built-in `theme.active_theme` (which never
> returns `None`). Pinned by `tests/regress_extension_theme.py`
> (14 assertions).

Rules:

1. Built-in is the default when no override exists.
2. Override must be **explicit and user-enabled** — never implicit by folder
   name or load order.
3. Conflict (two extensions `replaces` the same id) is **reported to the user,
   who picks the winner** (decision D18). Never auto-resolved by scan order,
   load order, or id. The losing extension is disabled with an explanation,
   not silently dropped. If the chosen winner later fails to load, fall back to
   the built-in (rule 4).
4. If an overriding extension **fails to load**, fall back to the built-in and
   log. Never leave the user with nothing.
5. Core logs which provider/component is active and whether it overrides.
6. **Aliases are one provider.** `bing` and `microsoft` are the *same* callable
   (`registry.TRANSLATORS`), so an override of either updates both, in both
   directions — the table, `router_order()` and `ExtensionManager.active()`
   never disagree.
7. An **alias conflict** — two extensions claiming aliases of one provider
   (`replaces="microsoft"` and `replaces="bing"`) — is rule 3 with no winner
   chosen yet: **no** override is applied, the built-in stays, and both
   extensions are disabled with an explanation. Discovery order never decides
   the winner.
8. A **runtime** failure is not a load failure (rule 4): a *loaded* override
   that raises or returns an unusable result at translate time falls through
   the normal provider chain (`RELIABILITY.md`) to the next provider. The
   replaced built-in is **not** revived, and the failure is reported through
   `Result.failures`/`provider_used`, never hidden.

## 7. Fail-open loading (mandatory)

Startup sequence:

```
scan extensions_dir
  └─ for each: validate manifest → import → run entrypoint.register(sdk)
       ├─ ok      → apply registrations (respecting overrides)
       └─ any error → log + disable THIS extension; continue startup
```

An extension that crashes on import or raises during `register` must not take
down the app. This is the counterpart to "one process" (`ARCHITECTURE.md` §7):
since there is no isolation, at least startup must be resilient.

> **Landed (2026-10-15):** `ExtensionManager.load_dir(dir)` runs exactly this
> sequence. It snapshots the registry before each extension and **rolls the
> extension's registrations back** on any failure, so a half-applied override
> never wins and the built-in stays active (rule 4). One bad extension is
> reported as `{"status": "disabled", "reason": …}`; the rest still load.
> Note: `extensions_dir` is now resolved by the `Paths` adapter
> (`WindowsAdapter.extensions_dir` → `%APPDATA%/QTranslate/extensions`).
> `app.main` now calls `load_user_extensions()`, which loads and commits the
> winners into `registry.TRANSLATORS` (resetting the cached router) so an
> extension provider actually serves translations — see
> `docs/review/EXTENSION_WIRING_2026-10-15.md`.
>
> **Override consistency (rules 6–8, 2026-10-15):** alias conflicts are
> resolved *after* the scan and *before* any commit, so no winner is picked
> from load order; `commit()` propagates an override across every name that
> shared the replaced callable; and a runtime failure of a loaded override
> falls through the provider chain without reviving the replaced built-in.
> Pinned by `tests/regress_extension_override.py` — see
> `docs/review/EXTENSION_OVERRIDE_2026-10-15.md`.

## 8. UI extension points (MVP = level B, decision D9)

Published slots a UI extension may target:

- **Theme tokens** — override color/font/style values (per-state).
- **Panel** — add a dockable panel to the main window.
- **Menu item** — add an entry to an existing menu / context menu.
- **Popup** — register an alternative result popup renderer.
- **(designed-for, not MVP)** — replace the main window entirely.

UI extensions talk to Core only through the host API and events — never by
reaching into `app.py` internals. This is exactly the coupling the audit found
today (`CURRENT_STATE.md` §3) and must not be reproduced in the new boundary.

## 9. Decisions on the previously-open points

All five were resolved and folded into `PROJECT_VISION.md`:

| # | Was | Resolved as |
|---|-----|-------------|
| 1 | Extensions folder location | **D16** — per-user app-data dir; never load from install dir. |
| 2 | Dependency management | **D17** — app bundles the runtime; an extension vendors deps inside its own folder; no auto pip/download at startup. |
| 3 | Override conflict rule | **D18** — user picks the winner; never auto-resolved by scan/load order or id. |
| 4 | SDK package name | **D19** — `qtranslate-sdk` is provisional; verify PyPI name + rights before any release. |
| 5 | Workflow code vs declarative | **D20** — Python code-only in MVP; no second format. |

> **Landed 2026-10-15 (Slice 9b): vendored-dep import hygiene.**
> `import_entrypoint` still puts the folder on `sys.path` only for the
> import itself, AND now rolls `sys.modules` back afterwards: plain-named
> vendored modules that were not imported before are dropped (they cannot
> shadow Core or a later extension), while a vendored dep that overwrote a
> name Core already owns is restored to Core's original object — the
> extension keeps the copy it bound at import time. The overwrite is
> **reported** in `extensions._LAST_VENDOR_SHADOWS` as
> `(extension_id, [module, ...])`, never auto-resolved. This is not a
> sandbox (in-process extensions still share the interpreter), but the two
> poisoning shapes — cross-extension and Core-shadow — are now closed and
> reported. Pinned by `tests/regress_extension_vendor.py` (10 assertions).

> **Register API is provisional.** `entrypoint` is `module:callable`, and the
> callable receives a host API (`extensions.ExtensionAPI`) with
> `register_provider(name, fn, replaces=None)`. The SDK signature is not frozen
> (`EXTENSION_SDK.md` §5/§9), so treat this as the MVP shape, not the contract.

## 10. What the SDK explicitly is NOT

- Not a way to publish Google/DeepL/etc. *endpoints* as public QTranslate APIs
  (provider keys/terms stay with each provider).
- Not a sandbox. In-process Python extensions run with the app's privileges;
  the manifest is a compatibility gate, **not** a security boundary
  (`PROJECT_VISION.md` §7 honesty rule).
- Not a marketplace. Distribution is folder-copy in v1 (D7, D14).
