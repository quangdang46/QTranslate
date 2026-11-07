"""Cursor-following loading marker -- .tmp's ``LoadingIndicator``.

The Swing reference does NOT open the quick-translate popup while a
fresh translation is in flight. It shows this tiny indeterminate
progress bar under the pointer for a guaranteed minimum of 350 ms,
then the popup opens once, already sized for the final result.
Opening a full popup with a spinner and replacing it <1 s later is
why the loading state was invisible -- sub-second translations never
gave the popup a perceptible frame.

Mirrors ``SelectionTranslateButton``/``MouseIcon`` window flags:
framedless, always-on-top, never takes focus or activates the app.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QProgressBar, QWidget

W, H = 45, 10
GAP_Y = 20          # .tmp places the marker at pointer + (0, 20)
FOLLOW_MS = 10      # .tmp tracks the pointer every 10 ms
MIN_VISIBLE_MS = 350


class LoadingIndicator(QWidget):
    """One shared marker; ``show_at_cursor``/``hide`` manage lifetime."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint
                         | Qt.WindowDoesNotAcceptFocus
                         | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(W, H)
        bar = QProgressBar(self)
        bar.setRange(0, 0)               # indeterminate
        bar.setTextVisible(False)
        bar.setGeometry(0, 0, W, H)
        bar.setStyleSheet(
            "QProgressBar { border: 2px solid #666; background: #eee;"
            " border-radius: 1px; }"
            "QProgressBar::chunk { background: #0078d7; }")
        self._timer = QTimer(self)
        self._timer.setInterval(FOLLOW_MS)
        self._timer.timeout.connect(self._follow)
        self._shown_at = 0
        self._hide_at = 0
        self._pending = False

    def show_at_cursor(self):
        """(Re)show under the pointer; cancels any pending hide."""
        from PySide6.QtCore import QDateTime
        self._pending = False
        self._shown_at = QDateTime.currentMSecsSinceEpoch()
        self._follow()
        self.show()
        self._timer.start()
        # Failsafe: if a translation callback is lost the marker must
        # not spin forever under the user's cursor.
        QTimer.singleShot(15000, self._hide_now)

    def _follow(self):
        p = QCursor.pos()
        self.move(p.x(), p.y() + GAP_Y)

    def hide(self):       # noqa: A003 -- Qt name, matches .tmp hideNow
        """Hide once the 350 ms minimum has elapsed; otherwise defer."""
        from PySide6.QtCore import QDateTime
        self._timer.stop()
        elapsed = QDateTime.currentMSecsSinceEpoch() - self._shown_at
        if elapsed >= MIN_VISIBLE_MS:
            super().hide()
            return
        if not self._pending:
            self._pending = True
            self._hide_at = MIN_VISIBLE_MS - elapsed
            QTimer.singleShot(self._hide_at, self._hide_now)

    def _hide_now(self):
        self._pending = False
        super().hide()
