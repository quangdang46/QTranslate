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

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (QComboBox, QLabel, QMenu, QPushButton,
                               QTextEdit)

from qtranslate_style import THUMB

from . import icons
from .widgets import (Base, LINK, button, combo, hline, icon, label, put,
                      rect, vline)

# The two text panes of the main window use a LARGER font than the
# controls around them: the help text is set in Tahoma 9pt (12px, 14px
# line pitch) while every button, combo and label is Tahoma 8pt (11px).
# Both were measured off the native capture -- the help line "Double Ctrl
# => Show main window (with translation of selected text, if any)" is 418px
# wide there, which is Tahoma 9pt and not Tahoma 8pt (363px).
PANE_FONT = QFont("Tahoma", 9)

# The result pane starts with native's own "nothing came back" line.
EMPTY_RESULT = "No data returned (timeout while sending data)."

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


class MainWindow(Base):
    """The main window: nav row, source pane, splitter, tool row, result
    pane, provider strip."""

    ORIGIN, SIZE = (1, 31), (514, 391)
    WANTS_FOCUS = True

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("QTranslate")
        self._build()

    # ---------------------------------------------------------------- build
    def _build(self):
        app = self.app
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
        hline(self, 59, 4, 512)

        # ---- source pane (capture y 59..211) ----------------------------
        # A 1px #7e7e7e frame around a white edit. The text starts three
        # pixels inside the frame; the scrollbar is 17px wide and its
        # thumb 2px, at the far right of the pane.
        rect(self, 5, 61, 507, 150, "#ffffff", "srcbg")
        vline(self, 4, 59, 212)
        vline(self, 511, 60, 212)
        self.src = QTextEdit()
        self.src.setObjectName("pane")
        self.src.setAcceptRichText(False)
        self.src.setFrameShape(QTextEdit.NoFrame)
        # The ID selector beats the app stylesheet's plain "QTextEdit"
        # rule, which would otherwise put a 1px #7e7e7e border on the
        # pane -- native's pane has no border of its own, only the frame
        # drawn around it.
        self.src.setStyleSheet(
            "#pane{background:transparent;border:none;color:#000;"
            'font-family:"Tahoma";font-size:12px;'
            "QScrollBar:vertical{background:#f0f0f0;width:16px;margin:0;}"
            "QScrollBar::handle:vertical{background:%s;margin:0 7px;"
            "min-height:20px;}}" % THUMB)
        put(self, self.src, 7, 61, 504, 150)
        self.src.document().setDefaultFont(PANE_FONT)
        self.src.document().setDocumentMargin(0)
        self.src.setPlainText(default_source_text())
        icon(self, 451, 190, "ui_icons", "mic")
        icon(self, 473, 190, "ui_icons", "headphone")
        hline(self, 211, 4, 512)

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
        self.cmb_tgt = combo(self, 256, 217, 177, "Vietnamese", 21,
                             values=app.target_names())
        self.btn_go = button(self, 438, 217, 73, "Translate", 22)
        hline(self, 242, 4, 512)

        # ---- result pane (capture y 242..392) ----------------------------
        rect(self, 5, 244, 507, 148, "#ffffff", "resbg")
        vline(self, 4, 242, 393)
        vline(self, 511, 243, 393)
        self.out = QTextEdit()
        self.out.setObjectName("pane")
        self.out.setAcceptRichText(False)
        self.out.setFrameShape(QTextEdit.NoFrame)
        self.out.setReadOnly(True)
        self.out.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.out.setStyleSheet(
            "#pane{background:transparent;border:none;color:#000;"
            'font-family:"Tahoma";font-size:12px;}')
        put(self, self.out, 8, 245, 503, 147)
        self.out.document().setDefaultFont(PANE_FONT)
        self.out.document().setDocumentMargin(0)
        self.out.setPlainText(EMPTY_RESULT)
        icon(self, 473, 372, "ui_icons", "headphone")
        hline(self, 392, 4, 512)
        hline(self, 393, 5, 511, "#ffffff")

        # ---- the provider strip (capture y 397..418) --------------------
        self.tabs = []
        names = app.ordered_services()
        for i, name in enumerate(names):
            self.tabs.append(self._strip_button(i, name, len(names)))

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
        x = 4 + 56 * i
        w = 512 - x if i == total - 1 else 56
        b = QPushButton()
        b.setFocusPolicy(Qt.NoFocus)
        b.setObjectName("service")
        b.setProperty("selected", "true" if i == 0 else "false")
        put(self, b, x, 397, w, 22)
        b.setProperty("service", name)
        b.clicked.connect(lambda _c=False, n=name: self.app.switch_service(n))
        icon(self, x + 3, 400, "service_icons", STRIP_ICONS.get(name, name))
        lab = label(self, x + 27, 408, self._strip_label(name, w))
        lab.setFixedWidth(w - 30)
        lab.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return b

    def _strip_label(self, name, width):
        """Native cuts a service name that does not fit its button down
        to two characters and an ellipsis."""
        from qtranslate import config
        full = config.SERVICE_DISPLAY.get(
            {v: k for k, v in config.SERVICE_NAMES.items()}.get(name), name)
        if self.fontMetrics().horizontalAdvance(full) <= width - 31:
            return full
        return full[:2] + "..."

    def _nav_menu(self):
        m = QMenu(self)
        m.setStyleSheet(
            "QMenu{background:#f9f9f9;border:1px solid #e5e5e5;}"
            "QMenu::item{padding:3px 24px 3px 38px;}"
            "QMenu::item:selected{background:#e5e5e5;}")
        a = QAction("Dictionary", self)
        a.triggered.connect(self.app.open_dictionary)
        m.addAction(a)
        a = QAction("History", self)
        a.triggered.connect(self.app.open_history)
        m.addAction(a)
        a = QAction("Options", self)
        a.triggered.connect(self.app.open_options)
        m.addAction(a)
        m.exec(self.btn_nav.mapToGlobal(self.btn_nav.rect().bottomLeft()))

    def _service_clicked(self, _e):
        self.app.open_service_page()

    def _src_changed(self, text):
        self.app.set_source_by_name(text)

    def _tgt_changed(self, text):
        self.app.set_target_by_name(text)

    # ------------------------------------------------------------- painting
    def render(self, text: str, back: str = ""):
        """Fill the result pane (and the back-translation pane, when the
        port has one)."""
        self.out.setPlainText(text or "")
        if back:
            self.app.render_back(back)

    def set_service_title(self, name: str):
        self.lbl_service.setText(name)
