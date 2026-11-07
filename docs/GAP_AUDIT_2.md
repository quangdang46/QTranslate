# GAP AUDIT 2 — independent re-check of `.tmp` coverage

Read-only audit of `/Users/tranquangdang21/Projects/QTranslate/.tmp/QTranslate`
(Kotlin, upstream 6.10) against the port `qtranslate/`. `RE_COVERAGE_CHECKLIST.md`
was verified, not trusted: every core use case, plugin dir, `Configuration.kt`
field group, menu surface and ui-swing window/dialog was compared. Verdicts:
**PORTED** / **DIVERGENCE-documented** / **REAL-GAP**.

## Verified PORTED (spot-checked, not exhaustive)

| .tmp surface | Port evidence |
|---|---|
| All 7 `main/domain/usecase` + 5 `workspace/{lookup,translation}` use cases | `qt/app.py` (`_run_comparison`, `_inline_lookup`, `_auto_dict_refresh`), `services/ai_translate.py` (`summarize`/`rewrite`/`vision_ocr`/`dict_lookup`/`spell_check`), `document.py`, `update_check.py` |
| All 14 `plugins/*` dirs | `services/{google_*,deepl,microsoft,tts,bing_spell,libretranslate,mozhi,mymemory,reverso,yandex_web,ocr,system_tts,system_spell,commons_images,ai_translate}.py`; `csv-services`→`examples/extensions/csv_dictionary`; `google-lens-services`→`examples/extensions/google_lens_ocr`; `wikimedia-reference` Wiktionary→`examples/extensions/wiktionary` (`migrate.py:619` maps the service id) |
| `Configuration.kt` field groups | `config.py:280-420` + injected `General.*` keys; per-field audit rows at `RE_COVERAGE_CHECKLIST.md:1040-1160` re-verified (network, popups, image search, selection, extra output, pinned languages, translation rules) |
| `HotkeyBinding.DEFAULTS` (18 actions) + local/global scope | `qt/hotkeys.py`, `qt/main_window.py:443-466` (Ctrl+Enter, Ctrl+`, Ctrl+Shift+S/H/D/C/X, Ctrl+L, Alt+1/2/3), tray mouse-mode submenu |
| Tray menu (`TrayPopupMenu.kt:50-105`) | `qt/tray.py:97-161` — same entries + port additions |
| Dialogs/windows: `QuickTranslateDialog`, `DictionaryDialog`, `HistoryDialog`, `ImageSearchDialog`, `DocumentTranslationDialog`, `SnippingToolDialog`, `UpdateDialog`, `InfoDialog`, `LanguageEditorDialog`, `HotkeyRecorderDialog`, `DynamicPluginSettingsDialog`, settings search | `qt/popup.py`, `dictionary.py`, `history_window.py`, `image_search.py`, `document_dialog.py`, `ocr_pick.py`, `update_check.py`, `options/*.py` (`RE_COVERAGE_CHECKLIST.md:1172-1184`) |
| Drag & drop (`ContentDropRouter.kt:26-33`) | `qt/main_window.py:1635-1700` (image→OCR, document→dialog, text→source) |
| Selection behavior OFF/SHOW_ICON/TRANSLATE/TRANSLATE_AND_READ + `SelectionReadSource` | `qt/app.py:2050-2116`, `mouse_icon.py`, `languages.py:202-216`, tray "Mouse mode" |
| History undo/redo navigation (`MainStore.handleUndo/handleRedo`, `HistoryNavigation.kt`) | `qt/main_window.py` back/forward + Alt+Left/Right (`app.on_back/on_forward`) |
| Inline dictionary gloss (`FetchInlineDefinitionUseCase`, `AutoLookupCoordinator`) | `qt/app.py:600-700` (`_inline_pick`/`_inline_lookup`/`_auto_dict_refresh`) |
| Comparison (`ParallelComparisonUseCase`, `TranslatorSet`, `ComparisonEligibility`) | `qt/app.py:741-920`, `qt/options/comparison.py`, `presets.py` |
| Startup registration, updater check, audio playback, document formats (docx/pdf/txt/srt/vtt) | `startup.py`, `update_check.py`, `player.py`, `document.py` |

## REAL-GAPs found

| # | .tmp feature | .tmp evidence | Port state | Verdict |
|---|---|---|---|---|
| 1 | **Hotkey preset switcher** — KeyboardPanel preset combo (LEGACY/MODERN/CUSTOM) bulk-replaces all bindings; `HotkeyPresets.identify` detects the active preset | `ui-swing/.../KeyboardPanel.kt:44,142-152,360,407`; `core/.../HotkeyPresets.kt:8-62`; `HotkeyDraftOperations.kt:18-22` | `qt/options/hotkeys.py` has per-action recorder only; no preset combo or MODERN rebind set anywhere in `qtranslate/` | **REAL-GAP** (minor UX feature, undocumented) |
| 2 | **Update dialog direct-asset download** — `ReleaseAssets.selectDownload` picks the platform asset; `Updater.downloadUrlFor` fills `downloadUrl`; dialog has a "Download" button opening the asset URL | `core/updater/ReleaseAssets.kt:19-32`; `core/updater/Updater.kt:91-103`; `ui-swing/update/UpdateDialog.kt:56-62,151-156` | `update_check.py` `select_download_asset`/`_download_url_for` pick the platform asset into `download_url`; `show_update_result` offers "Download" (`QDesktopServices.openUrl`) beside "Open release page", which remains the fallback when no asset matches | **PORTED** (was REAL-GAP; Skip/Remind-Later remain no-ops upstream — `MainAppFrame.kt:1660`. Pinned by `tests/regress_update_assets.py`) |
| 3 | **Dictionary word chips** — multi-word (comma/space-separated) input in the dictionary search field renders clickable word chips for per-word lookup | `ui-swing/dictionary/DictionaryChipController.kt:10-50`; `DictionaryPanel.kt:187-202` (`triggerLookup`/`parseWords`/`setup`) | `qt/dictionary.py:255` looks up the whole input string; no chip strip exists (grep `chip` → 0 hits in `qtranslate/`). The recorded popup-vs-window divergence (`RE_COVERAGE_CHECKLIST.md:1103-1196`) does not cover chips inside the persistent window | **REAL-GAP** (minor) |
| 4 | **App-wide notification channel** — `NotificationBus` + `AppNotification` + `NotificationCode` (UpdateAvailable, LanguageNotSupported, TtsNotSupported, UnknownError, Custom) drive the status bar, `NotificationPopover`, `ErrorDetailPopup`, and plugin `context.notify()` | `core/shared/notification/{NotificationCode,AppNotification,NotificationBus}.kt`; `PluginContext.kt:90`; `ScopedPluginContext.kt:110`; `ui-swing/main/statusbar/{StatusBar,StatusBarController,NotificationPopover,ErrorDetailPopup}.kt` | No notification surface in `qtranslate/` (grep `notification` → 0 product hits); errors render inline only. Only the *toolbar toggle* absence is noted (`qt/options/basics.py:237`) | **REAL-GAP** (moderate; architectural divergence never recorded) |
| 5 | **PluginContext capability surface** — Kotlin plugins get `scope`, `notify`, typed `settings`/`secrets` (SecretStore), scoped `http` (KtorHttpClient honoring `NetworkConfig`), `getPluginDataDirectory`, lifecycle hooks (`initialize`/`onEnable`/`onDisable`/`onSettingsChanged`), `supportsMultipleInstances`, plugin localization (`PluginLocalization`/`PluginTextResolver`), JAR fingerprint integrity (`PluginFingerprintRepository`), rich `SettingType`s (PASSWORD/TEXTAREA/DROPDOWN/FILE_PATH/DIRECTORY_PATH/SLIDER/CUSTOM_PANEL) | `api/plugin/PluginContext.kt:34-151`; `api/plugin/Plugin.kt:119-241`; `api/settings/SettingType.kt:6-55`; `core/plugin/storage/PluginFingerprintRepository.kt`; `core/plugin/text/PluginLocalization.kt`; `core/plugin/http/KtorHttpClient.kt` | **Superseded 2026-11-08 (qt-t00):** the portable subset is PORTED — `api.data_dir` (`<app data>/extensions_data/<id>/`), `api.notify`, `api.http_get`/`http_post` (over `session._net_open`; user proxy/timeout/retry apply), `api.on_load`/`on_unload`/`on_settings_changed` hooks, `api.secrets_*` (per-extension `secrets.json` in the data dir at 0600, outside Options.json), `api.tr` (extension `localization/<tag>.toml` bundles). Pinned by `tests/regress_ext_api.py`, `tests/regress_ext_secrets_i18n.py`. **Residual documented divergences:** JAR fingerprint/trust (`PluginFingerprintRepository` — extensions are Python source folders, nothing signed to fingerprint), plugin-code `validate()` hook with host timeout (`PluginValidateTimeoutTest` — GAP_AUDIT_3 row 3), upstream's host-strings-first `DisplayText` resolution + `@reference`/`[meta]` TOML, per-plugin scoped HTTP client isolation (the port shares the app's single `session._net_open` policy, not a per-plugin `KtorHttpClient`), and `SettingType` richness (schema kinds remain `bool`/`number`/string — `qt/options/extensions.py`). Whole-runtime divergence acknowledged at `RE_COVERAGE_CHECKLIST.md` "Deliberate divergences" + `EXTENSION_SDK.md` | **DIVERGENCE-documented** (residual; was REAL-GAP) |

## DIVERGENCE-documented (verified, not re-litigated)

- `LocalizationManager` TOML packs → native `lang.json` packs (`locale.py`).
- `layoutPresetId`/`toolbarVisibility`/`serviceSelector*` → no layout engine; pane toggles via `Show*Pane`/`Show*Bar` keys (`basics.py:230-250`).
- `quickDictionary*` popup fields + `showDictionaryPanel` dock → persistent `DictionaryWindow`.
- PDF layout-aware translation → text-only mode (`document.py:337`).
- Windows/Linux OCR/spell/TTS backends → macOS-first (`ocr.py`, `system_*.py`).
- `connectTimeout`/`socketTimeout` split, connection-pool caps → single urllib timeout (`RE_COVERAGE_CHECKLIST.md:1152-1153`).
- Donation nudge → promotional, skipped.
- Extension SDK is Python, not the Kotlin plugin ABI (F13, `EXTENSION_SDK.md`).

## Notes for the lead

- Gaps 1-3 are small, self-contained features; each needs a port decision
  (implement vs record as divergence) before the checklist's "full coverage"
  claim can stand unqualified.
- Gap 4 is the largest functional hole: `.tmp` routes service errors,
  unsupported-language/TTS notices and plugin messages through one bus; the
  port has no equivalent surface at all.
- Gap 5 is mostly architectural (Python source extensions vs JAR plugins),
  but `notify`, `secrets`, and per-plugin data dir are capabilities a
  third-party extension cannot currently express — worth an explicit
  divergence note at minimum.
