"""Pick a rectangle on the screen, for the OCR flow.

Native's "Text recognition" opens a full-screen region selector and
OCRs whatever the user drags out of it. This is the same thing on
PySide6: a frameless, translucent window over the whole screen, a
rubber band for the selection, and the grabbed PNG of the rectangle.

The overlay keys are native's own (FUN_004377CB): S saves the grab to a
PNG file, C copies it to the clipboard, Enter sends to OCR like a
release does, the arrows adjust the selection, Esc/Delete close. They
share ONE capture path (``_grab_png``), exactly as the native builder
does, so a fix to the capture fixes all three consumers.

The capture itself is the OS's -- ``QScreen.grabWindow`` -- so the
pixels are the screen's, exactly as native's are.
"""
from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget
class RegionPicker(QWidget):
    """A full-screen overlay that returns the rectangle the user drags.

    ``picked`` is called with the rectangle in SCREEN coordinates (the
    coordinates the grab is taken in) when the selection is made, and
    with None when the user cancels -- or when a key (S/C) terminates
    the pick early, because that key has already consumed the grab.
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
        else:
            self._picked(rect)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape or k == Qt.Key_Delete:
            self._cancel()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self._dragging = False
            rect = self._rect()
            self.hide()
            self._picked(rect if rect.width() >= 4 else None)
        elif k in (Qt.Key_S, Qt.Key_C):
            pm = self._grab()
            data = self._png_of(pm) if pm is not None else None
            self.hide()
            self._picked(None)
            if not data:
                return
            if k == Qt.Key_S:
                try:
                    import datetime as _dt
                    import os as _o
                    _dir = _o.path.expanduser("~")
                    try:
                        from qtranslate import config as _C
                        _dir = _C.load().get(
                            "Ocr", {}).get("SaveImagePath", "") or _dir
                    except Exception:
                        pass
                    _fn = "ocr_%s.png" % _dt.datetime.now().strftime(
                        "%Y%m%d_%H%M%S")
                    with open(_o.path.join(_dir, _fn), "wb") as _fh:
                        _fh.write(data)
                except Exception as ex:
                    print("[ocr save] %s" % ex)
            else:
                try:
                    QApplication.clipboard().setPixmap(pm)
                except Exception:
                    pass
        elif k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            if self._dragging:
                dx, dy = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
                          Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}[k]
                self._origin += QPoint(dx, dy)
                self._current += QPoint(dx, dy)
                self.update()

    def _png_of(self, pm) -> bytes | None:
        try:
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QBuffer.WriteOnly)
            pm.save(buf, "PNG")
            buf.close()
            return bytes(ba)
        except Exception:
            return None

    def _cancel(self):
        self._dragging = False
        self.hide()
        self._picked(None)

    # ------------------------------------------------------------- capture
    def _grab(self):
        """The current rubber-band rect as a pixmap (None when too thin).

        Shared by the OCR send, the S save and the C copy -- one capture
        path, as the native overlay's own _grab_png is.
        """
        try:
            r = self._rect()
            if r.width() < 5 or r.height() < 5:
                return None
            screen = QGuiApplication.primaryScreen()
            return screen.grabWindow(self.winId(),
                                     r.x(), r.y(), r.width(), r.height())
        except Exception:
            return None

    def _grab_png(self) -> bytes | None:
        try:
            pm = self._grab()
            if pm is None:
                return None
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QBuffer.WriteOnly)
            pm.save(buf, "PNG")
            buf.close()
            return bytes(ba)
        except Exception:
            return None

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
        picker.showFullScreen()
        picker.raise_()
        picker.activateWindow()
        # The caller polls ``result`` on its own cadence; a modal dialog
        # would block the event loop the picker needs.
        return picker, result


def grab_rect(rect: QRect) -> bytes:
    """The PNG bytes of a screen rectangle."""
    from PySide6.QtCore import QBuffer, QByteArray as _QBA
    screen = QGuiApplication.primaryScreen()
    pm = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
    ba = _QBA()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(ba)
