# Changelog (reverse-engineering log)

All entries are clean-room RE of QTranslate 6.10.0 for education.
`LIVE-OK` = verified against the real provider endpoint.

## Native-artifact recovery + tkk/cursor capture verified from the binary (2026-10-10)

- **The native binary was recoverable, not absent.** The only PE on disk was an
  NSIS 3.08 installer stub; the real 1,462,272-byte PE sat inside its appended
  solid-LZMA payload (stream at `0xF621` → `0x9bfa9`). Extraction independently
  reproduced byte-identically; see `docs/review/ARTIFACT_RECOVERY_2026-10-10.md`.
  Before this, `docs/RE_COVERAGE_CHECKLIST.md`'s 439 cited `FUN_xxxxxxxx`
  addresses resolved to **0** functions in the Ghidra project (which held the
  stub). After loading the recovered image they resolve to **390 by exact name**
  (49 are analyst-label differences), and **all 439 lie inside `.text`
  `0x401000..0x50cc00`**. The earlier `RE_EVIDENCE_PROVENANCE_2026-10-10.md`
  conclusion ("cannot be re-derived") was wrong and is now corrected in that file.
- **E21/F12 (Google tkk seed) — port changed to match the binary.**
  `FUN_0040FB54`/`FUN_0040FEC9` decompiled: two `ATL::CStringT::Find` calls slice
  between a start and an end marker, on
  `https://translate.google.<domain>/translate_a/element.js` (cp `0xFDE9`), with an
  hourly refresh guard. The markers are wide strings in `.rdata`: `"_ctkk='"`
  (`DAT_0051d57c`), `"';"` (`DAT_0051d58c`) and an **alternate start `"TKK='"`
  (`DAT_0051d5c4`)** that native retries with when the primary slice is empty.
  The port had a single regex over `_ctkk` with no alternate marker, so a page
  served with only `TKK=` fell back to tkk `0.0` while native still recovered the
  seed. `google_translate.py` now implements both marker pairs and the
  empty-result retry. `tests/regress_tkk_markers.py` (17 checks).
- **R2 (update manifest parser) — confirmed against the decompile.** `FUN_00461ADE`
  reads exactly `urls`/`href`/`provider`/`version`/`date`/`changelog` and no other
  keys, matching `updater.parse_manifest`. Port state now records it as verified
  **of the parser only** — no live update flow exists or can (host retired 2022).
- **C3/C8 (mouse capture) — evidence tightened, port extended.**
  `FUN_00404901` confirms `GetCursorPos` → `AccessibleObjectFromPoint` →
  `get_accName` with a `get_accValue` fallback. `FUN_00417E4E` confirms
  `GetRawInputData(0x10000003)` + `GetSystemMetrics(0x17)=SM_SWAPBUTTON` mapping to
  `0x201`/`0x202`. `FUN_004193F6` confirms the down-side own-window skip, exclusion
  check and `PtInRect` gate. `mouse_capture.py` gained `cursor_text()` (OLEACC),
  `_buttons_swapped()` (SM_SWAPBUTTON), `should_capture()` (own-window + PtInRect),
  and the hook now applies those gates. app.py mode 2 (`General.MouseMode == 2`)
  now routes OLEACC cursor text through `_translate_text()` instead of a
  synthesized Ctrl+C, falling back to the clipboard when the read is empty.
  `tests/regress_mouse_capture.py` (34 checks). Evidence:
  `docs/review/C3_C8_C10_MOUSE_2026-10-10.md`.
- **C10 — the row's prose was too strong and is corrected, not promoted.** The
  claim "no `SetCursor`/icon hook anywhere, only wndclass cursors" does not
  survive the real image: `SetCursor` has 14 callers and `LoadCursorW` 12. But
  their call sites cluster in the dialog/overlay region (`0x4373xx`/`0x50d4xx`),
  never in the mouse capture chain. The row now supports only the narrower,
  still-true claim about that chain. `SetWindowsHookExW` has **0** callers, so the
  port's `WH_MOUSE_LL` is a mechanism substitution, recorded as such.
- Checklist rows E21/F12/R2 moved `not-started` → `behaviour-verified` with the
  binary evidence named in-row; tally regenerated (`not-started` 11 → 8,
  `behaviour-verified` 11 → 14). **Gate state unchanged: BLOCKED (1), on G9 only.**

## G9 native window spec measured from the recovered image (2026-10-10)

- `docs/review/G9_SPEC_NATIVE_WINDOW_2026-10-10.md`: G9's part (a), the native
  window spec, parsed straight out of the recovered PE's `RT_DIALOG`. DLG129
  ("QTranslate") is **340×201 dialog units**, `WS_EX_CONTROLPARENT`, 17
  controls, font **`MS Shell Dlg` 8pt** (`DS_SETFONT`).
- 13/17 control ids pinned unambiguously: 1000/1017/1018 `RichEdit50W` (the
  three text panes), 1002 `ComboBox`, 1004 `Translate`, 1015 `<>`, 1134/1135
  separator statics, 1161 `SysLink "Info"`, 1009, 1029 `Fav`. The remaining 4
  are owner-draw icon buttons whose classes/strings resolve but whose ids do
  not — left UNKNOWN rather than guessed.
- Three checklist G9-row claims corrected by measurement: the font is not
  "Tahoma 9" (`Tahoma`/`Segoe UI` appear only once each, in Windows
  font-substitution tables, not in the template; `MS Shell Dlg` appears 20×);
  `526×366` is a runtime pixel size stated as template units; and control id
  `1001` is not in DLG129 at all (the source ComboBox is `1002`).
- **G9 stays `UNKNOWN`, Gate stays `BLOCKED (1)`.** Part (b) — the runtime
  screenshot diff — is still uncapturable on this host (`G9_RESULT_2026-10-09.md`).
  A correct spec is necessary for fidelity, not sufficient.

## Reliability layer + G9/re-artifact records (2026-10-10)

- `qtranslate/reliability.py`: error taxonomy (9 kinds, RELIABILITY.md §2),
  bounded retry with one shared budget + Retry-After (§3), FallbackRouter that
  preserves the request and names the provider that answered (§5), HealthTracker
  (§6). Phase 1 of `IMPLEMENTATION_PLAN.md`; imports neither tkinter nor Win32.
- Adapter (`ProviderRouter`): routes app.py's `_t_*` callables through the
  policy. Shaping (RemoveLineBreaks, 5000-char cut) happens once before the
  first attempt; the detect shortcut and the back-translation append stay
  outside the loop and run once on `provider_used`.
- `tests/regress_reliability.py`: 9 suites' worth of checks incl. the pinning
  test — provider 1 fails, provider 2 receives a byte-identical request.
  Runs under `python -I` on macOS (3.11/3.12/3.14 green).
- `docs/review/G9_RESULT_2026-10-09.md`: G9 BLOCKED. Native is i386 and cannot
  run here; the port cannot be screenshotted without a Screen Recording grant
  (`screencapture` exits 1, no file). No proxy baseline; `g9_evidence/` empty.
- `docs/review/ARTIFACT_RECOVERY_2026-10-10.md`: the Downloads `.exe` is an
  NSIS 3.08 stub; the real 1,462,272-byte PE was extracted from its solid
  LZMA1 payload (stream at `0xF621`, image at stream `0x9bfa9`). Re-imported to
  Ghidra: 3812 functions, 390/439 documented addresses resolve.
- `docs/review/D10_SPOTCHECK_Contents_2026-10-10.md`: Contents.EditSource/
  EditTranslation/EditBackTranslation verified as three distinct, persisting
  native keys (`+0x174/+0x178/+0x17c`). The port's separator text
  `--- back-translation ---` is NOT in the binary — port convention, not native.

# Changelog (reverse-engineering log)

All entries are clean-room RE of QTranslate 6.10.0 for education.
`LIVE-OK` = verified against the real provider endpoint.

## Keys loop (2026-10-08, help.txt 100% bound)

- Ctrl+K virtual keyboard; Ctrl+Space suggestion accept (label
  clickable); toolbar New (id1021)
- Right-click multi-select translate (fan-out + groove marks)
- All 17 main-window hotkeys bound; global registrar from Options.json
- `tests/ui_match.py` 82/82

## Babylon translate (2026-10-08, ID 13 ported 1:1)

- `services/babylon.py`: header/host/link, SupportedLanguages (76),
  JSONP request/response (paren-strip, [1] branch, `*` -> NL);
  endpoint SSL dead server-side (native error string via do_translate)
- Strip now 9/9 ServicesOrder; dict fixed to ID 20 lookup
- `tests/ui_match.py` 79/79

## UI 1:1 loop (2026-10-07/08, verified side-by-side vs native window)

- Main: full help.txt default text, ServicesOrder strip
  (Go..Mi..Pr..Ba..Ya..yo..Ba..Pa..DeepL), mic/headphone overlays,
  native error string, Tahoma, WINDOWPLACEMENT restore (526x366)
- Options 9/9 live on real Options.json: Basics, Appearance,
  Hotkeys (17 actions + Change/Clear), Services, Languages,
  Internet, Exceptions, Advanced, Updates
- History = DLG164 (Treeview + Clear + Save as) + History.json
  persistence; popup = borderless themed + dbl-click; Dictionary =
  services pane + XDXF-offline-first + zoom + history
- Hotkeys registrar reads Options.json (Alt+W replace, Ctrl+Q popup,
  clipboard monitor toggles); tray (pystray, optional); TTS slow flag;
  net stack honors Timeout+Proxy; OCR uses real OcrApiKey
- Suites: live 21/21, `tests/ui_match.py` 97/97, smoke 9/9

## Full-fidelity loop 2 (2026-10-08, 66 commits, all suites green)

- Hotkeys registrar from Options.json (Alt+W replace, Ctrl+Q popup,
  clipboard monitor, Ctrl+C+C, 17-action routing) + in-window keys
  (Shift+Esc, Ctrl+Tab, slots, Alt+Left/Right, Ctrl+Up, F11, panes)
- Net stack honors Timeout+Proxy; OCR region overlay + real key;
  SAPI speech fallback; TTS slow flag; spell gate
- History.json + placements (main/aux) + session restore + Cancel
  snapshot; 75-language table; tray states; crash hook
- All 19 DLGs mapped; dead services verified unrevivable with cause
- Suites: live 21/21, `tests/ui_match.py` 40/40, smoke 9/9

## i18n loop (2026-10-08, vi pack verified)

- `_pack`/`_T`/`_W`/`_Cw` helpers (lang.json Id maps; English fallback)
- Localized: nav/result menus, Options titles+pages order (Ids 10-18),
  full Basics, Appearance (+PopupIcons bitmask), Hotkeys actions,
  Internet, Advanced, Updates, Exceptions, History, aux titles
- `tests/ui_match.py` 46/46 (pages order/ids + vi resolve + fallback)

## i18n full (2026-10-08, vi 36 strings + 14 windows mapped)

- Helpers `_T`/`_W`/`_Cw` (menu/strings/windows/control Ids; en fallback)
- Localized: Translate btn (W1/1004), nav + result menus, Options
  titles/pages/labels (Basics full, Appearance + icons bitmask,
  Hotkeys actions, Internet, Advanced, Updates, Exceptions,
  History, aux titles), error 190, Update Check-now
- Verified: vi strings resolve (Chép bản dịch/Từ điển), en fallback
- Native orders kept: pages Ids 10-18, ProxyType 0-3, PopupIcons bits

## Render loop (2026-10-08, dict template + XSLT + links)

- `dict_template.html` byte-identical to RT_HTML-192 (3062 bytes,
  tested); XSLT k/tr/kref/iref/ex templates verified by test
- Result + dict panes: auto-URL tags (qtdp: internal re-lookup,
  http browser, FUN_004266C6); shared `tag_links` helper
- History CSV order fixed [a,c,b,e,d]; JSON `ensure_ascii=False`
  (native escapeStr keeps unicode)
- `tests/ui_match.py` 97/97

## History favorites (2026-10-08, strings 201/202)

- Star column + Favorite toggle + HistoryFilterFavorites filter;
  4-slot tuples with 3-slot file compat; tuple-safe unpacks
- Toolbar New (DLG129 id1021); DLG129 17-control table documented
- `tests/ui_match.py` 71/71

## Signing vectors (2026-10-08, node cross-checked)

- Baidu/Youdao/Promt/Google-tk known-answer vectors in smoke
  (endpoints dead/walled, algorithms bit-exact)
- `tests/ui_match.py` 71/71

## Exclusions live (2026-10-08, DisabledMode both ways)

- `foreground_excluded` reads live Disabled/Enabled/DisabledMode
  (was hardcoded blocklist); allowlist mode supported
- `tests/ui_match.py` 97/97 (wcsicmp vectors + live lists)

## Session loop (2026-10-08, panes + langs + options roundtrip)

- Contents.Edit*/SaveOnExit pane cache; SaveHistoryPath export dir;
  OptionsPageIndex last page; ActiveServices/DictionaryServices +
  LanguageFrom/To restore + persist (swap/combo/switch)
- CLI args override session; source combo shows LanguageFrom
- Full native defaults in config.py; stale 18s fixed
- 20/20 Options.json sections wired end to end

## Flags coverage (2026-10-08, all General keys audited)

- Wired: panes, tray, startup, cleanup, langs, services, detect,
  instant, spell, slow-TTS, OCR key/lang/archive, proxy, browser,
  mouse, phonetic (flag), favorites, history, placements, fonts
- Noted limits: cursor-hook mouse icon, DnD (tkinterdnd2),
  Extended (absent in modern Options.json), TTS phonetic (no API)
- `tests/ui_match.py` 71/71

## Theme loop (2026-10-08, ThemeName roundtrip)

- Theme choice persists `Appearance.ThemeName`; popup honors it
  (was hardcoded Flat Dark); `theme._hex` always 6-digit for Tk
- `tests/ui_match.py` 97/97 (hex + 8 palettes + vi boot)

## Services (`qtranslate/services/`)

- google_translate.py — `tk()` token + `/translate_a/single?client=gtx`,
  `dict-chrome-ex` fallback on 429 — **LIVE-OK**
- deepl.py — JSON-RPC split/translate — **LIVE-OK**
- microsoft.py — `ttranslatev3` + dynamic IID + 205 retry — **LIVE-OK**
  (via shared-jar `session.bing_translate()`)
- yandex.py — chunking + `srv=android` fallback — **LIVE-OK**
- baidu.py — GTK sign; detect **LIVE-OK**, translate needs page token
- youdao.py — md5 salt sign; needs page token
- naver.py — HmacMD5 PPG auth; **LIVE-OK** (new `/api/text/*`, `/api/tts/*`,
  `/api/dictionary/*` — no auth; earlier `/apis/*` hits 404)
- promt.py — ghcs hash; needs `paft` (markup changed)
- dictionary.py — 11 providers; Urban + Lingvo **LIVE-OK**, rest dead/changed
- spell.py — Google suggest + Yandex speller — **LIVE-OK**
- ocr.py — ocr.space multipart — endpoint verified (demo-key limited)

## Native (`docs/NATIVE_ARCH.md`, `docs/PIPELINE.md`)

Startup → hotkey reg → msg loop + pretranslate → 3-mode capture →
SendInput synth → ActiveScript boot (GUIDs) → 9 JS-boundary invokers →
libcurl fetch → popup render (classifier/initializer/subclass/layout) →
BASS TTS → history/options/crash/XDXF/tray/update/OCR/spell/menus.

## App (`qtranslate/`)

- app.py — hotkey translate popup + Listen + layout-convert hotkeys, themed
- player.py — ctypes BASS playback (**real audio verified**)
- layout.py, config.py, history.py, theme.py, xdxf.py, session.py, tts.py
