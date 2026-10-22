"""The History window (native DLG 178) on PySide6.

The geometry is measured off ``docs/review/native_screens/2133.png`` (the
real QTranslate 6.10.0 history window, 476x320, client area 474x288 at
``(1, 31)``):

  * a search field across the top, x 4..471, y 34..55, with a small
    clear button at its right end (x 456..465, y 40..49);
  * a white list panel under it, x 4..471, y 60..287, in which each
    entry is a FACE-coloured header row (a star and the source text)
    with the translation on an indented white row under it;
  * the bottom row: Clear, Save as..., the star toggle, and OK.

The list is the app's own history -- the same list the tkinter front
end writes -- so both front ends show the same entries.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from qtranslate_style import FACE, TEXT

from .widgets import (Base, button, hline, icon, label, panel, put, rect)


class HistoryWindow(Base):
    """The History window: the search field, the list, the bottom row."""

    ORIGIN, SIZE = (1, 31), (474, 288)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("History")
        self._build()

    def _build(self):
        # The search field, and the small clear button at its right.
        field = self._field()
        self.btn_clear_search = button(self, 456, 40, 10, "")
        self.btn_clear_search.setObjectName("flat")

        # The list panel.
        self.list = panel(self, 4, 60, 468, 228)
        self._fill()

        # The bottom row.
        self.btn_clear = button(self, 5, 294, 71, "Clear", 21)
        self.btn_save = button(self, 84, 294, 107, "Save as...", 21)
        self.btn_star = button(self, 199, 294, 19, "", 21)
        self.btn_ok = button(self, 399, 294, 71, "OK", 21)

        self.btn_ok.clicked.connect(self.close)
        self.btn_clear.clicked.connect(self._clear)

    def _field(self):
        from PySide6.QtWidgets import QLineEdit
        e = QLineEdit()
        e.setStyleSheet("QLineEdit{background:#fff;border:none;}")
        put(self, e, 4, 34, 467, 21)
        return e

    def _fill(self):
        """The list: one header row per entry, with its translation
        under it."""
        y = 66
        for entry in list(self.app.history)[:12]:
            service, src, res = entry
            rect(self.list, 5, y - 1, 466, 13, FACE, "histrow")
            icon(self.list, 8, y - 3, "ui_icons", "star")
            label(self.list, 31, y + 5, src[:60])
            icon(self.list, 27, y + 15, "service_icons", service)
            label(self.list, 51, y + 20, res[:60])
            y += 30

    def _clear(self):
        self.app.history = []
        self._fill()
