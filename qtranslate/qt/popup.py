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

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
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

        self._extension_icons()

        self.lbl_text = QLabel("", self)
        self.lbl_text.setStyleSheet("background:transparent;color:%s;"
                                     % POPUP_TEXT)
        self.lbl_text.setGeometry(6, 30, 188, 16)

    def _extension_icons(self):
        """Entries an extension contributed to the popup's icon row.

        The slot is ("popup", "icons") -- native's PopupWindowIcons. A
        contribution is a callable returning a short label; it is placed
        in the row after the star. With no extension the row is exactly
        the native's (a close mark, the pair, the star), so the pixels
        are unchanged.
        """
        app = getattr(self, "app", None)
        manager = getattr(app, "ext_manager", None)
        slots = getattr(manager, "ui_slots", None) if manager else None
        if slots is None:
            return
        try:
            entries = slots.entries("popup", "icons")
        except Exception:
            return
        x = 148
        for entry in entries:
            contrib = entry.get("contribution")
            if not callable(contrib):
                continue
            try:
                label = str(contrib() or "")
            except Exception:
                continue
            if not label:
                continue
            q = QLabel(label[:2], self)
            q.setStyleSheet("background:transparent;color:%s;" % POPUP_ICON)
            q.setGeometry(x, 4, 14, 16)
            x += 16

    def set_text(self, source: str, result: str, pair: str = ""):
        """Show one translation."""
        self.lbl_pair.setText(pair or (source or "")[:40])
        self.lbl_text.setText(result or "")
        self.adjustSize()
        self._extension_body(source, result, pair)

    def _extension_body(self, source: str, result: str, pair: str):
        """Let an extension render the popup's body instead.

        The published slot is ``("popup", "body")``: an extension
        registers anything callable, and it receives the same three
        pieces the built-in label gets. Its answer replaces the
        built-in text. With no extension the built-in label is left
        exactly as it was, so the native's pixels are unchanged.
        """
        app = getattr(self, "app", None)
        manager = getattr(app, "ext_manager", None)
        slots = getattr(manager, "ui_slots", None) if manager else None
        if slots is None:
            return
        try:
            winner = slots.winner("popup", "body")
        except Exception:
            return
        if not winner:
            return
        contrib = winner.get("contribution")
        if not callable(contrib):
            return
        try:
            text = contrib(source, result, pair)
        except TypeError:
            # A contribution may take just the result; the simplest
            # contract wins rather than failing the popup.
            try:
                text = contrib(result)
            except Exception:
                return
        except Exception:
            return
        if text is None:
            return
        self.lbl_text.setText(str(text))
        self.adjustSize()

    # ------------------------------------------------------------- show
    def place(self):
        """The Appearance popup settings, native's ShowPopupWindow.

        The tkinter popup did this through `_place_aux`; the bodies it
        drew are the same three: the saved alpha, the position (near the
        pointer when PopupAutoPos is on, the remembered blob when not),
        and the auto-close timer.
        """
        try:
            from qtranslate import config as _C
            _ap = _C.load().get("Appearance", {})
        except Exception:
            _ap = {}
        # PopupAutoFocus: steal focus only when enabled (default False).
        if _ap.get("PopupAutoFocus"):
            try:
                self.activateWindow()
                self.setFocus()
            except Exception:
                pass
        # Transparency 0..255 -> window alpha (only when < 255). Native
        # default 217 (DAT_005494A4), not 255.
        try:
            _tr = int(_ap.get("Transparency", 217))
            self.setWindowOpacity(_tr / 255.0 if 0 < _tr < 255 else 1.0)
        except Exception:
            pass
        # PopupAutoPos: place near the pointer. When off, restore the
        # remembered geometry (General.WindowPopupPlacement).
        if _ap.get("PopupAutoPos", True):
            try:
                p = QCursor.pos()
                self.move(p.x() + 12, p.y() + 12)
            except Exception:
                pass
        else:
            try:
                from qtranslate.placement import decode_placement
                rc = decode_placement(
                    _C.load().get("General", {})
                    .get("WindowPopupPlacement", ""))
                if rc:
                    x, y, _w, _h, _fl = rc
                    self.move(x, y)
            except Exception:
                pass
        # PopupTimeout (seconds): auto-close; 0/absent = stay.
        try:
            _to = int(_ap.get("PopupTimeout", 0))
        except Exception:
            _to = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        if _to > 0:
            self._timer.start(_to * 1000)
