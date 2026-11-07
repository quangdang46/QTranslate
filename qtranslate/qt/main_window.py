"""The main window (native DLG 129) on PySide6.

Every number here was MEASURED off ``docs/review/native_screens/2131.png``:
the geometry in ``qtranslate-pyside6-spec.md`` §3, and the fonts, the
colours and the icon positions measured off the same capture. The
coordinates are the ones in the native capture; ``Base.ORIGIN`` says
where that capture's client area starts and ``put()`` converts them, so
the numbers can be copied straight across.

The behaviour is the port's: the same core (``qtranslate.engine``,
``qtranslate.registry``, ``qtranslate.config``) does the translating, the
same history file is written, the same settings are persisted. This
module is the VIEW; it owns no translation logic of its own.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QSize, QEvent, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QFont, QIcon,
                           QKeySequence, QPalette, QShortcut, QTextCursor)
from PySide6.QtWidgets import (QComboBox, QLabel, QMenu, QPushButton,
                               QTextEdit)

from qtranslate_style import THUMB

from . import icons
from .context_menus import append_extensions, pack_labels
from .widgets import (Base, LINK, button, combo, extension_menu_entries,
                      hline, icon, label, put,
                      rect, vline)

# The two text panes of the main window use a LARGER font than the
# controls around them: the help text is set in Tahoma 9pt (12px, 14px
# line pitch) while every button, combo and label is Tahoma 8pt (11px).
# Both were measured off the native capture -- the help line "Double Ctrl
# => Show main window (with translation of selected text, if any)" is 418px
# wide there, which is Tahoma 9pt and not Tahoma 8pt (363px).
#
# The face itself is NOT hardcoded: General.FontName/TextSize resolve
# through qtranslate.fonts.resolve_font -- the same contract
# qtranslate_style._ui_font applies to the controls -- with the measured
# Tahoma 9pt pair as the fallback.
PANE_FONT_FALLBACK = ("Tahoma", 9)
# The pane stylesheet's pixel size at the fallback's 9pt: 12px measured.
PANE_FONT_PX = 12


def _pane_font():
    """``(family, point_size, pixel_size)`` for the two text panes.

    ``resolve_editor_font`` owns the config contract (empty editor
    name -> inherit ``General.FontName``/``TextSize``, garbage size
    -> 9, clamp at 6) -- the .tmp uiFont/editorFont split. TextSize
    is a POINT size
    while the pane stylesheet is in pixels, so the pixel size is scaled
    off the measured 12px-at-9pt pair -- the same grid
    ``qtranslate_style._ui_font`` uses for the controls.
    """
    try:
        from qtranslate import config as _cfg
        from qtranslate.fonts import resolve_editor_font
        name, size = resolve_editor_font(_cfg.load() or {})
    except Exception:
        name, size = PANE_FONT_FALLBACK
    return name, size, max(6, int(round(PANE_FONT_PX * size / 9.0)))


# The result pane starts with native's own "nothing came back" line.
EMPTY_RESULT = "No data returned (timeout while sending data)."

# Instant translation (.tmp MainStore.observeInstantTranslation):
# INSTANT_TRANSLATION_DEBOUNCE_MS = 350, INSTANT_TRANSLATE_MIN_CHARS = 2
# (AppConstants.kt). The flag is native menu 1/20, persisted as
# Options.json General.InstantTranslation -- the same General.* slot
# General.ReadPhonetically already uses for menu 1/50.
INSTANT_DEBOUNCE_MS = 350
INSTANT_MIN_CHARS = 2

# The nine providers of the bottom strip. The ICON of each one was
# recovered from the installer payload; the LABEL is the service's
# display name, cut to two characters and an ellipsis when the name does
# not fit the button (measured off the native capture: "Baidu" shows as
# "Ba..." on a 56px button, but "DeepL" fits on the last, wider one).
STRIP_ICONS = {
    "google": "google", "microsoft": "microsoft", "promt": "promt",
    "babylon": "babylon", "yandex": "yandex", "youdao": "youdao",
    "baidu": "baidu", "naver": "naver", "deepl": "deepl",
}


def default_source_text() -> str:
    """Native's source pane on a fresh start: the version line, then the
    WHOLE help.txt (native's own file, recovered and bundled)."""
    lines = ["QTranslate Version  6.10.0", ""]
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(here, "assets", "locales", "English", "help.txt"),
                 "C:/Program Files (x86)/QTranslate/Locales/English/help.txt"):
        try:
            with open(path, encoding="utf-8-sig") as f:
                lines.append(f.read().strip())
            return "\n".join(lines)
        except Exception:
            continue
    lines.append("Double Ctrl => Show main window\n"
                 "Ctrl+Q => Translate selected text\n"
                 "Ctrl+E => Listen to selected text")
    return "\n".join(lines)


def _cycle_target(win):
    """Ctrl+L: advance the target combo one language, wrapping around.

    The combo's items ARE the enabled target names, so stepping the
    index steps the language; ``_tgt_changed`` then persists it through
    the same path a manual pick takes.
    """
    try:
        cmb = win.cmb_tgt
        n = cmb.count()
        if n < 2:
            return
        cmb.setCurrentIndex((cmb.currentIndex() + 1) % n)
    except Exception:
        pass


def _copy_translation(win):
    """Ctrl+Shift+C (.tmp COPY_TRANSLATION, LOCAL): the whole result
    text to the clipboard -- not just the current selection."""
    try:
        text = win.out.toPlainText()
        if not text:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
    except Exception:
        pass


class MainWindow(Base):
    """The main window: nav row, source pane, splitter, tool row, result
    pane, provider strip."""

    ORIGIN, SIZE = (1, 31), (514, 391)
    WANTS_FOCUS = True

    def __init__(self, app):
        super().__init__()
        self.app = app
        try:
            from qtranslate.locale import ui_caption
            self.setWindowTitle(ui_caption(1, "QTranslate"))
        except Exception:
            self.setWindowTitle("QTranslate")
        self.setAcceptDrops(True)
        # Native's main window is user-resizable and remembers its
        # geometry between runs (the main-window audit). ``Base`` pins
        # the client to SIZE; lift the ceiling, keep the floor, and
        # restore whatever frame the last run saved.
        self.setMinimumSize(*self.SIZE)
        self.setMaximumSize(16777215, 16777215)
        self._restore_geometry()
        self._build()

    # ---------------------------------------------------------------- build
    def _build(self):
        app = self.app
        # Appearance.ColorBack/ColorText/ColorFrame are THIS window's
        # colours (native's defaults: back 0xf0f0f0, text black, frame
        # 0x7a6c5d) -- the Options page's three swatches. They are NOT
        # the popup's; popup.py keeps its own theme-derived colours.
        try:
            from qtranslate_style import popup_colors
            _cbg, _ctx, _cfr = popup_colors()
        except Exception:
            _cbg = _ctx = _cfr = None
        self._mw_bg = _cbg or "#f0f0f0"
        self._mw_text = _ctx or "#000000"
        self._mw_frame = _cfr or "#7e7e7e"
        try:
            _pal = self.palette()
            _pal.setColor(QPalette.ColorRole.Window,
                          QColor(self._mw_bg))
            _pal.setColor(QPalette.ColorRole.WindowText,
                          QColor(self._mw_text))
            self.setPalette(_pal)
        except Exception:
            pass
        # ---- nav row (capture y 31..58) ---------------------------------
        # The back/forward pair is ONE joined button with a divider, and
        # the two arrows are the icons recovered from the binary.
        self.btn_back = self._nav_button(4, 34, 26, "back")
        self.btn_fwd = self._nav_button(30, 34, 26, "forward")
        self.lbl_service = label(self, 62, 44, app.service_title(),
                                 color=LINK, underline=True)
        self.btn_nav = button(self, 493, 37, 16, "")
        self.btn_nav.setObjectName("navmenu")
        icon(self, 493, 37, "ui_icons", "menu")
        hline(self, 59, 4, 512, self._mw_frame)

        # ---- source pane (capture y 59..211) ----------------------------
        # A 1px #7e7e7e frame around a white edit. The text starts three
        # pixels inside the frame; the scrollbar is 17px wide and its
        # thumb 2px, at the far right of the pane.
        rect(self, 5, 61, 507, 150, "#ffffff", "srcbg")
        vline(self, 4, 59, 212, self._mw_frame)
        vline(self, 511, 60, 212, self._mw_frame)
        pane_family, pane_pts, pane_px = _pane_font()
        self.src = QTextEdit()
        self.src.setObjectName("pane")
        self.src.setAcceptRichText(False)
        self.src.setFrameShape(QTextEdit.NoFrame)
        # The ID selector beats the app stylesheet's plain "QTextEdit"
        # rule, which would otherwise put a 1px #7e7e7e border on the
        # pane -- native's pane has no border of its own, only the frame
        # drawn around it.
        self.src.setStyleSheet(
            "QTextEdit#pane{background:transparent;border:none;color:%s;"
            'font-family:"%s";font-size:%dpx;'
            "QScrollBar:vertical{background:#f0f0f0;width:16px;margin:0;}"
            "QScrollBar::handle:vertical{background:%s;margin:0 7px;"
            "min-height:20px;}}"
            % (self._mw_text, pane_family, pane_px, THUMB))
        put(self, self.src, 7, 61, 504, 150)
        self.src.document().setDefaultFont(QFont(pane_family, pane_pts))
        self.src.document().setDocumentMargin(0)
        self.src.setPlainText(default_source_text())
        icon(self, 451, 190, "ui_icons", "mic")
        icon(self, 473, 190, "ui_icons", "headphone")
        hline(self, 211, 4, 512, self._mw_frame)

        # ---- the splitter's grip (three dots under the rule) ------------
        for x in (252, 256, 260):
            rect(self, x, 213, 3, 2, "#555555", "grip")

        # ---- tool row (capture y 213..238) ------------------------------
        self.btn_new = button(self, 5, 217, 29, "")
        self.btn_new.setObjectName("flat")
        icon(self, 11, 220, "ui_icons", "new")
        for y in (221, 227, 233):
            rect(self, 48, y, 4, 4, "#6d6d6d", "grip2")
        self.cmb_src = combo(self, 67, 217, 150, "Auto-Detect", 21,
                             values=app.source_names())
        # The source combo is an EDITABLE one in native, so its text
        # starts four pixels further in: MEASURED off capture 2131 (the
        # word starts 12px inside the frame, the target combo's 8px).
        self.cmb_src.setStyleSheet("QComboBox{padding-left:10px;}")
        self.btn_swap = button(self, 223, 217, 27, "")
        icon(self, 228, 220, "ui_icons", "swap")
        self.cmb_tgt = combo(self, 250, 217, 177, "Vietnamese", 21,
                             values=app.target_names())
        self.cmb_tgt.setStyleSheet("QComboBox{padding-left:10px;}")
        self.btn_go = button(self, 434, 217, 73, "Translate", 22)
        hline(self, 242, 4, 512, self._mw_frame)

        # ---- result pane (capture y 242..392) ----------------------------
        rect(self, 5, 244, 507, 148, "#ffffff", "resbg")
        vline(self, 4, 242, 393, self._mw_frame)
        vline(self, 511, 243, 393, self._mw_frame)
        self.out = QTextEdit()
        self.out.setObjectName("pane")
        self.out.setAcceptRichText(False)
        self.out.setFrameShape(QTextEdit.NoFrame)
        self.out.setReadOnly(True)
        self.out.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.out.setStyleSheet(
            "#pane{background:transparent;border:none;color:%s;"
            'font-family:"%s";font-size:%dpx;}'
            % (self._mw_text, pane_family, pane_px))
        self.out.document().setDefaultFont(QFont(pane_family, pane_pts))
        self.out.document().setDocumentMargin(0)
        self.out.setPlainText(EMPTY_RESULT)
        # Native keeps the back-translation in its OWN pane below the
        # result (Contents.EditBackTranslation is a separate stored
        # field, and General.BackTranslationSplitterPos records the
        # divider). The port used to concatenate with an invented
        # "--- back-translation ---" marker; the marker now only rides
        # inside the combined string until set_result() splits it.
        from PySide6.QtWidgets import (QSplitter, QVBoxLayout, QWidget)
        self.result_box = QWidget(self)
        put(self, self.result_box, 8, 245, 503, 147)
        self._split = QSplitter(Qt.Vertical, self.result_box)
        # .tmp's inline definition: a one-line gloss under a
        # single-word translation. The label lives in a wrapper around
        # the result edit so the splitter still sees one widget.
        from PySide6.QtWidgets import QLabel
        self.out_wrap = QWidget()
        _ow = QVBoxLayout(self.out_wrap)
        _ow.setContentsMargins(0, 0, 0, 0)
        _ow.setSpacing(0)
        _ow.addWidget(self.out, 1)
        self.defn = QLabel(self.out_wrap)
        self.defn.setStyleSheet(
            "color:#666666;font-size:10px;padding:0 2px;")
        self.defn.setTextFormat(Qt.PlainText)
        self.defn.setWordWrap(True)
        self.defn.setVisible(False)
        _ow.addWidget(self.defn)
        self._split.addWidget(self.out_wrap)
        self.back = QTextEdit()
        self.back.setObjectName("pane")
        self.back.setAcceptRichText(False)
        self.back.setFrameShape(QTextEdit.NoFrame)
        self.back.setReadOnly(True)
        self.back.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.back.setStyleSheet(
            "#pane{background:transparent;border:none;color:%s;"
            'font-family:"%s";font-size:%dpx;}'
            % (self._mw_text, pane_family, pane_px))
        self.back.document().setDefaultFont(QFont(pane_family, pane_pts))
        self.back.document().setDocumentMargin(0)
        self.back.setPlainText("")
        # .tmp's ExtraOutputPanel: the lower pane is ONE extra-output
        # surface with three mutually-exclusive modes -- backward
        # translation (native's EditBackTranslation), AI summary and AI
        # rewrite. A slim header carries the mode toggles plus the
        # option gear (length/style, and the input/output source).
        from PySide6.QtWidgets import (QHBoxLayout, QPushButton,
                                       QToolButton)
        self.extra_wrap = QWidget()
        _ev = QVBoxLayout(self.extra_wrap)
        _ev.setContentsMargins(0, 0, 0, 0)
        _ev.setSpacing(0)
        self.extra_bar = QWidget(self.extra_wrap)
        _eb = QHBoxLayout(self.extra_bar)
        _eb.setContentsMargins(4, 1, 4, 1)
        _eb.setSpacing(4)
        self._extra_buttons = {}
        for _mid, _lbl in (("back", "Back"), ("summary", "Summary"),
                           ("rewrite", "Rewrite"), ("compare", "Compare")):
            b = QPushButton(_lbl, self.extra_bar)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setFlat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton{border:1px solid #bfbfbf;border-radius:3px;"
                "padding:0 6px;font-size:10px;color:#333333;}"
                "QPushButton:checked{background:#d0d0d0;"
                "border-color:#909090;}")
            b.clicked.connect(
                lambda _c=False, m=_mid: self.set_extra_mode(m))
            self._extra_buttons[_mid] = b
            _eb.addWidget(b)
        _eb.addStretch(1)
        self.extra_src_btn = QToolButton(self.extra_bar)
        self.extra_src_btn.setText("Out")
        self.extra_src_btn.setToolTip(
            "Extra output source: translated text (Out) or "
            "original text (In)")
        self.extra_src_btn.setStyleSheet(
            "QToolButton{border:1px solid #bfbfbf;border-radius:3px;"
            "padding:0 5px;font-size:10px;color:#333333;}")
        self.extra_src_btn.clicked.connect(self._cycle_extra_source)
        self.extra_gear = QToolButton(self.extra_bar)
        self.extra_gear.setText("⚙")
        self.extra_gear.setToolTip("Extra output options")
        self.extra_gear.setStyleSheet(
            "QToolButton{border:1px solid #bfbfbf;border-radius:3px;"
            "padding:0 5px;font-size:10px;color:#333333;}")
        self.extra_gear.clicked.connect(self._extra_options_menu)
        _eb.addWidget(self.extra_src_btn)
        _eb.addWidget(self.extra_gear)
        # .tmp MainContentView's extra-output listen button
        # (ListenToText TextSource.ExtraOutput).
        self.extra_listen = QToolButton(self.extra_bar)
        self.extra_listen.setText("🔊")
        self.extra_listen.setToolTip("Listen to extra output")
        self.extra_listen.setStyleSheet(
            "QToolButton{border:1px solid #bfbfbf;border-radius:3px;"
            "padding:0 5px;font-size:10px;color:#333333;}")
        self.extra_listen.clicked.connect(
            lambda _c=False: app._speak_extra())
        _eb.addWidget(self.extra_listen)
        _ev.addWidget(self.extra_bar)
        _ev.addWidget(self.back)
        self._split.addWidget(self.extra_wrap)
        self._split.setStretchFactor(0, 3)
        self._split.setStretchFactor(1, 2)
        self.extra_wrap.setVisible(False)
        # Sync the checked button + option visibility with the stored
        # mode before anything can query it.
        self._extra_mode = "back"
        try:
            self._sync_extra_mode()
        except Exception:
            pass
        _rl = QVBoxLayout(self.result_box)
        _rl.setContentsMargins(0, 0, 0, 0)
        _rl.setSpacing(0)
        _rl.addWidget(self._split)
        # Native's BackTranslationSplitterPos: remember the divider.
        self._split.splitterMoved.connect(self._save_split_pos)
        try:
            from qtranslate import config as _cfg
            _pos = int(((_cfg.load() or {}).get("General", {}) or {})
                       .get("BackTranslationSplitterPos", 0) or 0)
            if _pos > 40:
                self._split.setSizes([_pos, 147 - _pos])
        except Exception:
            pass
        icon(self, 473, 372, "ui_icons", "headphone")
        hline(self, 392, 4, 512, self._mw_frame)
        hline(self, 393, 5, 511, "#ffffff")

        # ---- the provider strip (capture y 397..418) --------------------
        self.tabs = []
        # (button, icon, label, has_icon) per cell -- .tmp's
        # serviceSelectorAppearance picks which of icon/text each cell
        # shows; the widgets are siblings of the button, not children.
        self._strip_cells = []
        names = app.ordered_services()
        for i, name in enumerate(names):
            self.tabs.append(self._strip_button(i, name, len(names)))
        # The highlight follows the RESTORED service, not "first button"
        # (a session saved on DeepL opened with Google lit up).
        self.highlight_service(app.service)

        # wiring
        self.btn_go.clicked.connect(app.on_go)
        self.btn_new.clicked.connect(app.on_new)
        self.btn_swap.clicked.connect(app.on_swap)
        self.btn_nav.clicked.connect(self._nav_menu)
        self.lbl_service.mousePressEvent = self._service_clicked
        self.cmb_src.currentTextChanged.connect(self._src_changed)
        self.cmb_tgt.currentTextChanged.connect(self._tgt_changed)
        self.btn_back.clicked.connect(app.on_back)
        self.btn_fwd.clicked.connect(app.on_forward)

        # Instant translation: every edit re-arms the debounce; the
        # result renders through app._start_translation with a callback
        # that never reaches push_hist, so instant answers do not flood
        # the history (the gap .tmp's INSTANT origin creates).
        self.src.textChanged.connect(self._src_text_changed)

        # Session-history keys. Native walks the same entries the
        # back/forward buttons do (Alt+Left/Right -- SERVICES_PAGE_
        # PARITY §23); .tmp names the intents UndoTranslation /
        # RedoTranslation but binds them to those same buttons, so
        # Ctrl+Z stays the text pane's own undo and is NOT rebound here.
        self._sc_back = QShortcut(QKeySequence("Alt+Left"), self)
        self._sc_back.activated.connect(app.on_back)
        self._sc_fwd = QShortcut(QKeySequence("Alt+Right"), self)
        self._sc_fwd.activated.connect(app.on_forward)

        # .tmp LOCAL hotkeys (HotkeyBinding scope=LOCAL, Swing InputMap):
        # window-scoped shortcuts that only fire while the main window
        # has focus -- QShortcut's WindowShortcut context gives exactly
        # that. Defaults verbatim from HotkeyBinding.DEFAULTS.
        self._sc_go = QShortcut(QKeySequence("Ctrl+Enter"), self)
        self._sc_go.activated.connect(app.on_go)
        self._sc_opts = QShortcut(QKeySequence("Ctrl+,"), self)
        self._sc_opts.activated.connect(lambda: app.open_options())
        self._sc_swap = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self._sc_swap.activated.connect(app.on_swap)
        self._sc_hist = QShortcut(QKeySequence("Ctrl+Shift+H"), self)
        self._sc_hist.activated.connect(app.open_history)
        self._sc_doc = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        self._sc_doc.activated.connect(app.open_document_translation)
        self._sc_copy = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self._sc_copy.activated.connect(lambda: _copy_translation(self))
        self._sc_clear = QShortcut(QKeySequence("Ctrl+Shift+X"), self)
        self._sc_clear.activated.connect(lambda: self.src.clear())
        # CYCLE_TARGET_LANGUAGE (.tmp LOCAL, Ctrl+L): step the target
        # combo to the next enabled language, wrapping.
        self._sc_cycle = QShortcut(QKeySequence("Ctrl+L"), self)
        self._sc_cycle.activated.connect(lambda: _cycle_target(self))
        # FOCUS_INPUT/OUTPUT/EXTRA_OUTPUT: Alt+1/2/3.
        for _key, _w in (("Alt+1", self.src), ("Alt+2", self.out),
                         ("Alt+3", self.back)):
            _sc = QShortcut(QKeySequence(_key), self)
            _sc.activated.connect(
                lambda w=_w: (w.setFocus(),
                              w.moveCursor(
                                  QTextCursor.MoveOperation.End)))

        # Native's menus 2/3/4: right-click in the panes and on the combos.
        # Qt draws the standard edit menu for a QTextEdit by itself; the
        # native menus carry the port's OWN operations (Translate,
        # Dictionary search, Listen), so the standard menu is replaced and
        # the extension slot entries appended under a separator.
        self.src.setContextMenuPolicy(Qt.CustomContextMenu)
        self.src.customContextMenuRequested.connect(self._src_menu)
        self.out.setContextMenuPolicy(Qt.CustomContextMenu)
        self.out.customContextMenuRequested.connect(self._out_menu)
        for cmb in (self.cmb_src, self.cmb_tgt):
            cmb.setContextMenuPolicy(Qt.CustomContextMenu)
            cmb.customContextMenuRequested.connect(self._lang_menu)

        # ---- the extension panels --------------------------------------
        # An extension may contribute a panel to one of the native's
        # three panes (the "Show*Pane" toggles on the Options/Basics
        # page). The contribution is a callable; its answer is shown in
        # a strip docked at the bottom of the pane it claimed. With no
        # extension there is no strip at all, so the window is exactly
        # the native's pixels.
        self.panels = self._build_panels()
        self.apply_pane_visibility()

    def apply_pane_visibility(self):
        """Honour native's three Show*Pane settings.

        Native's main menu (id 1, items 65/70/80) toggles the top,
        middle and services panes, and the Settings file carries the
        same three keys. Before this the port drew all three always, so
        flipping ShowServicesPane changed nothing -- a setting that
        saves but does nothing is the exact shape the audit exists to
        catch. Qt hides the widgets the pane is made of.
        """
        try:
            from qtranslate import config
            general = (config.load() or {}).get("General", {})
        except Exception:
            return
        top = bool(general.get("ShowTopPane", True))
        middle = bool(general.get("ShowMiddlePane", True))
        services = bool(general.get("ShowServicesPane", True))
        # .tmp toolbarVisibility: isLanguageBarVisible hides the whole
        # tool row (.tmp's LanguageSelectionBar: clear, source, swap,
        # target, translate), isHistoryBarVisible the back/forward pair
        # (its TranslationHistoryBar's navigation half -- the port has
        # no status line or image/document buttons to hide).
        langbar = bool(general.get("ShowLanguageBar", True))
        histbar = bool(general.get("ShowHistoryBar", True))
        if self.src is not None:
            self.src.setVisible(top)
        for widget in (getattr(self, "cmb_src", None),
                       getattr(self, "cmb_tgt", None),
                       getattr(self, "btn_new", None),
                       getattr(self, "btn_swap", None),
                       getattr(self, "btn_go", None)):
            if widget is not None:
                widget.setVisible(top and langbar)
        for widget in (getattr(self, "result_box", None) or self.out,):
            widget.setVisible(middle)
        for widget in getattr(self, "tabs", ()) or ():
            widget.setVisible(services)
        # The pane's DRAWN chrome hides with it too: the 1px rules, the
        # pane-background rects and the pane icons are plain child
        # widgets, and hiding only the edits left them floating over
        # empty space (the pane-toggle audit). Band each child by its
        # vertical centre in capture coordinates; the nav row (cy < 55)
        # and the widgets already handled above always stay.
        try:
            from PySide6.QtWidgets import QWidget as _W
            oy = self.ORIGIN[1]
            keep = {w for w in (
                self.src, getattr(self, "result_box", None) or self.out,
                getattr(self, "cmb_src", None),
                getattr(self, "cmb_tgt", None), getattr(self, "btn_new",
                None), getattr(self, "btn_swap", None),
                getattr(self, "btn_go", None), self.btn_back,
                self.btn_fwd, self.lbl_service, self.btn_nav)
                if w is not None}
            keep.update(getattr(self, "tabs", ()) or ())
            keep.update((getattr(self, "panels", {}) or {}).values())
            for child in self.children():
                if not isinstance(child, _W) or child in keep:
                    continue
                try:
                    cy = child.y() + child.height() // 2 + oy
                except Exception:
                    continue
                if cy < 55:
                    continue                    # nav row: always shown
                if cy <= 241:
                    child.setVisible(top)
                elif cy <= 396:
                    child.setVisible(middle)
                else:
                    child.setVisible(services)
        except Exception:
            pass
        for w in (getattr(self, "btn_back", None),
                  getattr(self, "btn_fwd", None)):
            if w is not None:
                w.setVisible(histbar)
        self._apply_selector_appearance(services)

    def _apply_selector_appearance(self, services_visible=True):
        """.tmp ``serviceSelectorAppearance`` on the provider strip:
        ICONS_ONLY shows the icon alone (the name stays when the
        service has no icon, like .tmp's rebuildClassic), TEXT_ONLY
        drops the icons, ICONS_AND_TEXT keeps both."""
        try:
            from qtranslate import config
            mode = config.service_selector_appearance()
        except Exception:
            mode = "ICONS_AND_TEXT"
        for _b, ico, lab, has_icon in getattr(self, "_strip_cells", ()):
            try:
                ico.setVisible(bool(services_visible)
                               and mode != "TEXT_ONLY" and has_icon)
                lab.setVisible(bool(services_visible)
                               and (mode != "ICONS_ONLY" or not has_icon))
            except Exception:
                pass

    # The panel strips: pane slot -> the rect the strip is docked at, in
    # the window's client coordinates. The top pane's strip stops short
    # of the microphone and headphone icons (capture 2131, x 451 and
    # 473); the middle pane's stops short of its headphone (x 473).
    PANEL_STRIPS = {
        "top": (7, 195, 440, 16),
        "middle": (8, 376, 460, 16),
        # The services pane: the strip sits just above the provider
        # buttons, which start at y 397 (capture 2131).
        "services": (7, 381, 500, 15),
    }

    def _build_panels(self):
        """Show the panels an extension contributed, one per pane slot."""
        manager = getattr(self.app, "ext_manager", None)
        slots = getattr(manager, "ui_slots", None) if manager else None
        if slots is None:
            return {}
        out = {}
        for name, box in self.PANEL_STRIPS.items():
            try:
                entries = slots.entries("panel", name)
            except Exception:
                continue
            if not entries:
                continue
            contrib = entries[-1].get("contribution")
            if not callable(contrib):
                continue
            try:
                text = str(contrib() or "")
            except Exception as exc:            # noqa: BLE001
                text = "Extension failed: %s" % exc
            if not text:
                continue
            lbl = QLabel(text)
            lbl.setStyleSheet("background:#f0f0f0;color:#000000;"
                              "border:1px solid #7e7e7e;")
            put(self, lbl, *box)
            out[name] = lbl
        return out

    # ------------------------------------------------- instant translation
    def _general_flag(self, key, default):
        """One ``General`` key with the defaults document merged under the
        file (``config.general_setting``), so a pre-key Options.json
        still sees the default."""
        try:
            from qtranslate import config
            return bool(config.general_setting(key, default))
        except Exception:
            return bool(default)

    def _set_general_flag(self, key, on, after=None):
        """Write one ``General`` flag back to Options.json, then run the
        optional follow-up (the pane toggles re-apply visibility)."""
        try:
            from qtranslate import config
            cfg = config.load() or {}
            cfg.setdefault("General", {})[key] = bool(on)
            config.save(cfg)
        except Exception:
            pass
        if after is not None:
            try:
                after()
            except Exception:
                pass

    def _instant_enabled(self):
        return self._general_flag("InstantTranslation", False)

    def _browsing_history(self):
        """True while the panes show a history entry, not the live text.

        ``app._nav_idx`` is the app's read-only cursor: ``len(history)``
        means "now". While it sits inside the list the source pane holds
        a TRUNCATED snapshot (``push_hist`` stores src[:120]), and an
        instant retranslate of that would overwrite the result the user
        is actually looking at.
        """
        try:
            hist = getattr(self.app, "history", None) or []
            idx = getattr(self.app, "_nav_idx", len(hist))
            return bool(hist) and idx < len(hist)
        except Exception:
            return False

    def _maybe_remove_line_breaks(self):
        """Advanced.RemoveLineBreaks on the VISIBLE pane.

        .tmp UpdateInputText runs prepareInputText on every input
        change -- PDF-copied text lands in the pane already flattened
        (\\n->space, \\r dropped, double space collapsed, trimmed), not
        merely flattened at request time. The request layer
        (reliability.normalize_request) does the same for paths that
        bypass the pane; this keeps what the user SEES identical.
        blockSignals breaks the textChanged recursion; the result is
        stable after one pass (Kotlin's replace is also single-pass).
        """
        try:
            cur = self.src.toPlainText() or ""
            # Cheap shape check BEFORE any config access: plain text
            # with no newline/CR/double-space/edge-whitespace can never
            # change, so the common keystroke costs nothing.
            if ("\n" not in cur and "\r" not in cur and "  " not in cur
                    and cur == cur.strip()):
                return
            # The flag is cached against the file's mtime: a stat per
            # qualifying keystroke, a full JSON parse only when the
            # user actually edited Options.json (same "no disk read per
            # character" rule the instant flag documents).
            from qtranslate import config as _C
            path = getattr(_C, "DEFAULT_PATH", "") or ""
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                mtime = -1
            cache = getattr(self, "_rlb_cache", None)
            if cache is None or cache[0] != mtime:
                try:
                    val = bool(((_C.load() or {}).get("Advanced", {})
                                or {}).get("RemoveLineBreaks", False))
                except Exception:
                    val = False
                cache = self._rlb_cache = [mtime, val]
            if not cache[1]:
                return
            cleaned = (cur.replace("\n", " ").replace("\r", "")
                       .replace("  ", " ").strip())
            if cleaned == cur:
                return
            pos = self.src.textCursor().position()
            self.src.blockSignals(True)
            try:
                self.src.setPlainText(cleaned)
            finally:
                self.src.blockSignals(False)
            try:
                cur2 = self.src.textCursor()
                cur2.setPosition(min(pos, len(cleaned)))
                self.src.setTextCursor(cur2)
            except Exception:
                pass
        except Exception:
            pass

    def _src_text_changed(self):
        """Arm the instant-translation debounce on every edit.

        The flag is read when the timer FIRES, not per keystroke: a
        config.load() on every text change would be a disk read per
        character, and a toggle flipped mid-pause should apply to the
        pending request anyway.
        """
        self._maybe_remove_line_breaks()
        timer = getattr(self, "_instant_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(INSTANT_DEBOUNCE_MS)
            timer.timeout.connect(self._instant_translate)
            self._instant_timer = timer
        timer.start()
        self._maybe_auto_cleanup()

    def _maybe_auto_cleanup(self):
        """Menu-1 item 61 "Auto-cleanup of translation"
        (``General.AutoCleanupTranslation``, default off): an emptied
        source pane clears the result and back-translation panes too,
        so a stale translation cannot linger under fresh input.
        History browsing is exempt -- the panes show a saved entry,
        not live output."""
        try:
            # Cheap checks first: the config load below must not run
            # per keystroke (same rule the instant flag documents).
            if (self.src.toPlainText() or "").strip():
                return
            if self._browsing_history():
                return
            if not self._general_flag("AutoCleanupTranslation", False):
                return
            for w in (getattr(self, "out", None),
                      getattr(self, "back", None)):
                if w is not None and (w.toPlainText() or "").strip():
                    w.clear()
        except Exception:
            pass

    def _instant_translate(self):
        """The debounce fired: translate the CURRENT pane text, once."""
        try:
            # A hidden window cannot be typed into; the guard also keeps
            # the debounce inert in headless runs that never show it.
            if (not self.isVisible() or not self._instant_enabled()
                    or self._browsing_history()):
                return
            text = self.src.toPlainText()
            # .tmp clears the output the moment the input goes blank --
            # no request is spent on an empty string.
            if not text.strip():
                self.out.setPlainText("")
                return
            if len(text.strip()) < INSTANT_MIN_CHARS:
                return
            # A request already in flight (manual Translate, a swap
            # re-fire, an earlier instant answer) covers this text --
            # _start_translation drops a second one anyway, so do not
            # queue a stale duplicate behind it.
            try:
                if any(t.is_alive()
                       for t in getattr(self.app, "_threads", ())):
                    return
            except Exception:
                pass
            self.app._start_translation(text, self._instant_done)
        except Exception:
            pass

    def _instant_done(self, text, res):
        """Render an instant result WITHOUT touching the history.

        This is the callback ``app._start_translation`` invokes on the
        UI thread; unlike ``app._show_main_result`` it never calls
        ``push_hist``, which is what keeps instant answers out of the
        persisted history (.tmp gates ``buildHistory`` on the request's
        TranslationOrigin; the port's equivalent is simply not reaching
        the history write).
        """
        try:
            if self._browsing_history():
                return
            # The user kept typing while this was in flight: a newer
            # debounce is armed and will answer with the CURRENT text,
            # so a stale answer must not overwrite it.
            if self.src.toPlainText() != text:
                return
            self.render(getattr(res, "text", "") or "")
        except Exception:
            pass

    # ------------------------------------------------------------- helpers
    def _nav_button(self, x, y, w, name):
        """One half of the joined back/forward button."""
        b = QPushButton()
        b.setFocusPolicy(Qt.NoFocus)
        b.setObjectName("nav")
        b.setIcon(QIcon(icons.pixmap("ui_icons", name)))
        b.setIconSize(QSize(16, 16))
        put(self, b, x, y, w, 22)
        return b

    def _strip_button(self, i, name, total):
        """One provider button of the bottom strip. The nine sit shoulder
        to shoulder; the LAST one is stretched to the right edge of the
        window, which is why it can show "DeepL" where "Baidu" has to be
        cut down to "Ba..."."""
        # Native's nine sit in fixed 56px slots; id-less providers
        # (the .tmp plugin ports, extension providers) join after them,
        # so past nine the strip subdivides its 508px evenly instead of
        # running off the window's right edge.
        slot = 56 if total <= 9 else max(30, 508 // total)
        x = 4 + slot * i
        w = 512 - x if i == total - 1 else slot
        b = QPushButton()
        b.setFocusPolicy(Qt.NoFocus)
        b.setObjectName("service")
        b.setProperty("selected", "true" if i == 0 else "false")
        put(self, b, x, 397, w, 22)
        b.setProperty("service", name)
        b.clicked.connect(lambda _c=False, n=name: self.app.switch_service(n))
        icon_name = STRIP_ICONS.get(name, name)
        ico = icon(self, x + 3, 400, "service_icons", icon_name)
        lab = label(self, x + 27, 408, self._strip_label(name, w))
        lab.setFixedWidth(w - 30)
        lab.setProperty("service", name)
        lab.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._strip_cells.append(
            (b, ico, lab,
             not icons.pixmap("service_icons", icon_name).isNull()))
        return b

    def _strip_label(self, name, width):
        """Native cuts a service name that does not fit its button down
        to two characters and an ellipsis."""
        from qtranslate import config
        sid = {v: k for k, v in config.SERVICE_NAMES.items()}.get(name)
        full = config.SERVICE_DISPLAY.get(sid) \
            or config.EXTRA_SERVICE_DISPLAY.get(name) or name
        if self.fontMetrics().horizontalAdvance(full) <= width - 31:
            return full
        return full[:2] + "..."

    def _build_nav_menu(self):
        """Construct the nav menu WITHOUT exec'ing it (tests inspect
        the actions); ``_nav_menu`` pops it modally."""
        m = QMenu(self)
        m.setStyleSheet(
            "QMenu{background:#f9f9f9;border:1px solid #e5e5e5;}"
            "QMenu::item{padding:3px 24px 3px 38px;}"
            "QMenu::item:selected{background:#e5e5e5;}")
        app = self.app
        # Native's menu id 1 in full: the option TOGGLES first (items
        # 10..88), then the window commands (90..140). The labels and the
        # order come from the locale pack, so a translated UI gets
        # translated entries -- the same rule the context menus follow.
        lab = pack_labels(1)

        def toggle(item_id, default, key, default_on, after=None):
            """A checkable menu-1 toggle backed by a General.* key.

            The state shown is the state Options.json holds (merged with
            the defaults document), so the menu cannot disagree with the
            file; ``after`` runs the live follow-up (pane visibility).
            """
            act = QAction(lab.get(item_id, default), self)
            act.setCheckable(True)
            act.setChecked(self._general_flag(key, default_on))
            act.toggled.connect(
                lambda on, k=key, f=after: self._set_general_flag(k, on, f))
            m.addAction(act)

        def dead(item_id, default):
            """An item native has and the port does not implement yet:
            drawn disabled, not dropped, so the gap stays visible."""
            act = QAction(lab.get(item_id, default), self)
            act.setEnabled(False)
            m.addAction(act)

        # Spell checking IS live: bing_spell.check feeds corrections and
        # the source pane's context menu offers "Spelling suggestions"
        # (.tmp PerformSpellCheckUseCase + InputTextPanel). Extended has
        # no port-side operation -- drawn disabled.
        toggle(10, "Spell checking", "SpellChecking", True)
        toggle(20, "Instant translation", "InstantTranslation", False)
        # Backward translation IS live: _start_translation passes
        # General.BackTranslation into engine.translate's back_translate
        # path; popup/Alt+W deliberately bypass it.
        toggle(30, "Backward translation", "BackTranslation", False)
        dead(40, "Extended")
        # Read phonetically IS live: engine.translate appends the
        # romanization when General.ReadPhonetically is on (J7).
        toggle(50, "Read phonetically", "ReadPhonetically", False)
        # Items 60/61/62 are live too: _drop_text honours
        # ClearInputOnDragDrop (drop replaces vs appends),
        # _maybe_auto_cleanup honours AutoCleanupTranslation (emptied
        # source clears the result panes), and _contents_enabled gates
        # the Contents.* persist/restore on SaveContentsOnExit.
        toggle(60, "Clear input on Drag && Drop",
               "ClearInputOnDragDrop", True)
        toggle(61, "Auto-cleanup of translation",
               "AutoCleanupTranslation", False)
        toggle(62, "Save contents on exit", "SaveContentsOnExit", True)
        # The three Show*Pane toggles: apply_pane_visibility already
        # reads these keys; this is the UI that was missing.
        toggle(65, "Show top pane", "ShowTopPane", True,
               self.apply_pane_visibility)
        toggle(70, "Show middle pane", "ShowMiddlePane", True,
               self.apply_pane_visibility)
        toggle(80, "Show services pane", "ShowServicesPane", True,
               self.apply_pane_visibility)
        # closeEvent/changeEvent already honour these two keys.
        toggle(81, "Minimize to system tray on minimize",
               "MinimizeToTrayOnMinimize", False)
        toggle(82, "Minimize to system tray on close",
               "MinimizeToTrayOnClose", False)
        # Items 85-88: the "On startup" group -- a disabled caption plus
        # three exclusive actions writing General.MainWindowStartupAction
        # (0=Show window, 1=Minimize to tray, 2=Restore previous state).
        # The startup path in qt/app.py reads the same key; a config
        # without it derives the action from MainWindowShowOnLoad.
        head = QAction(lab.get(85, "On startup"), self)
        head.setEnabled(False)
        m.addAction(head)
        try:
            from qtranslate import config as _C
            _g = (_C.load() or {}).get("General", {})
            _v = _g.get("MainWindowStartupAction")
            if _v is None:
                _v = 0 if _g.get("MainWindowShowOnLoad", True) else 1
            _act = int(_v)
        except Exception:
            _act = 0
        grp = QActionGroup(self)
        grp.setExclusive(True)
        for item_id, default, val in [
                (86, "Show window", 0),
                (87, "Minimize to tray", 1),
                (88, "Restore previous state", 2)]:
            act = QAction(lab.get(item_id, default), self)
            act.setCheckable(True)
            act.setChecked(_act == val)
            act.triggered.connect(
                lambda _c=False, v=val: self._set_startup_action(v))
            grp.addAction(act)
            m.addAction(act)
        m.addSeparator()
        for item_id, default, fn in [
                (90, "Dictionary", app.open_dictionary),
                (100, "History", app.open_history),
                (110, "Keyboard", app.open_keyboard),
                (120, "Options", app.open_options),
                (125, "About QTranslate", app.show_about)]:
            act = QAction(lab.get(item_id, default), self)
            act.triggered.connect(lambda _c=False, f=fn: f())
            m.addAction(act)
        # Native's startup-action group (85..88) is a four-way choice,
        # not a toggle; it stays unimplemented rather than faked.
        # Item 130 "Help" is live: .tmp OptionsPopupMenu.helpSubmenu --
        # How to use / Contact us / Check for updates / auto-check.
        help_menu = m.addMenu(lab.get(130, "Help"))
        how = QAction("How to use", help_menu)
        how.triggered.connect(lambda _c=False: self._show_help())
        help_menu.addAction(how)
        contact = QAction("Contact us", help_menu)
        contact.triggered.connect(lambda _c=False: self._contact_us())
        help_menu.addAction(contact)
        help_menu.addSeparator()
        from qtranslate import update_check as _UC
        chk = QAction("Check for updates", help_menu)
        chk.triggered.connect(lambda _c=False: _UC.check_now(app))
        help_menu.addAction(chk)
        auto = QAction("Automatically check for updates", help_menu)
        auto.setCheckable(True)
        try:
            from qtranslate import config as _C
            auto.setChecked(bool((_C.load() or {}).get("Update", {})
                                 .get("CheckForUpdates", True)))
        except Exception:
            pass
        auto.triggered.connect(lambda on: self._set_auto_update(on))
        help_menu.addAction(auto)
        act = QAction(lab.get(140, "Exit"), self)
        act.triggered.connect(lambda _c=False: app.quit())
        m.addAction(act)
        # The nav menu is native's menu id 1 (ui_slots "main"): an
        # extension may add entries to it.
        m = append_extensions(m, self, app, "main")
        return m

    def _set_startup_action(self, value):
        """Persist ``General.MainWindowStartupAction`` (0/1/2) -- the
        "On startup" radio group; the next launch's window visibility
        is decided in ``qt/app.py``'s startup block."""
        try:
            from qtranslate import config
            cfg = config.load() or {}
            g = cfg.setdefault("General", {})
            g["MainWindowStartupAction"] = int(value)
            # Keep the legacy bool coherent for anything still reading it.
            g["MainWindowShowOnLoad"] = (int(value) == 0)
            config.save(cfg)
        except Exception:
            pass

    def _show_help(self):
        """Help -> How to use: the bundled help.txt in a dialog."""
        from PySide6.QtWidgets import QMessageBox
        try:
            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            with open(os.path.join(here, "assets", "locales", "English",
                                   "help.txt"), encoding="utf-8-sig") as f:
                text = f.read().strip()
        except Exception:
            text = ("Double Ctrl => Show main window\n"
                    "Ctrl+Q => Translate selected text\n"
                    "Ctrl+E => Listen to selected text")
        QMessageBox.information(self, "QTranslate -- How to use", text)

    def _contact_us(self):
        """Help -> Contact us: the project's page in the browser."""
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl("https://github.com/ahatem/QTranslate"))
        except Exception:
            pass

    def _set_auto_update(self, on):
        """Help -> auto-check toggle: Update.CheckForUpdates, the same
        key the Updates options page writes."""
        try:
            from qtranslate import config
            cfg = config.load() or {}
            cfg.setdefault("Update", {})["CheckForUpdates"] = bool(on)
            config.save(cfg)
        except Exception:
            pass

    def _nav_menu(self):
        m = self._build_nav_menu()
        m.exec(self.btn_nav.mapToGlobal(self.btn_nav.rect().bottomLeft()))

    def _search_images(self):
        """Context-menu "Search images": the selected word, else the
        word under the cursor -- .tmp InputTextPanel's rule."""
        import re as _re
        cur = self.src.textCursor()
        word = (cur.selectedText() or "").strip()
        if not word or any(c.isspace() for c in word):
            word = ""
            pos = cur.position()
            text = self.src.toPlainText()
            m = None
            for m in _re.finditer(r"\w+", text):
                if m.start() <= pos <= m.end():
                    word = m.group(0)
                    break
            if not word and text:
                # cursor sits between words -- take the word before it
                before = _re.findall(r"\w+", text[:pos])
                word = before[-1] if before else ""
        self.app.open_image_search(word)

    def _pane_menu(self, which):
        """Native's pane menus: menu 2 in the source pane, menu 3 in the
        result. Each item is an operation the port already has; an id
        with no operation behind it is drawn disabled, not dropped, so
        the audit's gap stays visible in the UI instead of silent.

        The extension slot entries land under a separator, per
        ``ui_slots`` -- those slots now have a host instead of a name.
        """
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        app = self.app
        lab = pack_labels(3 if which == "result" else 2)
        m = QMenu(self)
        if which == "source":
            # .tmp inserts the spelling-suggestions submenu at the TOP
            # of the source pane's menu when the click lands on a
            # correction that has suggestions.
            self._add_spelling_menu(m)
        if which == "source":
            ops = [
                (10, "Undo", self.src.undo if self.src.isUndoRedoEnabled()
                 else None),
                (20, "Cut", lambda: self.src.cut()),
                (30, "Cut all",
                 lambda: (self.src.selectAll(), self.src.cut())),
                (40, "Copy", lambda: self.src.copy()),
                (50, "Copy all",
                 lambda: (self.src.selectAll(), self.src.copy())),
                (60, "Paste", lambda: self.src.paste()),
                (70, "Select all", lambda: self.src.selectAll()),
                (75, "Translate", app.on_go),
                (80, "Dictionary search for",
                 lambda: app.open_dictionary()),
                # Native's InputTextPanel puts "Search images" beside
                # "Find in dictionary" -- same word, same question.
                (85, "Search images", self._search_images),
                (90, "Listen",
                 lambda: app._speak(self.src.toPlainText())),
            ]
        else:
            ops = [
                (10, "Open", app.on_go),
                (15, "Copy text",
                 lambda: self.out.selectAll() or self.out.copy()),
                (20, "Copy translation", lambda: self.out.copy()),
                (30, "Delete", lambda: self.out.clear()),
                (40, "Listen",
                 lambda: app._speak(self.out.toPlainText())),
            ]
        for item_id, default, fn in ops:
            act = QAction(lab.get(item_id, default), self)
            if fn is None:
                act.setEnabled(False)
            else:
                try:
                    act.triggered.connect(
                        lambda _c=False, f=fn: f())
                except Exception:
                    act.setEnabled(False)
            m.addAction(act)
        m = append_extensions(
            m, self, app, "result_context" if which == "result"
            else "source_context")
        pane = self.out if which == "result" else self.src
        pos = pane.mapToGlobal(pane.cursorRect().center()
                               if which == "source"
                               else pane.viewport().rect().center())
        m.exec(pos)

    def _add_spelling_menu(self, m):
        """"Spelling suggestions" submenu for the correction under the
        cursor (.tmp InputTextPanel.buildSpellingMenu)."""
        try:
            pos = self.src.textCursor().position()
            corr = self.app.spell_correction_at(pos)
        except Exception:
            return
        if not corr or not corr.get("suggestions"):
            return
        from PySide6.QtWidgets import QMenu
        sub = QMenu("Spelling suggestions", m)
        for sug in corr["suggestions"]:
            act = sub.addAction(sug)
            act.triggered.connect(
                lambda _c=False, c=corr, s=sug:
                    self.app.apply_spell_correction(c, s))
        # Called before the ops are added, so addMenu lands the submenu
        # at the top exactly where .tmp's menu.insert(spellingMenu, 0)
        # puts it; the separator mirrors menu.insert(spellingMenuSeparator, 1).
        m.addMenu(sub)
        m.addSeparator()

    def _src_menu(self, _p):
        self._pane_menu("source")

    def _out_menu(self, _p):
        self._pane_menu("result")

    def _lang_menu(self, _p):
        """Native's menu 4: the language combos' own menu."""
        from PySide6.QtWidgets import QMenu
        lab = pack_labels(4)
        m = QMenu(self)
        ops = [
            # Native's Reset puts the combo back to its default; Edit...
            # opens the Languages page, which is where the native edits
            # the list. "Always detect language" is a source-side
            # behaviour with no port-side operation yet, so it is drawn
            # disabled rather than faked.
            (10, "Reset", lambda: self.app.set_default_languages()),
            (20, "Edit...", self.app.open_languages_page),
            (30, "Always detect language", None),
        ]
        for item_id, default, fn in ops:
            act = QAction(lab.get(item_id, default), self)
            if fn is None:
                act.setEnabled(False)
            else:
                act.triggered.connect(lambda _c=False, f=fn: f())
            m.addAction(act)
        m = append_extensions(m, self, self.app, "language")
        m.exec(self.cmb_src.mapToGlobal(
            self.cmb_src.rect().bottomLeft()))

    def _service_clicked(self, _e):
        self.app.open_service_page()

    def _src_changed(self, text):
        self.app.set_source_by_name(text)

    def _tgt_changed(self, text):
        self.app.set_target_by_name(text)

    # ----------------------------------------------------- tray semantics
    def _tray_prefs(self):
        try:
            from qtranslate import config as cfg
            return (cfg.load() or {}).get("General", {}) or {}
        except Exception:
            return {}

    # ----------------------------------------------------- window geometry
    def _restore_geometry(self):
        try:
            from PySide6.QtCore import QByteArray
            from qtranslate import config
            cfg = config.load() or {}
            general = cfg.get("General", {}) or {}
            raw = general.get("WindowGeometry")
            # One-time salvage: an earlier build stored the frame under
            # a dedicated "Ui" section; move it into General and drop
            # the section so Options.json keeps the native 20 + known
            # additions (regress_options_roundtrip pins that set).
            ui = cfg.get("Ui") or {}
            if ui.get("MainWindowGeometry") and not raw:
                raw = ui["MainWindowGeometry"]
                general["WindowGeometry"] = raw
                cfg["General"] = general
            if "Ui" in cfg:
                del cfg["Ui"]
                try:
                    config.save(cfg)
                except Exception:
                    pass
            if raw:
                self.restoreGeometry(QByteArray(raw))
        except Exception:
            pass

    def _queue_geometry_save(self):
        """Debounced save: resizes stream move/resize events, so write
        the frame once the user stops dragging the corner."""
        try:
            from PySide6.QtCore import QTimer
            if getattr(self, "_geo_timer", None) is None:
                self._geo_timer = QTimer(self)
                self._geo_timer.setSingleShot(True)
                self._geo_timer.setInterval(500)
                self._geo_timer.timeout.connect(self._write_geometry)
            self._geo_timer.start()
        except Exception:
            pass

    def _write_geometry(self):
        try:
            from qtranslate import config
            cfg = config.load() or {}
            cfg.setdefault("General", {})["WindowGeometry"] = \
                bytes(self.saveGeometry().toBase64()).decode()
            config.save(cfg)
        except Exception:
            pass

    def resizeEvent(self, event):                 # noqa: N802 (Qt name)
        super().resizeEvent(event)
        self._queue_geometry_save()

    def moveEvent(self, event):                   # noqa: N802 (Qt name)
        super().moveEvent(event)
        self._queue_geometry_save()

    def _close_action(self):
        """General.CloseAction tri-state (.tmp closeButtonBehavior:
        ASK/MINIMIZE_TO_TRAY/EXIT). Absent, derive from the native
        MinimizeToTrayOnClose flag so existing configs keep working."""
        prefs = self._tray_prefs()
        try:
            v = str(prefs.get("CloseAction", "") or "").lower()
        except Exception:
            v = ""
        if v in ("ask", "minimize", "exit"):
            return v
        return ("minimize" if prefs.get("MinimizeToTrayOnClose",
                                        False) else "exit")

    def _ask_close(self):
        """The ASK branch's dialog (.tmp showCloseDialog): Minimize to
        tray / Exit plus "Remember my choice", which persists
        General.CloseAction so the dialog never asks twice."""
        from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                                       QLabel, QVBoxLayout)
        dlg = QDialog(self)
        try:
            from qtranslate.locale import ui_caption
            dlg.setWindowTitle(ui_caption(1, "QTranslate"))
        except Exception:
            dlg.setWindowTitle("QTranslate")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Minimize to tray or exit?"))
        remember = QCheckBox("Remember my choice")
        lay.addWidget(remember)
        box = QDialogButtonBox()
        min_btn = box.addButton("Minimize to tray",
                                QDialogButtonBox.AcceptRole)
        exit_btn = box.addButton("Exit", QDialogButtonBox.DestructiveRole)
        lay.addWidget(box)
        choice = {"v": None}
        min_btn.clicked.connect(lambda: choice.update(v="minimize"))
        exit_btn.clicked.connect(lambda: choice.update(v="exit"))
        box.rejected.connect(dlg.reject)
        dlg.exec()
        v = choice["v"]
        if v and remember.isChecked():
            try:
                from qtranslate import config as _C
                cfg = _C.load() or {}
                cfg.setdefault("General", {})["CloseAction"] = v
                _C.save(cfg)
            except Exception:
                pass
        return v

    def closeEvent(self, event):
        """General.CloseAction / MinimizeToTrayOnClose: native keeps
        running in the tray instead of quitting when the window
        closes; "ask" shows the .tmp close dialog first."""
        self._write_geometry()
        action = self._close_action()
        if action == "ask":
            choice = self._ask_close()
            if choice is None:
                event.ignore()
                return
            action = choice
        if action == "minimize":
            event.ignore()
            self.hide()
            return
        super().closeEvent(event)

    def changeEvent(self, event):
        """General.MinimizeToTrayOnMinimize: minimize parks the window
        in the tray rather than the taskbar."""
        try:
            if (event.type() == QEvent.WindowStateChange
                    and self.isMinimized()
                    and self._tray_prefs().get("MinimizeToTrayOnMinimize",
                                               False)):
                self.hide()
        except Exception:
            pass
        super().changeEvent(event)

    # ------------------------------------------------------------- painting
    def _save_split_pos(self, _pos, _idx):
        """Persist the result/back divider (General.BackTranslation-
        SplitterPos -- the native option's own key)."""
        try:
            from qtranslate import config
            cfg = config.load() or {}
            cfg.setdefault("General", {})[
                "BackTranslationSplitterPos"] = int(
                    self._split.sizes()[0])
            config.save(cfg)
        except Exception:
            pass

    def set_result(self, text):
        """Route a (possibly combined) result into the two panes.

        The engine's back-translation arrives inside the result string
        behind the port's BACKTRANSLATION_MARKER; native stores it as
        the separate Contents.EditBackTranslation field, which is what
        the lower pane shows. A result with no marker hides the pane.
        """
        try:
            from qtranslate import reliability as _REL
            main, back = _REL.split_backtranslation(text or "")
        except Exception:
            main, back = (text or ""), ""
        # In the AI modes the lower pane belongs to the extra-output
        # worker -- writing the back-translation here would flash the
        # wrong content before the summary/rewrite lands.
        if self.extra_mode() != "back":
            back = ""
        for w, t in ((self.out, main or (text or "")),
                     (self.back, back)):
            try:
                w.blockSignals(True)
                w.setPlainText(t)
                w.blockSignals(False)
            except Exception:
                pass
        try:
            if self.extra_mode() == "back":
                self.set_extra_visible(bool(back))
        except Exception:
            pass

    # ------------------------------------------------------ extra output
    # .tmp ExtraOutputType: the lower pane is one surface with modes.
    # "back" is the port's default so existing installs keep the
    # native EditBackTranslation behaviour; "summary"/"rewrite" are the
    # ai-services plugin's Summarizer/Rewriter roles; "compare" is the
    # port's surface for .tmp's ParallelComparisonUseCase rows (native
    # has no comparison feature at all).
    _EXTRA_TYPE_KEYS = {"back": "BackwardTranslate",
                        "summary": "Summarize",
                        "rewrite": "Rewrite",
                        "compare": "Compare"}
    _EXTRA_TYPE_MODES = {v: k for k, v in _EXTRA_TYPE_KEYS.items()}

    def _extra_cfg(self):
        try:
            from qtranslate import config as _C
            return (_C.load() or {}).get("General", {}) or {}
        except Exception:
            return {}

    def extra_mode(self):
        """"back" | "summary" | "rewrite" -- the active extra-output
        mode (General.ExtraOutputType; absent/unknown -> "back")."""
        return self._EXTRA_TYPE_MODES.get(
            self._extra_cfg().get("ExtraOutputType") or "",
            "back")

    def _sync_extra_mode(self):
        mode = self.extra_mode()
        self._extra_mode = mode
        for mid, btn in getattr(self, "_extra_buttons", {}).items():
            try:
                btn.blockSignals(True)
                btn.setChecked(mid == mode)
                btn.blockSignals(False)
            except Exception:
                pass
        # The gear + source toggle only matter for the AI modes --
        # .tmp hides configure when the active type declares no
        # options (backward translation has none).
        ai_mode = mode in ("summary", "rewrite")
        for w in (getattr(self, "extra_gear", None),
                  getattr(self, "extra_src_btn", None)):
            try:
                if w is not None:
                    w.setVisible(ai_mode)
            except Exception:
                pass
        try:
            self.extra_src_btn.setText(
                "In" if self._extra_cfg().get(
                    "ExtraOutputSource") == "Input" else "Out")
        except Exception:
            pass

    def set_extra_mode(self, mode):
        """Persist General.ExtraOutputType and ask the app to refresh
        the extra output for the current texts (like .tmp's
        RefreshExtraOutput -- the translation itself is NOT redone)."""
        if mode not in self._EXTRA_TYPE_KEYS:
            return
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            cfg.setdefault("General", {})[
                "ExtraOutputType"] = self._EXTRA_TYPE_KEYS[mode]
            _C.save(cfg)
        except Exception:
            pass
        self._sync_extra_mode()
        app = getattr(self, "app", None)
        if app is not None:
            try:
                app.refresh_extra_output()
            except Exception:
                pass

    def _cycle_extra_source(self):
        """ExtraOutputSource Input|Output toggle (the In/Out button)."""
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            g = cfg.setdefault("General", {})
            g["ExtraOutputSource"] = (
                "Output" if g.get("ExtraOutputSource") == "Input"
                else "Input")
            _C.save(cfg)
        except Exception:
            pass
        self._sync_extra_mode()
        app = getattr(self, "app", None)
        if app is not None:
            try:
                app.refresh_extra_output()
            except Exception:
                pass

    _EXTRA_OPTIONS = {
        "summary": ("SummaryLength",
                    [("SHORT", "Short"), ("MEDIUM", "Medium"),
                     ("LONG", "Long")], "MEDIUM"),
        "rewrite": ("RewriteStyle",
                    [("FORMAL", "Formal"), ("CASUAL", "Casual"),
                     ("CONCISE", "Concise"), ("DETAILED", "Detailed"),
                     ("SIMPLIFIED", "Simplified")], "FORMAL"),
    }

    def _extra_options_menu(self):
        """The gear popup: the active mode's option list, checkable,
        persisted to General.SummaryLength / General.RewriteStyle."""
        from PySide6.QtWidgets import QMenu
        mode = self.extra_mode()
        spec = self._EXTRA_OPTIONS.get(mode)
        if spec is None:
            return
        key, choices, default = spec
        menu = QMenu(self)
        current = self._extra_cfg().get(key) or default
        for value, label in choices:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(value == current)
            act.triggered.connect(
                lambda _c=False, k=key, v=value: self._set_extra_option(k, v))
        menu.exec(self.extra_gear.mapToGlobal(
            self.extra_gear.rect().bottomLeft()))

    def _set_extra_option(self, key, value):
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            cfg.setdefault("General", {})[key] = value
            _C.save(cfg)
        except Exception:
            pass
        app = getattr(self, "app", None)
        if app is not None:
            try:
                app.refresh_extra_output()
            except Exception:
                pass

    def set_extra_visible(self, visible):
        """Show/hide the whole extra-output wrap (bar + pane)."""
        try:
            self.extra_wrap.setVisible(bool(visible))
        except Exception:
            pass

    def set_inline_definition(self, text):
        """The one-line gloss under the result (.tmp inlineDefinition);
        hidden when empty -- every failure is silent like upstream."""
        try:
            self.defn.setText(text or "")
            self.defn.setVisible(bool((text or "").strip()))
        except Exception:
            pass

    def set_extra_text(self, text, visible=None):
        """Fill the extra pane for summary/rewrite modes (the back
        mode's content arrives through set_result's marker split)."""
        try:
            self.back.blockSignals(True)
            self.back.setPlainText(text or "")
            self.back.blockSignals(False)
        except Exception:
            pass
        if visible is None:
            visible = bool((text or "").strip())
        self.set_extra_visible(visible)

    def render(self, text: str, back: str = ""):
        """Fill the result pane (and the back-translation pane, when the
        port has one)."""
        if back:
            try:
                from qtranslate import reliability as _REL
                text = (text or "") + _REL.BACKTRANSLATION_MARKER + back
            except Exception:
                text = (text or "") + "\n\n" + back
        self.set_result(text)
        # .tmp SwapLanguagesUseCase refuses a blank result -- and the
        # button itself goes dead with it, so the affordance matches
        # the behaviour instead of inviting a click that no-ops.
        try:
            usable = bool((text or "").strip()) \
                and (text or "").strip() != EMPTY_RESULT
            self.btn_swap.setEnabled(usable)
        except Exception:
            pass

    # ------------------------------------------------------------- drag & drop
    # Native's main window accepts a dropped IMAGE for text recognition
    # (the OCR audit's missing pipeline). An image file dropped on the
    # window goes through the same ocr_bytes path the region picker
    # uses; dropped plain text lands in the source pane instead.
    def dragEnterEvent(self, event):               # noqa: N802 (Qt name)
        try:
            from PySide6.QtCore import QMimeData
            mime = event.mimeData()
            if mime.hasImage() or mime.hasUrls():
                event.acceptProposedAction()
                return
            if mime.hasText():
                event.acceptProposedAction()
                return
        except Exception:
            pass
        event.ignore()

    def dropEvent(self, event):                    # noqa: N802 (Qt name)
        try:
            mime = event.mimeData()
            app = self.app
            # An image dragged straight from a browser/page arrives as
            # QImage data, not a URL -- encode it the same way.
            if mime.hasImage():
                try:
                    import io as _io
                    img = mime.imageData().toImage()
                    if not img.isNull():
                        out = _io.BytesIO()
                        img.save(out, "PNG")
                        app.ocr_bytes(out.getvalue())
                        event.acceptProposedAction()
                        return
                except Exception:
                    pass
            for url in mime.urls() or []:
                path = url.toLocalFile() if hasattr(url, "toLocalFile") \
                    else str(url)
                if not path or not os.path.isfile(path):
                    continue
                ext = os.path.splitext(path)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif",
                           ".tif", ".tiff", ".webp"):
                    try:
                        from PySide6.QtGui import QImage
                        img = QImage(path)
                        if not img.isNull():
                            import io as _io
                            out = _io.BytesIO()
                            img.save(out, "PNG")
                            app.ocr_bytes(out.getvalue())
                            event.acceptProposedAction()
                            return
                    except Exception:
                        continue
                # DroppedContentClassifier order: images first, then
                # DOCUMENTS (.docx/.pdf/.txt/.srt/.vtt -> the document
                # translation dialog), everything else falls through
                # to the text-file branch below.
                from qtranslate import document as _DOC
                if _DOC.format_of(path) is not None:
                    app.open_document_translation(path)
                    event.acceptProposedAction()
                    return
                # A dropped TEXT file goes into the source pane; binary
                # files that fail a strict decode are skipped rather
                # than pasted in as mojibake.
                try:
                    with open(path, "rb") as f:
                        raw = f.read(40000)
                    text = raw.decode("utf-8")
                    if not text.strip():
                        continue
                    self._drop_text(text[:20000])
                    event.acceptProposedAction()
                    return
                except (UnicodeDecodeError, OSError):
                    continue
            if mime.hasText():
                self._drop_text(mime.text()[:20000])
                event.acceptProposedAction()
                return
        except Exception:
            pass
        event.ignore()

    def _drop_text(self, text):
        """Put dropped text into the source pane.

        Menu-1 item 60 "Clear input on Drag && Drop"
        (``General.ClearInputOnDragDrop``, default on): ON clears the
        pane first -- the drop REPLACES the input; OFF keeps the
        existing text and appends the drop after a newline. (Native's
        exact drag semantics are not recoverable from the port's
        references; the label's plain reading is implemented.)
        """
        try:
            cur = self.src.toPlainText() or ""
            if self._general_flag("ClearInputOnDragDrop", True):
                self.src.setPlainText(text)
            else:
                self.src.setPlainText(
                    (cur + "\n" + text) if cur.strip() else text)
        except Exception:
            self.src.setPlainText(text)

    def set_service_title(self, name: str):
        self.lbl_service.setText(name)

    def highlight_service(self, name: str):
        """The strip's active cell: the selection blue on the button the
        app's service names, the flat style on the rest. The build only
        set `selected` on the FIRST button and nothing ever moved it."""
        for b in self.tabs:
            on = b.property("service") == name
            b.setProperty("selected", "true" if on else "false")
            b.style().unpolish(b)
            b.style().polish(b)
