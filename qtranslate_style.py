"""QTranslate look for PySide6.

Stock Fusion does NOT match the screenshots (Fusion outline is #ababab and its
checkbox is black-on-white). Measured values differ, so this module keeps Fusion
as the base and overrides colours/shape with a palette + QSS + small generated PNGs.

Usage:
    from qtranslate_style import apply_style, EtchedGroupBox
    app = QApplication(sys.argv); apply_style(app)
"""
import os, tempfile
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QGroupBox

# ---- design tokens (measured from screenshots) ------------------------------
FACE, WINDOW, BORDER, TEXT, DIM = "#f0f0f0", "#ffffff", "#7e7e7e", "#000000", "#6d6d6d"
ACCENT, CHECK, THUMB, COLSEP = "#0078d7", "#005eb8", "#858585", "#e5e5e5"
BTN_HL, BTN_TOP, BTN_BOT, BTN_SHADE = "#ffffff", "#e3e3e3", "#d4d4d4", "#cacaca"
BTN_PRESS_TOP = "#c9c9c9"          # ESTIMATE: no pressed-state screenshot
DIS_BG = "#e1e1e1"
ARROW, TICK = "#191919", "#191919"   # combobox arrows / normal checkbox tick (measured)
CB_TOP, CB_BOT = "#e1e1e1", "#d8d8d8"
# The 1px shadow a themed button casts under itself (MEASURED off the capture).
BTN_SHADOW = "#fcfcfc"
POPUP_BG, POPUP_BORDER, POPUP_ICON, POPUP_TEXT = "#d0d0d0", "#53606c", "#3a3a3a", "#040404"
# The provider strip at the bottom of the main window: its nine buttons
# are flatter than the ordinary ones, and the FIRST one is the selected
# service, drawn in a solid grey with a darker border.
STRIP_TOP, STRIP_BOT = "#dedede", "#dadada"
STRIP_SEL, STRIP_SEL_BORDER = "#b0b0b0", "#737373"
# The font: the Win32 dialog font, which is Tahoma 8pt (11px) on this
# Windows. MEASURED, not guessed: the Options label "Keyboard layout
# indicator:" is 125px wide in the native capture, which is Tahoma 8pt
# (127px) and not Segoe UI 8pt (135px) nor Tahoma 9pt (142px).
FONT_FAMILY, FONT_SIZE = "Tahoma", 11
# The virtual keyboard's key labels are in a DIFFERENT face: MEASURED off
# capture 2134, the native's "Esc" is 15x9, "Tab" 18x9, "Shift" 23x9,
# "BkSp" 24x12 and "AltGr" 27x9, and only Segoe UI 9pt (12px) has
# those ink boxes (Tahoma 8pt gives 15x8, 16x9, 21x9, 22x11, 23x9).
# So the window's own text is the Win32 dialog font and the KEYS are
# Segoe UI -- the spec's original "Segoe UI 9pt" was right about the
# keys and wrong about the rest.
KEY_FONT_FAMILY, KEY_FONT_SIZE = "Segoe UI", 12

_dir = tempfile.mkdtemp(prefix="qtstyle_")


def _png(name, w, h, draw):
    pm = QPixmap(w, h); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, False); draw(p); p.end()
    path = os.path.join(_dir, name).replace("\\", "/"); pm.save(path); return path


def _updown(p):                     # combobox arrows: two filled 5px-wide triangles, 7x8
    p.setPen(Qt.NoPen); p.setBrush(QColor(ARROW))
    for x0, x1, y in [(3, 3, 0), (2, 4, 1), (1, 5, 2), (1, 5, 5), (2, 4, 6), (3, 3, 7)]:
        p.drawRect(x0, y, x1 - x0 + 1, 1)


def _tick(p, color):                # checkbox tick on the 11x11 interior, pixel-matched to the screenshots
    pts = [(2, 4), (3, 5), (4, 6), (5, 5), (6, 4), (7, 3), (8, 2), (9, 1)]
    p.setPen(Qt.NoPen)
    halo = QColor(color); halo.setAlpha(120)
    for x, y in pts:                # soft side pixels (reference has #5e5e5e halos)
        p.setBrush(halo); p.drawRect(x - 1, y, 1, 1); p.drawRect(x + 1, y, 1, 1)
    p.setBrush(QColor(color))
    for x, y in pts:
        p.drawRect(x, y, 1, 1)


def button_gradient(height):
    """The Win32 themed button face for a control ``height`` px tall.

    MEASURED off the native captures. The face is a fixed pixel
    pattern, not a fixed fraction of the height: a 1px white gloss
    row, then a ramp down one level per row to #d3d3d3, then a
    #cacaca shadow row, then the 1px border. A 22px button (the main
    window's Translate button, capture 2131 rows 217..238) reads
    255, 227..211, 202, border; an 18px key (the virtual keyboard's,
    capture 2134 rows 38..55) reads 255, 226..212, 202, border.

    A QSS gradient's stops are fractions of the height, so the stops
    have to move with it -- which is why this is a function and not a
    constant. The one in ``qss()`` is the 21px one, which reproduces the
    native's 21px buttons (the History and Options OK buttons) row for
    row; the 18px keys and the 22px Translate button are within one
    level of it.
    """
    gloss = 2.0 / height
    ramp = (height - 2) / height
    shade = (height - 1) / height
    # The two stops at the gloss must NOT share a position: Qt leaves a
    # hole (an unpainted pixel) where a gradient has two stops at the
    # same offset, so the white band is written with a 1/100000 gap.
    return (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {BTN_HL},"
            f"stop:{gloss - 0.00001:.5f} {BTN_HL},stop:{gloss:.5f} {BTN_TOP},"
            f"stop:{ramp:.5f} #d3d3d3,stop:{shade:.5f} {BTN_SHADE},"
            f"stop:1 {BTN_SHADE})")


def qss():
    arrow = _png("updown.png", 7, 8, _updown)
    tick_k = _png("tick_black.png", 11, 11, lambda p: _tick(p, TICK))
    tick_w = _png("tick_white.png", 11, 11, lambda p: _tick(p, "#ffffff"))
    # 21px control: row0 border, row1 white, rows 2..18 e3->d3, row19 #cacaca, row20 border
    grad = button_gradient(21)
    grad_p = (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {BTN_PRESS_TOP},stop:1 {BTN_BOT})")
    return f"""
* {{ font-family: "{FONT_FAMILY}"; font-size: {FONT_SIZE}px; color: {TEXT}; }}
QWidget {{ background: {FACE}; }}
QLabel, QCheckBox {{ background: transparent; }}
QPushButton, QToolButton {{
  border: 1px solid {BORDER}; border-radius: 2px; background: {grad};
  padding: 0 8px; }}
QPushButton:pressed, QToolButton:pressed {{ background: {grad_p}; }}
/* The virtual keyboard's keys: 28px wide, so they cannot carry the
   ordinary buttons' 8px padding -- "BkSp" would be clipped. */
QPushButton#key {{ border: 1px solid {BORDER}; border-radius: 2px; padding: 0; background: {grad}; }}
QPushButton#flat {{ border: none; background: transparent; padding: 0; }}
QPushButton#navmenu {{ border: none; background: transparent; padding: 0; }}
QPushButton#service {{
  border: 1px solid {BORDER}; border-radius: 2px; padding: 0;
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {STRIP_TOP},stop:1 {STRIP_BOT}); }}
QPushButton#service[selected="true"] {{
  border: 1px solid {STRIP_SEL_BORDER}; background: {STRIP_SEL}; }}
QPushButton:disabled, QToolButton:disabled {{ background: {DIS_BG}; color: {DIM}; border-color: {DIS_BG}; }}
QComboBox {{
  border: 1px solid {BORDER}; border-radius: 2px; background: {grad};
  padding: 0 14px 0 5px; }}
QComboBox:disabled {{ background: {FACE}; color: {DIM}; border-color: {DIM}; }}
QComboBox::drop-down {{ border: none; width: 11px; subcontrol-origin: padding; subcontrol-position: right center; }}
QComboBox::down-arrow {{ image: url({arrow}); width: 7px; height: 8px; }}
QComboBox QAbstractItemView {{
  background: {WINDOW}; border: 1px solid {BORDER};
  selection-background-color: {ACCENT}; selection-color: #ffffff; outline: 0; }}
QLineEdit, QTextEdit, QPlainTextEdit, QListWidget, QListView, QTreeWidget, QTableWidget {{
  background: {WINDOW}; border: 1px solid {BORDER}; border-radius: 0;
  selection-background-color: {ACCENT}; selection-color: #ffffff; }}
QLineEdit:disabled {{ background: {FACE}; color: {DIM}; border-color: {DIM}; }}
QListWidget::item {{ padding: 0 2px; }}
QListWidget::item:selected {{ background: {ACCENT}; color: #ffffff; }}
QHeaderView::section {{ background: {WINDOW}; border: none; border-right: 1px solid {COLSEP}; padding: 0 6px; }}
QCheckBox::indicator {{ width: 12px; height: 12px; border: 1px solid {BORDER};
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {CB_TOP},stop:1 {CB_BOT}); }}
QCheckBox::indicator:checked {{ image: url({tick_k}); }}
QCheckBox::indicator:disabled {{ border-color: {DIM}; }}
/* checkboxes INSIDE list views (Services, Languages) are blue with a white tick */
QListView::indicator {{ width: 11px; height: 11px; border: 1px solid {BORDER}; background: {WINDOW}; }}
QListView::indicator:checked {{ background: {CHECK}; border: 1px solid {CHECK}; image: url({tick_w}); }}
/* The port draws the Services and Languages checklists as QCheckBox widgets
   with the "blue" property set rather than as a QListView, so the rule
   that makes them blue has to name the property. */
QCheckBox[blue="true"]::indicator {{ width: 11px; height: 11px; border: 1px solid {BORDER}; background: {WINDOW}; }}
QCheckBox[blue="true"]::indicator:checked {{ background: {CHECK}; border: 1px solid {CHECK}; image: url({tick_w}); }}
QGroupBox {{ border: none; margin-top: 7px; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 9px; padding: 0 2px; background: {FACE}; }}
QScrollBar:vertical {{ background: {FACE}; width: 14px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {THUMB}; margin: 0 6px; min-height: 20px; }}
QScrollBar:horizontal {{ background: {FACE}; height: 14px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {THUMB}; margin: 6px 0; min-width: 20px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
QSplitter::handle {{ background: {FACE}; }}
QMenu {{ background: #f9f9f9; border: 1px solid #e5e5e5; }}
QMenu::item {{ padding: 3px 24px 3px 38px; }}
QMenu::item:selected {{ background: #e5e5e5; }}
QMenu::separator {{ height: 1px; background: #d7d7d7; margin: 2px 0; }}
"""


def apply_style(app: QApplication):
    app.setStyle("Fusion")
    P, R = QPalette(), QPalette.ColorRole
    for r, c in [(R.Window, FACE), (R.Base, WINDOW), (R.Button, BTN_TOP), (R.WindowText, TEXT),
                 (R.Text, TEXT), (R.ButtonText, TEXT), (R.Highlight, ACCENT), (R.HighlightedText, "#ffffff")]:
        P.setColor(r, QColor(c))
    P.setColor(QPalette.Disabled, R.WindowText, QColor(DIM))
    P.setColor(QPalette.Disabled, R.Text, QColor(DIM))
    P.setColor(QPalette.Disabled, R.ButtonText, QColor(DIM))
    app.setPalette(P)
    f = QFont(FONT_FAMILY); f.setPixelSize(FONT_SIZE); app.setFont(f)
    app.setStyleSheet(qss())


class EtchedGroupBox(QGroupBox):
    """Win32 etched frame: 1px #7e7e7e line + 1px white line offset (+1,+1); title sits ON the top line.
    QSS cannot draw the white offset, so everything is painted here (children stay normal widgets).

    MEASURED off the native Options capture 2140: the frame's top line is on
    the widget's own top edge (y=35 for the Advanced group, whose border
    runs x=152..635), and the title STRADDLES that line -- "Advanced" has
    its cap-top 4px above the line and its baseline 4px below it. The
    title's background clears the frame line for the width of the text
    plus 2px on each side (the native's line is broken from x=160 to
    x=214, and the ink starts at x=167).
    """
    # The title's text starts 9px inside the frame, its baseline 4px
    # below the frame's top line (so the letters straddle the line), and
    # it cuts a gap in that line from 8px inside the frame to 8px past
    # the end of the text. The title also reaches 4px ABOVE the frame's
    # top line, so the widget is that much taller at the top and the
    # frame is drawn 4px down (see `qtranslate.qt.widgets.group`).
    TITLE_X, TITLE_BASE, GAP_PAD = 9, 4, 8
    FRAME_TOP = 4

    def paintEvent(self, e):
        p = QPainter(self)
        fm = self.fontMetrics()
        p.fillRect(self.rect(), QColor(FACE))
        top = self.FRAME_TOP
        r = QRect(0, top, self.width() - 1, self.height() - top - 1)
        p.setPen(QPen(QColor("#ffffff"), 1)); p.drawRect(r.translated(1, 1))
        p.setPen(QPen(QColor(BORDER), 1));    p.drawRect(r)
        t = self.title()
        if t:
            w = fm.horizontalAdvance(t) + self.GAP_PAD
            p.fillRect(QRect(self.TITLE_X - 1, top, w, 2), QColor(FACE))
            p.setPen(QColor(DIM if not self.isEnabled() else TEXT))
            p.drawText(self.TITLE_X, top + self.TITLE_BASE, t)
        p.end()
