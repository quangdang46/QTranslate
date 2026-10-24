"""The dictionary window on PySide6.

Every number here was MEASURED off ``docs/review/native_screens/2132.png``:
the geometry in ``qtranslate-pyside6-spec.md`` section 6, and the fonts,
the colours and the icon positions measured off the same capture. The
coordinates are the ones in the native capture; ``Base.ORIGIN`` says
where that capture's client area starts and ``put()`` converts them.

The behaviour is the port's: the same core (``qtranslate.registry``)
does the looking up, the same settings are persisted. This module is the
VIEW; it owns no dictionary logic of its own.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QTextEdit

from qtranslate_style import DIM

from .context_menus import build as build_menu
from .widgets import (Base, button, combo, field, icon, label, panel, put,
                      rect, vline)

# The dictionary services, in native's strip order, with the icon each
# one draws. The names are the port's own (``config.DICT_DISPLAY``); the
# icons were recovered from the installer payload and are pixel-identical
# to the ones native draws.
DICT_ICONS = {
    "Google Search": "google-search",
    "WordReference": "wordreference",
    "Babylon Dictionary": "babylon",
    "Wikipedia": "wikipedia",
    "Multitran": "multitran",
    "ImTranslator": "imtranslator",
    "Reverso": "reverso",
    "Urban Dictionary": "urban",
    "ABBYY Lingvo Live": "lingvo",
    "youdao": "youdao",
    "Oxford Learner Dictionary": "oxford",
}

# The strip's cell: 42 pixels at native's own 11 services, of which 1
# is the divider that separates it from the cell before, 3 the gap, 16
# the icon and 22 the label. At a different service count the cell
# width is COMPUTED (see _cell_width) so the strip always ends before
# the scrollbar: at 42px fixed, cell 11 ran under the scrollbar and the
# last cells were cut (the operator's screenshot 2166).
CELL = 42
STRIP_Y, STRIP_H = 307, 22
STRIP_X = 3


class _Cell(QFrame):
    """One cell of the service strip; clicking it selects that
    dictionary."""

    def __init__(self, window):
        super().__init__()
        self.window = window

    def mousePressEvent(self, event):
        self.window.select(self)


class DictionaryWindow(Base):
    """The dictionary window: the language row, the result area and the
    strip of dictionary services along the bottom."""

    ORIGIN, SIZE = (1, 31), (474, 301)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Dictionary")
        self._build()

    # ---------------------------------------------------------------- build
    def _build(self):
        app = self.app
        # ---- the top row (capture y 31..55) ----------------------------
        # The language combo, the white box that holds the two navigation
        # arrows on the left and the search and history buttons on the
        # right, and the ':' menu.
        self.cmb_lang = combo(self, 4, 35, 154, "English", 19,
                              values=app.source_names())
        # Native's combo puts its text eight pixels inside the frame, not
        # the five the shared stylesheet gives every other combo.
        self.cmb_lang.setStyleSheet("QComboBox{padding-left:7px;}")
        panel(self, 163, 34, 283, 22, "navbox")
        self.btn_prev = button(self, 168, 38, 12, "")
        self.btn_next = button(self, 180, 38, 12, "")
        for b in (self.btn_prev, self.btn_next):
            b.setStyleSheet("QPushButton{border:none;background:transparent;}")
        for x, arrow in ((168, "◀"), (180, "▶")):
            lab = label(self, x, 45, arrow, color=DIM)
            lab.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # The search field: native's row is [language v] [<][>] [field]
        # [magnifier] [clock] [menu], and the white box the field sits
        # in is the navbox panel drawn above.
        self.inp = field(self, 196, 36, 205, 18, "")
        self.inp.returnPressed.connect(self.do_search)
        self.lbl_search = icon(self, 407, 37, "ui_icons", "search")
        self.lbl_search.mousePressEvent = self._search_clicked
        icon(self, 427, 37, "ui_icons", "history")
        self.btn_menu = button(self, 452, 37, 16, "")
        self.btn_menu.setObjectName("flat")
        self.btn_menu.clicked.connect(self.show_header_menu)
        icon(self, 452, 37, "ui_icons", "menu")

        # ---- the result area (capture y 56..306) ------------------------
        # Native leaves it empty, and it is the window's own face colour
        # -- not a white pane -- with the scrollbar down its right side.
        vline(self, 445, 56, 306)
        rect(self, 457, 56, 6, 250, "#f9f9f9", "sbtrack")
        label(self, 460, 55, "⌃", color=DIM)
        label(self, 460, 248, "⌄", color=DIM)
        self.out = QTextEdit()
        self.out.setAcceptRichText(False)
        self.out.setFrameShape(QTextEdit.NoFrame)
        self.out.setReadOnly(True)
        self.out.setStyleSheet("QTextEdit{background:transparent;border:none;}")
        put(self, self.out, 1, 56, 444, 250)

        # ---- the service strip (capture y 307..328) ---------------------
        services = self._services()
        # Native 2132: the strip runs the FULL window width -- the last
        # cell stretches to the right edge, it does not stop before the
        # result pane's scrollbar (which sits above the strip, not
        # beside it). Even width from the count, the last one takes the
        # remainder.
        n = max(1, len(services))
        cell_w = (474 - 1 - STRIP_X) // n
        self.strip = []
        for i, name in enumerate(services):
            w = cell_w + (474 - 1 - STRIP_X - cell_w * n if i == n - 1
                          else 0)
            self.strip.append(self._strip_cell(i, name, w))
        self.select(self.strip[0] if self.strip else None)

    # ------------------------------------------------------------- helpers
    def _services(self):
        """The dictionary services, in the order the port keeps them."""
        from qtranslate import config
        try:
            cfg = config.load()
            ids = cfg.get("DictionariesOrder") or config.DEFAULT_DICTIONARIES_ORDER
        except Exception:
            ids = config.DEFAULT_DICTIONARIES_ORDER
        return [config.DICT_DISPLAY.get(i, "") for i in ids
                if i in config.DICT_DISPLAY]

    def _strip_cell(self, i, name, cell_w=CELL):
        """One cell of the bottom strip: a divider, the service's own
        icon, and its name cut to the first letter and an ellipsis."""
        x = STRIP_X + cell_w * i
        cell = _Cell(self)
        cell.setObjectName("cell")
        cell.setProperty("service", DICT_ICONS.get(name, ""))
        cell.setProperty("display", name)
        cell.setStyleSheet("QFrame#cell{background:#dadada;border:none;}")
        put(self, cell, x + 1, STRIP_Y + 1, cell_w - 1, STRIP_H - 2)
        vline(self, x, STRIP_Y, STRIP_Y + STRIP_H)
        icon(self, x + 4, STRIP_Y + 3, "dict_icons", DICT_ICONS.get(name, ""))
        lab = QLabel(name[:1] + "...")
        lab.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lab.setStyleSheet("QLabel{background:transparent;color:#000000;}")
        lab.setFixedSize(14, 16)
        lab.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        put(self, lab, x + 28, STRIP_Y + 3, 14, 16)
        return cell

    # ------------------------------------------------------------ behaviour
    def select(self, cell):
        """Make one cell the selected dictionary.

        Native 2132: the SELECTED cell is the light one (white against
        the grey strip), not the darker -- the port had it inverted.
        """
        for other in self.strip:
            other.setStyleSheet("QFrame#cell{background:#dadada;border:none;}")
        if cell is None:
            return
        cell.setStyleSheet("QFrame#cell{background:#ffffff;border:none;}")
        self.service = cell.property("service")
        self.service_display = cell.property("display")

    # ------------------------------------------------------------ the search
    def _search_clicked(self, _e=None):
        self.do_search()

    def selected_service(self):
        """The display name of the selected strip cell."""
        return getattr(self, "service_display", "")

    def do_search(self):
        """Look the field's word up, the way native's magnifier does.

        The lookup is Core (``qtranslate.dictionary_search``): it
        resolves the dictionary language, asks the selected service and
        renders the cards. It runs on a worker thread -- the services
        are network calls -- and the answer comes back on the UI
        thread.
        """
        word = self.inp.text().strip()
        if not word:
            return
        from qtranslate import dictionary_search as DS
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            exact = bool(cfg.get("DictionaryExactSearch", True))
        except Exception:
            cfg, exact = {}, True
        services = [self.selected_service()] if self.selected_service() \
            else None
        target = getattr(self.app, "target", "en")
        self.out.setPlainText("querying %d dictionaries..."
                              % (len(services) if services else 11))

        def work():
            try:
                cards, summary = DS.search(word, exact=exact,
                                           services=services, target=target,
                                           cfg=cfg)
            except Exception as exc:            # noqa: BLE001
                cards, summary = [], "[error] %s" % exc
            self.app._on_ui(lambda: self.out.setPlainText(summary))

        threading.Thread(target=work, daemon=True).start()

    def lookup(self, word, src="auto", tgt="en"):
        """Look ``word`` up with the selected dictionary and show it."""
        from qtranslate import registry
        fn = registry.DICTS.get(self.service)
        if not fn or not word:
            return ""
        try:
            res = fn(word, src, tgt)
        except Exception:
            return ""
        text = getattr(res, "text", res) or ""
        self.out.setPlainText(str(text))
        return str(text)

    # ------------------------------------------------------------ the ':' menu
    def show_header_menu(self):
        """Native's menu 7: the dictionary window's own ':' button menu.

        It has exactly one item -- "Show Full History" -- which opens
        the History window, because that is what the native menu carries.
        """
        m = build_menu(
            self, self.app, "dict_header", 7,
            [(10, "Show Full History", self.app.open_history)])
        m.exec(self.btn_menu.mapToGlobal(
            self.btn_menu.rect().bottomLeft()))

    # ------------------------------------------------- the strip's row menu
    def show_strip_menu(self, gpos=None):
        """Native's menu 8: the dictionary strip's own row menu.

        "Show info" reports what the selected cell IS; "Remove
        dictionary" takes it out of ``DictionariesOrder``, which is the
        same setting the Services page writes. Native puts this menu on
        the active strip row, which is why it hangs off the strip rather
        than the window.
        """
        m = build_menu(self, self.app, "dict_header", 8, [
            (10, "Show info", self._show_info),
            (20, "Remove dictionary", self._remove_dictionary),
        ])
        anchor = self.strip[0] if self.strip else self.btn_menu
        m.exec(gpos if gpos is not None else anchor.mapToGlobal(
            anchor.rect().bottomLeft()))

    def _selected_id(self):
        """The ``DictionariesOrder`` id of the selected cell."""
        name = self.selected_service()
        for did, display in self.app._core()[0].DICT_DISPLAY.items():
            if display == name:
                return did
        return None

    def _show_info(self):
        from PySide6.QtWidgets import QMessageBox
        name = self.selected_service() or "(none selected)"
        QMessageBox.information(self, "Dictionary", name)

    def _remove_dictionary(self):
        """Drop the selected cell from ``DictionariesOrder``."""
        did = self._selected_id()
        if did is None:
            return
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            order = list(cfg.get("DictionariesOrder")
                         or _C.DEFAULT_DICTIONARIES_ORDER)
            cfg["DictionariesOrder"] = [i for i in order if i != did]
            _C.save(cfg)
        except Exception:
            return
        # Rebuild the strip so the removed cell disappears now, not at
        # the next start.
        for cell in self.strip:
            cell.setParent(None)
            cell.deleteLater()
        self.strip = []
        for i, name in enumerate(self._services()):
            self.strip.append(self._strip_cell(i, name))
        if self.strip:
            self.select(self.strip[0])

    # -------------------------------------------------- right-click the strip
    def contextMenuEvent(self, event):          # noqa: N802 (Qt name)
        pos = event.pos()
        if pos.y() >= STRIP_Y:
            self.show_strip_menu(event.globalPos())
            return
        super().contextMenuEvent(event)
