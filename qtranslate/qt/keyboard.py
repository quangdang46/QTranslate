"""The virtual keyboard (native DLG 213) on PySide6.

The geometry is measured off ``docs/review/native_screens/2134.png`` (the
real QTranslate 6.10.0 virtual keyboard, 464x198; the client area is
462x166 at ``(1, 31)``).

Every key's rectangle was read off that capture twice -- once from the
horizontal runs of the key's top border and once from the vertical runs
of its side borders -- and the two agree:

  * the six rows start at capture y 38, 59, 80, 101, 122 and 143, and
    the first five rows' keys are 18 tall (the bottom row's are 19),
    so there is a 3px gap between the rows;
  * the number row starts with the backtick and steps by 31;
  * the language combo is at the bottom left, x 8, y 170, 168x19, and
    it is FOCUSED in the capture (the dotted rectangle), so this one is
    too.

The coordinates are SCREENSHOT coordinates, like everywhere else in the
port: ``put()`` subtracts the window's ``ORIGIN``.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QComboBox

from qtranslate_style import BTN_HL, BTN_SHADE, BTN_TOP

from .widgets import Base, button, put

# The key labels are in a DIFFERENT face from the rest of the app:
# MEASURED off capture 2134, the native's "Esc" is 15x9, "Tab" 18x9,
# "Shift" 23x9, "BkSp" 24x12 and "AltGr" 27x9, and only Segoe UI 9pt
# (12px) has those ink boxes (Tahoma 8pt gives 15x8, 16x9, 21x9,
# 22x11, 23x9). The window's own text is the Win32 dialog font
# (Tahoma 8pt); the KEYS are Segoe UI.
KEY_FONT_FAMILY, KEY_FONT_SIZE = "Segoe UI", 12


def _face_gradient(height):
    """The themed button face for a control ``height`` px tall.

    The Win32 face is a fixed PIXEL pattern, not a fixed fraction of
    the height: a 1px white gloss row, then a ramp down one level per
    row to #d3d3d3, then a #cacaca shadow row, then the 1px border.
    An 18px key (capture 2134 rows 38..55) reads 255, 226..212, 202,
    border; a 21px button (capture 2133 rows 294..314) reads 255,
    227..211, 202, border.

    A QSS gradient's stops are fractions of the height, so they have to
    move with it. The two stops at the gloss must NOT share a position:
    Qt leaves an unpainted hole where a gradient has two stops at the
    same offset, so the white band is written with a 1/100000 gap.
    """
    gloss = 2.0 / height
    ramp = (height - 2) / height
    shade = (height - 1) / height
    return (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {BTN_HL},"
            f"stop:{gloss - 0.00001:.5f} {BTN_HL},stop:{gloss:.5f} {BTN_TOP},"
            f"stop:{ramp:.5f} #d3d3d3,stop:{shade:.5f} {BTN_SHADE},"
            f"stop:1 {BTN_SHADE})")

# Each row is a list of (label, x, width), measured off the capture.
ROWS = [
    # y = 38: Esc, F1..F4, a gap, F5..F8, a gap, F9..F12
    [("Esc", 8, 28), ("F1", 52, 28), ("F2", 83, 28), ("F3", 114, 28),
     ("F4", 145, 28), ("F5", 193, 28), ("F6", 224, 28), ("F7", 255, 28),
     ("F8", 286, 28), ("F9", 335, 28), ("F10", 366, 28), ("F11", 397, 28),
     ("F12", 428, 28)],
    # y = 59
    [("`", 8, 28), ("1", 39, 28), ("2", 70, 28), ("3", 101, 28),
     ("4", 132, 28), ("5", 163, 28), ("6", 194, 28), ("7", 225, 28),
     ("8", 256, 28), ("9", 287, 28), ("0", 318, 28), ("-", 349, 28),
     ("=", 380, 28), ("BkSp", 411, 45)],
    # y = 80
    [("Tab", 8, 45), ("q", 56, 28), ("w", 87, 28), ("e", 118, 28),
     ("r", 149, 28), ("t", 180, 28), ("y", 211, 28), ("u", 242, 28),
     ("i", 273, 28), ("o", 304, 28), ("p", 335, 28), ("[", 366, 28),
     ("]", 397, 28), ("\\", 428, 28)],
    # y = 101
    [("Caps", 8, 53), ("a", 64, 28), ("s", 95, 28), ("d", 126, 28),
     ("f", 157, 28), ("g", 188, 28), ("h", 219, 28), ("j", 250, 28),
     ("k", 281, 28), ("l", 312, 28), (";", 343, 28), ("'", 374, 28),
     ("Enter", 405, 51)],
    # y = 122
    [("Shift", 8, 69), ("z", 80, 28), ("x", 111, 28), ("c", 142, 28),
     ("v", 173, 28), ("b", 204, 28), ("n", 235, 28), ("m", 266, 28),
     (",", 297, 28), (".", 328, 28), ("/", 359, 28), ("Shift", 390, 66)],
    # y = 143
    [("Ctrl", 8, 42), ("Win", 53, 31), ("Alt", 87, 37), ("", 127, 121),
     ("AltGr", 251, 40), ("Apps", 294, 38), ("^", 335, 28),
     ("v", 366, 28), ("<", 397, 28), (">", 428, 28)],
]

# The row each ROWS entry sits at.
ROW_Y = [38, 59, 80, 101, 122, 143]

# The height of each row's keys. MEASURED off the capture's border
# rows: the first five rows are 18 tall (38..55, 59..76, 80..97,
# 101..118, 122..139) and the bottom row is 19 (143..161) -- which is
# why its labels sit a pixel lower.
ROW_H = [18, 18, 18, 18, 18, 19]

# The 1px line the Win32 theme draws under every control it draws
# (measured: #fcfcfc at capture y 56, below the first row's border at
# y 55; and at y 189, below the combo's border at 188). It is outside
# the control's own rectangle, so it is painted by the window.
SOFT_EDGE = "#fcfcfc"

# The keys that press a key rather than type a character, by (label,
# x) -- the two "v"s and the two "Shift"s are different keys. The
# names are the ones the `keyboard` package uses.
SPECIAL = {
    ("BkSp", 411): "backspace",
    ("Tab", 8): "tab",
    ("Caps", 8): "caps lock",
    ("Shift", 8): "shift",
    ("Shift", 390): "shift",
    ("Enter", 405): "enter",
    ("Ctrl", 8): "ctrl",
    ("Win", 53): "win",
    ("Alt", 87): "alt",
    ("AltGr", 251): "alt gr",
    ("Apps", 294): "menu",
    ("^", 335): "up",
    ("v", 366): "down",
    ("<", 397): "left",
    (">", 428): "right",
}


class LanguageCombo(QComboBox):
    """The keyboard's language combo.

    Native's is a Win32 combo box, and when it has the focus Windows
    draws the dotted focus rectangle around the text -- the capture
    shows it. Qt's Fusion combo does not, so this one draws it: a 1px
    dot every other pixel, from the capture's x 14..156 and
    y 172..186, i.e. 6..148 and 2..16 inside the widget. The corners
    belong to the top and bottom edges (the native's dots there are at
    x 15, 17, ... and the side edges start one row lower), so the
    sides are drawn from y0+1 and the top and bottom from x0+1.
    """

    FOCUS_RECT = (6, 2, 148, 16)

    # The background under the focus rectangle, measured off the
    # capture. Windows draws the rectangle by XORing white with the
    # background, so its dots are not black: they read 255 XOR bg --
    # 28 on the combo's 227 grey, 43 on its 212. The keys are the
    # widget's rows.
    BG = {2: 227, 3: 225, 5: 224, 7: 221, 9: 219, 11: 217, 13: 215,
          15: 212, 16: 212}

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self.hasFocus():
            return
        x0, y0, x1, y1 = self.FOCUS_RECT
        p = QPainter(self)
        for x in range(x0 + 1, x1, 2):
            for y in (y0, y1):
                v = 255 ^ self.BG[y]
                p.setPen(QColor(v, v, v))
                p.drawPoint(x, y)
        for y in range(y0 + 1, y1, 2):
            v = 255 ^ self.BG[y]
            p.setPen(QColor(v, v, v))
            p.drawPoint(x0, y)
            p.drawPoint(x1, y)
        p.end()


class KeyboardWindow(Base):
    """The virtual keyboard: six rows of keys and the language combo."""

    ORIGIN, SIZE = (1, 31), (462, 166)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Keyboard")
        self._build()

    def _build(self):
        self.keys = {}
        self.edges = []           # the 1px soft edges under the controls
        for row, y, h in zip(ROWS, ROW_Y, ROW_H):
            for text, x, w in row:
                b = button(self, x, y, w, text, h)
                b.setObjectName("key")
                # The face is the themed button's own gradient, and the
                # gradient's stops move with the height -- an 18px key
                # is not the 22px button the app's stylesheet carries.
                # The label's size has to be set in the stylesheet, not
                # with setFont(): the app's QSS sets the font size on
                # every widget and would win. The 2px bottom padding
                # lifts the label by the one pixel that native's is
                # higher than the centre.
                b.setStyleSheet(
                    "QPushButton{font-family:%s;font-size:%dpx;"
                    "border-radius:2px;background:%s;padding:0 0 2px 0;}"
                    % (KEY_FONT_FAMILY, KEY_FONT_SIZE, _face_gradient(h)))
                b.clicked.connect(
                    lambda _=False, t=text, k=x: self._key_pressed(t, k))
                self.keys[(text, x)] = b
                self.edges.append((x, y + h, w))
        # The language combo at the bottom left. Native's capture has it
        # focused, so this one takes the focus when the window opens.
        self.cmb_lang = LanguageCombo()
        self.cmb_lang.addItem("English")
        self.cmb_lang.setFocusPolicy(Qt.StrongFocus)
        self.cmb_lang.setStyleSheet(
            "QComboBox{background:%s;padding:0 14px 0 7px;}"
            "QComboBox::drop-down{width:13px;}"
            % _face_gradient(19))
        put(self, self.cmb_lang, 8, 170, 168, 19)
        self.edges.append((8, 189, 168))

    def paintEvent(self, e):
        super().paintEvent(e)
        # The soft edge under each control. It is drawn by the window,
        # because it is OUTSIDE the control's own rectangle and a
        # control would paint over it.
        p = QPainter(self)
        p.setPen(QColor(SOFT_EDGE))
        ox, oy = self.ORIGIN
        for x, y, w in self.edges:
            p.drawLine(x - ox, y - oy, x - ox + w - 1, y - oy)
        p.end()

    def showEvent(self, e):
        super().showEvent(e)
        # The focus goes to the language combo. During showEvent the
        # window is not active yet, and a focus request to an inactive
        # window is ignored, so it is made on the next event-loop turn
        # as well as right away.
        self.cmb_lang.setFocus(Qt.OtherFocusReason)
        QTimer.singleShot(0, lambda: self.cmb_lang.setFocus(
            Qt.OtherFocusReason))

    def _key_pressed(self, text, x):
        """Type a key into the focused window, the way the virtual
        keyboard does."""
        if not text:
            return
        # The keys that are not letters press the key they stand for:
        # the arrows move the caret, BkSp deletes, and so on. The names
        # are the ones the `keyboard` package uses.
        name = SPECIAL.get((text, x))
        try:
            import keyboard
            keyboard.press(name if name else text)
        except Exception:
            pass
