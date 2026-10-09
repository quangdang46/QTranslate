# Extension SDK

> Status: **PLANNING / DESIGN.** The public contract for Python extensions
> (decisions D5, D6, D7, D8, D9). Signatures here are design-level and **will be
> frozen before release**; nothing is implemented.

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

**Still genuinely open (implementation detail, not architecture):** the exact
*dependency isolation mechanism* implied by D17 — how an extension's vendored
deps are placed on the import path without colliding with Core's own. This is
solved with the Extension Manager in Phase 3/6, not now.

## 10. What the SDK explicitly is NOT

- Not a way to publish Google/DeepL/etc. *endpoints* as public QTranslate APIs
  (provider keys/terms stay with each provider).
- Not a sandbox. In-process Python extensions run with the app's privileges;
  the manifest is a compatibility gate, **not** a security boundary
  (`PROJECT_VISION.md` §7 honesty rule).
- Not a marketplace. Distribution is folder-copy in v1 (D7, D14).
