"""Pick a rectangle on the screen, for the OCR flow.

Native's "Text recognition" opens a full-screen region selector and
OCRs whatever the user drags out of it. This is the same thing on
PySide6: a frameless, translucent window over the whole screen, a
rubber band for the selection, and the grabbed PNG of the rectangle.

The capture itself is the OS's -- ``QScreen.grabWindow`` -- so the
pixels are the screen's, exactly as native's are.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


class RegionPicker(QWidget):
    """A full-screen overlay that returns the rectangle the user drags.

    ``picked`` is called with the rectangle in SCREEN coordinates (the
    coordinates the grab is taken in) when the selection is made, and
    with None when the user cancels.
    """

    def __init__(self, picked):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool)
        self._picked = picked
        self._origin = QPoint()
        self._current = QPoint()
        self._dragging = False
        self.setWindowState(Qt.WindowActive)
        self.setCursor(Qt.CrossCursor)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

    # ---------------------------------------------------------------- events
    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self._cancel()
            return
        self._origin = e.globalPosition().toPoint()
        self._current = self._origin
        self._dragging = True
        self.update()

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._current = e.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if not self._dragging:
            return
        self._dragging = False
        rect = self._rect()
        self.hide()
        if rect.width() < 4 or rect.height() < 4:
            self._picked(None)
            return
        self._picked(rect)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._cancel()

    def _cancel(self):
        self._dragging = False
        self.hide()
        self._picked(None)

    # ------------------------------------------------------------- painting
    def _rect(self) -> QRect:
        return QRect(self._origin, self._current).normalized()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 60))
        if self._dragging:
            r = self._rect()
            p.setPen(QPen(QColor(0, 120, 215), 2))
            p.drawRect(r)
            p.fillRect(r, QColor(0, 120, 215, 40))

    # ----------------------------------------------------------------- usage
    @staticmethod
    def pick():
        """Show the picker and return the chosen rectangle, or None.

        The caller runs this on the UI thread; the result arrives
        through the ``picked`` callback, because a modal dialog would
        block the event loop the picker needs.
        """
        result = {"rect": None, "done": False}

        def _picked(rect):
            result["rect"] = rect
            result["done"] = True

        picker = RegionPicker(_picked)
        screen = QGuiApplication.primaryScreen()
        picker.setGeometry(screen.geometry())
        picker.show()
        picker.raise_()
        picker.activateWindow()
        return picker, result


def grab_rect(rect: QRect) -> bytes:
    """The PNG bytes of a screen rectangle."""
    from PySide6.QtCore import QBuffer, QByteArray
    screen = QGuiApplication.primaryScreen()
    pm = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(ba)
