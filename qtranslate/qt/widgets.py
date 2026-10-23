"""Layout helpers for the PySide6 port.

The coordinates are the ONES MEASURED FROM THE NATIVE CAPTURES: every
number in ``qtranslate-pyside6-spec.md`` is a pixel position read off
``docs/review/native_screens/*.png``.

The convention is the reference renderer's (``qtranslate_ui.py``): a
coordinate is a position in the ORIGINAL SCREENSHOT, which includes the
Windows title bar and the 1-pixel frame. Each window declares
``ORIGIN`` -- where its client area starts inside that screenshot -- and
``put()`` subtracts it, so the numbers in the spec can be copied
straight across without a second conversion.

There is ONE implementation of these helpers, here, and the reference
renderer imports it, so the reference and the real windows cannot drift
apart.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QCheckBox,
                               QComboBox, QFrame, QLabel, QLineEdit, QListView,
                               QPushButton, QWidget)

from qtranslate_style import (ACCENT, BORDER, BTN_SHADOW, COLSEP, DIM,
                              FACE, POPUP_BG, POPUP_BORDER, POPUP_ICON,
                              POPUP_TEXT, THUMB, TEXT, EtchedGroupBox)

from . import icons

LINK = "#0066cc"

# How tall a combo's drop-down list may get.
#
# MEASURED off the native's own dialog resources: DLG129's two language
# combos (ids 1001 and 1002) are 120 DIALOG UNITS tall, and for a
# CBS_DROPDOWNLIST the template's cy IS the height of the dropped-down
# list. The dialog's font is "MS Shell Dlg" 8pt, whose average
# character height (plus leading) is 15px, so one vertical DLU is
# 15/8 px and the list is 120 * 15/8 = 225px. (The tool that reads the
# resources is ``tools/dlg_parse.py``; the conversion is the Windows
# one, ``px_y = du_y * avg_char_h / 8``.)
#
# It matters because the Qt combo draws its drop-down as tall as the
# LIST, not as tall as the list may be: with the 74 languages of the
# native's own table the drop-down came out 1266px tall -- taller than
# the screen, with the languages past the fold reachable only by
# scrolling with the wheel and no scroll bar to show that they were
# there. The native's list is 225px and scrolls.
DROPDOWN_H = 225

# The section headings of the Services page, MEASURED off the native
# capture 2136: the text is #003399 and the rule that runs beside it is
# #b2c1e0. The headings are Tahoma 9pt (12px), not the 8pt of the body.
HEADING, HEADING_LINE = "#003399", "#b2c1e0"


def origin_of(parent):
    """Where the parent window's client area starts in the screenshot."""
    return getattr(parent, "ORIGIN", None) or getattr(parent, "_abs", (0, 0))


def put(parent, w, l, t, ww, hh):
    """Place a widget at a SCREENSHOT coordinate, converted to client."""
    ox, oy = origin_of(parent)
    w.setParent(parent)
    w.setGeometry(l - ox, t - oy, ww, hh)
    w.show()
    return w


def label(parent, l, cy, text, color=None, bold=False, underline=False,
          w=None, align=Qt.AlignLeft, size=None):
    """A label whose text sits on the row ``cy``.

    ``size`` is the font size in PIXELS: the app's stylesheet asks for
    11px (Tahoma 8pt) everywhere, and the few labels that the native
    draws bigger -- the section headings -- have to override it in the
    widget's own stylesheet, which is the only one that wins.
    """
    q = QLabel(text)
    q.setAlignment(align | Qt.AlignVCenter)
    st = ""
    if color:
        st += f"color:{color};"
    if bold:
        st += "font-weight:700;"
    if underline:
        st += "text-decoration:underline;"
    if size:
        st += f"font-size:{size}px;"
    q.setStyleSheet("QLabel{background:transparent;" + st + "}")
    if w is None:
        if size:
            f = QFont(q.font())
            f.setPixelSize(size)
            width = QFontMetrics(f).horizontalAdvance(text) + 6
        else:
            width = q.fontMetrics().horizontalAdvance(text) + 6
    else:
        width = w
    return put(parent, q, l, cy - 8, width, 16)


def button(parent, l, t, w, text, h=21, enabled=True, shadow=False):
    """A themed push button.

    ``shadow`` draws the 1px light line the theme's buttons cast under
    themselves: MEASURED off the capture (a #fcfcfc row under the
    button's bottom border). The flat buttons -- the ones with no
    border -- have none.
    """
    b = QPushButton(text)
    b.setEnabled(enabled)
    b.setFocusPolicy(Qt.NoFocus)
    if shadow:
        rect(parent, l, t + h, w, 1, BTN_SHADOW)
    return put(parent, b, l, t, w, h)


class _ComboView(QListView):
    """The list inside a combo's drop-down.

    NOT the default ``QComboBoxListView``. With the app's stylesheet the
    default one paints the CURRENT item with the background the combo's
    own rule gives it -- and that rule carries a GRADIENT (the Win32
    button face), which Qt cannot use for an item, so the current
    language came out as a black bar with black text on it: the row the
    user is standing on was unreadable. A plain ``QListView`` draws the
    current item with the palette's Highlight (the accent) and
    HighlightedText (white), which is what the native's Win32 drop-down
    shows.
    """


class _HideScrollers(QObject):
    """Keeps the drop-down's up/down buttons out of sight.

    The Qt container draws those two buttons when the style emulates a
    popup-menu combo -- Fusion does -- and shows them again whenever the
    list scrolls. The native's Win32 drop-down has a scroll bar and no
    buttons, so every show is turned into a hide.
    """

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            obj.hide()
            return True
        return False


def combo(parent, l, t, w, text, h=20, enabled=True, values=None,
          dropdown_h=DROPDOWN_H):
    """A combo box, with the drop-down the native's has.

    The drop-down is the part the user sees when the list opens, and it
    had three faults, all of them measured rather than guessed (see
    ``tests/regress_qt_combo_popup.py``):

    * it was as tall as the whole list -- 1266px for the 74 languages
      of the native's own table -- so it ran off the screen; it is now
      bounded by the native's own drop-down height,
    * it had no scroll bar, so the languages past the fold could not be
      reached, and
    * its current row was painted black on black.

    ``dropdown_h`` is that bound in pixels; a list shorter than the
    bound still opens at its own height.
    """
    c = QComboBox()
    view = _ComboView()
    c.setView(view)
    # AFTER setView(): the container forces the vertical scroll bar off
    # (it emulates the old-style combo, which has no scroll bar), and a
    # Win32 drop-down scrolls.
    view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    view.setUniformItemSizes(True)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    container = c.view().parentWidget()
    container.setMaximumHeight(dropdown_h)
    hider = _HideScrollers()
    hider.setParent(container)
    for child in container.children():
        # The container's other children are the two up/down scroller
        # buttons it draws when the style emulates a popup-menu combo.
        if child is not view:
            child.installEventFilter(hider)
    for v in (values if values is not None else [text]):
        c.addItem(v)
    if text and values is None:
        c.setCurrentIndex(0)
    elif text in (values or ()):
        c.setCurrentIndex(list(values).index(text))
    c.setEnabled(enabled)
    c.setFocusPolicy(Qt.NoFocus)
    return put(parent, c, l, t, w, h)


def check(parent, l, cy, text, on=False, blue=False):
    """A checkbox; ``blue`` = the one INSIDE a list view (blue box,
    white tick) rather than the ordinary one (grey fill, black tick)."""
    c = QCheckBox(text)
    c.setChecked(on)
    c.setFocusPolicy(Qt.NoFocus)
    c.setProperty("blue", "true" if blue else "false")
    width = 13 + 5 + c.fontMetrics().horizontalAdvance(text) + 4
    return put(parent, c, l, cy - 8, width, 16)


def group(parent, l, t, w, h, title):
    """Native's Win32 group box (see ``qtranslate_style.EtchedGroupBox``).

    ``l, t`` is where the FRAME is: the native draws the title so that
    it straddles the frame's top line, which puts the top of the title
    4px above it. The widget is that much taller at the top, so the
    frame lands where the measurement says it does.
    """
    top = EtchedGroupBox.FRAME_TOP
    return put(parent, EtchedGroupBox(title), l, t - top, w, h + top)


def field(parent, l, t, w, h, text="", enabled=True):
    e = QLineEdit(text)
    e.setEnabled(enabled)
    e.setTextMargins(3, 0, 0, 0)
    return put(parent, e, l, t, w, h)


def panel(parent, l, t, w, h, name="panel"):
    """A white inset area with a 1px border (a list or a text pane)."""
    f = QFrame()
    f.setObjectName(name)
    f.setStyleSheet(f"QFrame#{name}{{background:#fff;border:1px solid {BORDER};}}")
    put(parent, f, l, t, w, h)
    f._abs = (l, t)
    return f


def rect(parent, l, t, w, h, color, name="r"):
    f = QFrame()
    f.setObjectName(name)
    f.setStyleSheet(f"QFrame#{name}{{background:{color};border:none;}}")
    return put(parent, f, l, t, w, h)


def hline(parent, y, x0, x1, color=BORDER):
    return rect(parent, x0, y, x1 - x0, 1, color)


def vline(parent, x, y0, y1, color=BORDER):
    return rect(parent, x, y0, 1, y1 - y0, color)


def icon(parent, l, t, kind, name):
    """One of the icons recovered from the native binary."""
    pm = icons.pixmap(kind, name)
    q = QLabel()
    q.setPixmap(pm)
    q.setFixedSize(pm.width(), pm.height())
    q.setStyleSheet("QLabel{background:transparent;}")
    q.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    return put(parent, q, l, t, pm.width(), pm.height())


def sq(parent, l, t, color, s=14):
    return rect(parent, l, t, s, s, color)


def extension_menu_entries(parent, app, slot):
    """The menu contributions an extension registered for ``slot``.

    Every menu the app draws calls this with its OWN slot name
    (``ui_slots.MENU_SLOT_IDS``: main, source_context, result_context,
    language, tray, history_ctx, dict_header, history_menu, ocr), so a
    contribution lands in the menu its author targeted instead of only in
    the tray. Returns ``[(label, callable), ...]``; empty when no
    extension contributes, which leaves the menu exactly as native's.
    """
    manager = getattr(app, "ext_manager", None)
    slots = getattr(manager, "ui_slots", None) if manager else None
    if slots is None:
        return []
    try:
        entries = slots.entries("menu", slot)
    except Exception:
        return []
    out = []
    for entry in entries:
        contrib = entry.get("contribution")
        if callable(contrib):
            out.append((entry.get("label") or "Extension", contrib))
    return out


class Base(QWidget):
    """A window whose client area is a fixed size, as native's are.

    The size is the CLIENT size: the native capture is the client plus
    the OS title bar and frame, and the difference is in ``ORIGIN``.
    """

    ORIGIN = (1, 31)
    SIZE = (514, 391)

    # True when the window wants the keyboard focus itself rather than
    # one of its children. The main window sets it because its source
    # pane is an edit control: give that the focus and it draws a
    # blinking caret, which the native's capture does not have.
    WANTS_FOCUS = False

    def __init__(self):
        super().__init__()
        self.setFixedSize(*self.SIZE)
        self.setAutoFillBackground(True)
