# SPEC: Port giao diện QTranslate 6.10 (Windows) sang Python + PySide6

> Đính kèm file `qtranslate_style.py`. Dùng nguyên văn, không viết lại style.
> Mọi số đo ở đây lấy từ pixel ảnh gốc. Mục "CHƯA CHẮC" ở cuối liệt kê chỗ còn là ước lượng.

## 0. Luật cứng
1. Python 3 + PySide6. CẤM tkinter/ttk/customtkinter.
2. Gọi `apply_style(app)` từ `qtranslate_style.py`. KHÔNG tự `setStyle`/`setPalette`/`setStyleSheet` toàn cục lần nữa.
3. **Fusion mặc định KHÔNG khớp ảnh gốc** (viền #ababab, checkbox đen-trắng). Đừng tin "Fusion + palette là đủ". Style trong file đã được kiểm lại bằng pixel.
4. Mọi widget đặt bằng toạ độ cố định (`setGeometry(l, t, w, h)`), KHÔNG dùng layout tự co giãn. Toạ độ ở dưới là toạ độ trong vùng client của cửa sổ.
5. Chỉ dùng màu trong bảng token. Cấm hex ngoài bảng.
6. Title bar, nút min/max/close, tray menu: của OS/Qt, không tự vẽ.
7. Màu cam/xanh lạ trong ảnh gốc (#ffdb8f, #39398f, #db8f39, #dbffff...) là ClearType, BỎ QUA.
8. Phần KHÔNG thuộc QTranslate: nền editor #1e1e1e, status bar #007acc, taskbar.
9. Thiếu dữ liệu thì HỎI, không đoán. Không thêm tính năng, nút, màu không có trong spec.

## 1. Token (đã đo)
| Token | Hex | Dùng cho |
|---|---|---|
| FACE | #f0f0f0 | nền cửa sổ, dialog, toolbar |
| WINDOW | #ffffff | ô nhập, list, pane dịch |
| BORDER | #7e7e7e | viền 1px mọi control |
| TEXT | #000000 | chữ |
| DIM | #6d6d6d | chữ/icon disabled |
| ACCENT | #0078d7 | hàng được chọn (chữ trắng) |
| CHECK | #005eb8 | checkbox TRONG list (Services, Languages) |
| THUMB | #858585 | thumb scrollbar (mảnh, 2px) |
| COLSEP | #e5e5e5 | đường kẻ cột header |
| BTN | #fff → #e3e3e3 → #d3d3d3 → #cacaca | gradient nút (mục 2.1) |
| ARROW/TICK | #191919 | mũi tên combobox, dấu tick checkbox thường |
| CB fill | #e1e1e1 → #d8d8d8 | nền checkbox thường |
| DIS_BG | #e1e1e1 | nút disabled (chữ #6d6d6d) |
| POPUP | bg #d0d0d0, viền #53606c, icon #3a3a3a, chữ #040404 | popup Ctrl+Q |
| MENU | bg #f9f9f9, viền #e5e5e5, sep #d7d7d7 | tray menu |
| TITLEBAR | #eff4f9 | title bar Win11 (OS vẽ) |
| STRIP | #dedede → #dadada, viền #7e7e7e | 9 nút dịch vụ ở đáy main window |
| STRIP_SEL | #b0b0b0, viền #737373 | nút dịch vụ ĐANG CHỌN |
| LINK | #0066cc | link "Google", "Register here..." — ĐO ĐƯỢC (ảnh gốc: 0,102,204) |
| HEADING | #005eb8 (ước lượng) | tiêu đề section trong Services; đường kẻ #b5c9e0 |

Font: **Tahoma 8pt (11px)** cho mọi control; **Tahoma 9pt (12px)** cho HAI khung
text của main window (source + result). **ĐO ĐƯỢC 2026-10-22.**

Cách đo: so BỀ RỘNG INK và PITCH DÒNG của chữ trong ảnh gốc với ứng viên
đo bằng `QFontMetrics`:
- Main window, dòng "Global hotkeys (default values):" — ảnh gốc rộng **170px**,
  pitch dòng **14px**. Tahoma 9pt: 172px / 14px ✓. Tahoma 8pt: 153px / 13px ✗.
  Segoe UI 9pt: 158px / 16px ✗.
- Main window, dòng "Double Ctrl => Show main window (with translation of
  selected text, if any)" — ảnh gốc **418px**. Tahoma 9pt: 420 ✓, 8pt: 363 ✗.
- Main window, dòng "No data returned (timeout while sending data)." (khung
  result) — ảnh gốc **260px**. Tahoma 9pt: 262 ✓.
- Options, nhãn "Keyboard layout indicator:" — ảnh gốc **125px**. Tahoma 8pt:
  127 ✓, Segoe UI 8pt: 135 ✗, Tahoma 9pt: 142 ✗.

Font đoán trước đây (Segoe UI 9pt) SAI. Sửa tại `qtranslate_style.py`:
`FONT_FAMILY = "Tahoma"`, `FONT_SIZE = 11`, và `PANE_FONT = QFont("Tahoma", 9)`
cho hai `QTextEdit` của main window (đặt qua `document().setDefaultFont`,
vì QSS không set được font của document).

Hai khung text dùng font 9pt vì native vẽ chúng bằng font lớn hơn: "MS Shell
Dlg" 8pt cho control, nhưng edit control của native nhận font 9pt.

## 2. Công thức từng widget (đã render offscreen và so pixel)
### 2.1 Nút (QPushButton), cao 21px
Cột pixel từ trên xuống phải ĐÚNG như sau: `#7e7e7e` (viền) → `#ffffff` → `#e3e3e3` … `#d3d3d3` (giảm dần ~1 mức/hàng) → `#cacaca` → `#7e7e7e` (viền). Bo góc 2px. Dưới nút ngoài cùng có 1px `#fcfcfc` làm bóng nhẹ: QSS không vẽ được, bỏ qua trừ khi cần khớp tuyệt đối.
Nút disabled: nền #e1e1e1 phẳng, chữ #6d6d6d, không gradient.
Kiểm tra bằng số: **nút OK trong Options cao đúng 21px, các hàng như trên**.

### 2.2 Combobox (QComboBox), cao 20–21px
Cùng kiểu nút. Mũi tên là **hai tam giác đặc xếp dọc** (không phải ▼): trên 1-3-5px rộng, cách 2 hàng, dưới 5-3-1px rộng; màu #191919; tâm cách mép phải ngoài ~6px. Combobox disabled (ô HTTP): nền #f0f0f0, viền và chữ #6d6d6d.

### 2.3 Checkbox
- **Checkbox thường** (Appearance, Advanced, Exceptions, Hotkeys, Updates): 13×13, viền #7e7e7e, nền gradient #e1e1e1→#d8d8d8 (cả khi chưa tick), dấu tick ĐEN #191919.
- **Checkbox trong list** (Services, Languages): 13×13, khi tick nền và viền #005eb8, dấu tick TRẮNG; chưa tick: nền trắng, viền #7e7e7e.
- Nhãn cách hộp 5px (hộp x=160 → nhãn x=178).

### 2.4 Group box (class `EtchedGroupBox`)
Khung khắc nổi Win32: viền 1px #7e7e7e kèm 1px trắng lệch (+1,+1). Tiêu đề nằm ĐÈ lên đường viền trên, bắt đầu cách mép trái 9px, nền FACE.

### 2.5 Ô nhập, list, bảng
Viền 1px #7e7e7e, nền trắng, góc vuông. Ô disabled: nền FACE, viền và chữ #6d6d6d.

### 2.6 Scrollbar
Mảnh: thumb 2px #858585 trên track FACE, không có nút mũi tên. Riêng Dictionary: track #f9f9f9, mũi tên chevron ⌃/⌄ xám ở hai đầu.

### 2.7 Splitter ngang (cửa sổ chính)
Cao 6px: viền 1px #7e7e7e ở trên và dưới, giữa có 3 chấm grip.

## 3. Cửa sổ chính (516×423)
| y | Vùng | Chi tiết |
|---|---|---|
| 0–30 | Title bar | OS vẽ. Icon tròn xám + "QTranslate" |
| 30–59 | Toolbar | nền FACE. Nút ◀ (x4, 24×22) ▶ (x30), chữ/mũi tên DIM. Link "Google" x62. Icon ⋮ x≈500. Kẻ dưới y=59 |
| 60–210 | Pane trên | trắng, padding 3px 6px, dòng 14px. Scrollbar mảnh phải. Icon mic (x451,y129), tai nghe (x472,y129) |
| 211–217 | Splitter | xem 2.7 |
| 217–237 | Hàng control (cao 21) | nút new-doc x4 w31 · ⋮ x41 · combo nguồn "Auto-Detect" x67 w150 · nút ⇄ x223 w27 · combo đích "Vietnamese" x256 w177 · nút "Translate" x438 w73. Kẻ dưới y=242 |
| 243–391 | Pane dưới | trắng. Tai nghe (x472,y125 trong pane). Hiển thị kết quả/lỗi |
| 392–423 | Thanh provider | kẻ trên y=392. 9 tab cao 22px (y397–418), rộng 57, bắt đầu x4: Go… Mi… Pr… Ba… Ya… yo… Ba… Pa… DeepL. Mỗi tab: icon 12px + nhãn bị cắt, kiểu nút |
Phím: Ctrl+Enter dịch · Ctrl+N xoá bản dịch.
Phím toàn cục: Double Ctrl hiện cửa sổ chính · Ctrl+Q popup · Ctrl+Shift+Q từ điển · Ctrl+E đọc · Alt+W thay chữ đang chọn.

## 4. Popup Ctrl+Q (200×68)
`Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint`. Nền #d0d0d0, viền 1px #53606c, góc vuông.
Hàng toolbar cao 24px, padding 6px, cách nhau 7px: ✕ · "English to Viet…" (cắt ellipsis) · ★ · 📖 · 🎧 · ⧉ · "tā". Icon màu #3a3a3a. Bản dịch ở y=30, x=6, chữ #040404, 12px.
Vị trí: ngay dưới-phải đoạn text đang chọn, kẹp trong màn hình. Đóng bằng Esc, click ngoài hoặc ✕.

## 5. Options (dialog 646×389; riêng trang Hotkeys ảnh gốc là 663×388, xem 5.8)
Khung chung: title bar OS, "Options". Sidebar listbox (5,30) 141×323, viền #7e7e7e, nền trắng; 9 mục cao 13px, mục đầu cách trên 1px: Basics, Hotkeys, Internet, Services, Languages, Appearance, Exceptions, Advanced, Updates. Mục chọn: nền #0078d7, chữ trắng.
Footer: OK (404,364) · Cancel (484,364) · Apply (565,364), mỗi nút 73×21, Apply disabled.

### 5.1 Internet
- Group "Connection" (152,35) 484×45: nhãn "Timeout, sec:" (157,59); combo (375,50) 255 rộng, giá trị "10".
- Group "Proxy" (152,91) 484×101: combo (157,105) 470 "Use system proxy settings"; combo disabled (162,134) 78 "HTTP"; ô disabled (248,134) 277 rộng; ô disabled "0" (532,134) 95; hai ô disabled (248,160) và (441,160), mỗi ô 186.

### 5.2 Services
List (155,31) 481×272, viền #7e7e7e. Trong list, toạ độ tương đối: tiêu đề "Translation" (13,5) màu HEADING + đường kẻ ngang từ x77, dài 376. Mục cách nhau 18px, bắt đầu y25: checkbox xanh x5, icon 14px x21, nhãn x38. Provider: Google, Microsoft, Promt, Babylon, Yandex, youdao, Baidu, Papago, DeepL (tất cả tick). Tiêu đề "Dictionary" tại y191, mục bắt đầu y212: Google Search, WordReference, Babylon Dictionary, Wikipedia (bị cắt). Scrollbar dọc thumb x471,y17,cao157.
Nút dưới list y=309: ▲ (157, w24, disabled) · ▼ (187, w24, disabled) · "Add dictionary…" (219, w117) · "Remove dictionary" (342, w118, chữ DIM).

### 5.3 Languages
List (155,31) 481×272. 4 cột, 18 hàng, hàng cao 14px, hàng đầu y2, hộp x=3/129.5/256/382.5, nhãn cách hộp 16px. Tất cả tick (xanh). Thanh cuộn ngang thumb (18,262) 238×2. Nút "Check / Uncheck all" (155,308) 481×21.
Cột 1: Afrikaans, Albanian, Arabic, Armenian, Azerbaijani, Basque, Belarusian, Bengali, Bulgarian, Catalan, Chinese (Simplified), Chinese (Traditional), Croatian, Czech, Danish, Dutch, English, Esperanto.
Cột 2: Estonian, Filipino, Finnish, French, Galician, Georgian, German, Greek, Haitian Creole, Hebrew, Hindi, Hmong, Hungarian, Icelandic, Indonesian, Irish, Italian, Japanese.
Cột 3: Kannada, Kazakh, Khmer, Korean, Lao, Latin, Latvian, Lithuanian, Macedonian, Malay, Maltese, Marathi, Mongolian, Norwegian, Persian, Polish, Portuguese, Romanian.
Cột 4: Russian, Serbian, Sinhala, Slovak, Slovenian, Spanish, Swahili, Swedish, Tajik, Tamil, Tatar, Telugu, Thai, Turkish, Ukrainian, Urdu, Uzbek, Vietnamese.

### 5.4 Appearance
Group "General" (152,35) 484×56: checkbox "Enable window style" (tâm y55, chưa tick); nhãn "Theme:" (157,77); combo (397,68) 233 "--- Default ---".
Group "Popup window" (152,98) 484×226. Checkbox tâm y: Enable auto size 122 ✓ · Enable auto position 144 ✓ · Activate when opened 167 · Pin when dragging 190 ✓ (hộp x=160).
Nhãn x=157, tâm y: "Auto-hide delay:" 213 · "Transparency (0 - 90):" 237 · "Frame thickness:" 261 · "Icons:" 286 · "Background color:" 313.
Combo "5" (397,204) 115 + chữ "seconds" (523,206); ô nhập "15" (397,227) 233×20; combo "2" (397,252) 233.
Icons: 4 nút toggle 22×22 đang nhấn, x=398/421/444/467, y=275 (sách, tai nghe, copy, "tā").
Hàng màu y=305, cao 17: nhãn "Text color:" (320), swatch #000000 (378) 87 rộng; nhãn "Frame color:" (482), swatch #5d6c7a (549) 78 rộng. Swatch Background color không hiện trong ảnh gốc (xem CHƯA CHẮC).

### 5.5 Exceptions
Combo (155,33) 481 "Disabled for these programs:". Bảng (153,60) 483×221: header "Program Name" (7,5), "Window Class Name" (246,5), kẻ cột x240 #e5e5e5. Hàng cách nhau 17.6px, đầu y25. 7 hàng "* All Programs *" với lớp: SysListView32, SysTreeView32, ListBox, ScrollBar, ComboBox, msctls_hotkey32, ConsoleWindowClass; hàng 8: "mstsc.exe" | "* All Windows *".
Nút y=288: Add (155,w71) · Modify (234,w72) · Delete (314,w72). Checkbox "Enable smart detection" (154, tâm y321, ✓).

### 5.6 Advanced
Group "Advanced" (152,35) 484×178. Nhãn x157 + combo (455, w175, cao 20), tâm y: Default browser 56 "Internet Explorer" · Copy action 80 "Ctrl + C" · Keyboard layout indicator 104 "None" · Preferred domain 128 "com".
Checkbox x160 tâm y: Enable GUI translation 154 · Enable listening to the same text at a slower speed 177 ✓ · Remove line breaks 200.
Group "Mouse mode" (152,224) 484×66: "Enable mouse mode only when Ctrl is pressed" 244 · "Click on system tray icon switches mouse mode" 268 ✓.
Group "API keys" (152,296) 484×54: "OCR API key:" (157,315); ô nhập (387,304) 243×22; link "Register here for free OCR API key" (157,331).

### 5.7 Updates
Checkbox "Automatically check for updates" (161, tâm y44). Ô lớn (153,63) 481×230, viền #7e7e7e. Nút "Check now" (524,300) 110×21.

### 5.8 Hotkeys (ảnh gốc 663×388)
Sidebar (10,28) 142×323. Checkbox "Enable hotkeys" (159,34). Bảng (159,60) 465×251: header "Action" (6,4), "Hotkey" (323,4), kẻ cột x317. 13 hàng cách nhau 17px, đầu y24: Show main window · Show popup window [Ctrl + Q] · Show dictionary window · Show history window · Show keyboard window · Listen to selected text · Copy translation to clipboard · Replace selected text [Alt + W] · Switch mouse mode · Translate clipboard content · Translate clipboard in main window · Translate clipboard in popup window · Dictionary from clipboard. Cột Hotkey x=323. Footer OK/Cancel/Apply ở x=408/489/570, rộng 75, y=361.

## 6. Cửa sổ Dictionary (476×333)
Title bar OS + icon sách. Combo "English" (4,35) 153. Ô tìm kiếm (163,34) 274×21: mũi tên ◀ ▶ xám bên trái, icon kính lúp (x407) và đồng hồ (x427) bên phải. Icon ⋮ (457,36). Vùng nội dung trống nền FACE. Scrollbar dọc (455,60) 19×240, nền #f9f9f9. Thanh tab dưới y=306, cao 21, 11 tab rộng 42 từ x4: G. (đang nhấn, nền #c4c4c4), W, B., W, M., I., R., U., A., y., O.

## 7. Cửa sổ History (476×320)
Title bar OS + icon đồng hồ. Ô tìm (4,34) 467×21 với ✕ đậm bên phải. List (4,61) 467×225: hàng nhóm cao 17px nền FACE: ★ + "person_record" (đậm); hàng con: icon Google 14px + "người_record" (x44,y25). Nút y=294: Clear (4,w73) · Save as… (83,w108) · ★ vàng (197,w20) · OK (398,w73).

## 8. Cửa sổ Keyboard (464×198)
Title bar OS + icon bàn phím. Phím = nút 20px cao. Hàng 1 (y37): Esc x8 w27; F1–F12 w28 tại x = 52, 84, 116, 148 | 196, 228, 260, 292 | 336, 368, 400, 430.
Các hàng khác dải đều từ x8 đến x456, khe 3px, đơn vị rộng ~31px: hàng 2 (y57) ` 1…0 - = BkSp(2) · hàng 3 (y79) Tab(1.5) q…p [ ] \(1.5) · hàng 4 (y100) Caps(1.9) a…l ; ' Enter(2.2) · hàng 5 (y121) Shift(2.3) z…m , . / Shift(2.8) · hàng 6 (y142) Ctrl Win Alt (1.4 mỗi phím) Space(6.3) AltGr Apps (1.5) ^ v < >. Combo "English" (8,169) 150.

## 9. Tray menu (Windows 11, DÙNG QSystemTrayIcon + QMenu)
Thứ tự: **QTranslate** (đậm) · Dictionary · Text recognition · History · Keyboard · Options · About QTranslate · ─── · ✓ Enable global hotkeys (checkable, bật) · Mouse mode ▸ · ─── · Exit. Pitch 22px. Bản gốc là menu native Win11 (bo 8px); bản Qt sẽ khác nhẹ, chấp nhận.

## 10. Nghiệm thu (tự kiểm, không báo xong nếu chưa làm)
1. Chạy từng cửa sổ, `widget.grab().save("out.png")`, so với ảnh gốc bằng Pillow ở các điểm: viền nút (#7e7e7e), hàng trắng ngay dưới viền trên, hàng #cacaca ngay trên viền dưới, tâm mũi tên combobox, màu checkbox thường (xám, tick đen) và trong list (xanh, tick trắng).
2. Nút OK Options cao đúng 21px, tại (404,364).
3. Không còn hex ngoài bảng token (grep).
4. Báo rõ chỗ nào chưa khớp, không giấu.

## CHƯA CHẮC (hỏi, đừng đoán)
- ~~Font Segoe UI 9pt chưa đo được~~ → ĐÃ ĐO: Tahoma 8pt cho control,
  Tahoma 9pt cho hai khung text của main window (xem mục 1).
- LINK #0066cc và HEADING #005eb8 là ước lượng.
- Màu nút khi nhấn (#c9c9c9 → #d4d4d4) là ước lượng: ảnh gốc không có trạng thái pressed.
- Swatch "Background color" trong Appearance không hiện trong ảnh (có thể là #d0d0d0).
- Dialog Options có hai kích thước (663×388 và 646×389): cần chọn một.
- Trang Basics chưa có ảnh.
- Icon provider, icon toolbar chưa có asset gốc; cắt từ ảnh hoặc dùng icon đơn giản cùng nét.
- 1px bóng #fcfcfc dưới nút và dưới combobox: chưa tái hiện được bằng QSS.
