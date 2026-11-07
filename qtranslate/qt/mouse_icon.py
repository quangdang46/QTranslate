"""The floating translate icon of mouse mode "Show icon".

Reference UX (.tmp/QTranslate ``SelectionTranslateButton``): a small
unobtrusive button appears next to the selection's release point --
below-right of the cursor, flipping to the other side near a screen
edge so it never covers the selection or clips off-screen. It never
takes focus, fades rather than snaps, auto-hides after a few seconds
(the countdown pauses while the pointer is over it, so it cannot
disappear from under a reaching user), and the app dismisses it on an
outside press. Clicking it hands the captured text back to the app,
which translates it exactly like Ctrl+Q would.
"""
from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, QPoint,
                            Qt, QTimer)
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QGraphicsOpacityEffect,
                               QLabel, QWidget)

SIZE = 32
BADGE = 18
# .tmp SelectionTranslateButton: GAP=14 from the cursor, VISIBLE_MS=4000.
GAP = 14
VISIBLE_MS = 4000
FADE_MS = 160


def _badge_pixmap(app):
    """The icon to show: the current service's own icon, else a drawn
    'Q' roundel -- never an empty box."""
    try:
        from .widgets import icons
        pm = icons.pixmap("service_icons",
                          getattr(app, "service", "google") or "google")
        if pm is not None and not pm.isNull():
            return pm.scaled(BADGE, BADGE, Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
    except Exception:                       # noqa: BLE001
        pass
    pm = QPixmap(BADGE, BADGE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.blue)
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, BADGE - 2, BADGE - 2)
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
        # Qt.Popup is the flag QMenu uses for "appear without activating
        # the app" on macOS -- a plain Qt.Tool window still pulls the
        # whole process forward on show(), the source app resigns key,
        # and the next synthetic Cmd+C lands nowhere (verified live:
        # frontmost flipped TextEdit -> python the moment pop() ran).
        super().__init__(None, Qt.FramelessWindowHint | Qt.Popup
                         | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.app = app
        self._text = ""
        self._on_translate = on_translate
        self.setFixedSize(SIZE, SIZE)
        lab = QLabel(self)
        lab.setPixmap(_badge_pixmap(app))
        lab.setGeometry((SIZE - BADGE) // 2, (SIZE - BADGE) // 2,
                        BADGE, BADGE)
        lab.setStyleSheet("background:transparent;")
        lab.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        lab.mousePressEvent = self._clicked
        self.mousePressEvent = self._clicked
        self.setStyleSheet(
            "MouseIcon { background: rgba(255,255,255,230);"
            " border: 1px solid rgba(0,0,0,60); border-radius: 8px; }"
            "QLabel { background: transparent; }")
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0.0)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        # Generation counter: a _done() scheduled by an OLD fade-out
        # must not hide an icon that was popped again in between
        # (audit: stale-hide race made freshly shown icons vanish).
        self._gen = 0

    # ------------------------------------------------------------- show/hide
    def pop(self, x, y, text):
        """Show below-right of the release point (.tmp placeNear).

        Prefers the corner clear of the selection; flips horizontally
        or vertically when that would leave the monitor, then clamps
        inside the screen under the pointer.
        """
        self._text = text or ""
        self._gen += 1
        self.move(*self._place(x, y))
        self.show()
        # No raise_(): on macOS ordering a window front can activate the
        # app even for a non-activating panel, and the popup flags
        # already keep it above the source app's windows.
        self._fade_to(1.0)
        self._arm_timer()

    def dismiss(self):
        """Outside press or teardown: fade out and clear the payload."""
        self._text = ""
        self._timer.stop()
        self._fade_out()

    def is_showing(self) -> bool:
        return self.isVisible()

    def contains_point(self, x, y) -> bool:
        """Screen-space hit test for the outside-press dismissal."""
        g = self.geometry()
        return g.contains(QPoint(int(x), int(y)))

    def _place(self, x, y):
        screen = QApplication.screenAt(QPoint(int(x), int(y)))
        if screen is None:
            screen = QApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        if geo is None:
            return int(x) + GAP, int(y) + GAP
        gx, gy = int(x) + GAP, int(y) + GAP
        if gx + SIZE > geo.x() + geo.width():
            gx = int(x) - GAP - SIZE
        if gy + SIZE > geo.y() + geo.height():
            gy = int(y) - GAP - SIZE
        gx = max(geo.x(), min(gx, geo.x() + geo.width() - SIZE))
        gy = max(geo.y(), min(gy, geo.y() + geo.height() - SIZE))
        return gx, gy

    def _arm_timer(self):
        self._timer.start(VISIBLE_MS)

    def enterEvent(self, _e):
        # The countdown pauses over the button -- it must not disappear
        # from under a user who is reaching for it (.tmp hideTimer).
        self._timer.stop()

    def leaveEvent(self, _e):
        if self.isVisible():
            self._arm_timer()

    # ---------------------------------------------------------------- fade
    def _fade_to(self, target: float):
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(FADE_MS)
        anim.setStartValue(self._opacity.opacity())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._anim = anim

    def _fade_out(self):
        gen = self._gen

        def _done():
            if gen != self._gen:
                return          # a newer pop() owns the widget now
            self.hide()
            self._text = ""
        self._fade_to(0.0)
        QTimer.singleShot(FADE_MS + 30, _done)

    # ---------------------------------------------------------------- click
    def _clicked(self, _e):
        text, self._text = self._text, ""
        try:
            self._timer.stop()
            self.hide()
        except Exception:
            pass
        if text:
            try:
                self._on_translate(text)
            except Exception:
                pass

    def current_text(self):
        return self._text
