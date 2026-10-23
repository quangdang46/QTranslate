# FEATURE CHECKLIST — kiểm thử thực tế từng feature

Ghi ngày: **2026-10-23**. Commit đã kiểm kê: `e60fc6e` (`main`, working
tree sạch). Suite tự động: **134 suites, 0 failed** (chạy lại trên đúng
commit này, 23/10/2026, exit code 0). Pixel-parity: **0.0037 trên 12 màn
hình**. Docs-consistency: **0 findings**.

Quy tắc đọc:

- `PASS` chỉ khi đã chạy và có bằng chứng đi kèm. Không được đổi `PASS`
  chỉ vì module import được hoặc mock test xanh.
- `NEED` là việc còn phải làm bằng thao tác thật (desktop GUI, mạng,
  âm thanh, thiết bị). `BLOCKED` ghi rõ lý do.
- Mỗi mục đều có đường dẫn test đã chạy; mục nào `NEED` ở cột test thật
  là chưa đủ bằng chứng trên commit hiện tại.

---

## A. Translation engine

| ID | Feature | Đường code | Test đã chạy | Trạng thái trên `e60fc6e` |
|---|---|---|---|---|
| A01 | Dịch từ cửa sổ chính (Translate) | `qtranslate/qt/app.py` `on_go` | `regress_app_reliability_e2e.py` (10) lái `app.on_go()` với provider rigged | PASS offline |
| A02 | Chọn ngôn ngữ nguồn | `set_source_by_name`, combo `cmb_src` | `regress_source_language.py` (13) | PASS offline |
| A03 | Chọn ngôn ngữ đích | `set_target_by_name`, combo `cmb_tgt` | `regress_qt_features.py` (83) | PASS offline |
| A04 | Auto Detect | `registry.detect_language` qua `_USES_AUTO_DETECT` | `regress_source_language.py`, `regress_provider_auto.py` (g9 A) | PASS offline |
| A05 | Swap nguồn/đích | `on_swap` | `regress_qt_features.py` | PASS offline |
| A06 | Dịch bằng dịch vụ được chọn | `engine.translate` + `registry.TRANSLATORS` | `regress_engine.py`, `regress_router_order.py` | PASS offline (mock/provider rigged) |
| A07/A08 | Thứ tự ưu tiên + router chain | `reliability.py` ProviderRouter | `regress_reliability.py` | PASS offline |
| A09 | Fallback khi provider chính lỗi | `engine.translate` fallback chain | `regress_app_reliability_e2e.py` (fallback case) | PASS offline |
| A10 | Lỗi khi tất cả provider fail: hiện native error string, không giả vờ thành công | `engine.translate` → `Result.provider_used=""` | `regress_app_reliability_e2e.py` (lỗi `Result.ok` đã sửa 23/10) | PASS offline |
| A11 | Back Translation | `engine._run_back_translate` | `tests/regress_*back*`, `regress_translate_response_chain.py` | PASS offline (mock) |
| A12 | Hiển thị provider đã trả kết quả + lỗi liên quan | `res.provider_used` → result pane, `res.failures` → note | `regress_app_reliability_e2e.py` | PASS offline |
| A13 | Unicode (tiếng Việt có dấu, non-Latin) | toàn chuỗi engine→pane | `regress_common_fuzz.py`, `regress_unquote_html.py` | PASS offline |
| A14 | Input rỗng/khoảng trắng/văn bản dài/nhiều dòng/ký tự đặc biệt | `engine.translate` edge branches | `regress_translate_errors.py`, `regress_common_fuzz.py` | PASS offline |
| A15 | Dịch nhanh qua popup không qua cửa sổ chính | `hotkey_popup` → `show_translation` | `regress_popup_smoke.py` (20), `regress_qt_features.py` (stub popup) | **NEED** kiểm chứng trong ứng dụng thật (popup thật + clipboard thật) |
| A16 | Replace Selection (Alt+W) | `hotkey_replace_selection` | `regress_sendkeys.py` (wrapper pin) | **NEED** kiểm thử thay thế thật trong app ngoài |

### A17–A25. Providers (mỗi cái kiểm live riêng)

| ID | Provider | Test contract | Trạng thái trên `e60fc6e` |
|---|---|---|---|
| A17 | Google | `regress_google_tk.py`, `regress_tkk_markers.py`, chain/response suites | Endpoint sống theo audit gần nhất; **NEED** live re-check |
| A18 | DeepL | `regress_deepl_payload.py` | Endpoint sống theo audit gần nhất; **NEED** live re-check |
| A19 | Yandex | `regress_yandex_disk.py`, `regress_service_lang_tables.py` | Endpoint sống theo audit gần nhất; **NEED** live re-check |
| A20 | Baidu | `regress_baidu_sign.py` | PASS offline (sign); **NEED** live |
| A21 | Naver/Papago | `regress_naver_auth.py` | PASS offline; **NEED** live |
| A22 | Youdao | `regress_youdao_sign.py` | PASS offline (sign); **NEED** live |
| A23 | Microsoft/Bing | `regress_microsoft_request.py`, `regress_microsoft_chain.py` | **DEAD BY EVIDENCE** — endpoint trả `{"statusCode":400}` cho đúng request native build; port báo empty thay vì crash (`KeyError: 0` đã sửa) |
| A24 | PROMT | `regress_promt_hash.py`, `regress_promt_pageload.py` | PASS offline; **NEED** live |
| A25 | Babylon | `regress_dict_uri_native.py` + babylon rows trong `ui_match.py` (`babylon-id/langs/host/error-path`) | **DEAD** theo audit (endpoint chết); trả lỗi rõ ràng |

---

## B. Text capture (Bôi đen / Clipboard / Ctrl+Q)

| ID | Feature | Đường code | Test đã chạy | Trạng thái trên `e60fc6e` |
|---|---|---|---|---|
| B01/B03 | Đọc selection qua mouse capture/OLEACC | `qtranslate/mouse_capture.py`, `cursor_text` | `regress_mouse_capture.py` (42), `regress_mouse_capture_c8.py`, `regress_oleacc_contract.py` | PASS offline (contract + stub) |
| B02 | Đọc qua Clipboard | `clipboard.read_text` | `regress_clipboard.py` | PASS |
| B04 | Gửi Ctrl+C khi cần | `selection.copy_selection` → `sendkeys.send("ctrl+c")` | `regress_selection_capture.py` (15) | PASS offline (seam-injected) |
| B05 | Ctrl+Q đọc đúng văn bản đang chọn | `hotkey_popup` → `selection.copy_selection` → fallback `_clipboard_text` | `regress_selection_capture.py`, `regress_qt_features.py` (Ctrl+Q dùng `copy_selection` stub, reject stale clipboard) | PASS offline; **NEED** thao tác thật ngoài app |
| B06 | Fallback sang clipboard khi không lấy được selection | `if not text: _clipboard_text()` | cùng các suite trên | PASS offline |
| B07 | Không lấy nhầm clipboard cũ | sequence-number poll, không fixed sleep | `regress_selection_capture.py` (slow-copy wait) | PASS offline |
| B08 | Không mất focus/nhập nhầm ký tự | native chờ modifier thả ra trước (alt/shift loop) | `regress_selection_capture.py` (held-modifier) | PASS offline (logic); **NEED** desktop thật |
| B09 | Hoạt động với nhiều app khác nhau | — | — | **NOT TESTED** — cần người rà Notepad/browser/editor |
| B10 | Selection rỗng / app không cho copy | trả `""` → báo không có gì để dịch | `regress_selection_capture.py` (refused Ctrl+C) | PASS offline |

---

## C. Popup dịch nhanh

| ID | Feature | Đường code | Test đã chạy | Trạng thái trên `e60fc6e` |
|---|---|---|---|---|
| C01 | Mở bằng Ctrl+Q | `hotkey_popup` + `hotkeys.install` (queued `_on_ui`) | `regress_popup_smoke.py` (hotkey→popup chain), `regress_hotkey_coverage.py` | PASS offline |
| C02 | Hiển thị đúng nguồn + kết quả | `PopupWindow.set_text(src,res,pair)` | `ui_match.py` popup-*, `regress_qt_features.py` popup bounds | PASS offline (layout+text) |
| C03 | Hiện gần con trỏ theo `PopupAutoPos` | `PopupWindow.place()` | `regress_popup_smoke.py` (`QCursor.pos()` pin) | PASS (code pin); **NEED** desktop thật |
| C04 | Tự co giãn theo nội dung, có giới hạn | `_wanted_width`/`_measure`, `MIN_WIDTH=220`/`MAX_WIDTH=598` | `ui_match.py` (bounded/grows/clamped), `regress_popup_smoke.py`, `regress_qt_features.py` | PASS |
| C05 | Không tràn màn hình ở mép | clamp + `place()` | code có, chưa có test vị trí mép | **NEED** |
| C06 | Nhiều màn hình | `QCursor.pos()` + screen geometry | — | **NOT TESTED** |
| C07 | Transparency (mặc định 217) | `setWindowOpacity(217/255)` | `regress_popup_smoke.py`, `regress_screens.py` (default pin) | PASS offline |
| C08 | Timeout tự đóng | `PopupTimeout` + QTimer | `regress_popup_smoke.py` | PASS offline |
| C09 | Pin/drag popup | `PopupPinWhenDragging` | — | **NEED** kiểm thủ công |
| C10 | Icon/header (⭐📖🎧⧉tā — nay là 5 pixmap RT_ICON) | `_header_icons`, manifest `book/copy/translit` | render đối chiếu 2 ảnh native 2162/2163 (xem PROGRESS 23/10) | PASS (visual review, thủ công) |
| C11 | Double-click header mở main window | `help.txt:33`; `show_popup` wiring | — | **NEED** |
| C12 | Không treo UI khi mạng chậm | dịch trong `_translate` (sync) | **CHƯA** — còn sync trên UI thread | **NEED** (đo rồi mới sửa; không mù quáng bỏ fallback) |
| C13 | Extension render popup body | `("popup","body")` slot + `_extension_body` | `regress_qt_extension_ui.py` (34) | PASS |

---

## D. Mouse mode

| ID | Feature | Đường code | Test | Trạng thái |
|---|---|---|---|---|
| D01–D03 | 3 modes đúng tên native | `tray.MOUSE_MODES` | `regress_qt_features.py` (`MOUSE_MODES == (...)`) | PASS |
| D04/D05 | Bật/tắt + chuyển từ tray | `set_mouse_mode`, config `MouseMode/MouseModeOn` | `regress_qt_features.py` (save/start/stop) | PASS offline |
| D06 | Hotkey switch mouse mode | `hotkey_switch_mouse_mode` | `regress_hotkey_coverage.py` | PASS offline (registration) |
| D07–D10 | Capture thật ngoài app, no-repeat loop, persistence | `_mouse_work`, `_capture_selection` | `regress_mouse_capture.py` | PASS offline; **NEED** desktop thật + restart persistence check |

---

## E. Dictionary (11 providers)

Contract: `regress_dict_registry_complete.py`, `regress_dict_lang_tables.py`, `regress_dict_response_chain.py`, `regress_dict_uri_native.py`, `regress_dict_card*.py`, `regress_xdxf_*.py`, `smoke_dict.py` — tất cả xanh trên `e60fc6e`.

| ID | Provider | Trạng thái |
|---|---|---|
| E01 Oxford | UI wired | PASS offline; **NEED** live |
| E02 Lingvo | UI wired | PASS offline; **NEED** live |
| E03 Urban | UI wired | PASS offline; **NEED** live |
| E04 Wikipedia | UI wired | PASS offline; **NEED** live |
| E05 Multitran | UI wired | PASS offline; **NEED** live |
| E06 WordReference | cần Playwright Chromium (optional) | **BLOCKED** — thiếu dep |
| E07 Reverso | UI wired | PASS offline; **NEED** live |
| E08 Babylon dict | DEAD endpoint (như translator) | **DEAD BY EVIDENCE** |
| E09 ImTranslator | DEAD endpoint theo audit | **DEAD BY EVIDENCE** |
| E10 Google Search | DEAD theo audit | **DEAD BY EVIDENCE** |
| E11 Youdao dict | UI wired | PASS offline; **NEED** live |

E12–E23 (mở window, tra từ, HTML render, XDXF offline-first, zoom, entry points từ tray/hotkey): `regress_dict_card_native.py`, `regress_dictionary_html.py`, `regress_xdxf_render.py`, `regress_qt_features.py` — PASS offline; **NEED** thao tác thật cho E16/E17/E22.

---

## F. History

| ID | Feature | Test | Trạng thái |
|---|---|---|---|
| F01–F05 | Lưu lượt dịch + restore + AutoDetect src | `regress_history_dispatch.py`, `regress_enable_history.py`, `regress_qt_features.py` | PASS |
| F06/F07 | Khôi phục vào main / xóa | `regress_qt_features.py` (history lifecycle) | PASS offline |
| F08 | Persist qua restart | `regress_history_export.py`, `regress_session*.py` | PASS |
| F09/F10 | Export + Unicode | `regress_history_export.py` | PASS |
| F11–F13 | Back-translation entries, file hỏng, bulk/dup/long | `regress_history_export.py`, fuzz suites | PASS offline |

---

## G. OCR

| ID | Feature | Test | Trạng thái |
|---|---|---|---|
| G01–G04 | Overlay chọn vùng, preview | `qtranslate/qt/ocr_pick.py`, `regress_qt_features.py` | PASS offline |
| G05/G06 | Gửi ảnh → nhận text | `regress_ocr_multipart.py`, `regress_ocr_languages.py` | PASS offline (request shape); **NEED** live OCR + API key |
| G07/G08 | Dịch sau OCR, ngôn ngữ OCR | `services.ocr.ocr_text` + `OCR_EXT` | PASS offline |
| G11/G12 | multipart + API key từ settings | `regress_ocr_multipart.py` | PASS offline |
| G13–G15 | key thiếu/sai, ảnh lỗi, bundle | `regress_updater.py`-style error paths | **NEED** live + bundle check |

---

## H. Virtual Keyboard

`regress_sapi_and_keyboard.py` (19): full key grid incl. number row +
punctuation, pinned vì port tkinter cũ từng thiếu. **PASS trên
`e60fc6e`.** H03–H08 (gõ thật vào ô nhập, Shift, focus): **NEED**
desktop.

## I. TTS

| ID | Feature | Test | Trạng thái |
|---|---|---|---|
| I01–I04 | Đọc nguồn/dịch, nút + hotkey | `regress_player.py`, `regress_tts_request.py`, `regress_tts_slow.py` | PASS offline (request/backend selection) |
| I05 | Slow mode | `regress_tts_slow.py` | PASS |
| I06–I08 | Provider/lang, thiếu voice, text rỗng/dài | `regress_player.py` (extension fallback), `regress_reliability*` | PASS offline; **âm thanh thật: NOT TESTED** |
| I09–I11 | Không đọc nhầm nguồn↔đích, Google romanization, extension TTS | `regress_google_romanization.py`, `regress_extension_capabilities.py` | PASS offline |

BASS/SAPI: `tests/live_bass.py` tồn tại cho live check thủ công; không
chạy tự động.

## J. Speech input / spell / phonetics

| Feature | Test | Trạng thái |
|---|---|---|
| J01–J03 Speech input | `regress_speech_input.py` (+ adapter `needs-permission`) | PASS offline (contract); **mic thật: NOT TESTED** |
| J04–J07 Spell check + suggest | `regress_spell_request.py`, `regress_spell_headers.py`, `SPELL_EXT` trong `regress_extension_capabilities.py` | PASS offline; **NEED** live |
| J08 Phonetics/romanization | `regress_phonetics.py`, `regress_google_romanization.py` | PASS |
| J09 Convert layout hotkey | `regress_hotkey_coverage.py` | PASS (registration) |

---

## K. Hotkeys (17 actions)

`regress_hotkey_decode.py` (17-key codec), `regress_hotkey_coverage.py`
(all wired), `regress_hotkey_option_keys.py`, `regress_qt_combo_popup.py`
(15) — **PASS**. K18–K25 (đổi/xóa/trùng/modifier/minimize/layout):
`regress_options_roundtrip.py` + `regress_hotkey_option_keys.py` PASS
offline. **K23** (no cross-thread widget touch): PASS qua `_UiInvoker`
(`regress_qt_features.py`). **K24** (hotkey khi app khác focus):
**NEED** desktop thật.

## L. Tray

`regress_tray_menu.py`, `regress_tray_state.py`, `regress_exclusions.py`
— **PASS**. L01/L02/L12/L13 (icon hiện, right-click, double-click,
exit), L16 (no-tray OS): **NEED** desktop thật. L15 (extension tray
action): PASS (`regress_qt_extension_ui.py`).

## M. Main window

`ui_match.py` main-* + `tools/render_qt.py --compare` (mean 0.0037, 12
screens) — **PASS**. M05–M15 (copy, replace, focus/tab, minimize,
placement restore, rapid-switch): `regress_placement.py`,
`regress_qt_features.py` PASS offline; **NEED** thao tác thật cho
focus/tab/đa độ phân giải.

## N. Options (9 trang)

`regress_options_roundtrip.py`, `regress_proxy_options.py`,
`regress_dlg129_spec.py` (+ `tools/dlg_parse.py`), `ui_match.py`
pages-9/order/ids — **PASS**. N01 Basics: mở/lưu được, **so pixel:
BLOCKED** (không có ảnh native — BLOCKERS B4). N02–N09: setting→hành vi
đã pin ở mức code; **NEED** restart-persistence thủ công từng trang.

## O. Config / data / startup

`regress_platforms.py` (paths, DEFAULT_PATH tuyệt đối, ensure_dir),
`regress_session*.py`, `regress_single_instance.py`,
`regress_crash_*.py`, `regress_startup_entry.py`, `regress_cli_args.py`
— **PASS**.

## P. Themes / locale / assets

`regress_theme_all.py`, `regress_theme_colors.py`,
`regress_theme_loader_jsonc.py`, `regress_locale*.py` (36 packs),
`regress_fonts.py`, `regress_extension_theme.py` — **PASS**. P05
(chuyển ngôn ngữ UI), P08 (label tràn): **NEED** visual.

## Q. Extension system (8 capabilities + lifecycle + SDK)

`regress_extensions.py`, `regress_extension_loading.py`,
`regress_extension_e2e.py`, `regress_extension_capabilities.py` (9,
lái đủ 8 capability qua ĐƯỜNG APP THẬT: `engine.translate`,
`sdk.dict_lookup`, `player.play_text`, `ocr_text`, `google_suggest`),
`regress_extension_override.py`, `regress_override_persistence.py`,
`regress_extension_theme.py`, `regress_extension_vendor.py`,
`regress_extension_vendored_dep.py`, `regress_example_extension.py`,
`regress_ui_slots.py`, `regress_qt_extension_ui.py` (34),
`regress_sdk.py`, `regress_sdk_package.py` (22, build wheel + cài venv
sạch) — **PASS**. Q13/Q14/Q18 (extension lỗi không kéo app): PASS.
Q17 (override picker): PASS. Q19 (dep isolation): PASS.
**Còn:** Q21 PyPI publish — **BLOCKED** (D19: cần người verify tên).

## R. Reliability

`regress_reliability.py`, `regress_reliability_audit.py`,
`regress_app_reliability_e2e.py` (10, lái `app.on_go()` thật),
`regress_router_order.py`, `regress_translate_errors.py`,
`regress_request.py`, `regress_net_open.py`, `regress_result_shape.py`,
`regress_core_result*.py` — **PASS**. R14 (UI không treo khi dịch
chậm): **NEED** — còn sync, là việc P1 đã nêu. R15 (đo thời gian từng
giai đoạn): **NOT TESTED** — phải đo trước khi sửa.

## S. Qt UI parity (12/12 màn hình đã chụp)

`tools/render_qt.py --compare`: **mean 0.0037 trên `e60fc6e`**. S07
Basics: **BLOCKED** (thiếu ảnh native). S20 (click không ăn, giá trị
không lưu): S06 tray menu cũng **thiếu ảnh native** (CONTRACT_AUDIT
P2 — evidence exhausted).

## T. Platform / CLI / bundle

| ID | Feature | Test | Trạng thái |
|---|---|---|---|
| T01–T05 | Entry point, CLI args, headless, crash reporter, single-instance | `regress_startup_entry.py`, `regress_cli_args.py`, `regress_crash_*.py`, `regress_single_instance.py`, `SELFTEST 29/29` | PASS |
| T06–T08 | Adapters theo OS, không báo nhầm macOS | `regress_platforms.py` (MacOSAdapter ~ paths, Win32-only → UNAVAILABLE) | PASS offline |
| T09–T13 | Bundle Windows + selftest frozen + đủ module | `tools/build_bundle.py` (frozen-gap check), `regress_startup_entry.py` | PASS lần build gần nhất; **NEED** build lại sau commit `e60fc6e` |
| T14 | Bundle macOS | — | **BLOCKED** — cần máy macOS |
| T15 | Báo rõ unsupported | `UnavailableAdapter` | PASS |

## U. Feature phụ

`regress_encode_uri.py`, `regress_reg_exp_*.py`, `regress_unquote_html.py`,
`regress_parse_json_lenient.py`, `regress_session_markers.py`,
`regress_default_source_header.py`, `regress_exact_search.py`,
`regress_layout_pairs.py` — **PASS**.

---

## Tổng hợp NEED/BLOCKED (không được tự đóng)

| # | Việc | Loại | Cần ai/cái gì |
|---|---|---|---|
| 1 | Bấm Ctrl+Q thật ngoài app, nhiều app | NEED | người + desktop |
| 2 | Popup cạnh chuột/đa màn hình/mép | NEED | người + desktop |
| 3 | Live providers (Google/DeepL/Yandex/...) | NEED | mạng |
| 4 | OCR live + API key | NEED | key |
| 5 | TTS nghe thật / mic thật | NEED | thiết bị âm thanh |
| 6 | Replace selection thật | NEED | người + desktop |
| 7 | Settings restart-persistence từng Options page | NEED | người |
| 8 | Basics + tray menu pixel-compare | BLOCKED | ảnh native (B4) |
| 9 | Bundle lại sau `e60fc6e` | NEED | chạy `build_bundle.py` |
| 10 | macOS build + run | BLOCKED | máy macOS |
| 11 | G9 review + waiver | BLOCKED | người duyệt (không tự gán) |
| 12 | Đo perf từng giai đoạn dịch (R15) rồi mới tối ưu R14 | NEED | chạy đo, không đoán |

Đồng bộ docs: `PROJECT_VISION.md` còn câu cũ "giữ Tkinter / chỉ docs
trong planning" trong khi `HANDOFF.md` đã ghi Qt-only — đã liệt kê ở
`DOC_DRIFT_REPORT` dưới đây, không dùng dòng cũ làm kết luận.

---

# DOC_DRIFT_REPORT (song hành, không thay code)

1. `PROJECT_VISION.md` — còn yêu cầu giữ Tkinter + "planning chỉ docs".
   Thực tế: tkinter đã xóa 23/10, Qt là frontend duy nhất. → cần sửa
   VISION, không phải sửa code.
2. `COMPATIBILITY_MATRIX.md` — nhiều hàng còn `ported` ở nghĩa cũ
   (module tồn tại) trong khi `CONTRACT_AUDIT.md` đã nâng một số lên
   `behaviour-verified` kèm suite. → giữ `ported` cho hàng chưa có
   acceptance test thật, không nâng hàng loạt.
3. `TEST_RESULTS.md` — số suite lịch sử (130/133) là của commit cũ;
   số đúng cho `e60fc6e` là **134 suites, 0 failed** (đã chạy lại).
4. `HANDOFF.md` — là log chạy, không phải source of truth cho trạng
   thái gate; gate xem ở `RE_COVERAGE_CHECKLIST` + `BLOCKERS.md`.
