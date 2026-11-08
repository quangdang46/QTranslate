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
BTN_MID = "#d3d3d3"                  # the ramp's middle stop (measured)
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

# The last palette ``apply_style`` installed. ``EtchedGroupBox`` paints
# itself (QSS cannot draw the offset white line) and reads this so a
# themed app does not keep painting the measured light greys.
_ACTIVE = {"pal": None, "font": (FONT_FAMILY, FONT_SIZE)}

_dir = tempfile.mkdtemp(prefix="qtstyle_")


def _png(name, w, h, draw):
    pm = QPixmap(w, h); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, False); draw(p); p.end()
    path = os.path.join(_dir, name).replace("\\", "/"); pm.save(path); return path


def _updown(p, color=ARROW):        # combobox arrows: two filled 5px-wide triangles, 7x8
    p.setPen(Qt.NoPen); p.setBrush(QColor(color))
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


# ------------------------------------------------------------- colour math
def _rgb(c):
    """``#rrggbb`` -> ``(r, g, b)`` ints; black on anything unparseable."""
    try:
        v = int(str(c).lstrip("#"), 16)
    except Exception:
        return (0, 0, 0)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def _hex(rgb):
    r, g, b = (max(0, min(255, int(v))) for v in rgb)
    return "#%02x%02x%02x" % (r, g, b)


def _lum(c):
    """WCAG relative luminance of a ``#rrggbb`` colour, 0..1."""
    def chan(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(c)
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _ratio(a, b):
    """WCAG contrast ratio between two ``#rrggbb`` colours."""
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _mix(c1, c2, t):
    """Blend ``c1`` toward ``c2`` by ``t`` (0 keeps c1, 1 gives c2)."""
    a, b = _rgb(c1), _rgb(c2)
    return _hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def _fix_fg(fg, bg, minimum=3.0):
    """``fg`` when it reads on ``bg``, else black or white -- whichever
    contrasts better. This is the guard that keeps a dark theme from
    pairing a light face with light text (the audit's C1)."""
    if _ratio(fg, bg) >= minimum:
        return fg
    return "#000000" if _ratio("#000000", bg) >= _ratio("#ffffff", bg) \
        else "#ffffff"


def _slot(colors, key):
    """One colour out of a ``state_colors`` record, or None."""
    v = (colors or {}).get(key)
    return v if isinstance(v, str) and v.startswith("#") else None


# ------------------------------------------------------------- the palette
def _default_palette():
    """Every colour the stylesheet needs, at the measured values."""
    return {
        "face": FACE, "window": WINDOW, "text": TEXT, "dim": DIM,
        "accent": ACCENT, "border": BORDER,
        "btn_hl": BTN_HL, "btn_top": BTN_TOP, "btn_mid": BTN_MID,
        "btn_bot": BTN_BOT, "btn_shade": BTN_SHADE,
        "btn_press_top": BTN_PRESS_TOP, "btn_press_bot": BTN_BOT,
        "btn_border": BORDER, "btn_text": TEXT, "btn_shadow": BTN_SHADOW,
        "dis_bg": DIS_BG,
        "edit_bg": WINDOW, "edit_border": BORDER, "edit_text": TEXT,
        "menu_bg": "#f9f9f9", "menu_border": "#e5e5e5",
        "menu_text": TEXT, "menu_sel": "#e5e5e5", "menu_sep": "#d7d7d7",
        "thumb": THUMB, "colsep": COLSEP, "check": CHECK,
        "cb_top": CB_TOP, "cb_bot": CB_BOT, "tick": TICK,
        "strip_top": STRIP_TOP, "strip_bot": STRIP_BOT,
        "strip_sel": STRIP_SEL, "strip_sel_border": STRIP_SEL_BORDER,
        "arrow": ARROW,
    }


def _theme_palette(theme):
    """The measured palette with a theme record's slots merged in.

    The native theme names colours per CONTROL -- ``Window`` for the
    frame, ``Button`` for the push buttons, ``Edit`` for the text
    inputs -- and the port reads them through ``state_colors`` so an
    unset slot stays unset. Every slot the theme leaves out keeps (or,
    on a dark face, derives) a readable value: this is what keeps
    Theme120/121's dark faces from leaving light button gradients
    under near-white text.
    """
    pal = _default_palette()
    try:
        from qtranslate import theme as T
        win = T.state_colors(theme, "Window", "Normal")
        wind = T.state_colors(theme, "Window", "Disabled")
        btn = T.state_colors(theme, "Button", "Normal")
        btnp = T.state_colors(theme, "Button", "Pressed")
        btnd = T.state_colors(theme, "Button", "Disabled")
        edt = T.state_colors(theme, "Edit", "Normal")
    except Exception:
        return _finish_palette(pal)

    pal["face"] = _slot(win, "Back") or pal["face"]
    pal["text"] = _slot(win, "Text") or pal["text"]
    pal["border"] = _slot(win, "Border") or pal["border"]

    # Buttons: BackTop/BackBottom are the two gradient ends, Border the
    # rim, Text the label; GleamTop/Shadows feed the gloss and shade rows.
    bt, bb = _slot(btn, "BackTop"), _slot(btn, "BackBottom")
    if bt:
        pal["btn_top"] = bt
        pal["btn_hl"] = _slot(btn, "GleamTop") or _mix(bt, "#ffffff", 0.6)
        pal["btn_mid"] = _mix(bt, bb or bt, 0.5)
    if bb:
        pal["btn_bot"] = bb
    pal["btn_shade"] = _slot(btn, "ShadowBottom") or _slot(btn, "ShadowTop") \
        or _mix(pal["btn_bot"], "#000000", 0.12)
    pal["btn_border"] = _slot(btn, "Border") or pal["border"]
    pal["btn_text"] = _slot(btn, "Text") or pal["text"]
    pt, pb = _slot(btnp, "BackTop"), _slot(btnp, "BackBottom")
    pal["btn_press_top"] = pt or _mix(pal["btn_top"], "#000000", 0.15)
    pal["btn_press_bot"] = pb or _mix(pal["btn_bot"], "#000000", 0.15)
    # A dark face needs a dark disabled face too; a light one keeps the
    # measured DIS_BG.
    db = _slot(btnd, "BackTop") or _slot(btnd, "BackBottom")
    if db and _ratio(db, pal["btn_top"]) < 1.2:
        db = None                     # inherited Normal -- derive instead
    pal["dis_bg"] = db or (
        _mix(pal["btn_top"], pal["face"], 0.5) if _lum(pal["face"]) < 0.4
        else DIS_BG)
    pal["dim"] = _slot(wind, "Text") or _slot(btnd, "Text") or pal["dim"]

    # Edits (the text inputs and the combo drop-down list).
    eb, et, ed = _slot(edt, "Back"), _slot(edt, "Text"), _slot(edt, "Border")
    if eb:
        pal["edit_bg"] = eb
        pal["window"] = eb
    if et:
        pal["edit_text"] = et
    if ed:
        pal["edit_border"] = ed

    # Menus have no theme section; they follow the window face so a
    # dark theme does not leave a #f9f9f9 menu under light text.
    pal["menu_bg"] = pal["face"] if _lum(pal["face"]) < 0.6 else "#f9f9f9"
    pal["menu_border"] = pal["border"]
    pal["menu_sel"] = pal["accent"]
    pal["menu_sep"] = _mix(pal["face"], pal["text"], 0.25) \
        if _lum(pal["face"]) < 0.6 else "#d7d7d7"

    # Slots a theme never names still have to read on a dark face:
    # derive the edit/list background from the face when Edit is absent.
    if not eb and _lum(pal["face"]) < 0.4:
        pal["edit_bg"] = pal["window"] = _mix(pal["face"], "#ffffff", 0.10)
        pal["edit_border"] = _mix(pal["face"], "#ffffff", 0.28)

    return _finish_palette(pal)


def _finish_palette(pal):
    """Contrast pass: no face may keep a foreground it cannot be read
    against. Runs on the themed AND the default palette so the guard
    is one code path."""
    pal["text"] = _fix_fg(pal["text"], pal["face"])
    # Disabled text sits on BOTH the face (labels) and the disabled
    # control face, so it must clear the worse of the two.
    best = None
    for cand in (pal["dim"], "#000000", "#ffffff"):
        score = min(_ratio(cand, pal["face"]), _ratio(cand, pal["dis_bg"]))
        if best is None or score > best[0]:
            best = (score, cand)
    pal["dim"] = best[1] if best[0] >= 3.0 else _fix_fg(pal["dim"], pal["face"])
    pal["btn_text"] = _fix_fg(pal["btn_text"], pal["btn_bot"])
    pal["edit_text"] = _fix_fg(pal["edit_text"], pal["edit_bg"])
    pal["menu_text"] = _fix_fg(pal["text"], pal["menu_bg"])
    # The drop-down arrow is a glyph on the button face: keep it
    # readable there too (a dark #191919 arrow vanishes on #575757).
    if _ratio(pal["arrow"], pal["btn_bot"]) < 3.0:
        pal["arrow"] = pal["btn_text"]
    return pal


def _palette(theme=None):
    if theme:
        return _theme_palette(theme)
    return _finish_palette(_default_palette())


# ------------------------------------------------------------- the font
def _ui_font():
    """``(family, pixel_size)`` from ``General.FontName``/``TextSize``.

    ``qtranslate.fonts.resolve_font`` owns the config contract (empty
    name -> platform default, garbage size -> 9, clamp at 6). TextSize
    is a POINT size -- the Tk/native convention -- while the measured
    stylesheet is in PIXELS, and its default 11px IS TextSize 9, so the
    port scales the setting onto that pixel grid rather than switching
    units.
    """
    try:
        from qtranslate import config as C
        from qtranslate.fonts import resolve_font
        name, size = resolve_font(C.load().get("General", {}))
    except Exception:
        name, size = FONT_FAMILY, 9
    px = max(6, int(round(FONT_SIZE * size / 9.0)))
    return (name or FONT_FAMILY), px


# ------------------------------------------------------------- the QSS
def button_gradient(height, pal=None):
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

    ``pal`` is a palette from ``_palette``; the defaults are the
    measured light values.
    """
    pal = pal or _default_palette()
    gloss = 2.0 / height
    ramp = (height - 2) / height
    shade = (height - 1) / height
    # The two stops at the gloss must NOT share a position: Qt leaves a
    # hole (an unpainted pixel) where a gradient has two stops at the
    # same offset, so the white band is written with a 1/100000 gap.
    return (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {pal['btn_hl']},"
            f"stop:{gloss - 0.00001:.5f} {pal['btn_hl']},stop:{gloss:.5f} {pal['btn_top']},"
            f"stop:{ramp:.5f} {pal['btn_mid']},stop:{shade:.5f} {pal['btn_shade']},"
            f"stop:1 {pal['btn_shade']})")


def _pressed_gradient(pal):
    return (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {pal['btn_press_top']},stop:1 {pal['btn_press_bot']})")


def qss(pal=None, family=None, size=None):
    """The application stylesheet for ``pal`` (default: measured look).

    ``family``/``size`` are the resolved UI font (see ``_ui_font``);
    they default to the measured Tahoma 11px.
    """
    pal = pal or _default_palette()
    family = family or FONT_FAMILY
    size = FONT_SIZE if size is None else size
    p = pal
    arrow = _png("updown.png", 7, 8, lambda dr: _updown(dr, p["arrow"]))
    tick_k = _png("tick_black.png", 11, 11, lambda dr: _tick(dr, p["tick"]))
    tick_w = _png("tick_white.png", 11, 11, lambda dr: _tick(dr, "#ffffff"))
    # 21px control: row0 border, row1 white, rows 2..18 e3->d3, row19 #cacaca, row20 border
    grad = button_gradient(21, p)
    grad_p = _pressed_gradient(p)
    return f"""
* {{ font-family: "{family}"; font-size: {size}px; color: {p['text']}; }}
QWidget {{ background: {p['face']}; }}
QLabel, QCheckBox {{ background: transparent; }}
QPushButton, QToolButton {{
  border: 1px solid {p['btn_border']}; border-radius: 2px; background: {grad};
  color: {p['btn_text']}; padding: 0 8px; }}
QPushButton:pressed, QToolButton:pressed {{ background: {grad_p}; }}
/* The virtual keyboard's keys: 28px wide, so they cannot carry the
   ordinary buttons' 8px padding -- "BkSp" would be clipped. */
QPushButton#key {{ border: 1px solid {p['btn_border']}; border-radius: 2px; padding: 0; background: {grad}; color: {p['btn_text']}; }}
QPushButton#flat {{ border: none; background: transparent; padding: 0; color: {p['text']}; }}
QPushButton#navmenu {{ border: none; background: transparent; padding: 0; color: {p['text']}; }}
QPushButton#service {{
  border: 1px solid {p['btn_border']}; border-radius: 2px; padding: 0;
  color: {p['btn_text']};
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {p['strip_top']},stop:1 {p['strip_bot']}); }}
QPushButton#service[selected="true"] {{
  border: 1px solid {p['strip_sel_border']}; background: {p['strip_sel']}; color: {p['btn_text']}; }}
QPushButton:disabled, QToolButton:disabled {{ background: {p['dis_bg']}; color: {p['dim']}; border-color: {p['dim']}; }}
QComboBox {{
  border: 1px solid {p['btn_border']}; border-radius: 2px; background: {grad};
  color: {p['btn_text']}; padding: 0 14px 0 7px; }}
QComboBox:disabled {{ background: {p['face']}; color: {p['dim']}; border-color: {p['dim']}; }}
QComboBox::drop-down {{ border: none; width: 12px; subcontrol-origin: padding; subcontrol-position: right center; }}
QComboBox::down-arrow {{ image: url({arrow}); width: 7px; height: 8px; }}
QComboBox QAbstractItemView {{
  background: {p['edit_bg']}; border: 1px solid {p['edit_border']};
  color: {p['edit_text']};
  selection-background-color: {p['accent']}; selection-color: #ffffff; outline: 0; }}
QLineEdit, QTextEdit, QPlainTextEdit, QListWidget, QListView, QTreeWidget, QTableWidget {{
  background: {p['edit_bg']}; border: 1px solid {p['edit_border']}; border-radius: 0;
  color: {p['edit_text']};
  selection-background-color: {p['accent']}; selection-color: #ffffff; }}
QLineEdit:disabled {{ background: {p['face']}; color: {p['dim']}; border-color: {p['dim']}; }}
QListWidget::item {{ padding: 0 2px; }}
QListWidget::item:selected {{ background: {p['accent']}; color: #ffffff; }}
QHeaderView::section {{ background: {p['edit_bg']}; border: none; border-right: 1px solid {p['colsep']}; color: {p['edit_text']}; padding: 0 6px; }}
/* The theme's checkbox: a white top row, then the face's ramp. The
   stops are MEASURED off the native capture (2139). */
QCheckBox::indicator {{ width: 11px; height: 12px; border: 1px solid {p['border']};
  border-radius: 2px;
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:0.0714 #ffffff,
    stop:0.143 {p['cb_top']},stop:0.86 #d4d4d4,stop:0.93 {p['cb_bot']},stop:1 {p['cb_bot']}); }}
QCheckBox::indicator:checked {{ image: url({tick_k}); }}
QCheckBox::indicator:disabled {{ border-color: {p['dim']}; }}
/* checkboxes INSIDE list views (Services, Languages) are blue with a white tick */
QListView::indicator {{ width: 11px; height: 11px; border: 1px solid {p['border']}; border-radius: 2px; background: {p['edit_bg']}; }}
QListView::indicator:checked {{ background: {p['check']}; border: 1px solid {p['check']}; image: url({tick_w}); }}
/* The port draws the Services and Languages checklists as QCheckBox widgets
   with the "blue" property set rather than as a QListView, so the rule
   that makes them blue has to name the property. */
QCheckBox[blue="true"]::indicator {{ width: 11px; height: 11px; border: 1px solid {p['border']}; border-radius: 2px; background: {p['edit_bg']}; }}
QCheckBox[blue="true"]::indicator:checked {{ background: {p['check']}; border: 1px solid {p['check']}; image: url({tick_w}); }}
QGroupBox {{ border: none; margin-top: 7px; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 9px; padding: 0 2px; background: {p['face']}; color: {p['text']}; }}
QScrollBar:vertical {{ background: {p['face']}; width: 14px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p['thumb']}; margin: 0 6px; min-height: 20px; }}
QScrollBar:horizontal {{ background: {p['face']}; height: 14px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {p['thumb']}; margin: 6px 0; min-width: 20px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
QSplitter::handle {{ background: {p['face']}; }}
QMenu {{ background: {p['menu_bg']}; border: 1px solid {p['menu_border']}; color: {p['menu_text']}; }}
QMenu::item {{ padding: 3px 24px 3px 38px; color: {p['menu_text']}; }}
QMenu::item:selected {{ background: {p['menu_sel']}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {p['menu_sep']}; margin: 2px 0; }}
"""


def apply_style(app: QApplication, theme=None):
    """Apply the look.

    ``theme`` is a theme record in the native's shape (the same dict
    ``qtranslate.theme.active_theme`` returns). When one is given, the
    colours it names OVERRIDE the measured tokens -- that is how a theme
    shipped as an extension changes the app, which is what
    ``EXTENSION_SDK.md`` promises. A theme that names nothing keeps the
    measured look, so the default path is unchanged.

    The ``General.FontName``/``TextSize`` settings are honoured here
    too: the app font and the stylesheet's ``*`` rule both come from
    ``_ui_font``, so the font controls on the Basics page have a live
    consumer (they apply on the next ``apply_theme``/startup).
    """
    pal = _palette(theme)
    family, px = _ui_font()
    _ACTIVE["pal"], _ACTIVE["font"] = pal, (family, px)
    app.setStyle("Fusion")
    P, R = QPalette(), QPalette.ColorRole
    for r, c in [(R.Window, pal["face"]), (R.Base, pal["edit_bg"]),
                 (R.Button, pal["btn_top"]), (R.WindowText, pal["text"]),
                 (R.Text, pal["text"]), (R.ButtonText, pal["btn_text"]),
                 (R.Highlight, pal["accent"]), (R.HighlightedText, "#ffffff")]:
        P.setColor(r, QColor(c))
    P.setColor(QPalette.Disabled, R.WindowText, QColor(pal["dim"]))
    P.setColor(QPalette.Disabled, R.Text, QColor(pal["dim"]))
    P.setColor(QPalette.Disabled, R.ButtonText, QColor(pal["dim"]))
    P.setColor(QPalette.Disabled, R.Button, QColor(pal["dis_bg"]))
    app.setPalette(P)
    f = QFont(family); f.setPixelSize(px); app.setFont(f)
    app.setStyleSheet(qss(pal, family, px))


def apply_font(app: QApplication, name=None, size=None):
    """Re-apply the UI font from ``General.FontName``/``TextSize``.

    This is the call the Basics page's font combos need after they
    write the config (``options/base.py``'s ``notify_app`` reaches
    ``app.apply_theme``, which lands here through ``apply_style`` --
    calling this directly re-reads the config and rebuilds only the
    font-bearing parts of the stylesheet, keeping the active palette).

    ``name``/``size`` optionally override the configured values (the
    resolved point size is scaled onto the stylesheet's pixel grid, see
    ``_ui_font``). Returns the ``QFont`` now installed on ``app``.
    """
    family, px = _ui_font()
    if name is not None:
        family = (name or "").strip() or FONT_FAMILY
    if size is not None:
        try:
            px = max(6, int(round(FONT_SIZE * int(size) / 9.0)))
        except Exception:
            pass
    pal = _ACTIVE["pal"] or _palette(None)
    _ACTIVE["font"] = (family, px)
    f = QFont(family); f.setPixelSize(px)
    app.setFont(f)
    try:
        app.setStyleSheet(qss(pal, family, px))
    except Exception:
        pass
    return app.font()


def popup_colors():
    """The Appearance popup colours as ``(bg, text, frame)`` hex strings.

    ``Appearance.ColorBack``/``ColorText``/``ColorFrame`` are the popup's
    own colours in the settings file (0xBBGGRR ints, the same order the
    Options page's swatches write). Returns ``None`` for a slot the
    config does not name, so the caller keeps its measured default;
    ``qtranslate.qt.main_window`` prefers these over the measured
    constants when they are set.
    """
    try:
        from qtranslate import config as C
        ap = (C.load() or {}).get("Appearance", {}) or {}
    except Exception:
        ap = {}

    def _bgr(v):
        try:
            v = int(v)
        except Exception:
            return None
        return "#%02x%02x%02x" % (v & 255, (v >> 8) & 255, (v >> 16) & 255)

    return (_bgr(ap.get("ColorBack")), _bgr(ap.get("ColorText")),
            _bgr(ap.get("ColorFrame")))


def popup_frame_thickness():
    """``Appearance.PopupWindowFrameThickness`` (1-4 px), default 2.

    ``qtranslate.qt.popup`` reads it when it draws the popup border.
    """
    try:
        from qtranslate import config as C
        v = int((C.load() or {}).get("Appearance", {})
                .get("PopupWindowFrameThickness", 2))
    except Exception:
        v = 2
    return v if 1 <= v <= 4 else 2


def popup_auto_size():
    """``Appearance.PopupAutoSize`` -- whether the popup sizes to its
    text (True) or keeps a fixed size (False). ``qtranslate.qt.popup``
    consumes the key directly via its ``_appearance()`` config read
    (popup.py); this accessor has no callers and stays for symmetry
    with the other popup_* helpers."""
    try:
        from qtranslate import config as C
        return bool((C.load() or {}).get("Appearance", {})
                    .get("PopupAutoSize", True))
    except Exception:
        return True


def popup_pin_when_dragging():
    """``Appearance.PopupPinWhenDragging`` -- whether a drag pins the
    popup; ``qtranslate.qt.popup`` reads it on mouse release."""
    try:
        from qtranslate import config as C
        return bool((C.load() or {}).get("Appearance", {})
                    .get("PopupPinWhenDragging", True))
    except Exception:
        return True


def popup_icon_mask():
    """``Appearance.PopupIcons`` as the four header-icon toggle bits.

    The Options page's "Icons:" row is four toggle buttons (native spec
    §5.4: "4 nút toggle 22×22 đang nhấn"); the stored int is a bitmask
    over the popup's toggleable header icons (book, headphone, copy,
    transliteration -- the star is not one of them). The default 30 =
    bits 1-4 set = all four shown. ``qtranslate.qt.popup`` hides the
    icons whose bit is clear.
    """
    try:
        from qtranslate import config as C
        v = int((C.load() or {}).get("Appearance", {})
                .get("PopupIcons", 30))
    except Exception:
        v = 30
    return v & 0b11110


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
    TITLE_X, TITLE_BASE, GAP_PAD = 9, 5, 8
    FRAME_TOP = 4

    def _pal(self):
        return _ACTIVE["pal"] or _default_palette()

    def paintEvent(self, e):
        p = QPainter(self)
        pal = self._pal()
        fm = self.fontMetrics()
        p.fillRect(self.rect(), QColor(pal["face"]))
        top = self.FRAME_TOP
        r = QRect(0, top, self.width() - 1, self.height() - top - 1)
        p.setPen(QPen(QColor("#ffffff"), 1)); p.drawRect(r.translated(1, 1))
        p.setPen(QPen(QColor(pal["border"]), 1));    p.drawRect(r)
        t = self.title()
        if t:
            w = fm.horizontalAdvance(t) + self.GAP_PAD
            p.fillRect(QRect(self.TITLE_X - 1, top, w, 2), QColor(pal["face"]))
            p.setPen(QColor(pal["dim"] if not self.isEnabled() else pal["text"]))
            p.drawText(self.TITLE_X, top + self.TITLE_BASE, t)
        p.end()
