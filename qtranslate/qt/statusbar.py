"""The main window's status bar — the port of .tmp's ``StatusBar``.

Upstream (``ui-swing/.../statusbar/StatusBar.kt`` +
``StatusBarController.kt``) the bar is a slim strip under the provider
buttons carrying three things: a chip with the latest status message
(coloured by notification type), a bell button that opens the
``NotificationPopover`` history list, and an indeterminate progress
bar while a translation runs.

The port has no status-message pipeline (no ``StatusCode`` events) and
no loading flag on the window, so the honest minimum is the
notification half: the chip shows the LATEST notification posted to
``qtranslate.notify``'s bus — severity glyph + title/body, coloured by
severity like upstream's chip — and defaults to upstream's own
``ready_message`` ("Ready") when nothing has been posted. Clicking the
bar opens a small menu listing the buffered notifications, the same
job ``NotificationPopover`` does (the bus buffer itself is in-memory
and replay-only, so the bar keeps its own last-10 view).

Visibility is ``General.ShowStatusBar`` (upstream
``toolbarVisibility.isStatusBarVisible``, default true); the main
window owns the toggle and the bottom-strip geometry.
"""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QWidget

from qtranslate import notify as _notify

# The strip's height in client pixels; the main window reserves
# HEIGHT + a 4px gap below the provider strip for it.
HEIGHT = 18
# Upstream's ``main_window_status_bar.ready_message`` (embedded_en.toml).
READY = "Ready"
# .tmp's NotificationPopover caps its list at 50; the bus replays 10,
# so the bar's own view keeps the same ten the bus itself remembers.
HISTORY_MAX = 10

# Severity -> (glyph, colour). The colours are the toast surface's own
# (qt/notify.py) so the two notification surfaces agree.
_SEVERITY = {
    _notify.Severity.INFO: ("\u2022", "#3a6ea5"),
    _notify.Severity.WARNING: ("\u25b2", "#b8860b"),
    _notify.Severity.ERROR: ("\u2716", "#c42b1c"),
}


def _text_of(n):
    """One notification as a single line: title, then body when it
    adds anything (upstream's Custom case renders "title: body")."""
    title = (n.title or "").strip()
    body = (n.body or "").strip()
    if title and body and body != title:
        return "%s \u2014 %s" % (title, body)
    return title or body


class StatusBar(QWidget):
    """The slim bottom strip: latest-notification chip + history menu.

    ``app`` supplies the UI-thread marshalled ``_on_ui`` (the same
    invoker ``qt/notify.py`` uses); an app without one gets direct
    delivery, which is correct whenever the poster is already on the
    UI thread.
    """

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app
        self._dead = False
        self._latest = None
        self._history = deque(maxlen=HISTORY_MAX)
        self.setFixedHeight(HEIGHT)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Notifications")
        self.setStyleSheet(
            "QWidget{background:#f0f0f0;border-top:1px solid #bfbfbf;}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 6, 0)
        lay.setSpacing(6)
        self._glyph = QLabel(self)
        self._glyph.setFixedWidth(12)
        self._glyph.setAlignment(Qt.AlignCenter)
        self._glyph.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self._glyph)
        self._msg = QLabel(self)
        self._msg.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self._msg, 1)
        self._more = QLabel("\u25be", self)
        self._more.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self._more)

        self._full_text = READY
        self._show_ready()

        bus = _notify.default_bus()
        self._handler = self._deliver
        bus.subscribe(self._handler)
        # The bus outlives the window; drop the handler with it so a
        # closed window stops receiving (and repainting for) posts.
        self.destroyed.connect(self._on_destroyed)

    def _on_destroyed(self, *_a):
        self._dead = True
        try:
            _notify.default_bus().unsubscribe(self._handler)
        except Exception:
            pass

    # ------------------------------------------------------------ feed
    def _deliver(self, n):
        """Bus handler: marshal to the UI thread, then record."""
        try:
            invoker = getattr(self._app, "_on_ui", None)
            if callable(invoker):
                invoker(lambda: self._record(n))
            else:
                self._record(n)
        except Exception:
            pass

    def _record(self, n):
        if self._dead:
            return
        try:
            self._latest = n
            self._history.append(n)
            self._show_latest()
        except Exception:
            pass

    # ---------------------------------------------------------- render
    def _show_ready(self):
        self._full_text = READY
        self._glyph.setText("")
        self._msg.setText(READY)
        self._msg.setToolTip("")
        self._msg.setStyleSheet("color:%s;" % self._window_text())

    def _window_text(self):
        try:
            return self.palette().color(QPalette.ColorRole.WindowText).name()
        except Exception:
            return "#000000"

    def _show_latest(self):
        n = self._latest
        text = _text_of(n) if n is not None else ""
        if not text:
            self._show_ready()
            return
        sev = getattr(n, "severity", _notify.Severity.INFO)
        glyph, colour = _SEVERITY.get(sev, _SEVERITY[_notify.Severity.INFO])
        self._full_text = text
        self._glyph.setText(glyph)
        self._glyph.setStyleSheet("color:%s;" % colour)
        # Upstream colours the chip text by type; INFO stays plain.
        if sev is _notify.Severity.INFO:
            self._msg.setStyleSheet("color:%s;" % self._window_text())
        else:
            self._msg.setStyleSheet("color:%s;" % colour)
        self._elide()

    def _elide(self):
        """QLabel does not elide on its own; do it against the label's
        actual width so a long body cannot push the strip wide."""
        try:
            w = self._msg.width()
            if w > 8:
                self._msg.setText(
                    QFontMetrics(self._msg.font()).elidedText(
                        self._full_text, Qt.ElideRight, w - 4))
            else:
                self._msg.setText(self._full_text)
        except Exception:
            self._msg.setText(self._full_text)

    def resizeEvent(self, event):                 # noqa: N802 (Qt name)
        super().resizeEvent(event)
        self._elide()

    # --------------------------------------------------------- history
    def mousePressEvent(self, event):             # noqa: N802 (Qt name)
        """Click anywhere on the strip -> the recent-notifications menu,
        the port's stand-in for .tmp's NotificationPopover."""
        try:
            self._show_history(event.globalPosition().toPoint()
                               if hasattr(event, "globalPosition")
                               else event.globalPos())
        except Exception:
            pass
        super().mousePressEvent(event)

    def _show_history(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#f9f9f9;border:1px solid #e5e5e5;}"
            "QMenu::item{padding:3px 18px 3px 10px;}"
            "QMenu::item:selected{background:#e5e5e5;}")
        if not self._history:
            act = menu.addAction("No notifications")
            act.setEnabled(False)
        else:
            for n in reversed(self._history):
                text = _text_of(n) or "(empty notification)"
                sev = getattr(n, "severity", _notify.Severity.INFO)
                glyph, _c = _SEVERITY.get(
                    sev, _SEVERITY[_notify.Severity.INFO])
                act = menu.addAction("%s  %s" % (glyph, text))
                act.setEnabled(False)
            menu.addSeparator()
            clear = menu.addAction("Clear")
            clear.triggered.connect(self.clear_history)
        menu.exec(pos)

    def clear_history(self):
        """The popover's "Clear all": empties the LIST only — the chip
        keeps showing the latest notification, like upstream."""
        self._history.clear()

    # ------------------------------------------------------------ test
    def latest_text(self):
        return self._full_text
