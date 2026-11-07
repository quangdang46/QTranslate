"""The notification surface on PySide6: transient toast popups.

This is the view half of the port of .tmp's notification UI. Upstream
the core posts to ``NotificationBus`` and the Swing status bar keeps a
``NotificationPopover`` list anchored to a bell icon; this port has no
status bar or bell, so the honest equivalent is a small frameless toast
that appears briefly — the same "surface a posted notification to the
user" job, minus the history list (the bus itself is the record).

``attach(app)`` subscribes the bus once and shows one toast per
notification; rapid notifications stack upward from the bottom-right
corner of the screen under the pointer, each auto-hiding after
``TOAST_MS``. All widget work is marshalled through ``app._on_ui`` (the
``_UiInvoker`` queued-signal pattern app.py already uses for
background threads), so ``notify()`` is safe from any thread.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, \
    QPainterPath
from PySide6.QtWidgets import QLabel, QWidget

from qtranslate import notify as _notify
from qtranslate_style import ACCENT, BORDER, FACE, TEXT

# Toast lifetime: long enough to read two short lines, short enough not
# to nag — upstream notifications persist in the popover; a toast does
# not, so the window is generous but bounded.
TOAST_MS = 5000
# At most this many toasts stack at once; the oldest is replaced by the
# newest (a notification storm must not cover the screen).
MAX_TOASTS = 3

# Severity -> the strip colour down the toast's left edge. The port's
# palette has no warning/error tokens, so these are the standard
# traffic-light hues.
_SEVERITY_COLOR = {
    _notify.Severity.INFO: ACCENT,
    _notify.Severity.WARNING: "#d7a200",
    _notify.Severity.ERROR: "#c42b1c",
}


class _Toast(QWidget):
    """One transient notification popup.

    Frameless, always-on-top, non-activating. ``paintEvent`` draws the
    rounded face, the severity strip and the border; the transparent
    ``QLabel`` child paints the text on top.
    """

    def __init__(self, notification, parent=None):
        super().__init__(parent,
                         Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._strip = QColor(
            _SEVERITY_COLOR.get(notification.severity, ACCENT))
        title = notification.title or ""
        body = notification.body or ""
        text = ("<b>%s</b><br>%s" % (title, body)) if body else \
            "<b>%s</b>" % title
        self._label = QLabel(text, self)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setStyleSheet(
            "QLabel { color: %s; background: transparent; "
            "padding: 8px 10px 8px 14px; }" % TEXT)
        self._label.setMaximumWidth(340)
        self.adjustSize()
        self.setFixedSize(self.size())
        self._label.setGeometry(self.rect())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, self.width() - 1,
                            self.height() - 1, 6, 6)
        p.fillPath(path, QColor(FACE))
        # The severity strip: a 4px bar down the left edge, clipped to
        # the rounded corner by the same path.
        p.save()
        p.setClipPath(path)
        p.fillRect(0, 0, 4, self.height(), self._strip)
        p.restore()
        p.setPen(QColor(BORDER))
        p.drawPath(path)
        p.end()
        super().paintEvent(event)


class _ToastStack:
    """The toasts currently on screen, bottom-up from the corner."""

    def __init__(self, app):
        self.app = app
        self._toasts = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------- surface
    def push(self, notification):
        with self._lock:
            if len(self._toasts) >= MAX_TOASTS:
                oldest = self._toasts.pop(0)
                oldest.deleteLater()
            toast = _Toast(notification)
            self._toasts.append(toast)
        self._place()
        toast.show()
        QTimer.singleShot(TOAST_MS, toast.hide)
        # Once hidden the widget is dead weight: drop it on the next
        # event-loop turn so the stack list stays honest.
        QTimer.singleShot(TOAST_MS + 100, lambda t=toast: self._drop(t))

    def _drop(self, toast):
        with self._lock:
            if toast in self._toasts:
                self._toasts.remove(toast)
        self._place()
        toast.deleteLater()

    def _place(self):
        """Stack the live toasts upward from the bottom-right corner of
        the screen under the cursor — the position a tray-adjacent
        notification occupies on every platform Qt supports."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or \
            QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        y = geo.bottom() - 12
        for toast in reversed(self._toasts):
            toast.move(geo.right() - toast.width() - 12,
                       y - toast.height())
            y -= toast.height() + 8


_stack = None
_attached = False
_attach_lock = threading.Lock()


def attach(app):
    """Wire the bus to the toast surface for ``app`` (a ``QtApp``).

    Idempotent: the first call subscribes; later calls (tests, a second
    front end) return the existing stack. The handler is a plain
    callable — it marshals through ``app._on_ui`` itself, so the bus may
    post from any thread.
    """
    global _stack, _attached
    with _attach_lock:
        if _attached:
            return _stack
        _attached = True
    stack = _ToastStack(app)
    _stack = stack

    def _deliver(n):
        app._on_ui(lambda: stack.push(n))

    _notify.default_bus().subscribe(_deliver)
    return stack


def detach():
    """Test hook: forget the stack so ``attach`` can run again."""
    global _stack, _attached
    with _attach_lock:
        _stack = None
        _attached = False
