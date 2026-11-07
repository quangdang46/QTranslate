# GAP AUDIT 3 — .tmp TEST-suite contract mining

Audit of .tmp test suites vs port. Verdicts: PORTED / DIVERGENCE / REAL-GAP.
(Condensed from full agent report; supersedes stale notes in GAP_AUDIT_2.)

## REAL-GAPs

| # | Subsystem | Contract | Evidence |
|---|---|---|---|
| 1 | MyMemory segmentation | Utf8Segmenter splits at \n\n paragraph boundaries even under byte limit; 500-byte cap | .tmp Utf8SegmenterTest.kt:9-24; port mymemory.py:87-99 splits on size only |
| 2 | Bing/Microsoft auth recovery | 401/403 → drop cached token, refresh once, retry once, never loop; non-auth not retried; no token leak | .tmp BingAuthRecoveryTest.kt:48-201; port microsoft.py:127-133 only retries statusCode==205 |
| 3 | Plugin validate timeout | Outer cap formula, 15s floor, host-timeout override | PluginValidateTimeoutTest.kt:18-79; no validate concept in extensions.py — divergence candidate |
| 4 | Retry-After hint on errors | Retried-then-failed 429 reports Retry-After seconds as error hint | KtorHttpClientRetryTest.kt:175-258; session.py:104-128 hint feeds sleep only |
| 5 | Selection restore failure | Permanent restore failure → bounded retries(3), logged, action NOT dispatched | SelectionCaptureTest.kt:306-345; selection.py:209-214 ignores restore result |
| 6 | Clipboard sequence wrap | DWORD wrap still counts as change; seq 0/fail → unavailable | ClipboardMonitorsTest.kt:53-77; clipboard.py:50 c_int restype reads >2^31 negative |
| 7 | Auto-lookup hidden main window | Coordinator checks isMainVisible before dock refresh | AutoLookupCoordinatorTest.kt:225-230; app.py:695-716 lacks main-window guard |
| 8 | Auto-lookup retrigger | Settings change/re-enable retriggers lookup for idle translated result only | AutoLookupCoordinatorTest.kt:241-274; no retrigger path in port |
| 9 | Line-break \r semantics | \r dropped joining neighbors; quick stores cleaned text; replace reuses prepareInputText | QuickTranslateLineBreaksTest.kt:55-106; reliability.py:864 \s*\n\s* misses lone \r |
| 10 | OCR RTL line order | Visual→logical reorder for Arabic+Latin runs (geometry decides) | OcrLineOrderTest.kt:14-192; services/ocr.py:180-185 verbatim join — **DIVERGENCE, documented** (see below) |
| 11 | Ext runtime residual | PluginTrust/JAR fingerprint, validate(), scoped HTTP client, SettingType richness | api/plugin/PluginContext.kt; secrets+i18n+http+hooks now PORTED (qt-t00); residual = documented divergences (RE_COVERAGE_CHECKLIST "Deliberate divergences") |
| 12 | Proxy password storage | Password in SecretStore, never persisted config | NetworkConfigMappingTest.kt:51-73; **PORTED 2026-11-08** — `qtranslate/secrets.py` (`network.proxy.password`, secrets.json 0600 next to Options.json), `config.load()` migrates legacy plaintext, `session.py`/`internet.py` read/write the store |

## Row 10 detail — OCR RTL line order (DIVERGENCE)

Upstream's `OcrLineOrder` (`plugins/system-services/.../OcrLineOrder.kt`)
rebuilds logical reading order for lines `Windows.Media.Ocr` reports in
VISUAL order (words left→right with monotonic x), reversing RTL runs while
keeping embedded Latin runs LTR — geometry decides, engine order ignored.
That helper exists ONLY for the Windows OCR backend.

The port has no Windows.Media.Ocr backend. Its OCR chain
(`services/ocr.py::_OCR_STAGES`) is: extension recognizers → macOS Vision
(`_macos_vision_ocr`, darwin only) → tesseract CLI → ocr.space cloud →
Google Cloud Vision → AI vision. None of these emit Windows-style
visual-order word lists: Vision returns per-line candidate strings,
tesseract/cloud engines return engine reading order. So there is no
visual-order input for a port of `OcrLineOrder` to consume today — the
reorder is absent because its trigger is absent.

What's missing / affected:
- **Windows**: upstream's reorder applies; the port doesn't run
  Windows.Media.Ocr at all (tesseract is the Windows-capable offline
  fallback). If a Windows OCR backend is ever added it MUST port
  `OcrLineOrder` (Arabic+embedded-Latin lines come back visually
  ordered otherwise).
- **macOS Vision**: whether `VNRecognizeTextRequest` emits logical or
  visual order for mixed-direction text is UNVERIFIED (out of scope);
  `ocr.py:180-185` joins `topCandidates_(1).string()` per observation
  verbatim. If Vision proves visual-order on RTL, the same geometry
  reorder would be needed there.
- tesseract/ocr.space/Google-Vision/AI stages: engine-defined order;
  no upstream contract to match.

## Unverified items — verdicts (2026-11-08)

- **Instant translation pipeline: PORTED.** `.tmp`
  `MainStore.observeInstantTranslation` is translate-as-you-type in the
  MAIN window (350 ms debounce, min 2 chars,
  `AppConstants.INSTANT_TRANSLATION_DEBOUNCE_MS/MIN_CHARS`), NOT
  mouse-mode auto-translate-on-selection. The port implements it in
  `qt/main_window.py` (`INSTANT_DEBOUNCE_MS=350`, `INSTANT_MIN_CHARS=2`,
  `_src_text_changed`→`_instant_translate`→`_instant_done`), gated on
  `General.InstantTranslation` and window visibility, skipping history
  (`push_hist` not reached) exactly like upstream's TranslationOrigin.
  Auto-copy correctly excludes it: `_instant_done` renders via
  `win.render` and never reaches `app._maybe_auto_copy`
  (app.py:956-963 comment corrected — the pipeline exists, it just
  doesn't feed that hook).
- **DoubleCtrl detector: REAL-GAP (documented divergence).** `.tmp`
  `DoubleCtrlDetector` (ui-swing/.../input/DoubleCtrlDetector.kt) is a
  pure press/release state machine: two genuine Ctrl taps <400 ms apart
  (with no other key in the combination, press-observed-only) trigger
  SHOW_MAIN_WINDOW; `isDoubleCtrlEnabled` rides `HotkeyBinding`. The
  port PERSISTS the gesture — `HotKeyMainWindow=0x8000` (bit15 "Double"
  prefix, `config.format_hotkey` displays "Double Ctrl") and
  `migrate.py` maps `isDoubleCtrlEnabled`↔0x8000 — but NOTHING detects
  it: `hotkey_combo(0x8000)` yields no combo (vk=0), so `hotkeys.install`
  registers nothing, and no tap-pair detector exists in `qt/hotkeys.py`,
  `macos_tap.py`, `macos_hotkeys.py` or `app.py`. (`hotkey_combo` also
  masks bit15 off a chord, so a hypothetical "Double Ctrl+Q" would fire
  on a SINGLE Ctrl+Q — the Double qualifier is silently dropped.) A
  bare-Ctrl tap pair
  needs a lower-level key stream than `keyboard.add_hotkey`/Carbon
  hotkeys provide (upstream uses `MainGlobalKeyListener`+`QInputBackend`).
  Documented in RE_COVERAGE_CHECKLIST B4/B5 notes; implementing the
  detector is a real feature, not a docs fix.
- image_search panel internals, dictionary selection-menu parity,
  options/internet.py proxy UI — still open (out of this bead's scope).

## Resolution status (post-fix)

| # | Status |
|---|---|
| 1 MyMemory \n\n split | FIXED — `_segments` ports Utf8Segmenter (paragraph flush + 500B cap, lossless join) |
| 2 MS auth 401/403 | FIXED — refresh-once-retry-once in session.bing_translate + microsoft._service_request; `bing_auth_error` → AUTH_EXPIRED, no token leak |
| 3 Plugin validate timeout | DIVERGENCE — no validate() concept; documented residual |
| 4 Retry-After hint | FIXED — `HTTPError.retry_after_seconds` → `Failure.retry_after` on RATE_LIMITED |
| 5 Restore failure gate | FIXED — `_restore_with_retry` (3×50ms busy), `restore-failed` suppresses dispatch |
| 6 Clipboard seq wrap | FIXED — `c_uint32` restype, 0→-1, wrap-safe poll |
| 7 Hidden-main guard | FIXED — `_auto_dict_refresh` requires `win.isVisible()` |
| 8 Auto-lookup retrigger | FIXED — `_auto_lookup_settings_check` signature-diff on Apply path + dictionary open edge |
| 9 \r line-breaks | FIXED — `prepare_input_text` exact port; cleaned text stored in `_popup_src_full` |
| 10 OCR RTL order | DIVERGENCE — Windows.Media.Ocr-only upstream; documented |
| 11 Ext runtime residual | PARTIAL — secrets/i18n/http/hooks/lifecycle PORTED; JAR trust/validate/scoped-HTTP/SettingType richness = documented divergence |
| 12 Proxy password | FIXED — was plaintext in Options.json; now `qtranslate/secrets.py` (0600, upstream key `network.proxy.password`), load() migrates legacy |

## Remaining REAL-GAP
- **DoubleCtrl detection**: `HotKeyMainWindow=0x8000` persists/displays but no detector exists (needs raw key stream). Documented in RE_COVERAGE_CHECKLIST B4/B5.
