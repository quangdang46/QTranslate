"""The translation popup (native's Ctrl+Q window) on PySide6.

The popup is NOT a fixed 200x68 box. Native sizes it to its content: a
header strip with the language pair and the icon row, the translation
body under it, and -- while the pointer is over the window -- a provider
strip along the bottom. It grows to fit a long translation and shrinks
for a short one, bounded only by the screen.

MEASURED off the operator's two captures of the native
(``screenshots`` 2162 and 2163, 2026-10-23), which supersede the older
2130 reading of a small empty popup:

    2162  the window spans x 24..622 (598 client pixels) for a text that
          wraps to two lines; the body is the SAME grey as the header,
          with no white panel behind the text
    2163  the same window with the pointer over it: the provider strip
          sits on the bottom row (``#e0e0e0``, the selected cell
          ``#b0b0b0``), the cells are 65px apart, and the header icons
          end 5px from the right edge at 17px steps

So the width tracks the text, clamped to a reading range whose UPPER
bound is the 598px the native itself settled on, and the height is the
header + the wrapped body + (while hovering) the strip. Nothing is
hardcoded to a pixel count that assumes a short string.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QLabel, QWidget

from qtranslate_style import ACCENT, POPUP_BORDER, POPUP_ICON, POPUP_TEXT

from . import icons


def popup_bg() -> str:
    """The popup's own background: the platform's ``COLOR_BTNFACE``.

    Native's ``DefaultColorTheme`` leaves ``Window/Normal`` unset and
    every slot it does not compile comes from ``GetSysColor`` -- so the
    popup paints with the SYSTEM button face, not with a constant this
    port picked.

    Both captures confirm it. 2163's field is ``#f0f0f0``, which is this
    host's ``COLOR_BTNFACE``. 2162's field reads ``#cccccc`` -- 204 --
    which is the SAME ``#f0f0f0`` seen through the popup's default
    transparency of 217: ``240 * 217 / 255 = 204.2``. One popup, two
    pictures, and the only difference is how much of what is behind it
    shows through.

    A hardcoded ``#d0d0d0`` matched neither. On a host whose button face
    is a different colour it would not match at all.

    The palette is asked of Win32 directly where it exists. Qt's own
    ``QPalette.Button`` answers with its own style's colour -- on this
    host ``#e3e3e3``, which is neither capture -- because the native asks
    the OS, not a toolkit.
    """
    try:
        import ctypes
        c = int(ctypes.windll.user32.GetSysColor(15))   # COLOR_BTNFACE
        return "#%02x%02x%02x" % (c & 255, (c >> 8) & 255, (c >> 16) & 255)
    except Exception:
        pass
    try:
        pal = QGuiApplication.palette()
        # QPalette.Button is the button face; asking the platform for it
        # is what GetSysColor(COLOR_BTNFACE) does in native.
        c = pal.color(QPalette.Button)
        if c.isValid():
            return c.name()
    except Exception:
        pass
    return "#f0f0f0"

# The width range. The lower bound is the narrowest a two-word result
# still reads at; the upper is the 598 client pixels the native itself
# settled on (2162: x 24..622) for a long line. Both are bounds, not the
# size -- the text decides inside them.
MIN_WIDTH = 220
MAX_WIDTH = 598
# The header: the close mark, the pair, the icons on the right.
# 2162: the client starts at y 23 and the first body line's glyphs start
# at y 47 -- a 24px header.
HEADER_H = 24
# The provider strip, shown only while the pointer is over the window.
# 2163: the buttons span y 55..76, so 22px.
STRIP_H = 22
# The body's left inset. 2162 puts the first glyph at x 26, two pixels
# inside the frame at x 24.
PAD = 3
# The header icons are right-aligned and 17px apart: 2163 has them at
# x 510, 527, 544, 564, 580 with the frame at 599. The last one keeps a
# 6px margin.
ICON_STEP = 17
ICON_MARGIN = 6


def _measure(text: str, width: int, font: QFont) -> int:
    """The height a wrapped body needs at ``width``.

    Measured with the SAME wrap flag the label uses (``TextWordWrap``)
    and with the label's own font, so a long translation wraps into more
    lines and the window grows instead of clipping.
    """
    from PySide6.QtGui import QFontMetrics
    fm = QFontMetrics(font)
    rect = fm.boundingRect(0, 0, max(1, width - 2 * PAD), 100000,
                           int(Qt.TextWordWrap), text or "")
    # boundingRect returns the text block's height; an empty or one-line
    # body still needs one line's worth.
    return max(int(rect.height()), int(fm.height()))


def _strip_icon_name(name: str) -> str:
    """The ``service_icons`` asset for a provider, or '' if there is none."""
    from . import icons as _icons
    try:
        if _icons.pixmap("service_icons", name) is not None:
            return name
    except Exception:
        pass
    return ""


def _strip_label(parent, name: str, width: int, app) -> str:
    """The service's display name, cut to ``xx...`` when it does not fit.

    This is native's own rule, the one the main window's strip applies:
    a 65px cell leaves 42px for the text, which fits "Google", "Promt",
    "Baidu" and "DeepL" but not the longer names -- 2163 shows "Mic...",
    "Bab...", "Yan...", "you..." and "Pap...", so a name that does not
    fit is cut to THREE characters and an ellipsis.
    """
    full = ""
    try:
        full = app.service_display(name) if app else name
    except Exception:
        full = name
    from PySide6.QtGui import QFontMetrics
    fm = QFontMetrics(parent.font())
    if fm.horizontalAdvance(full) <= width - 23:
        return full
    return full[:3] + "..."


class PopupWindow(QWidget):
    """The popup: a frameless tool window that sizes itself to its text."""

    ORIGIN, SIZE = (0, 0), (MIN_WIDTH, HEADER_H + 24)

    def __init__(self, app=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool
                         | Qt.WindowStaysOnTopHint)
        self.app = app
        try:
            self.setFocusPolicy(Qt.StrongFocus)
        except Exception:
            pass
        self.setStyleSheet("Popup{background:%s;border:1px solid %s;}"
                           % (popup_bg(), POPUP_BORDER))
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMouseTracking(True)

        self.btn_close = QLabel("✕", self)
        self.btn_close.setStyleSheet("background:transparent;color:%s;"
                                     % POPUP_ICON)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.mousePressEvent = self._on_close_click

        self.lbl_pair = QLabel("", self)
        self.lbl_pair.setStyleSheet("background:transparent;color:%s;"
                                    % POPUP_ICON)

        self._header = self._header_icons()

        # Native draws the translation on the SAME grey as the header --
        # both captures show one flat ``#cccccc`` / ``#f0f0f0`` field from
        # the title row to the last line of text, with no white panel
        # behind it. A white body was the port's own invention.
        self.lbl_text = QLabel("", self)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.lbl_text.setStyleSheet("background:transparent;color:%s;"
                                    "border:none;" % POPUP_TEXT)

        self._strip = self._provider_strip()
        try:
            self._fill("", "", "")
        except Exception:
            pass

    def _on_close_click(self, event):
        """Clicking the X closes the popup (native behaviour)."""
        try:
            self.hide()
        except Exception:
            pass

    # ------------------------------------------------------------ pieces
    def _header_icons(self):
        """The five marks on the right of the title row.

        Native's row is star, dictionary, listen, copy and the
        transliteration mark, right-aligned at 17px steps with a 6px
        margin from the frame (2163: x 510, 527, 544, 564, 580 with the
        frame at 599).

        All five are pixmaps from the binary's own RT_ICON resources, not
        glyphs. They were glyphs first, and two of the five came out as
        tofu boxes: this host's 488 font families have no coverage of
        U+1F4D6 or U+29C9, so the picture showed empty rectangles where
        native shows a book and a copy mark. Native draws pixels, so the
        port does too.
        """
        # The star is the OUTLINE one (``star_off``): both captures show
        # the grey hollow star, which is native's "not in Favorites" mark.
        # Filling it in would claim a saved entry the user never made.
        out = []
        for name in ("star_off", "book", "headphone", "copy", "translit"):
            q = QLabel("", self)
            q.setStyleSheet("background:transparent;")
            q.setPixmap(icons.pixmap("ui_icons", name))
            out.append(q)
        out.extend(self._extension_icons())
        return out

    def _provider_strip(self) -> QWidget:
        """The strip the native reserves along the bottom.

        Both captures are the same height -- 2162 is 81px, 2163 is 82px
        -- so the strip's ROW is always there and only its CELLS appear
        while the pointer is over the window. The port used to add the
        strip's height on hover, which made the window grow under the
        cursor. The cells come from the app, so the strip follows
        whatever services are live rather than a hardcoded list.
        """
        w = QWidget(self)
        w.setStyleSheet("background:#e0e0e0;")
        self._strip_buttons = []
        self._strip_icons = []
        self._strip_labels = []
        self._strip_names = []
        names = []
        try:
            names = self.app.ordered_services() if self.app else []
        except Exception:
            names = []
        for i, name in enumerate(names):
            # 2163's separators sit 65px apart (x 70, 135, 200, ...), and
            # each cell is an icon then the service's display name, cut
            # the same way the main window's strip cuts it ("Micro...").
            b = QLabel(w)
            b.setGeometry(65 * i, 0, 65, STRIP_H)

            ico = QLabel(w)
            icon_name = _strip_icon_name(name)
            if icon_name:
                ico.setPixmap(icons.pixmap("service_icons", icon_name))
                ico.setGeometry(65 * i + 4, 3, 16, 16)

            lab = QLabel(w)
            lab.setText(_strip_label(self, name, 65, self.app))
            lab.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lab.setGeometry(65 * i + 22, 0, 42, STRIP_H)

            # Clicking a cell SWITCHES the provider: the cell becomes the
            # active one (the selection blue, like the main window's
            # listbox), the app's service follows, and the popup's
            # source is re-translated through the chosen provider.
            handler = (lambda _e, n=name: self._strip_clicked(n))
            for child in (b, ico, lab):
                child.mousePressEvent = handler
                child.setCursor(Qt.PointingHandCursor)
                child.hide()
            self._strip_buttons.append(b)
            self._strip_icons.append(ico)
            self._strip_labels.append(lab)
            self._strip_names.append(name)
        self._paint_strip()
        return w

    def _strip_clicked(self, name):
        """The operator's report (2026-10-24): clicking a strip cell did
        nothing. It now selects the provider -- highlight first, so the
        click is acknowledged even before the answer arrives -- then
        re-translates the popup's source through the chosen provider on
        the app's worker (the same no-second-request rule as on_go)."""
        app = self.app
        if app is None or name not in self._strip_names:
            return
        app.switch_service(name)
        self._active_service = name
        self._paint_strip()
        src = (getattr(self, "_source_text", "")
               or (app.win.src.toPlainText() if app.win else ""))
        if src:
            app._start_translation(src, self._show_strip_result)

    def _show_strip_result(self, text, res):
        """The re-translation's landing spot (UI thread)."""
        if res.ok and res.text:
            pair = (self.app.popup_pair(res.provider_used)
                    if self.app else "")
            self.set_text(text, res.text, pair)
            # This path bypasses push_hist, so emit the extension event
            # here too -- a strip re-translation is a translation done.
            if self.app is not None:
                self.app._emit_extension_event("translation.done", {
                    "provider": res.provider_used, "text": text,
                    "result": res.text, "ok": True})

    def _paint_strip(self):
        """The active cell is the selection blue with white text; the
        rest stay the strip's grey. The port used to mark the active
        cell with a slightly darker GREY, which no one could see."""
        active = getattr(self, "_active_service", None)
        if active is None and self.app is not None:
            active = self.app.service
        for b, ico, lab, name in zip(getattr(self, "_strip_buttons", []),
                                     getattr(self, "_strip_icons", []),
                                     getattr(self, "_strip_labels", []),
                                     getattr(self, "_strip_names", [])):
            on = name == active
            b.setStyleSheet(
                "background:%s;border:none;border-right:1px solid %s;"
                % (ACCENT if on else "#e0e0e0", "#7e7e7e"))
            lab.setStyleSheet("background:transparent;color:%s;border:none;"
                              % ("#ffffff" if on else "#000"))

    def _extension_icons(self):
        """Entries an extension contributed to the popup's icon row.

        The slot is ("popup", "icons") -- native's PopupWindowIcons. A
        contribution is a callable returning a short label.
        """
        app = getattr(self, "app", None)
        manager = getattr(app, "ext_manager", None)
        slots = getattr(manager, "ui_slots", None) if manager else None
        labels = []
        if slots is None:
            return labels
        try:
            entries = slots.entries("popup", "icons")
        except Exception:
            return labels
        for entry in entries:
            contrib = entry.get("contribution")
            if not callable(contrib):
                continue
            try:
                text = str(contrib() or "")
            except Exception:
                continue
            if not text:
                continue
            q = QLabel(text[:2], self)
            q.setStyleSheet("background:transparent;color:%s;" % POPUP_ICON)
            labels.append(q)
        return labels

    # ------------------------------------------------------------- layout
    def _wanted_width(self, source: str, result: str) -> int:
        """The width the content asks for, clamped to the reading range."""
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.lbl_text.font())
        longest = max(
            [fm.horizontalAdvance(line) for line in (result or "").split("\n")]
            or [0])
        pair = QFontMetrics(self.lbl_pair.font()).horizontalAdvance(
            source or "")
        want = max(longest, pair) + 2 * PAD + 2
        return max(MIN_WIDTH, min(MAX_WIDTH, want))

    def _fill(self, source: str, result: str, pair: str):
        """Place the header, the body and the strip row."""
        self.lbl_pair.setText(pair or (source or "")[:40])
        self.lbl_text.setText(result or "")
        w = self._wanted_width(source, result)
        body_h = _measure(result or "", w, self.lbl_text.font())
        # The strip row is reserved whether or not the pointer is on the
        # window (see ``_provider_strip``), so hovering never resizes it.
        h = HEADER_H + body_h + 2 * PAD + STRIP_H

        self.setFixedSize(w, h)
        self.btn_close.setGeometry(PAD, 4, 12, 16)
        self.lbl_pair.setGeometry(PAD + 16, 4, max(60, w - 190), 16)
        # Right-aligned, 17px apart, 6px in from the frame.
        n = len(self._header)
        x0 = w - ICON_MARGIN - ICON_STEP * n
        for i, q in enumerate(self._header):
            q.setGeometry(x0 + ICON_STEP * i, 4, 16, 16)
        self.lbl_text.setGeometry(PAD, HEADER_H, w - 2 * PAD, body_h)
        self._strip.setGeometry(1, h - STRIP_H - 1, w - 2, STRIP_H)

    def set_text(self, source: str, result: str, pair: str = "",
                 provider: str = ""):
        """Show one translation, sized to it."""
        self._source_text = source
        # A translation that arrives from elsewhere (hotkey, main window)
        # may have been served by a different provider: the strip's
        # highlight follows the SERVING provider, not the click history.
        if provider:
            self._active_service = provider
        self._paint_strip()
        self._fill(source, result, pair)
        self._extension_body(source, result, pair)

    def _extension_body(self, source: str, result: str, pair: str):
        """Let an extension render the popup's body instead."""
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
            try:
                text = contrib(result)
            except Exception:
                return
        except Exception:
            return
        if text is None:
            return
        self._fill(source, str(text), pair)

    # --------------------------------------------------------------- hover
    def _set_hover(self, on):
        """Show or hide the strip's cells. The row itself is always
        reserved. Split from enterEvent because a popup that opens
        UNDER THE CURSOR never gets an enter event -- the operator's
        report (2026-10-24): the strip looked missing. ``showEvent``
        checks the cursor itself now."""
        for group in ("_strip_buttons", "_strip_icons", "_strip_labels"):
            for w in getattr(self, group, None) or ():
                (w.show if on else w.hide)()

    def enterEvent(self, event):                # noqa: N802 (Qt name)
        self._set_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event):                # noqa: N802 (Qt name)
        self._set_hover(False)
        super().leaveEvent(event)

    def keyPressEvent(self, event):             # noqa: N802 (Qt name)
        """Esc closes the popup (native's hotkey)."""
        if event.key() == Qt.Key_Escape:
            try:
                self.hide()
            except Exception:
                pass
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):          # noqa: N802 (Qt name)
        """Click-outside closes the popup (native's behaviour)."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.MouseButtonPress and self.isVisible():
            # Only the ACTIVE popup should respond to click-outside;
            # old popup instances may still have filters installed.
            app = getattr(self, "app", None)
            if app is not None:
                try:
                    if getattr(app, "_popup", None) is not self:
                        return False
                except Exception:
                    pass
            pos = event.globalPos() if hasattr(event, "globalPos") else None
            if pos is not None and not self.geometry().contains(pos):
                try:
                    self.hide()
                except Exception:
                    pass
                return False
        return False

    def showEvent(self, event):                 # noqa: N802 (Qt name)
        # A popup that opens under the cursor (the common Ctrl+Q case --
        # it places at the pointer) never receives an enter event, so
        # the provider strip stayed hidden until the pointer left and
        # came back. Check on show instead.
        try:
            if self.underMouse():
                self._set_hover(True)
        except Exception:
            pass
        try:
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.ActiveWindowFocusReason)
        except Exception:
            pass
        super().showEvent(event)

    # ------------------------------------------------------------- show
    def place(self):
        """The Appearance popup settings, native's ShowPopupWindow."""
        try:
            from qtranslate import config as _C
            _ap = _C.load().get("Appearance", {})
        except Exception:
            _ap = {}
        try:
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.ActiveWindowFocusReason)
        except Exception:
            try:
                self.raise_()
                self.show()
            except Exception:
                pass
        try:
            _tr = int(_ap.get("Transparency", 217))
            self.setWindowOpacity(_tr / 255.0 if 0 < _tr < 255 else 1.0)
        except Exception:
            pass
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
        try:
            _to = int(_ap.get("PopupTimeout", 0))
        except Exception:
            _to = 0
        # POPUP TIMEOUT IS OPT-IN and click-outside CLOSES the popup --
        # the operator's report (2026-10-24): the answer arrived, the
        # popup showed for five seconds and vanished while he was still
        # reading ("giật lag rồi không thấy gì"). A zero timeout means
        # the popup stays until the user clicks elsewhere or closes it.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        if _to > 0:
            self._timer.start(_to * 1000)
        from PySide6.QtWidgets import QApplication as _QA
        # Install only one active filter — remove any previous instance on this
        # object before installing the fresh one. This prevents stale filters
        # accumulating over many translations.
        try:
            _QA.instance().removeEventFilter(self)
        except Exception:
            pass
        _QA.instance().installEventFilter(self)
