"""Reference UI for the QTranslate port. LAYOUT ONLY: no logic, no networking.

COORDINATES = pixels in the ORIGINAL SCREENSHOT (which includes the Windows title bar and 1px frame).
Each window class declares ORIGIN = where the client area starts inside that screenshot;
helpers subtract it, so you can copy numbers straight from the screenshots/spec.
  Main/Dictionary/History/Keyboard: ORIGIN (1, 31)    Options: ORIGIN (1, 26)    Options Hotkeys (663x388 shot): (0, 24)

Run  `python qtranslate_ui.py out_dir`  to render every window offscreen to PNG (client area only).
"""
import os, sys
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QLabel, QLineEdit,
                               QPushButton, QWidget)
from qtranslate_style import apply_style

# The layout helpers live in ONE place -- qtranslate.qt.widgets -- so the
# reference renderer and the real windows cannot drift apart.
from qtranslate.qt.widgets import (ACCENT, BORDER, COLSEP, DIM, FACE, HEADING,
                                   HEADING_LINE, LINK, POPUP_BG, POPUP_BORDER,
                                   POPUP_ICON, POPUP_TEXT, TEXT, THUMB, Base,
                                   button, check, combo, field, group, hline,
                                   label, panel, put, rect, sq)


# ---------------------------------------------------------------- Main window (screenshot 516x423)
class MainWindow(Base):
    ORIGIN, SIZE = (1, 31), (514, 391)

    def __init__(self):
        super().__init__()
        b = button(self, 4, 33, 24, "◀", 22); b.setStyleSheet("color:%s" % DIM)
        b = button(self, 30, 33, 24, "▶", 22); b.setStyleSheet("color:%s" % DIM)
        label(self, 62, 45, "Google", color=LINK, underline=True)
        label(self, 497, 45, "⋮")
        hline(self, 59, 1, 515)
        top = rect(self, 1, 60, 514, 151, "#fff", "top")
        txt = ("QTranslate Version  6.10.0\n\nGlobal hotkeys (default values):\n"
               "Double Ctrl => Show main window (with translation of selected text, if any)\n"
               "Ctrl+Q => Translate selected text and show it in popup window\n"
               "Ctrl+Shift+Q => Show dictionary window\nCtrl+E => Listen to selected text\n\n"
               "Main window hotkeys:\nCtrl+Enter => Translate text\nCtrl+N => Clear current translation")
        t = QLabel(txt); t.setStyleSheet("background:transparent;"); t.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        put(self, t, 7, 63, 480, 145)
        rect(self, 502, 62, 2, 40, THUMB)
        label(self, 451, 138, "🎤"); label(self, 472, 138, "🎧")
        hline(self, 211, 1, 515); hline(self, 213, 1, 515); hline(self, 214, 1, 515)
        rect(self, 249, 212, 16, 3, "#555")
        button(self, 4, 217, 31, "▯"); label(self, 41, 227, "⋮")
        combo(self, 67, 217, 150, "Auto-Detect", 21)
        button(self, 223, 217, 27, "⇄")
        combo(self, 256, 217, 177, "Vietnamese", 21)
        button(self, 438, 217, 73, "Translate")
        hline(self, 242, 1, 515)
        rect(self, 1, 243, 514, 149, "#fff", "bot")
        label(self, 7, 254, "No data returned (timeout while sending data).")
        label(self, 472, 380, "🎧")
        hline(self, 392, 1, 515)
        cols = ["#4285f4", "#f5a623", "#2bb673", "#1a73c8", "#e53935", "#d32f2f", "#2d6cdf", "#1dc078", "#0f2b46"]
        for i, (n, c) in enumerate(zip(["Go…", "Mi…", "Pr…", "Ba…", "Ya…", "yo…", "Ba…", "Pa…", "DeepL"], cols)):
            sq(self, 8 + 57 * i, 402, c, 12); button(self, 4 + 57 * i, 397, 57, "      " + n, 22)


# ---------------------------------------------------------------- Dictionary (476x333)
class DictWindow(Base):
    ORIGIN, SIZE = (1, 31), (474, 301)

    def __init__(self):
        super().__init__()
        combo(self, 4, 35, 153, "English", 20)
        f = field(self, 163, 34, 274, 21)
        label(self, 170, 45, "◀ ▶", color=DIM)
        label(self, 408, 45, "⌕"); label(self, 428, 45, "◷"); label(self, 457, 45, "⋮")
        rect(self, 455, 60, 19, 240, "#f9f9f9")
        label(self, 460, 72, "⌃", color=DIM); label(self, 460, 284, "⌄", color=DIM)
        cols = ["#4285f4", "#d9534f", "#1a73c8", "#999999", "#2d6cdf", "#7a3d9e", "#2d6cdf", "#e8890c", "#e53935", "#d33", "#8a8a2a"]
        for i, (n, c) in enumerate(zip(["G.", "W", "B.", "W", "M.", "I.", "R.", "U.", "A.", "y.", "O."], cols)):
            b = button(self, 4 + 42 * i, 306, 42, "     " + n)
            if i == 0: b.setStyleSheet("QPushButton{background:#c4c4c4;}")
            sq(self, 8 + 42 * i, 309, c, 14)


# ---------------------------------------------------------------- History (476x320)
class HistWindow(Base):
    ORIGIN, SIZE = (1, 31), (474, 288)

    def __init__(self):
        super().__init__()
        f = field(self, 4, 34, 467, 21); label(self, 455, 45, "✕", bold=True)
        panel(self, 4, 61, 467, 225)
        rect(self, 5, 63, 465, 17, FACE)
        label(self, 10, 71, "★", color="#555"); label(self, 28, 71, "person_record", bold=True)
        sq(self, 26, 83, "#4285f4"); label(self, 48, 89, "người_record")
        button(self, 4, 294, 73, "Clear"); button(self, 83, 294, 108, "Save as…")
        b = button(self, 197, 294, 20, "★"); b.setStyleSheet("QPushButton{color:#e6c800;padding:0}")
        button(self, 398, 294, 73, "OK")


# ---------------------------------------------------------------- Keyboard (464x198)
class KbdWindow(Base):
    ORIGIN, SIZE = (1, 31), (462, 166)

    def __init__(self):
        super().__init__()
        button(self, 8, 37, 27, "Esc", 20)
        for i, x in enumerate([52, 84, 116, 148, 196, 228, 260, 292, 336, 368, 400, 430]):
            button(self, x, 37, 28, "F%d" % (i + 1), 20)

        def row(y, keys):
            tot = sum(k[1] for k in keys); u = (448 - 3 * (len(keys) - 1)) / tot; x = 8.0
            for lab, w in keys:
                button(self, round(x), y, round(w * u), lab, 20); x += w * u + 3
        R = lambda s: [(k, 1) for k in s.split(" ")]
        row(57, R("` 1 2 3 4 5 6 7 8 9 0 - =") + [("BkSp", 2)])
        row(79, [("Tab", 1.5)] + R("q w e r t y u i o p [ ]") + [("\\", 1.5)])
        row(100, [("Caps", 1.9)] + R("a s d f g h j k l ; '") + [("Enter", 2.2)])
        row(121, [("Shift", 2.3)] + R("z x c v b n m , . /") + [("Shift", 2.8)])
        row(142, [("Ctrl", 1.4), ("Win", 1.4), ("Alt", 1.4), ("", 6.3), ("AltGr", 1.5), ("Apps", 1.5)] + R("^ v < >"))
        combo(self, 8, 169, 150, "English", 20)


# ---------------------------------------------------------------- Options (screenshot 646x389)
SIDEBAR = ["Basics", "Hotkeys", "Internet", "Services", "Languages", "Appearance", "Exceptions", "Advanced", "Updates"]


class OptionsBase(Base):
    ORIGIN, SIZE = (1, 26), (644, 362)
    SEL = 0

    def __init__(self):
        super().__init__()
        panel(self, 5, 30, 141, 323)
        for i, n in enumerate(SIDEBAR):
            q = QLabel(n); q.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            sel = i == self.SEL
            q.setStyleSheet("QLabel{padding-left:2px;background:%s;color:%s;}" % (ACCENT if sel else "transparent", "#fff" if sel else TEXT))
            put(self, q, 6, 31 + i * 13, 139, 13)
        button(self, 404, 364, 73, "OK"); button(self, 484, 364, 73, "Cancel"); button(self, 565, 364, 73, "Apply", enabled=False)
        self.build()

    def build(self): ...


class Internet(OptionsBase):
    SEL = 2

    def build(self):
        group(self, 152, 35, 484, 45, "Connection"); label(self, 157, 59, "Timeout, sec:"); combo(self, 375, 50, 255, "10")
        group(self, 152, 91, 484, 101, "Proxy"); combo(self, 157, 105, 470, "Use system proxy settings")
        c = combo(self, 162, 134, 78, "HTTP", enabled=False)
        field(self, 248, 134, 277, 20, enabled=False); field(self, 532, 134, 95, 20, "0", enabled=False)
        field(self, 248, 160, 186, 20, enabled=False); field(self, 441, 160, 186, 20, enabled=False)


class Services(OptionsBase):
    SEL = 3

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        TR = [("Google", "#4285f4"), ("Microsoft", "#f5a623"), ("Promt", "#2bb673"), ("Babylon", "#1a73c8"), ("Yandex", "#e53935"),
              ("youdao", "#d32f2f"), ("Baidu", "#2d6cdf"), ("Papago", "#1dc078"), ("DeepL", "#0f2b46")]
        DI = [("Google Search", "#4285f4"), ("WordReference", "#d9534f"), ("Babylon Dictionary", "#1a73c8"), ("Wikipedia", "#ffffff")]
        label(lst, 168, 41, "Translation", color=HEADING); hline(lst, 43, 232, 608, HEADING_LINE)
        for i, (n, c) in enumerate(TR):
            check(lst, 160, 63 + 18 * i, "", True, blue=True)
            sq(lst, 176, 56 + 18 * i, c); label(lst, 193, 63 + 18 * i, n)
        label(lst, 168, 229, "Dictionary", color=HEADING); hline(lst, 231, 232, 608, HEADING_LINE)
        for i, (n, c) in enumerate(DI):
            check(lst, 160, 249 + 18 * i, "", True, blue=True); sq(lst, 176, 242 + 18 * i, c); label(lst, 193, 249 + 18 * i, n)
        rect(lst, 626, 48, 2, 157, THUMB)
        button(self, 157, 309, 24, "▲", enabled=False); button(self, 187, 309, 24, "▼", enabled=False)
        button(self, 219, 309, 117, "Add dictionary…"); b = button(self, 342, 309, 118, "Remove dictionary"); b.setStyleSheet("color:%s" % DIM)


LANGS = ["Afrikaans Albanian Arabic Armenian Azerbaijani Basque Belarusian Bengali Bulgarian Catalan Chinese_(Simplified) Chinese_(Traditional) Croatian Czech Danish Dutch English Esperanto",
         "Estonian Filipino Finnish French Galician Georgian German Greek Haitian_Creole Hebrew Hindi Hmong Hungarian Icelandic Indonesian Irish Italian Japanese",
         "Kannada Kazakh Khmer Korean Lao Latin Latvian Lithuanian Macedonian Malay Maltese Marathi Mongolian Norwegian Persian Polish Portuguese Romanian",
         "Russian Serbian Sinhala Slovak Slovenian Spanish Swahili Swedish Tajik Tamil Tatar Telugu Thai Turkish Ukrainian Urdu Uzbek Vietnamese"]


class Languages(OptionsBase):
    SEL = 4

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        for ci, col in enumerate(LANGS):
            x = round(158 + ci * 126.5)
            for i, n in enumerate(col.split(" ")):
                check(lst, x, 39 + 14 * i, n.replace("_", " "), True, blue=True)
        rect(lst, 173, 293, 238, 2, THUMB)
        button(self, 155, 308, 481, "Check / Uncheck all")


class Appearance(OptionsBase):
    SEL = 5

    def build(self):
        group(self, 152, 35, 484, 56, "General"); check(self, 160, 55, "Enable window style"); label(self, 157, 77, "Theme:")
        combo(self, 397, 68, 233, "--- Default ---")
        group(self, 152, 98, 484, 226, "Popup window")
        for cy, t, on in [(122, "Enable auto size", 1), (144, "Enable auto position", 1), (167, "Activate when opened", 0), (190, "Pin when dragging", 1)]:
            check(self, 160, cy, t, bool(on))
        label(self, 157, 213, "Auto-hide delay:"); combo(self, 397, 204, 115, "5"); label(self, 523, 213, "seconds")
        label(self, 157, 237, "Transparency (0 - 90):"); field(self, 397, 227, 233, 20, "15")
        label(self, 157, 261, "Frame thickness:"); combo(self, 397, 252, 233, "2")
        label(self, 157, 286, "Icons:")
        for i, g in enumerate(["▤", "∩", "⧉", "tā"]):
            b = button(self, 398 + 23 * i, 275, 22, g, 22); b.setStyleSheet("QPushButton{background:#c4c4c4;padding:0}")
        label(self, 157, 313, "Background color:"); label(self, 320, 313, "Text color:"); label(self, 482, 313, "Frame color:")
        rect(self, 378, 305, 87, 17, "#000000"); rect(self, 549, 305, 78, 17, "#5d6c7a")


class Exceptions(OptionsBase):
    SEL = 6

    def build(self):
        combo(self, 155, 33, 481, "Disabled for these programs:")
        t = panel(self, 153, 60, 483, 221)
        label(t, 160, 72, "Program Name"); label(t, 399, 72, "Window Class Name"); rect(t, 393, 62, 1, 18, COLSEP)
        EX = [("* All Programs *", c) for c in ["SysListView32", "SysTreeView32", "ListBox", "ScrollBar", "ComboBox", "msctls_hotkey32", "ConsoleWindowClass"]]
        EX.append(("mstsc.exe", "* All Windows *"))
        for i, (a, b) in enumerate(EX):
            label(t, 160, 92 + 17.6 * i, a); label(t, 399, 92 + 17.6 * i, b)
        button(self, 155, 288, 71, "Add"); button(self, 234, 288, 72, "Modify"); button(self, 314, 288, 72, "Delete")
        check(self, 154, 321, "Enable smart detection", True)


class Advanced(OptionsBase):
    SEL = 7

    def build(self):
        group(self, 152, 35, 484, 178, "Advanced")
        for cy, t, v in [(56, "Default browser:", "Internet Explorer"), (80, "Copy action:", "Ctrl + C"),
                         (104, "Keyboard layout indicator:", "None"), (128, "Preferred domain:", "com")]:
            label(self, 157, cy, t); combo(self, 455, cy - 10, 175, v)
        check(self, 160, 154, "Enable GUI translation"); check(self, 160, 177, "Enable listening to the same text at a slower speed", True)
        check(self, 160, 200, "Remove line breaks")
        group(self, 152, 224, 484, 66, "Mouse mode")
        check(self, 160, 244, "Enable mouse mode only when Ctrl is pressed"); check(self, 160, 268, "Click on system tray icon switches mouse mode", True)
        group(self, 152, 296, 484, 54, "API keys"); label(self, 157, 315, "OCR API key:"); field(self, 387, 304, 243, 22)
        label(self, 157, 338, "Register here for free OCR API key", color=LINK, underline=True)


class Updates(OptionsBase):
    SEL = 8

    def build(self):
        check(self, 161, 44, "Automatically check for updates"); panel(self, 153, 63, 481, 230)
        button(self, 524, 300, 110, "Check now")


class Hotkeys(Base):
    """Screenshot is 663x388 (different from the other pages)."""
    ORIGIN, SIZE = (0, 24), (663, 364)

    def __init__(self):
        super().__init__()
        panel(self, 10, 28, 142, 323)
        for i, n in enumerate(SIDEBAR):
            q = QLabel(n); sel = i == 1
            q.setStyleSheet("QLabel{padding-left:2px;background:%s;color:%s;}" % (ACCENT if sel else "transparent", "#fff" if sel else TEXT))
            put(self, q, 11, 29 + i * 13, 140, 13)
        check(self, 159, 41, "Enable hotkeys", True)
        t = panel(self, 159, 60, 465, 251)
        label(t, 165, 72, "Action"); label(t, 482, 72, "Hotkey"); rect(t, 477, 62, 1, 247, COLSEP)
        rows = [("Show main window", ""), ("Show popup window", "Ctrl + Q"), ("Show dictionary window", ""), ("Show history window", ""),
                ("Show keyboard window", ""), ("Listen to selected text", ""), ("Copy translation to clipboard", ""),
                ("Replace selected text", "Alt + W"), ("Switch mouse mode", ""), ("Translate clipboard content", ""),
                ("Translate clipboard in main window", ""), ("Translate clipboard in popup window", ""), ("Dictionary from clipboard", "")]
        for i, (a, k) in enumerate(rows):
            label(t, 165, 93 + 17 * i, a)
            if k: label(t, 482, 93 + 17 * i, k)
        rect(t, 629, 75, 2, 164, THUMB)
        button(self, 408, 361, 75, "OK"); button(self, 489, 361, 75, "Cancel"); button(self, 570, 361, 75, "Apply", enabled=False)


# ---------------------------------------------------------------- Popup (200x68, own window)
class Popup(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setFixedSize(200, 68); self.ORIGIN = (0, 0)
        self.setStyleSheet(f"Popup{{background:{POPUP_BG};border:1px solid {POPUP_BORDER};}}")
        x = 7
        for txt, w in [("✕", 12), ("English to Viet…", 96), ("★", 14), ("▤", 14), ("∩", 14), ("⧉", 14), ("tā", 14)]:
            q = QLabel(txt, self); q.setStyleSheet(f"background:transparent;color:{POPUP_ICON};"); q.setGeometry(x, 4, w + 4, 16); x += w + 7 if w > 14 else w + 6
        r = QLabel("người_record", self); r.setStyleSheet(f"background:transparent;color:{POPUP_TEXT};"); r.setGeometry(6, 30, 180, 16)
        self.setAttribute(Qt.WA_StyledBackground, True)


ALL = [("main", MainWindow), ("dict", DictWindow), ("hist", HistWindow), ("kbd", KbdWindow), ("hotkeys", Hotkeys),
       ("internet", Internet), ("services", Services), ("languages", Languages), ("appearance", Appearance),
       ("exceptions", Exceptions), ("advanced", Advanced), ("updates", Updates), ("popup", Popup)]

if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv); apply_style(app)
    out = sys.argv[1] if len(sys.argv) > 1 else "render"; os.makedirs(out, exist_ok=True)
    for name, cls in ALL:
        w = cls(); w.show(); app.processEvents(); w.grab().save(os.path.join(out, name + ".png"))
    print("rendered", len(ALL), "windows ->", out)
