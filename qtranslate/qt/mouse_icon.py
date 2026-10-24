"""The floating translate icon of mouse mode 0 ("Show icon").

Native's mode 0: select text, click, and a small QTranslate icon pops up
UNDER the selection -- clicking it translates, no Ctrl+Q needed. The
port treated mode 0 as "off" because it could not draw that icon
(checklist row C10, `not-started`). This is the icon.

The window is a 24px frameless always-on-top tool window showing the
app's service icon; it carries the captured text and hides itself after
a few seconds or on any click elsewhere. Clicking it hands the captured
text back to the app, which translates it exactly like Ctrl+Q would.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

SIZE = 24


def _badge_pixmap(app):
    """The icon to show: the current service's own icon, else a drawn
    'Q' roundel -- never an empty box."""
    try:
        from .widgets import icons
        pm = icons.pixmap("service_icons",
                          getattr(app, "service", "google") or "google")
        if pm is not None and not pm.isNull():
            return pm
    except Exception:                       # noqa: BLE001
        pass
    pm = QPixmap(SIZE, SIZE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.blue)
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, SIZE - 2, SIZE - 2)
    p.setPen(Qt.white)
    f = p.font()
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "Q")
    p.end()
    return pm


class MouseIcon(QWidget):
    """The under-the-selection translate button."""

    def __init__(self, app, on_translate):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool
                         | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput * 0)
        self.app = app
        self._text = ""
        self._on_translate = on_translate
        self.setFixedSize(SIZE, SIZE)
        lab = QLabel(self)
        lab.setPixmap(_badge_pixmap(app))
        lab.setGeometry(0, 0, SIZE, SIZE)
        lab.setStyleSheet("background:transparent;")
        lab.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        lab.mousePressEvent = self._clicked
        self.mousePressEvent = self._clicked
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def pop(self, x, y, text):
        """Show under the selection at screen (x, y), for 6 seconds."""
        self._text = text or ""
        self.move(max(0, x - SIZE // 2), y + 14)
        self.show()
        self.raise_()
        self._timer.start(6000)

    def _clicked(self, _e):
        text, self._text = self._text, ""
        self.hide()
        if text:
            self._on_translate(text)

    def current_text(self):
        return self._text
