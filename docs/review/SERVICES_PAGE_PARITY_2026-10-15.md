# Options → Services page: behavior parity note (2026-10-15)

> Static code audit (read-only). No screenshot, no window opened. No row
> state changed. This is a *port-behavior* note, not RE evidence.

## 1. What the port does (`app.py` Services page)

| Native behavior | Port equivalent | Verdict |
|---|---|---|
| Reorder providers (ServicesOrder) | ▲/▼ `_move` swaps + `_refresh` | parity |
| Enable/disable provider | On/Off `_toggle` on `DisabledServices` / `DisabledDictionaries` | parity |
| Check/Uncheck all (DLG174) | All `_check_all`: clear-all if any disabled, else disable-all | parity (semantics match DLG174) |
| Persist 4 keys | `_save()` writes `ServicesOrder`, `DisabledServices`, `DictionariesOrder`, `DisabledDictionaries` to Options.json **and** the live `cfg` dict | parity+ (native needs Apply; see §2) |
| Disabled shown gray | `_paint` grays `itemconfig` for disabled ids | parity |

## 2. One deliberate divergence: save timing

Native M22 (`FUN_00434577`) is a change-tracker: edits arm the Apply
button (`GetDlgItem 0x419`), and persisting happens on OK/Apply (which
posts parent `0x8001`/`0x8002` and calls the saver `FUN_004561F0`).

The port saves **immediately** on every move/toggle (`_save()` inside
`_refresh`/`_toggle`/`_check_all`). Net persisted state is identical —
reorder + toggle + close + reopen yields the same Options.json either
way — but there is no "edit then Cancel to discard" path. This is a
conscious UX simplification, not a fidelity gap in the saved data. If a
future slice wants Cancel-to-discard, the `_save` calls move behind an
Apply gate; the list mechanics stay unchanged.

## 3. Languages page: per-key defaults fix (same tree)

The Languages page used one default (`17`) for all four language combos,
so a first run with no Options.json showed `en` for "Translate from"
instead of native `auto`. Fixed to per-key native defaults (verified
against the real Options.json: From=1/auto, To=57/vi, Dictionary=17/en,
Keyboard=17/en). Only visible on first run — a present Options.json
always carries all four keys, so existing installs were unaffected.

## 4. Advanced page audit (same day, no changes needed)

- Mouse-mode gate order matches native: `EnableGuiTranslation`
  (DAT_005494e4) → `EnableMouseModeOnCtrl` (Ctrl held) → exclusions →
  mode-2 OLEACC (`cursor_text`) → clipboard fallback (`ctrl+c`).
- `CopyAction` honored: 0 = clipboard only, 1 = copy + retype, default 0.
- `OcrApiKey` read with `"helloworld"` fallback (native behavior).
- No fixes required; recorded so the surface is not re-audited blind.

## 5. History lifecycle audit (same day, no changes needed)

- `push_hist` gated by `General.EnableHistory` (off = no record).
- `_load_history` returns `[]` when `ClearHistoryOnExit`; `_save_history`
  honors `Contents.SaveOnExit` and deletes `History.json` on the clear
  path — matching the native `FUN_00419122` lifecycle (I1).
- 500-entry cap, fav as per-entry field (I5), not a separate store.
- No fixes required.

## 6. Dictionary window audit (same day, no changes needed)

- `DisabledDictionaries` filtered before display/query (was previously
  queried regardless).
- `ShowServicesPane` toggle, `DictionaryZoom` font scaling, `ExactSearch`
  persisted to `Dictionary.DictionaryExactSearch` (+0x181).
- Per-word `DictionaryHistory.json`, dict source from
  `General.LanguageDictionary` (fix landed this tree).
- No fixes required.

## 7. Hotkey action audit (same day, no changes needed)

- All 17 `HotKey*` actions bound (`_actions` table → `keyboard.add_hotkey`);
  unbound (0) entries skipped, failures printed not raised.
- Every action has a handler: popup/main/replace/listen×2/dict×2/
  history/keyboard/layout/copy/OCR/clipboard×3/speech/mouse-mode.
- No fixes required.

## 8. Tray menu audit (same day, no changes needed)

- Order matches the user-verified native order (Dictionary / Text
  recognition / History / Keyboard / Options / About — sep — Enable
  global hotkeys [checkable] / Mouse mode [radio submenu] — sep — Exit).
- Rendered by pystray as the real taskbar menu, not self-drawn (spec
  hard rule 5).
- No fixes required.

## 9. Popup path audit (same day, no changes needed)

- Two text slots (G1: result + aux), themed, frame-thickness border,
  lang-pair header + icon glyphs, Esc close.
- `PopupAutoFocus` / `PopupAutoPos` (+ `WindowPopupPlacement` when off) /
  `Transparency` / `PopupTimeout` all honored.
- No fixes required.

## 10. OCR path audit (same day, no changes needed)

- `Advanced.OcrApiKey` with `"helloworld"` fallback (native behavior).
- `Ocr.OcrLanguage` (Google index, default 17) mapped to ocr.space
  codes (`eng`/`vie`/`fre`/…); `Ocr.SaveImagePath` archives captures
  as timestamped PNGs.
- Response parse `ParsedResults[0].ParsedText` (K1) in services/ocr.py.
- No fixes required.

## 11. Layout pairs fix (same tree — real behavior bug, not audit)

`layout.py`'s explicit table restated the generic JCUKEN map instead of
the native explicit set: 6 of 8 `FUN_00404E09` pairs wrong (EN `w`→`ц`
not `'`, EN `q`→`й` not `/`, EN `'`→`э` not comma; RU `'`, `,`, `/`
missing entirely) while P2 read `ported`. Fixed to the decompile-
verified set with build order generic → uppercase mirrors → explicit
LAST (a mirror loop placed after the pairs silently uppercased `w`→`W`
on the first attempt — recorded so the ordering is not "cleaned up").
Pinned by `tests/regress_layout_pairs.py` (13 checks, PASS) + generic
fallback intact + `Ghbdtn`→`Привет` round-trip.

## 12. Internet page audit (same day, no changes needed)

- UI: Timeout (ms) entry + ProxyType combo (system/none/manual/
  auto-detect) + Host/Port/Username/Password, persisted via `_save_n`
  to both Options.json and live `cfg`.
- Net stack (`session.net_options`) reads the same keys: Timeout ms→s,
  ProxyType 0/1/2/3 mapping, Scheme-aware proxy URL. Page → engine
  chain closed.
- No fixes required.

## 13. Appearance page audit (same day, no changes needed)

- Theme selector (persisted to `Appearance.ThemeName`), 5 popup
  behavior toggles, Transparency + FrameThickness entries, PopupIcons
  bitmask checkboxes (1138–1141, default 30), 3 color entries
  (Back/Text/Frame as `#rrggbb`).
- Every key has a reader in the popup path (audited §9).
- No fixes required.

## 14. Hotkeys page audit (same day, no changes needed)

- Enable-hotkeys toggle, action Treeview (display names from lang pack
  Windows Id 16 / control 1165, order-matched to HOTKEY_NAMES).
- Change capture: Tk state bits → native mod bits (Shift 0x1→4,
  Ctrl 0x4→2, Alt 0x8→1, Win 0x40→8), packed `vk|(mods<<8)` per
  FUN_00405A17; Clear unbinds (code 0). Both persist to Options.json
  + live cfg.
- No fixes required.

## 15. Exceptions page audit (same day, no changes needed)

- Disabled/Enabled `[exe, class]` pair lists with Add/Delete,
  DisabledMode toggle, persisted via `_save_x` to Options.json + live
  cfg.
- Engine reads through `exclusions.foreground_excluded()` at 3 call
  sites (hotkey, clipboard monitor, mouse capture). Module is
  tkinter-free (verified by import).
- No fixes required.

## 16. Advanced + Updates pages audit (same day, no changes needed)

- Advanced: 5 behavior flags + OCR key / Preferred+Google domains /
  browser id / layout indicator / CopyAction / MouseMode entries, all
  persisted via `_save_a` to Options.json + live `cfg`. Every key has
  a reader (mouse gates, OCR path, `_open_url` browser pick, TTS slow,
  CopyAction retype).
- Updates: `CheckForUpdates` toggle + Check-now (manifest parse via
  `updater.py`; host retired = `dead:host-retired` on R1, UI retained
  as native has it).
- No fixes required.

## 17. Basics page audit (same day, no changes needed)

- Startup toggle (HKCU Run write/delete), locale/font/size combos,
  AutoDetection First/Second/SpeechRecognition combos (persisted as
  SUPPORTED_LANGS indices), History Enable/ClearOnExit/Expand flags —
  every widget has a persist callback (`_save_general`,
  `_save_autodetect`, `_save_history_flag`).
- No fixes required. With this, all 9 Options pages are audited:
  Services, Languages, Internet, Appearance, Hotkeys, Exceptions,
  Advanced, Updates, Basics.

## 18. Virtual keyboard audit (same day, no changes needed)

- DLG162 geometry (308×102 placement default), key labels from
  `LanguageKeyboard` via EN2RU (RU layout when index ≠ 17), keys type
  into the source pane, Space/Backspace included.
- Approximation noted, not a bug: any non-en index shows JCUKEN
  (native only ever has the EN/RU HKL pair).
- No fixes required.

## 19. About dialog audit (same day, no changes needed)

- DLG133 shape (version + OK + 2 SysLinks) present. Port uses 360×200
  vs native 315×135 DU (≈551×506 px) — deliberate re-layout (port
  About carries less content), not a bug; recorded for G9 part (a).
- No fixes required.

## 20. Listen path audit (same day, no changes needed)

- Main-window listen (result pane → `speak` thread) + hotkey Ctrl+E
  (clipboard → `speak` thread), both through `speak` →
  `player.play_text` (online BASS → SAPI fallback, slow flag honored).
- No fixes required.

## 21. Clipboard monitor audit (same day, no changes needed)

- Sequence-number poll (`GetClipboardSequenceNumber`) with exclusion
  gate, 5000-char cap, translate → render → history, plus the popup
  variant. Mechanism substitution for the native clipboard viewer
  (C4) — recorded, not hidden.
- No fixes required.

## 22. Replace/copy audit (same day, no changes needed)

- Alt+W replace: clipboard → translate → CopyAction gate (copy-only vs
  copy+retype via `keyboard.write`) → main panes update. Matches C6
  write-back semantics.
- Copy result: result pane → clipboard.
- No fixes required.

## 23. Swap/history-nav audit (same day, no changes needed)

- Swap (`<>`): exchanges From/To (keeps `auto` at source when target
  was `auto`), persists indices via `_persist_langs`.
- Alt+Left/Right: session-history navigation with position cursor.
- No fixes required.

## 24. Suggest/instant/multi-service audit (same day, no changes needed)

- Suggest strip: `SpellChecking` gate, 3–60 char window, top-5 via
  `registry.google_suggest`, Ctrl+Space accept.
- Instant translation: `InstantTranslation` flag, 600 ms debounce,
  ≥2 chars.
- Multi-service fan-out with per-provider error `Result` guard (bare-
  str assignment would crash on `.text`).
- No fixes required.

## 25. Render path audit (same day, no changes needed)

- `render()`: result-pane write + auto-URL tagger (`qtdp:` re-lookup,
  http → browser; G3/H5-H6) + backtrans-split with the INFERRED-widget
  caveat stated inline.
- `current()`: single (service, src, tgt, src-lang) source for all
  capture paths.
- No fixes required.

## 26. Startup/shutdown audit (same day, no changes needed)

- Boot: option seeding (`addOption` bridge, D11), crash-report
  consume-once + delete (Q1–Q2), startup action (normal/minimized/
  tray) + show-on-load.
- Close: history save + placement save, minimize-to-tray when set.
- No fixes required.

## 27. i18n helper audit (same day, no changes needed)

- `_T` (Strings + Menus by Id), `_W` (Windows titles), `_Cw`
  (control labels) — all fall back to the English default when the
  pack lacks the entry (O2/O4: English pack ends at Id 10).
- No fixes required.

## 28. Nav menu + service strip audit (same day, no changes needed)

- Nav menu (native FUN_0042DF28 ids): dictionary/history entries,
  detect/backtr/phonetic toggles persisted to General.
- Service strip: current sunken, multi-select groove highlight.
- No fixes required.

## 29. OCR region overlay audit (same day, gap noted)

- Flow matches K2: fullscreen rubber-band → min-size guard → ImageGrab
  → PNG → worker thread → `_ocr_bytes`. Esc cancels.
- ~~Gap: overlay keys missing~~ **CLOSED 2026-10-15:** `S` (save PNG
  to SaveImagePath-or-home, FUN_0043845C), `C` (copy bitmap to
  clipboard as CF_DIB via BMP-strip, FUN_004383A2 — first attempt
  wrongly opened an external viewer, corrected before commit),
  arrows (nudge selection), Del/Esc (close), Enter (OCR-send) all
  wired through one shared `_grab_png` capture path. BMP→DIB strip
  verified offline (40-byte BITMAPINFOHEADER intact).

## 30. Offline-dict manager audit (same day, no changes needed)

- DLG173 shape (Add/Remove *.xdxf + list), persisted to
  `OfflineDictionaries`; dict window queries XDXF before online
  providers (H2 chain).
- No fixes required.

## 31. Export dialog audit (same day, no changes needed)

- Save-dialog filter built native-shaped (`desc (*.ext)` per History
  plugin, FUN_0042856e); writer dispatch by filename extension
  (`exporter_for`, FUN_00428483 — not hardwired HTML); SaveHistoryPath
  persisted; unknown-extension error surfaced.
- No fixes required.

## 32. History-window + item-menu audit (same day, gap noted)

- Window: Treeview (translation/fav/service), substring filter +
  favorites toggle persisted, ExpandHistoryItems inline child rows,
  Clear + export, fav toggle (strings 201/202).
- ~~Gap: I6 five-entry menu missing~~ **CLOSED 2026-10-15:**
  history Treeview now has a right-click menu with all five I6 entries
  (Open 0x8028 → `load_sel`; Copy text 0x806E → clipboard source; Copy
  translation 0x8026 → clipboard result; Delete 0x8027 → splice +
  save + repaint; Listen 0x8099 → `speak` thread). Each handler is the
  operation the window already performed elsewhere — the menu is a new
  entry point, not new semantics. Disabled state with no selection.
  (The result-pane menu Id 3 stays as-is: it operates on the current
  pane, not a history entry, so history Delete does not belong there.)

## 33. LANG_CODES collision check (same day, no bug)

`_ISO_NAMES` maps both `zh-CN` and `zh-CHS` to `"Chinese (Simplified)"`,
which would collide in the reverse `LANG_CODES` dict — except `zh-CHS`
is not in Google `SUPPORTED_LANGS`, so the live `LANGS`/`LANG_DISPLAY`
never contains it. The entry only matters in the import-failure
fallback (`LANGS = list(_ISO_NAMES)`), where the app cannot run anyway.
Dead entry, harmless; deliberately not removed. Checked 2026-10-15.

## 34. Updates Check-now audit (same day, no changes needed)

- Check-now GETs the native manifest endpoint, parses via
  `updater.parse_manifest` (R2), renders version/date/changelog on
  success and an explicit BLOCKED message on failure (host retired
  2022, R1). The page labels this up front — no dead button
  pretending to work.
- No fixes required.

## 35. Options shell audit (same day, no changes needed)

- 9 pages in Windows Ids 10–18 order (Basics/Internet/Services/
  Languages/Appearance/Exceptions/Hotkeys/Advanced/Updates), labels
  localized via `_W`, placement persisted. With this, all 9 pages +
  shell are audited.
- No fixes required.

## 36. Toolbar/accelerator audit (same day, no changes needed)

- Backtr toggle persisted, service slots Ctrl+1..9, dictionary slots
  Ctrl+Alt+1..9, Shift+Esc reset pair (B6), fullscreen toggle.
- No fixes required.

## 37. URL-open helper audit (same day, no changes needed)

- `_open_url` honors `Advanced.DefaultBrowserId` (registered browser
  by id, system default when empty, fallback on failure).
- No fixes required. With this, every UI surface in `app.py` is
  audited: main toolbar/panes, 9 Options pages + shell, History +
  item menu, Dictionary + offline manager, popup, tray, keyboard,
  About, OCR overlay, clipboard/replace/copy, swap/nav, suggest/
  instant/multi, render, startup/shutdown, i18n, links.

## 38. Fix→test coverage (same day)

Every fix in this tree has a pinning test (all headless):

| Fix | Test | Checks |
|---|---|---|
| dict LanguageDictionary | regress_dict_lang | 9 |
| per-key language defaults | regress_ui_parity_fixes §1 | 6 |
| layout explicit pairs | regress_layout_pairs | 13 |
| history I6 five-entry menu | regress_ui_parity_fixes §2 | 9 |
| OCR overlay keys | regress_ui_parity_fixes §3 | 12 |
| template fallback | ui_match placement-template | 2 |
| router ServicesOrder | regress_router_order | 9 |

## 39. Sweep evidence (2026-10-15, re-run on this tree)

**30/30** headless suites PASS (28 prior + `regress_layout_pairs` +
`regress_ui_parity_fixes`), executed back-to-back on the current
working tree after all fixes above. The 9 tkinter-needing suites are
out of scope in this no-GUI session — explicitly not counted.

## 40. win32app audit (same day, divergences closed)

`win32app.py` is an intentionally-orphan reference entry point (wiring
test expects it), not the production path — both divergences closed
same-day (headless-safe, no GUI run):

- `_font_handle("Tahoma", 9)` (wrong font — native is **MS Shell Dlg
  8pt**) was dead code with no callers: deleted rather than fixed.
- `_translate` hardcoded `do_translate("google", text, "vi")` — now
  reads combos 1001/1002 via `_combo_text` (`CB_GETCURSEL` +
  `CB_GETLBTEXT`, mapped to codes), passing `src=`/`tgt=` through.
- Geometry is now correct post-fix (595×376 — the height arithmetic was itself fixed 2026-10-16: `/8` vertically, not `/4`).
- Pinned by `regress_ui_parity_fixes` §4 (4 checks).

## 41. headless.py audit (same day, no changes needed)

- Playwright/Chromium fetch fallback for JS-challenge-walled providers
  (WordReference Anubis wall) — the port's answer to F13 (no bundled
  JS engine): real browser only where urllib cannot reach.
- No fixes required.

## 42. updater.py audit (same day, no changes needed)

- `parse_manifest` reads exactly the byte-verified key set
  (`urls[{href,provider}]`, `version`, `date`, `changelog` + trailing
  history list), tolerant to missing fields, no network.
- No fixes required. With this, every module in `qtranslate/` has been
  audited this session.

## 43. Service strip audit (same day, no changes needed)

- Icons loaded from `Services/<Name>/Service.ico` (same derivation
  as the plugin loader + dict-card icon slot), short-text fallback,
  middle-click (open page) / right-click (multi-select) handlers, key
  bindings mirror help.txt Main window hotkeys.
- No fixes required.

## 44. RE-closed + ported: auto_detect / AlwaysDetectLanguage (same day)

RE decision (from the image, not inferred): the nav-menu item 0x808e
"Always detect language" (`FUN_0042dc18`) writes global
`DAT_0054941f` (check-marked via `FUN_00404014`, toggled in
`FUN_00430c52` case 0x808e, gated on `DAT_005493e8`). The
orchestrator `FUN_00404a12` packs that byte into `FUN_004606ba`,
whose **first branch** (`param_2 != 0`, concrete source) runs detect
(`FUN_0045fde8`) and overwrites the source — so the flag forces
detection even when the source is already concrete. The Options-page
byte at `DAT_005494e6` is a red herring: it drives the
collapse-whitespace `FUN_004046d6` (`\r\n`→space), i.e. it is
**RemoveLineBreaks**, not the detect flag.

Port fix (working tree): `do_translate` now reads `auto_detect` —
`src == "auto"` forces detection when the flag is set (not only when
the service lacks the `usesAutoDetectCode` hook), and a concrete `src`
is re-detected when the flag is set. Pinned by two new static checks
in `regress_provider_auto`.

## 45. Provider adapter audit (same day, no changes needed)

All 10 translate providers re-checked at the adapter-contract level:
google (tk+tkk), microsoft/bing (shared jar + tlookupv3 chain), deepl
(indices/codes), yandex (chunker + app_id), naver (tuple contract +
legacy fallback), youdao (`translate_web` live, legacy `translate_o`
kept as dead code), promt (session+pageLoad, exceptions propagate),
babylon (builder kept for a retired host — dead ≠ deleted), reverso
(port-added API, sourced), baidu (session-token gated, fail→fallback).
11 dict lookups share one `(word, sl, tl)` signature through DICTS
(tables re-verified: 11 × 76 entries + spot values, multitran arg
order pinned).
No fixes required.

## 46. Wiring to the engine (why this matters for the migration)

The same four keys this page writes are what `registry.router_order()`
and the dict task read at translate time. Before the migration slice,
the router used a hardcoded 5-name order and ignored three of the four
keys entirely — the page *looked* functional while the engine ignored
it. After the slice, the page → Options.json → engine chain is closed:
reorder here changes fallback order for real (pinned by
`tests/regress_router_order.py`).
