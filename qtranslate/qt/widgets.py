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

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QLabel,
                               QLineEdit, QPushButton, QWidget)

from qtranslate_style import (ACCENT, BORDER, COLSEP, DIM, FACE, POPUP_BG,
                              POPUP_BORDER, POPUP_ICON, POPUP_TEXT, THUMB,
                              TEXT, EtchedGroupBox)

from . import icons

LINK, HEADING, HEADING_LINE = "#0066cc", "#005eb8", "#b5c9e0"


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
          w=None, align=Qt.AlignLeft):
    q = QLabel(text)
    q.setAlignment(align | Qt.AlignVCenter)
    st = ""
    if color:
        st += f"color:{color};"
    if bold:
        st += "font-weight:700;"
    if underline:
        st += "text-decoration:underline;"
    q.setStyleSheet("QLabel{background:transparent;" + st + "}")
    width = w or (q.fontMetrics().horizontalAdvance(text) + 6)
    return put(parent, q, l, cy - 8, width, 16)


def button(parent, l, t, w, text, h=21, enabled=True):
    b = QPushButton(text)
    b.setEnabled(enabled)
    b.setFocusPolicy(Qt.NoFocus)
    return put(parent, b, l, t, w, h)


def combo(parent, l, t, w, text, h=20, enabled=True, values=None):
    c = QComboBox()
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
    """Native's Win32 group box (see ``qtranslate_style.EtchedGroupBox``)."""
    return put(parent, EtchedGroupBox(title), l, t, w, h)


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


class Base(QWidget):
    """A window whose client area is a fixed size, as native's are.

    The size is the CLIENT size: the native capture is the client plus
    the OS title bar and frame, and the difference is in ``ORIGIN``.
    """

    ORIGIN = (1, 31)
    SIZE = (514, 391)

    def __init__(self):
        super().__init__()
        self.setFixedSize(*self.SIZE)
        self.setAutoFillBackground(True)
