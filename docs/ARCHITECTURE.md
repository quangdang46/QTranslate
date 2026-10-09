# Architecture

> Status: **PLANNING.** Target architecture for the Core/Extension redesign
> (decision D13: design Core first, then migrate). No code yet. Line anchors
> into the current code are provided as evidence, not as the shape we keep.

## 1. Why the current structure can't host extensions

The audit of `qtranslate/app.py` (~4017 lines) shows the exact problem D13 is
meant to solve:

- **One class owns everything.** `class App` (`app.py:581-3335`) holds the main
  window, the popup host, Options (a single `open_options` method of ~1073
  lines, `app.py:1742-2815`), History, Dictionary, OCR, the virtual keyboard,
  and tray wiring.
- **Orchestration is interleaved with widgets.** `on_hotkey` (`app.py:3337`)
  reads Tk widget state via `app.current()`, calls `do_translate`, then writes
  back into `app.src` / `render` / `push_hist` — all in one function.
- **Dispatch is a hardcoded dict, not a registry.**
  `TRANSLATORS` (`app.py:221`) and `DICTS` (`app.py:234`) map fixed string keys
  to fixed adapter functions; `services/__init__.py` has a *separate, smaller*
  `REGISTRY` (only 5 of the 12 providers), so "the registry" is not the single
  source of truth.
- **Detection is a hardcoded tuple**, `app.py:496-503` — a provider that
  supports detect cannot be added without editing Core.

You cannot bolt a plugin system onto this by moving files. The boundary has to
be designed, then features migrate behind it.

## 2. Target layering

```
┌──────────────────────────────────────────────────────────┐
│ UI host (Tkinter)          presentation only              │
│   main window · popup · Options · History · Dictionary     │
│   extension UI slots (panel/widget/menu/popup)             │
├──────────────────────────────────────────────────────────┤
│ Core                                                      │
│   TranslationEngine   orchestration + reliability         │
│   Registry            providers/capabilities (single)     │
│   Config              Options.json R/W + schema           │
│   Storage             history, sessions, placements       │
│   Events              dispatch to subscribers             │
│   ExtensionManager    discovery · load · override · life  │
├──────────────────────────────────────────────────────────┤
│ Platform interfaces (implemented by adapters)             │
│   Clipboard · Hotkey · Capture · Audio · Window · Paths   │
├──────────────────────────────────────────────────────────┤
│ Adapters:  windows/            macos/                     │
│            (built-in)           (built-in)                │
├──────────────────────────────────────────────────────────┤
│ Built-in features (packaged in the build)                 │
│   providers: google, bing, deepl, yandex, baidu, naver…   │
│   dictionaries, TTS, OCR, spell, layout-convert           │
├──────────────────────────────────────────────────────────┤
│ User extensions (physical folder, external to build)      │
│   provider / workflow / theme / ui — loaded at startup     │
└──────────────────────────────────────────────────────────┘
```

**Dependency rule (enforced by tests):** arrows point *down only*. Core never
imports `tkinter`, `win32*`, `winreg`, `comtypes`, or a concrete provider.
Providers never import UI. Extensions import only the SDK.

## 3. Core components

### 3.1 TranslationEngine (decision D11, D12)
Owns the flow that today lives in `do_translate` (`app.py:537`) plus the
reliability policy from `RELIABILITY.md`. API shape (design-level):

```
engine.translate(request) -> Result
   ├─ resolve provider (explicit or ServicesOrder)
   ├─ provider.translate(request)     # dumb provider
   ├─ on failure → classify → retry/fallback (RELIABILITY.md)
   └─ Result(provider_used, text, detected_lang, meta)
```

The engine — not the UI — reads detect/back-translation flags, applies
`ServicesOrder`, and records history. `do_translate`'s current signature
`(service, text, target, source, detect, backtranslate)` becomes a
`TranslationRequest` value object so the fallback guarantee "preserve the
request across providers" is structural, not convention.

### 3.2 Registry (single source of truth)
Replaces the three current sources (`TRANSLATORS` `app.py:221`, `DICTS`
`app.py:234`, `services/REGISTRY`). One registry keyed by **stable string id**
(`provider.google`, `dict.urban`), with capability flags and search by
capability + language pair. Built-in and extension providers register into the
same registry through the same call.

### 3.3 Config
`config.py` already reads all 20 `Options.json` sections (`config.py:1-160`).
Core keeps the loader; the *schema* moves so extensions can declare their own
settings section. The numeric QTranslate service ids (`config.py:18`) become a
**compatibility mapping**, not internal identity (see §6).

### 3.4 Storage
History (`history.py`), session cookies (`session.py`), window placements
(`app.py:264-346`) become a Core storage API so a custom UI can persist
without reimplementing them.

### 3.5 Events
A minimal pub/sub so UI and extensions react to `translation.done`,
`provider.failed`, `history.saved` without Core calling into UI directly.

### 3.6 ExtensionManager
Discovery, manifest validation, load, override resolution (conflicts resolved
by the **user**, D18), fail-open (broken extension skipped, app continues).
Loaded from the per-user app-data extensions dir (D16). Detailed in
`EXTENSION_SDK.md`.

## 4. Platform interfaces

Extracted from the concrete Windows couplings found in the audit:

| Interface | Today (Windows-only evidence) | macOS plan |
|-----------|-------------------------------|------------|
| `Clipboard` | `pyperclip` + `ctypes …GetClipboardSequenceNumber` `app.py:3419` | `pyperclip`; NSPasteboard change count |
| `Hotkey` | `keyboard.add_hotkey` `app.py:3668` | macOS needs Accessibility permission; decide at adapter |
| `Capture` | `PIL.ImageGrab` `app.py:3277` (OCR region) | `screencapture`/Quartz |
| `Audio` | BASS via `player.py`; SAPI via `sapi.py` | CoreAudio/AVFoundation; same interface |
| `Window` | `pystray` + minimize-to-tray `app.py:3842` | `pystray` + menu-bar equivalent |
| `Paths` | hardcoded `C:/Program Files (x86)/QTranslate` `app.py:1806`, `theme.py:11`, `locale.py:11` | per-user app-data dir (D16); extensions dir lives here |
| `SpeechInput` | `comtypes` SAPI recognizer `app.py:1251` | Apple Speech |

**Honesty requirement:** an adapter must report a capability as
*unavailable* rather than pretend. macOS cross-app text capture may need
Accessibility permission or fall back to clipboard — that is an adapter
decision, tested, not assumed. (Matches the truthfulness rules in
`PROJECT_VISION.md` §7.)

## 5. What stays, what moves

| Today | Target | Notes |
|-------|--------|-------|
| `common.py` (Common.js port) | **compatibility shim** inside Core's provider adapter | Keep as the JS-faithful request/response layer for ported providers; not the public contract. |
| `services/*.py` | built-in **provider plugins** | Wrapped by the new `TranslationProvider` contract, not rewritten. |
| `do_translate` `app.py:537` | `TranslationEngine.translate` | Move logic out; keep behavior. |
| `TRANSLATORS`/`DICTS` `app.py:221/234` | `Registry` | Single source of truth. |
| `App` `app.py:581` | **split**: `MainWindow`, `OptionsDialog`, `HistoryView`, `DictionaryView`, `TrayController`, `PopupHost` | Each is a UI component behind the host API. |
| `on_hotkey`/clipboard monitor `app.py:3337/3407` | Core actions triggered by platform events | Event → Core orchestration → UI render. |
| `session.py` | Core session manager per provider | See `RELIABILITY.md` §4. |
| `win32app.py` | reference for the **Windows adapter** | Not a shipped path; a fidelity reference. |
| `theme.py`/`locale.py` | Core theme/i18n with pluggable source | Extensions can supply themes/packs. |
| `history.py`, `layout.py`, `xdxf.py` | Core storage / feature modules | Portable already. |

## 6. Compatibility layer

Per decision D10 (preserve 6.10), a thin **Compatibility Layer** bridges old
and new:

- map numeric service ids (`config.py:18`) ↔ stable plugin ids;
- map old language indices (`SupportedLanguages` tables) ↔ Core language codes;
- read `ServicesOrder` and preserve provider priority exactly;
- keep `RequestData`/`ResponseData` (`common.py:52`) for ported providers;
- keep old `Options.json` readable/writable so users don't lose settings.

It is a **bridge, not the core**. No stable plugin id is a number.

## 7. Process model

v1 runs Core + UI + extensions in **one process** (decision: no isolation yet —
`PROJECT_VISION.md` §6). The concession: an extension failure must be caught
and Core must continue with built-in fallback. Isolation (subprocess/RPC) is a
later, separately-planned change; the contract must not *preclude* it (i.e.
provider calls should be async-capable so a future remote provider fits).
