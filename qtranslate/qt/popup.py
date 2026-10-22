"""The translation popup (native's Ctrl+Q window) on PySide6.

Native's popup is a frameless 200x68 window: a grey body with a 1px
border, a top row with a close button, the language pair, a star and the
popup's own icons, and the translation below.

The capture is ``docs/review/native_screens/2130.png`` -- the popup
floating over another application, so the window itself is the 200x68
rectangle at (28, 30)..(227, 97) of that image, with its interior the
``#d0d0d0`` popup background and its border ``#53606c``. The rest of
that image is the application behind it, which is not part of the
popup.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from qtranslate_style import POPUP_BG, POPUP_BORDER, POPUP_ICON, POPUP_TEXT

from .widgets import icon


class PopupWindow(QWidget):
    """The popup: a frameless tool window that shows one translation."""

    ORIGIN, SIZE = (0, 0), (200, 68)

    def __init__(self, app=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool
                         | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setFixedSize(200, 68)
        self.setStyleSheet("Popup{background:%s;border:1px solid %s;}"
                           % (POPUP_BG, POPUP_BORDER))
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.btn_close = QLabel("✕", self)
        self.btn_close.setStyleSheet("background:transparent;color:%s;"
                                     % POPUP_ICON)
        self.btn_close.setGeometry(7, 4, 12, 16)

        self.lbl_pair = QLabel("", self)
        self.lbl_pair.setStyleSheet("background:transparent;color:%s;"
                                    % POPUP_ICON)
        self.lbl_pair.setGeometry(25, 4, 100, 16)

        self.lbl_star = QLabel("★", self)
        self.lbl_star.setStyleSheet("background:transparent;color:%s;"
                                    % POPUP_ICON)
        self.lbl_star.setGeometry(128, 4, 16, 16)

        self.lbl_text = QLabel("", self)
        self.lbl_text.setStyleSheet("background:transparent;color:%s;"
                                     % POPUP_TEXT)
        self.lbl_text.setGeometry(6, 30, 188, 16)

    def set_text(self, source: str, result: str, pair: str = ""):
        """Show one translation."""
        self.lbl_pair.setText(pair or (source or "")[:40])
        self.lbl_text.setText(result or "")
        self.adjustSize()
