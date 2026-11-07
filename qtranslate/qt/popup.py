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

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import (QColor, QCursor, QFont, QGuiApplication,
                           QPainter, QPalette, QPen)
from PySide6.QtWidgets import QLabel, QTextEdit, QWidget

from qtranslate_style import (ACCENT, POPUP_BORDER, POPUP_ICON, POPUP_TEXT,
                             popup_frame_thickness,
                             popup_icon_mask, popup_pin_when_dragging)

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
# .tmp QuickTranslateDialog's top panel carries the language row
# (source combo, swap, target combo) between the header and the body.
LANG_ROW_H = 22
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


class _Spinner(QWidget):
    """The rotating arc .tmp shows while a translation is in flight
    (QuickTranslateDialog's loading state / InlineLoadingBar)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def showEvent(self, event):                # noqa: N802 (Qt name)
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):                # noqa: N802 (Qt name)
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):               # noqa: N802 (Qt name)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(POPUP_ICON))
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(2, 2, 14, 14, self._angle * 16, 270 * 16)
        p.end()


class _PopupText(QTextEdit):
    """QTextEdit with the QLabel-style accessors callers expect."""

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str):
        self.setPlainText(text or "")


class PopupWindow(QWidget):
    """The popup: a frameless tool window that sizes itself to its text."""

    ORIGIN, SIZE = (0, 0), (MIN_WIDTH, HEADER_H + 24)

    def __init__(self, app=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool
                         | Qt.WindowStaysOnTopHint)
        # macOS: AppKit demotes tool windows of an INACTIVE app to
        # normal level -- the tray-resident QTranslate is never active,
        # so the popup composited BELOW the frontmost app while
        # isVisible() still reported True (the "need a second Ctrl+Q"
        # bug: only the second show()'s raise_() re-ordered it).
        # WA_MacAlwaysShowToolWindow is Qt's own fix for exactly this;
        # WA_ShowWithoutActivating matches MouseIcon/LoadingIndicator
        # so showing the answer never steals focus from the source app.
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.app = app
        try:
            self.setFocusPolicy(Qt.StrongFocus)
        except Exception:
            pass
        # Appearance.ColorBack/ColorText/ColorFrame are the MAIN
        # window's colours (docs/review/THEME_LOADER_AND_BGR_RETRACTION:
        # "colour the main window"), NOT the popup's -- the popup's own
        # colours come from the active theme. Feeding them here painted
        # the popup with settings that were never meant for it.
        self._pop_bg = popup_bg()
        self._pop_text = POPUP_TEXT
        self._pop_icon = POPUP_ICON
        self._pop_frame = POPUP_BORDER
        try:
            self._pop_thick = popup_frame_thickness()
        except Exception:
            self._pop_thick = 1
        self.setStyleSheet(
            "PopupWindow{background:%s;border:%dpx solid %s;}"
            % (self._pop_bg, self._pop_thick, self._pop_frame))
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMouseTracking(True)

        self.btn_close = QLabel("✕", self)
        self.btn_close.setStyleSheet("background:transparent;color:%s;"
                                     % self._pop_icon)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.mousePressEvent = self._on_close_click

        self.lbl_pair = QLabel("", self)
        self.lbl_pair.setStyleSheet("background:transparent;color:%s;"
                                    % self._pop_icon)

        self._header = self._header_icons()

        # Native draws the translation on the SAME grey as the header --
        # both captures show one flat ``#cccccc`` / ``#f0f0f0`` field from
        # the title row to the last line of text, with no white panel
        # behind it. A white body was the port's own invention.
        # QTextEdit, not QLabel: the result must be selectable (native's
        # AdvancedTextPane is read-only-but-selectable) and must SCROLL
        # when a long translation exceeds the screen -- the audit found
        # the QLabel version grew the window past the display with no
        # way to reach the bottom. ``_PopupText`` adds the QLabel-style
        # ``text()``/``setText()`` names the tests and older callers use.
        self.lbl_text = _PopupText("", self)
        self.lbl_text.setReadOnly(True)
        self.lbl_text.setFrameShape(QTextEdit.NoFrame)
        self.lbl_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.lbl_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lbl_text.setStyleSheet("background:transparent;color:%s;"
                                    "border:none;" % self._pop_text)
        # .tmp QuickTranslateDialog text panes take the EDITOR font
        # (editorFontConfig), not the UI font -- same resolution the
        # main window's panes use (qtranslate.fonts.resolve_editor_font).
        try:
            from qtranslate.fonts import resolve_editor_font
            _ef, _es = resolve_editor_font()
            _ef_px = max(6, int(round(12 * _es / 9.0)))
            _f = QFont(_ef or self.font().family())
            _f.setPixelSize(_ef_px)
            self.lbl_text.setFont(_f)
        except Exception:
            pass

        # .tmp DefinitionStrip (showDivider=true for the popup): the
        # one-line dictionary gloss under a single-word result. Read-only
        # SELECTABLE text like the result itself, drawn in the disabled
        # label colour with a hairline above it, hidden while blank.
        # ClickFocus = mouse-selectable without becoming a Tab stop
        # (.tmp skipFocusTraversal).
        self.defn = _PopupText("", self)
        self.defn.setReadOnly(True)
        self.defn.setFrameShape(QTextEdit.NoFrame)
        self.defn.setFocusPolicy(Qt.ClickFocus)
        self.defn.setStyleSheet(
            "background:transparent;color:%s;border:none;"
            "border-top:1px solid %s;" % (POPUP_ICON, POPUP_BORDER))
        try:
            self.defn.setFont(self.lbl_text.font())
        except Exception:
            pass
        self._defn_text = ""

        # .tmp QuickTranslateDialog's CompareBoard: when comparison is
        # eligible (>=2 effective translators) the quick popup shows
        # every secondary's answer under the primary result -- same
        # DefinitionStrip mechanics, capped harder because cards are
        # longer than a gloss.
        self.compare = _PopupText("", self)
        self.compare.setReadOnly(True)
        self.compare.setFrameShape(QTextEdit.NoFrame)
        self.compare.setFocusPolicy(Qt.ClickFocus)
        self.compare.setStyleSheet(
            "background:transparent;color:%s;border:none;"
            "border-top:1px solid %s;" % (self._pop_text, POPUP_BORDER))
        try:
            self.compare.setFont(self.lbl_text.font())
        except Exception:
            pass
        self._cmp_text = ""

        # .tmp QuickTranslateDialog's language row: source combo,
        # swap button, target combo -- changing either re-runs the
        # translation (RetranslateQuickTranslate) and persists the
        # preferred languages exactly like the main window's pickers.
        # The swap control is a passive QLabel like the header icons --
        # ui_match pins popup-no-buttons, so no real button widgets here.
        from PySide6.QtWidgets import QComboBox
        self._lang_bar = QWidget(self)
        self._lang_bar.setStyleSheet("background:transparent;")
        self.cmb_src = QComboBox(self._lang_bar)
        self.cmb_tgt = QComboBox(self._lang_bar)
        self.btn_swap = QLabel("⇄", self._lang_bar)
        self.btn_swap.setStyleSheet(
            "background:transparent;color:%s;" % self._pop_icon)
        self.btn_swap.setCursor(Qt.PointingHandCursor)
        self.btn_swap.setToolTip("Swap languages")
        self.btn_swap.mousePressEvent = (
            lambda _e: self._app_call("popup_swap"))
        for c in (self.cmb_src, self.cmb_tgt):
            c.setStyleSheet(
                "QComboBox{font-size:10px;padding:0 2px;}")
            c.setMaxVisibleItems(12)
        self.cmb_src.activated.connect(
            lambda _i: self._lang_changed("src"))
        self.cmb_tgt.activated.connect(
            lambda _i: self._lang_changed("tgt"))
        # .tmp popup keyboard shortcuts (WHEN_IN_FOCUSED_WINDOW):
        # Ctrl+C copy, Ctrl+E listen, Ctrl+S swap, Ctrl+P pin.
        from PySide6.QtGui import QShortcut, QKeySequence
        for keys, fn in (("Ctrl+C", self._icon_copy),
                         ("Ctrl+E", self._icon_listen),
                         ("Ctrl+S", lambda: self._app_call("popup_swap")),
                         ("Ctrl+P", self._toggle_pin)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(fn)

        self._strip = self._provider_strip()
        self._spin = _Spinner(self)
        self.sync_languages()
        self._loading = False
        # Floating-popup state (.tmp FloatingPopupBehavior): a pinned
        # popup never auto-hides and wears the accent border; a header
        # drag marks the position manual and persists the rect as
        # General.WindowPopupPlacement.
        self._pinned = False
        self._manually_moved = False
        self._dragging = False
        self._drag_offset = None
        self._drag_start = None
        self._hovering = False
        self._has_been_shown = False
        self._star_icon = None
        # The pair label is the header's drag surface: it spans most of
        # the title row between the close mark and the icon row.
        self.lbl_pair.mousePressEvent = self._header_press
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

    # ------------------------------------------------------------- pin
    def _toggle_pin(self):
        """The star icon / Ctrl+P: pin or unpin the popup."""
        self.set_pinned(not getattr(self, "_pinned", False))

    def set_pinned(self, on):
        """Pin state (.tmp FloatingPopupBehavior.isPinned +
        applyPinBorder): a pinned popup never auto-hides -- not on the
        idle timer, not on Escape -- and wears the accent border; the
        star fills in as the on-screen tell."""
        self._pinned = bool(on)
        try:
            self.setStyleSheet(
                "PopupWindow{background:%s;border:%dpx solid %s;}"
                % (self._pop_bg,
                   (self._pop_thick + 1) if self._pinned else self._pop_thick,
                   ACCENT if self._pinned else self._pop_frame))
            if self._star_icon is not None:
                self._star_icon.setPixmap(icons.pixmap(
                    "ui_icons", "star" if self._pinned else "star_off"))
        except Exception:
            pass
        if self._pinned:
            self._stop_idle_timer()
        elif self.isVisible():
            self._start_idle_timer()

    # ------------------------------------------------------------- drag
    def _header_press(self, event):
        """A left-press on the title row starts a window drag
        (.tmp FloatingPopupBehavior.installDrag on the top panel)."""
        try:
            if event.button() != Qt.LeftButton:
                return
            try:
                gp = event.globalPosition().toPoint()
            except Exception:
                gp = QCursor.pos()
            self._drag_offset = gp - self.frameGeometry().topLeft()
            self._drag_start = gp
            self._dragging = True
            self.grabMouse()
            self._stop_idle_timer()
        except Exception:
            pass

    def mousePressEvent(self, event):             # noqa: N802 (Qt name)
        # Only the header band drags; the body keeps its own events.
        try:
            if event.position().y() <= HEADER_H:
                self._header_press(event)
                return
        except Exception:
            pass
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):              # noqa: N802 (Qt name)
        if self._dragging and self._drag_offset is not None:
            try:
                pos = event.globalPosition().toPoint() - self._drag_offset
            except Exception:
                pos = QCursor.pos() - self._drag_offset
            self.move(pos)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):           # noqa: N802 (Qt name)
        if self._dragging:
            moved = 0
            try:
                if self._drag_start is not None:
                    gp = event.globalPosition().toPoint()
                    moved = max(abs(gp.x() - self._drag_start.x()),
                                abs(gp.y() - self._drag_start.y()))
            except Exception:
                pass
            self._dragging = False
            self._drag_offset = None
            self._drag_start = None
            try:
                self.releaseMouse()
            except Exception:
                pass
            # Only a REAL drag counts: a plain click on the title must
            # not mark the position manual, persist the rect, or pin
            # the popup under PopupPinWhenDragging.
            if moved >= 4:
                # A real drag marks the position manual (.tmp
                # wasManuallyMoved): place() stops auto-positioning and
                # the resting rect is persisted for PopupAutoPos=off.
                self._manually_moved = True
                self._save_popup_placement()
                # Appearance.PopupPinWhenDragging (native's old
                # QuickTranslateDialog): a dragged popup PINS -- the
                # user moved it somewhere deliberate, so it must not
                # auto-hide.
                try:
                    if popup_pin_when_dragging() and not self._pinned:
                        self.set_pinned(True)
                except Exception:
                    pass
            if not self._pinned:
                self._start_idle_timer()
        super().mouseReleaseEvent(event)

    # -------------------------------------------------------- persistence
    def _save_popup_placement(self):
        """Persist the popup rect as General.WindowPopupPlacement --
        the same WINDOWPLACEMENT blob the main and aux windows use
        (placement.encode_placement). There is no app-level save hook,
        so this writes through qtranslate.config directly."""
        try:
            from qtranslate import config as _C
            from qtranslate.placement import encode_placement
            g = self.geometry()
            cfg = _C.load()
            cfg.setdefault("General", {})["WindowPopupPlacement"] = \
                encode_placement(g.x(), g.y(), g.width(), g.height())
            _C.save(cfg)
        except Exception:
            pass

    @staticmethod
    def _appearance() -> dict:
        try:
            from qtranslate import config as _C
            return _C.load().get("Appearance", {}) or {}
        except Exception:
            return {}

    def _saved_popup_size(self):
        """(w, h) from General.WindowPopupPlacement, or None."""
        try:
            from qtranslate import config as _C
            from qtranslate.placement import decode_placement
            rc = decode_placement(
                _C.load().get("General", {})
                .get("WindowPopupPlacement", ""))
            if rc:
                return (rc[2], rc[3])
        except Exception:
            pass
        return None

    # --------------------------------------------------------- idle-hide
    def _start_idle_timer(self):
        """(Re)arm the PopupTimeout countdown. Opt-in like before: a
        zero timeout leaves the popup up until dismissed. Hover pauses
        it (enterEvent/leaveEvent) and a pinned popup never arms it --
        .tmp FloatingPopupBehavior.startIdleHide."""
        if getattr(self, "_pinned", False):
            return
        try:
            to = int(self._appearance().get("PopupTimeout", 0) or 0)
        except Exception:
            to = 0
        timer = getattr(self, "_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_idle_timeout)
            self._timer = timer
        else:
            timer.stop()
        if to > 0 and self.isVisible() and not self._hovering:
            timer.start(to * 1000)

    def _stop_idle_timer(self):
        timer = getattr(self, "_timer", None)
        if timer is not None:
            timer.stop()

    def _on_idle_timeout(self):
        # Last check at fire time: pin or hover during the countdown
        # still wins (.tmp checks isPinned again inside the timer).
        if self._pinned or self._hovering:
            return
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
        try:
            _mask = popup_icon_mask()
        except Exception:
            _mask = 30
        # Appearance.PopupIcons bitmask (bits 1-4 over book/headphone/
        # copy/translit; the star is not toggleable) -- the Options
        # page's "Icons:" row finally hides what it unchecks.
        _bits = {"book": 1 << 1, "headphone": 1 << 2,
                 "copy": 1 << 3, "translit": 1 << 4}
        for name in ("star_off", "book", "headphone", "copy", "translit"):
            if name in _bits and not (_mask & _bits[name]):
                continue
            q = QLabel("", self)
            q.setStyleSheet("background:transparent;")
            q.setPixmap(icons.pixmap("ui_icons", name))
            q.setCursor(Qt.PointingHandCursor)
            # Native's header row is a toolbar, not decoration: book opens
            # the dictionary on the source, headphone speaks the result,
            # copy puts the result on the clipboard. The transliteration
            # mark has no backend in the port yet, so it stays inert
            # rather than faking a reaction; the star toggles the pin.
            # The star is the pin toggle: .tmp's QuickTranslateDialog has
            # a dedicated pin button in its top panel, and the port's
            # header row has no spare slot, so the (otherwise inert)
            # star_off mark takes the job -- click pins, filled star
            # shows the pinned state.
            act = {"star_off": self._toggle_pin,
                   "book": self._icon_dictionary,
                   "headphone": self._icon_listen,
                   "copy": self._icon_copy}.get(name)
            if name == "star_off":
                self._star_icon = q
            if act is not None:
                q.mousePressEvent = lambda _e, a=act: a()
            out.append(q)
        out.extend(self._extension_icons())
        return out

    def _icon_dictionary(self):
        app = self.app
        word = (getattr(self, "_source_text", "") or "").strip()
        if app is None or not word:
            return
        try:
            app._dict_word = word.split()[0]
            app.open_dictionary()
        except Exception:
            pass

    def _icon_listen(self):
        if getattr(self, "_loading", False):
            return
        app = self.app
        # .tmp MainAppFrame wires the popup's listen to
        # ListenToText(TextSource.Input) -- the SOURCE text in the
        # source language ("most often used to check how the original
        # word is pronounced"), not the translation.
        text = getattr(self, "_source_text", "") or ""
        if app is None or not text:
            return
        lang = ""
        try:
            src = getattr(app, "source", "") or ""
            lang = (getattr(app, "_detected_src", "")
                    if src == "auto" else src) or ""
        except Exception:
            lang = ""
        app._speak(text, lang)

    def _icon_copy(self):
        if getattr(self, "_loading", False):
            return
        text = getattr(self, "_result_text", "") or ""
        if not text:
            return
        try:
            from qtranslate import clipboard as _cb
            _cb.write_text(text)
        except Exception:
            pass

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
        self._strip_has_icon = []
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
            has_icon = False
            if icon_name:
                pm = icons.pixmap("service_icons", icon_name)
                has_icon = not pm.isNull()
                ico.setPixmap(pm)
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
            self._strip_has_icon.append(has_icon)
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
            if self.app is not None:
                try:
                    self.app._popup_inline_definition(text, res.text)
                except Exception:
                    pass
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
            q.setStyleSheet("background:transparent;color:%s;" % self._pop_icon)
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
        self._loading = False
        try:
            self._spin.hide()
        except Exception:
            pass
        self._result_text = result or ""
        self.lbl_pair.setText(pair or (source or "")[:40])
        # Restore the result colour -- set_loading() paints the label
        # icon-grey and nothing used to put it back.
        self.lbl_text.setStyleSheet(
            "background:transparent;color:%s;border:none;"
            % self._pop_text)
        self.lbl_text.setPlainText(result or "")
        w = self._wanted_width(source, result)
        body_h = _measure(result or "", w, self.lbl_text.font())
        # .tmp PopupSizing caps the body at a screen fraction and scrolls
        # the rest; QTextEdit scrolls internally once body_h is capped.
        try:
            from PySide6.QtGui import QGuiApplication as _QGA
            scr = _QGA.screenAt(QCursor.pos()) or _QGA.primaryScreen()
            if scr is not None:
                body_h = min(body_h,
                             int(scr.availableGeometry().height() * 0.55))
        except Exception:
            pass
        # .tmp DefinitionStrip height is measured at the REAL width --
        # a wrapping pane asked at its old width clips or squeezes flat.
        # Glosses are capped ~150 chars upstream, so ~3 lines is the
        # ceiling; the rest would mean the lookup returned garbage.
        body_top = HEADER_H + LANG_ROW_H
        defn_txt_h = 0
        if self._defn_text:
            try:
                defn_txt_h = min(
                    _measure(self._defn_text, max(40, w - 2 * PAD),
                             self.defn.font()), 72)
            except Exception:
                defn_txt_h = 0
        defn_block = (defn_txt_h + 6) if defn_txt_h else 0

        # Comparison cards sit under the gloss; measured at the real
        # width like the definition, capped at ~8 lines -- beyond that
        # the popup stops being a popup.
        cmp_txt_h = 0
        if self._cmp_text:
            try:
                cmp_txt_h = min(
                    _measure(self._cmp_text, max(40, w - 2 * PAD),
                             self.compare.font()), 120)
            except Exception:
                cmp_txt_h = 0
        cmp_block = (cmp_txt_h + 6) if cmp_txt_h else 0

        # The strip row is reserved whether or not the pointer is on the
        # window (see ``_provider_strip``), so hovering never resizes it.
        h = (body_top + body_h + defn_block + cmp_block
             + 2 * PAD + STRIP_H)

        # Appearance.PopupAutoSize off (.tmp applySize): the popup keeps
        # the last size it was saved with -- the w/h inside the same
        # WindowPopupPlacement blob the position restore reads.
        if not self._appearance().get("PopupAutoSize", True):
            saved = self._saved_popup_size()
            if saved:
                w = max(MIN_WIDTH, int(saved[0]))
                h = max(HEADER_H + 24, int(saved[1]))
                # The fixed frame must still hold header + body +
                # definition + strip: shrink the scrollable result
                # first, the definition keeps its measured height.
                room = (h - body_top - 2 * PAD - STRIP_H
                        - defn_block - cmp_block)
                if body_h > max(20, room):
                    body_h = max(20, room)

        self.setFixedSize(w, h)
        self.btn_close.setGeometry(PAD, 4, 12, 16)
        self.lbl_pair.setGeometry(PAD + 16, 4, max(60, w - 190), 16)
        # Right-aligned, 17px apart, 6px in from the frame.
        n = len(self._header)
        x0 = w - ICON_MARGIN - ICON_STEP * n
        for i, q in enumerate(self._header):
            q.setGeometry(x0 + ICON_STEP * i, 4, 16, 16)
        # The language row sits between header and body (.tmp's
        # source/swap/target panel): combos sized to their content,
        # swap centred between them.
        try:
            self._lang_bar.setGeometry(0, HEADER_H, w, LANG_ROW_H)
            self._lang_bar.show()
            self.cmb_src.setGeometry(PAD, 2, 78, LANG_ROW_H - 4)
            self.btn_swap.setGeometry(PAD + 80, 2, 24, LANG_ROW_H - 4)
            self.cmb_tgt.setGeometry(PAD + 108, 2, 78, LANG_ROW_H - 4)
        except Exception:
            pass
        self.lbl_text.setGeometry(PAD, body_top, w - 2 * PAD, body_h)
        if defn_txt_h:
            self.defn.setPlainText(self._defn_text)
            self.defn.setGeometry(PAD, body_top + body_h + 3,
                                  w - 2 * PAD, defn_txt_h + 4)
            self.defn.show()
        else:
            self.defn.hide()
        if cmp_txt_h:
            self.compare.setPlainText(self._cmp_text)
            self.compare.setGeometry(
                PAD, body_top + body_h + defn_block + 3,
                w - 2 * PAD, cmp_txt_h + 4)
            self.compare.show()
        else:
            self.compare.hide()
        self._strip.setGeometry(1, h - STRIP_H - 1, w - 2, STRIP_H)

    def _app_call(self, name, *args):
        fn = getattr(getattr(self, "app", None), name, None)
        if callable(fn):
            try:
                return fn(*args)
            except Exception:
                return None
        return None

    def _lang_changed(self, which):
        combo = self.cmb_src if which == "src" else self.cmb_tgt
        self._app_call("popup_lang_changed", which, combo.currentText())

    def sync_languages(self):
        """Fill the language row from the app's live names and point the
        combos at the current pair (.tmp renders the combos from state
        on every emission)."""
        app = getattr(self, "app", None)
        if app is None:
            return
        try:
            sname = app._display(app.source) if app.source != "auto" \
                else app._display("auto")
            tname = app._display(app.target)
            for combo, names, cur in (
                    (self.cmb_src, app.source_names(), sname),
                    (self.cmb_tgt, app.target_names(), tname)):
                combo.blockSignals(True)
                combo.clear()
                for n in names:
                    combo.addItem(n)
                if cur and combo.findText(cur) < 0:
                    combo.addItem(cur)
                if cur:
                    combo.setCurrentText(cur)
                combo.blockSignals(False)
        except Exception:
            pass

    def set_loading(self, source: str, pair: str = ""):
        """.tmp's loading state: the popup opens immediately with the
        source text and a spinner while the translation is in flight,
        instead of leaving the user staring at nothing."""
        self._source_text = source
        self._defn_text = ""
        self._cmp_text = ""
        self._paint_strip()
        self._fill(source, "Translating…", pair or (source or "")[:40])
        # _fill() clears the flag -- the loading state only counts AFTER
        # the fill, or copy/listen can't tell placeholder from result.
        self._loading = True
        try:
            self.lbl_text.setPlainText("Translating…")
            self.lbl_text.setStyleSheet(
                "background:transparent;color:%s;border:none;" % self._pop_icon)
            body_top = HEADER_H + LANG_ROW_H
            self.lbl_text.setGeometry(
                PAD + 26, body_top,
                max(40, self.width() - 2 * PAD - 26),
                self.lbl_text.height())
            self._spin.move(PAD + 4, body_top + (self.height()
                           - body_top - STRIP_H) // 2 - 9)
            self._spin.show()
        except Exception:
            pass

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
        # A new translation invalidates the previous gloss; the app's
        # inline-definition lookup repopulates it when it lands.
        self._defn_text = ""
        self._cmp_text = ""
        self._defn_fill = (source, result, pair)
        self._fill(source, result, pair)
        self._extension_body(source, result, pair)

    def set_comparison(self, text):
        """.tmp QuickTranslateDialog comparison cards: blank hides,
        anything else shows the per-service answers under the result.
        Same re-layout + on-screen clamp as the definition gloss."""
        self._cmp_text = text or ""
        fill = getattr(self, "_defn_fill", None)
        if not fill:
            return
        try:
            self._fill(*fill)
        except Exception:
            pass
        if self.isVisible() and self._cmp_text:
            try:
                from PySide6.QtGui import QGuiApplication as _QGA
                scr = _QGA.screenAt(self.frameGeometry().center()) \
                    or _QGA.primaryScreen()
                if scr is not None:
                    a = scr.availableGeometry()
                    g = self.geometry()
                    if g.bottom() > a.bottom():
                        self.move(g.x(), a.bottom() - g.height())
            except Exception:
                pass

    def set_inline_definition(self, text):
        """.tmp DefinitionStrip.render: blank hides, anything else shows
        the gloss under the result. The lookup lands asynchronously, so
        this re-lays the window out around the NEW height -- and keeps
        it on screen when the growth would push the bottom edge off."""
        self._defn_text = text or ""
        fill = getattr(self, "_defn_fill", None)
        if not fill:
            return
        try:
            self._fill(*fill)
        except Exception:
            pass
        if self.isVisible() and self._defn_text:
            try:
                from PySide6.QtGui import QGuiApplication as _QGA
                scr = _QGA.screenAt(self.frameGeometry().center()) \
                    or _QGA.primaryScreen()
                if scr is not None:
                    a = scr.availableGeometry()
                    g = self.geometry()
                    if g.bottom() > a.bottom():
                        self.move(g.x(), a.bottom() - g.height())
            except Exception:
                pass

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
        checks the cursor itself now. The shown cells honour .tmp's
        ``serviceSelectorAppearance``: ICONS_ONLY keeps the name only
        when the service has no icon, TEXT_ONLY drops the icons."""
        try:
            from qtranslate import config as _C
            mode = _C.service_selector_appearance()
        except Exception:
            mode = "ICONS_AND_TEXT"
        for b, ico, lab, has_icon in zip(
                getattr(self, "_strip_buttons", ()),
                getattr(self, "_strip_icons", ()),
                getattr(self, "_strip_labels", ()),
                getattr(self, "_strip_has_icon", ())):
            if not on:
                b.hide()
                ico.hide()
                lab.hide()
                continue
            b.show()
            ico.setVisible(mode != "TEXT_ONLY" and has_icon)
            lab.setVisible(mode != "ICONS_ONLY" or not has_icon)

    def enterEvent(self, event):                # noqa: N802 (Qt name)
        self._hovering = True
        self._set_hover(True)
        # Hover pauses the idle-hide countdown (.tmp stops it while the
        # pointer is inside).
        self._stop_idle_timer()
        super().enterEvent(event)

    def leaveEvent(self, event):                # noqa: N802 (Qt name)
        self._hovering = False
        self._set_hover(False)
        if self.isVisible():
            self._start_idle_timer()
        super().leaveEvent(event)

    def keyPressEvent(self, event):             # noqa: N802 (Qt name)
        """Esc closes the popup (native's hotkey); Ctrl+P toggles the
        pin. A pinned popup ignores Escape -- .tmp guards onDismiss
        with !isPinned so a pinned answer is not one keystroke away
        from gone."""
        mods = event.modifiers()
        if mods & Qt.ControlModifier:
            # .tmp QuickTranslateDialog key actions: Ctrl+P pin,
            # Ctrl+C copy, Ctrl+E listen, Ctrl+S swap languages.
            if event.key() == Qt.Key_P:
                self._toggle_pin()
                return
            if event.key() == Qt.Key_C:
                self._icon_copy()
                return
            if event.key() == Qt.Key_E:
                self._icon_listen()
                return
            if event.key() == Qt.Key_S:
                app = getattr(self, "app", None)
                if app is not None and hasattr(app, "on_swap"):
                    try:
                        app.on_swap()
                    except Exception:
                        pass
                return
        if event.key() == Qt.Key_Escape and not getattr(self, "_pinned",
                                                        False):
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
            # A pinned popup survives outside clicks (.tmp
            # PopupDismissalPolicy skips isPinned).
            if getattr(self, "_pinned", False):
                return False
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
                # .tmp closePopupsOnClickOutside (default on): the
                # Options -> Appearance checkbox can keep the popup
                # open through outside clicks.
                try:
                    from qtranslate import config as _C
                    ap = ((_C.load() or {}).get("Appearance", {}) or {})
                    if not bool(ap.get("ClosePopupsOnClickOutside", True)):
                        return False
                except Exception:
                    pass
                try:
                    self.hide()
                except Exception:
                    pass
                return False
        return False

    def showEvent(self, event):                 # noqa: N802 (Qt name)
        self._has_been_shown = True
        # A popup that opens under the cursor (the common Ctrl+Q case --
        # it places at the pointer) never receives an enter event, so
        # the provider strip stayed hidden until the pointer left and
        # came back. Check on show instead.
        try:
            if self.underMouse():
                self._hovering = True
                self._set_hover(True)
        except Exception:
            pass
        try:
            self.raise_()
            if self._auto_focus():
                self.activateWindow()
                self.setFocus(Qt.ActiveWindowFocusReason)
        except Exception:
            pass
        # place() runs before show(), when isVisible() is still False --
        # the idle countdown arms here for the first show and re-arms
        # per translation while already visible.
        self._start_idle_timer()
        super().showEvent(event)

    def hideEvent(self, event):                 # noqa: N802 (Qt name)
        self._stop_idle_timer()
        # Persist the resting rect on close (.tmp hideDialog ->
        # onSavePosition/onSaveSize), but only once the popup has
        # actually been shown -- a never-placed window would save a
        # meaningless (0,0) origin.
        if self._has_been_shown:
            self._save_popup_placement()
        # A closed popup re-arms auto-position for the next
        # translation (.tmp resetManualMove on state reset) -- and the
        # pin dies with it too (.tmp MainTranslationPolicy.afterQuickClose:
        # a fresh open is never pinned, whatever the last one was left as).
        self._manually_moved = False
        try:
            if self._pinned:
                self.set_pinned(False)
        except Exception:
            self._pinned = False
        super().hideEvent(event)

    @staticmethod
    def _auto_focus() -> bool:
        """Appearance.PopupAutoFocus -- native's "take focus on show".

        Default False: the popup is an answer, not a destination; the
        user keeps typing in the app they were translating from. On
        macOS an activateWindow() here also pulls the whole app forward
        in the Dock, which reads as the translator stealing focus.
        """
        try:
            from qtranslate import config as _C
            return bool(_C.load().get("Appearance", {})
                        .get("PopupAutoFocus", False))
        except Exception:
            return False

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
            if self._auto_focus():
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
        x = y = None
        screen = None
        try:
            # .tmp applyPosition: once the user has dragged the window
            # it stops following the pointer, even with auto-position
            # on -- a popup that jumped back after being moved would be
            # fighting the person using it.
            _auto_pos = bool(_ap.get("PopupAutoPos", True))
            if _auto_pos and getattr(self, "_manually_moved", False):
                _auto_pos = False
            if _auto_pos:
                p = QCursor.pos()
                x, y = p.x() + 12, p.y() + 12
                screen = QGuiApplication.screenAt(p)
                # .tmp QuickTranslateDialog.applyPosition: prefer the
                # lower-right of the cursor, but flip to the other side
                # of the pointer when the popup would leave that
                # monitor -- clamp is only the last resort.
                if screen is not None:
                    a = screen.availableGeometry()
                    if x + self.width() > a.right():
                        x = p.x() - self.width() - 10
                    if y + self.height() > a.bottom():
                        y = p.y() - self.height() - 10
            else:
                from qtranslate.placement import decode_placement
                rc = decode_placement(
                    _C.load().get("General", {})
                    .get("WindowPopupPlacement", ""))
                if rc:
                    x, y, _w, _h, _fl = rc
                    screen = QGuiApplication.screenAt(QPoint(x, y))
        except Exception:
            pass
        if x is not None and y is not None:
            try:
                if screen is None:
                    screen = QGuiApplication.primaryScreen()
                if screen is not None:
                    from qtranslate.placement import clamp_window_position
                    area = screen.availableGeometry()
                    x, y = clamp_window_position(
                        x, y, self.width(), self.height(),
                        area.x(), area.y(), area.width(), area.height())
                self.move(x, y)
            except Exception:
                pass
        # POPUP TIMEOUT IS OPT-IN and click-outside CLOSES the popup --
        # the operator's report (2026-10-24): the answer arrived, the
        # popup showed for five seconds and vanished while he was still
        # reading ("giật lag rồi không thấy gì"). A zero timeout means
        # the popup stays until the user clicks elsewhere or closes it.
        # One QTimer for the popup's whole life: place() runs on every
        # translation, and re-creating it dropped the old timer's last
        # reference -- the same GC-of-live-Qt-object crash as the
        # per-translation PopupWindow did. _start_idle_timer re-arms it
        # per translation and honours pin/hover (.tmp startIdleHide).
        self._start_idle_timer()
        from PySide6.QtWidgets import QApplication as _QA
        # Install only one active filter — remove any previous instance on this
        # object before installing the fresh one. This prevents stale filters
        # accumulating over many translations.
        try:
            _QA.instance().removeEventFilter(self)
        except Exception:
            pass
        _QA.instance().installEventFilter(self)
