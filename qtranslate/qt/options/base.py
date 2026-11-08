"""The Options dialog (native DLG 154 and the nine page templates) on PySide6.

Every number here was MEASURED off the native captures in
``docs/review/native_screens``: 2135 (Internet), 2136 (Services), 2137
(Languages), 2138 (Appearance), 2139 (Exceptions), 2140 (Advanced), 2141
(Updates) and 2126 (Hotkeys, which is a 663x388 shot and so a different
size). The geometry is in ``qtranslate-pyside6-spec.md`` §5.

The behaviour is the port's: the same settings the tkinter front end
writes (``qtranslate.config``) are the ones this dialog shows, so the two
front ends agree on what the app is configured to do.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QTextEdit)

from qtranslate_style import ACCENT, DIM, FACE, TEXT, THUMB, WINDOW

from ..widgets import (Base, LINK, button, check, combo, field, group,
                       hline, icon, label, panel, put, rect, vline)

# The nine native pages in native's order, then the port's OWN page:
# Extensions is not a native page (native has no extension system), so
# it trails the captured order instead of sitting inside it.
SIDEBAR = ["Basics", "Hotkeys", "Internet", "Services", "Languages",
           "Appearance", "Exceptions", "Advanced", "Updates", "Extensions",
           "Comparison"]


class OptionsBase(Base):
    """The Options shell: the page list on the left, the page's body on
    the right, and the three buttons at the bottom.

    The shell is a SINGLE window: clicking a page in the list rebuilds
    the body in place rather than opening a new window. Each page module
    still owns its own ``build`` (its own numbers, its own file); the
    shell calls it with ``self`` after pointing the instance's ORIGIN
    and SIZE at the page's own.

    The shell's own chrome -- the sidebar panel, its rows, the rule and
    the three buttons -- is described by ``CHROME``, because the
    Hotkeys page's capture is a different size and its chrome sits at
    different coordinates. Everything is rebuilt on each swap, so a page
    with a different chrome gets it.
    """

    ORIGIN, SIZE = (1, 26), (644, 362)
    SEL = 0

    # The shell's chrome, in the page's own coordinates.
    #   panel      -- the bordered area the page list sits in
    #   row        -- x, y, width of one page-list row (the pitch is 13)
    #   face_row   -- the list view's empty first row (face colour)
    #   shadow_row -- the sunken frame's 1px white shadow
    #   rule       -- the etched line above the buttons: y, x0, x1
    #   buttons    -- each button's x, y, width, and whether it casts the
    #                 1px light shadow under itself
    CHROME = {
        "panel": (4, 29, 142, 324),
        "row": (7, 31, 139),
        "face_row": (5, 30, 140, 1),
        "shadow_row": (3, 353, 144, 1),
        "rule": (358, 3, 638),
        "buttons": {
            "OK": (403, 363, 73, True),
            "Cancel": (484, 363, 73, True),
            "Apply": (565, 363, 73, True),
        },
    }

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._page_name = SIDEBAR[self.SEL]
        self._rows = []
        # Draft semantics: every control writes through immediately, so
        # Cancel has to restore the file as it was when the dialog
        # opened -- otherwise "Cancel" would keep every edit.
        self._cfg_snapshot = cfg_load()
        self._cfg_committed = False
        # .tmp SettingsSearchController state: the query survives the
        # per-page chrome rebuilds, the index is built once per dialog.
        self._search_text = ""
        self._search_idx = None
        self._search_building = False
        try:
            from qtranslate.locale import ui_caption
            self.setWindowTitle(ui_caption(2, "Options"))
        except Exception:
            self.setWindowTitle("Options")
        self._show_page(self._page_name, first=True)

    def closeEvent(self, event):
        # The title-bar X is a Cancel too: edits are write-through, so
        # an uncommitted close restores the open-time snapshot. OK,
        # Apply and Cancel all set the flag before closing.
        if not getattr(self, "_cfg_committed", False):
            try:
                from qtranslate import config as _C
                _C.save(self._cfg_snapshot)
                notify_app(getattr(self, "app", None))
            except Exception:
                pass
        # An armed hotkey capture must not survive the dialog: the
        # recording flag lives on this shell and would keep swallowing
        # every bound chord after the window is gone.
        try:
            self._hk_recording = None
            self._hk_esc_armed = False
            self._hk_pending_double = None
            self._hk_chip_mods = 0
            self._hk_held_mods = 0
            self._hk_dc = None
        except Exception:
            pass
        super().closeEvent(event)

    # ---------------------------------------------------------------- shell
    def _build_chrome(self):
        """The sidebar, the rule and the three buttons, in this page's
        own coordinates."""
        ch = self.CHROME
        panel(self, *ch["panel"])
        face_row = ch.get("face_row")
        if face_row:
            rect(self, *face_row, FACE)
        shadow_row = ch.get("shadow_row")
        if shadow_row:
            rect(self, *shadow_row, WINDOW)
        # .tmp SettingsSearchController: a search field above the page
        # list; typing swaps the rows for matching settings, choosing a
        # hit navigates to its page and flashes the control. The index
        # is built lazily on the first query, exactly like upstream's
        # "pause on the first keystroke" tradeoff.
        rx, ry, rw = ch["row"]
        px, py, pw, ph = ch["panel"]
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search settings")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet("QLineEdit{padding:0 4px;}")
        put(self, self._search, rx, ry + 2, rw - 4, 16)
        # Chrome is rebuilt on every page swap; put the in-flight query
        # back so a hit-activation or an index build does not wipe it.
        self._search.blockSignals(True)
        self._search.setText(self._search_text)
        self._search.blockSignals(False)
        self._search.textChanged.connect(self._on_search)
        self._search.returnPressed.connect(self._search_enter)
        self._rows_y = ry + 20
        # The results list and the no-hits card share the rows' space;
        # both stay hidden until a query swaps them in (.tmp's
        # NAV_TREE/NAV_RESULTS/NAV_EMPTY cards).
        self._search_results = QListWidget(self)
        self._search_results.setStyleSheet(
            "QListWidget{border:none;background:transparent;}")
        put(self, self._search_results, rx, self._rows_y, rw,
            (py + ph) - self._rows_y)
        self._search_results.itemClicked.connect(
            lambda it: self._search_activate(it))
        self._search_results.hide()
        self._search_empty = QLabel(self)
        self._search_empty.setWordWrap(True)
        self._search_empty.setStyleSheet(
            "QLabel{color:%s;background:transparent;}" % DIM)
        put(self, self._search_empty, rx + 8, self._rows_y + 8,
            rw - 16, 60)
        self._search_empty.hide()
        self._rows = []
        for i, name in enumerate(SIDEBAR):
            # The page caption comes from the UI-language pack (Windows
            # section ids 10-18); port-owned pages have no id and keep
            # their English name.
            try:
                from qtranslate.locale import ui_page_caption
                shown = ui_page_caption(name)
            except Exception:
                shown = name
            q = QLabel(shown)
            q.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # No left padding: the text has to start one pixel inside the
            # row, the way native's does (MEASURED off the capture).
            put(self, q, rx, self._rows_y + 13 * i, rw, 13)
            # The caption may be localized; keep the English page name
            # for selection/highlight comparisons (_paint_rows).
            q.setProperty("qt_page", name)
            q.mousePressEvent = (lambda _e, n=name: self._goto(n))
            self._rows.append(q)
        ry, x0, x1 = ch["rule"]
        hline(self, ry, x0, x1)
        hline(self, ry + 1, x0, x1 - 1, WINDOW)
        self._btn_apply = None
        # The footer buttons' captions live in the pack's Windows
        # section (dialog 2 Controls: 1=OK, 2=Cancel, 1049=Apply).
        _BTN_IDS = {"OK": 1, "Cancel": 2, "Apply": 1049}
        for text, (bx, by, bw, shadow) in ch["buttons"].items():
            shown = text
            cid = _BTN_IDS.get(text)
            if cid:
                try:
                    from qtranslate.locale import ui_control_caption
                    shown = ui_control_caption(2, cid, text)
                except Exception:
                    pass
            b = button(self, bx, by, bw, shown, shadow=shadow)
            if text == "OK":
                b.clicked.connect(self._on_ok)
            elif text == "Cancel":
                b.clicked.connect(self._on_cancel)
            elif text == "Apply":
                b.clicked.connect(self._on_apply)
                self._btn_apply = b
                try:
                    b.setEnabled(True)
                except Exception:
                    pass
                try:
                    b.setStyleSheet("color:%s" % TEXT)
                except Exception:
                    pass

    def _paint_rows(self):
        """Repaint the sidebar highlight for the current page."""
        for q in self._rows:
            # Compare the stored page name, not the (possibly localized)
            # caption text -- under a non-English UI pack q.text() never
            # equals the English _page_name and no row would highlight.
            sel = q.property("qt_page") == self._page_name
            q.setStyleSheet("QLabel{background:%s;color:%s;}"
                            % (ACCENT if sel else "transparent",
                               "#ffffff" if sel else TEXT))

    def _clear(self):
        """Take down every widget the previous page built.

        The widgets are hidden and unparented, NOT deleted. A Qt widget
        that is deleted while a paint event for it is still queued is an
        access violation in the painter, and the Options dialog can
        have one queued for a page that is being swapped out. Hiding
        and unparenting removes them from the paint queue without
        destroying the object, and the next event loop pass frees them.
        """
        # A hotkey capture armed on the outgoing page must not leak:
        # _options_recording would keep swallowing every bound chord
        # until the user reopened Hotkeys and pressed a key.
        try:
            self._hk_recording = None
            self._hk_esc_armed = False
            self._hk_pending_double = None
            self._hk_chip_mods = 0
            self._hk_held_mods = 0
            self._hk_dc = None
        except Exception:
            pass
        for w in list(self.findChildren(object)):
            if w is self:
                continue
            try:
                w.hide()
                w.setParent(None)
            except Exception:
                pass

    def _show_page(self, page_name, first=False):
        """Rebuild a page's body in place, without a new window."""
        cls = PAGES.get(page_name)
        if cls is None:
            return
        if not first and page_name == self._page_name:
            return
        self._page_name = page_name
        self._clear()
        # The pages' numbers are written against each page class's own
        # ORIGIN/SIZE. Run the SAME build code with the shell as self,
        # after pointing the instance's ORIGIN/SIZE at the page's own.
        # The only page that differs is Hotkeys (ORIGIN (1,24) against
        # the shell's (1,26), SIZE 650 wide against 644): its rows are
        # shifted two screenshot pixels, and the window widens by 6.
        saved_origin, saved_size = self.ORIGIN, self.SIZE
        saved_chrome = self.CHROME
        try:
            self.ORIGIN, self.SIZE = cls.ORIGIN, cls.SIZE
            self.CHROME = cls.CHROME
            # The Languages page reads its column layout off the class
            # (BOX_X, COL_STEP, ...); same trick covers those.
            for attr in ("BOX_X", "BOX_Y", "COL_STEP", "ROW_STEP",
                         "TEXT_DX", "TEXT_DY"):
                if hasattr(cls, attr) and not hasattr(self, attr):
                    setattr(self, attr, getattr(cls, attr))
            if (self.width(), self.height()) != cls.SIZE:
                self.setFixedSize(*cls.SIZE)
            self._build_chrome()
            cls.build(self)
            self._localize_page()
        finally:
            self.ORIGIN, self.SIZE = saved_origin, saved_size
            self.CHROME = saved_chrome
        self._paint_rows()

    def _on_ok(self):
        self._cfg_committed = True
        try:
            self._on_apply()
        except Exception:
            pass
        self.close()

    def _on_cancel(self):
        """Restore the settings file to the dialog-open snapshot.

        Controls write through on every change, so without this the
        Cancel button was a plain close that kept every edit -- the
        opposite of what the button says.
        """
        try:
            from qtranslate import config as _C
            _C.save(self._cfg_snapshot)
        except Exception:
            pass
        self._cfg_committed = True
        self._notify_app()
        self.close()

    def _notify_app(self):
        try:
            app = getattr(self, "app", None)
            if app is not None and hasattr(app, "_load_session"):
                try:
                    app._load_session()
                except Exception:
                    pass
            if app is not None and app.win is not None:
                try:
                    # refresh combos if they exist
                    pass
                except Exception:
                    pass
        except Exception:
            pass

    def _on_apply(self):
        # Apply commits the file's current state: a later title-bar
        # close keeps it rather than restoring the open-time snapshot.
        self._cfg_committed = True
        try:
            from qtranslate import config as _C
            try:
                cfg = _C.load()
                _C.save(cfg)
            except Exception:
                pass
            # Notify app to reload if possible
            self._notify_app()
            try:
                notify_app(getattr(self, "app", None))
            except Exception:
                pass
        except Exception:
            pass

    def _localize_page(self):
        """Re-label this page's static texts in the UI language.

        The lang packs carry every native control caption under the
        page's dialog id (Windows section, ``Controls`` pairs, nested
        sublists included). Matching is by the ENGLISH text the port
        hardcoded: a label whose text equals a pack string is swapped
        for the translation; anything the pack does not know (the
        port's own rows, or strings the port re-worded like
        "Transparency (0 - 255)") stays English. Port-owned pages have
        no dialog id and are skipped entirely.
        """
        try:
            from qtranslate import locale as _L
            did = _L.PAGE_CAPTION_IDS.get(self._page_name)
            if not did:
                return
            en = _L.load_pack("English")
            ui = _L.ui_pack()
            if not en or not ui:
                return

            def _ctrls(pack):
                out = {}

                def rec(items):
                    for it in items or ():
                        if (isinstance(it, list) and len(it) == 2
                                and isinstance(it[0], int)
                                and isinstance(it[1], str)):
                            out[it[0]] = it[1]
                        elif isinstance(it, list):
                            rec(it)
                for m in pack.get("Windows", ()):
                    if isinstance(m, dict) and m.get("Id") == did:
                        rec(m.get("Controls"))
                return out

            ce, cu = _ctrls(en), _ctrls(ui)
            tr = {}
            for cid, en_text in ce.items():
                ui_text = cu.get(cid)
                if ui_text and ui_text != en_text:
                    tr[en_text] = ui_text
            if not tr:
                return
            from PySide6.QtWidgets import (QCheckBox, QGroupBox, QLabel)
            def _swap(w, t, new):
                w.setText(new)
                # The geometry was sized for the English string; grow
                # the widget (never shrink) so a longer translation is
                # not clipped. Group boxes keep their frame -- their
                # title is painted inside it.
                g = w.geometry()
                need = w.fontMetrics().horizontalAdvance(new) + 18
                if need > g.width():
                    w.setGeometry(g.x(), g.y(), need, g.height())

            for w in self.findChildren(QLabel):
                t = w.text()
                if t in tr:
                    _swap(w, t, tr[t])
            for w in self.findChildren(QCheckBox):
                t = w.text()
                if t in tr:
                    _swap(w, t, tr[t])
            for w in self.findChildren(QGroupBox):
                t = w.title()
                if t in tr:
                    w.setTitle(tr[t])
        except Exception:
            pass

    # ------------------------------------------------------- settings search
    # .tmp SettingsSearchController/Index: typing in the sidebar field
    # filters every page's settings; a hit navigates to its page and
    # flashes the control. Entries are collected by scanning the built
    # page -- the same "instrumented helpers" outcome upstream gets from
    # addCheckbox/addRow, without touching every page's build code.

    # Pages deliberately left unindexed, like upstream's PluginsPanel:
    # a manager for a runtime list, not a page of settings.
    _SEARCH_EXCLUDE = {"Extensions"}

    def _on_search(self, text=None):
        if text is None:
            try:
                text = self._search.text()
            except Exception:
                text = ""
        self._search_text = text or ""
        q = self._search_text.strip().lower()
        if not q:
            for r in self._rows:
                r.show()
            self._search_results.hide()
            self._search_empty.hide()
            return
        hits = [h for h in self._search_index()
                if self._search_match(h, q)]
        for r in self._rows:
            r.hide()
        if not hits:
            self._search_results.hide()
            # Naming the query back is the difference between "nothing
            # matched what you typed" and a sidebar that looks broken
            # (.tmp's NAV_EMPTY card does the same).
            self._search_empty.setText(
                'No settings match "%s"' % self._search_text.strip())
            self._search_empty.show()
            return
        self._search_empty.hide()
        self._search_results.clear()
        for h in hits:
            it = QListWidgetItem(h["label"])
            it.setData(Qt.UserRole, h)
            # The path line tells identically-labelled rows apart,
            # upstream's "page › section" subtitle.
            it.setToolTip("%s  ›  %s" % (h["page"], h["section"]
                                       or h["page"]))
            self._search_results.addItem(it)
        self._search_results.show()

    def _search_match(self, h, q):
        return any(q in str(h.get(k, "")).lower()
                   for k in ("label", "section", "hint", "page"))

    def _search_enter(self):
        """Down-from-field equivalent: Enter activates the first hit
        (.tmp's enterResults moves into the results list)."""
        if self._search_results.count() > 0:
            self._search_activate(self._search_results.item(0))

    def _search_index(self):
        """Build the index once per dialog: visit every searchable page
        through the same _show_page path navigation uses, then scan the
        built widgets. Upstream builds panels lazily for the same
        reason -- most pages do not exist until asked."""
        if self._search_idx is not None or self._search_building:
            return self._search_idx or []
        self._search_building = True
        idx = []
        cur = self._page_name
        try:
            for name in SIDEBAR:
                if name in self._SEARCH_EXCLUDE:
                    continue
                try:
                    self._show_page(name)
                    idx.extend(self._collect_search(name))
                except Exception:
                    continue
        finally:
            self._search_building = False
            try:
                self._show_page(cur)
            except Exception:
                pass
        self._search_idx = idx
        return idx

    def _collect_search(self, page):
        """Scan the freshly built page for setting rows, the way
        upstream's instrumented layout helpers record entries: every
        body QLabel that heads a row (something sits to its right on
        the same line) is an entry anchored on the label; checkboxes
        are entries by their own text; a control with no row label
        still registers when it carries a tooltip."""
        from PySide6.QtWidgets import (QComboBox, QLineEdit,
                                       QPlainTextEdit, QTextEdit)
        rule_y = self.CHROME["rule"][0]
        groups = []    # (top, bottom, title) in dialog coords
        labels = []    # (cy, right, x, y, text)
        controls = []  # (cy, x, y, widget)
        checks = []    # (x, y, text)
        for w in self.findChildren(object):
            if w is self._search or w is self._search_empty:
                continue
            is_lab = isinstance(w, QLabel)
            is_ctl = isinstance(w, (QCheckBox, QComboBox, QLineEdit,
                                    QTextEdit, QPlainTextEdit))
            if not is_lab and not is_ctl:
                continue
            try:
                if not w.isVisible():
                    continue
                pos = w.mapTo(self, QPoint(0, 0))
            except Exception:
                continue
            x, y = pos.x(), pos.y()
            # Sidebar chrome lives left of x=148; the footer buttons
            # sit below the rule. Everything between is page content.
            if x < 148 or y >= rule_y - 2:
                continue
            cy = y + w.height() // 2
            if isinstance(w, QCheckBox):
                t = (w.text() or "").strip()
                if t:
                    checks.append((x, y, t))
            elif is_lab:
                t = (w.text() or "").strip()
                if t:
                    labels.append((cy, x + w.width(), x, y, t))
            else:
                controls.append((cy, x, y, w))
        try:
            from PySide6.QtWidgets import QGroupBox
            for g in self.findChildren(QGroupBox):
                try:
                    pos = g.mapTo(self, QPoint(0, 0))
                    groups.append((pos.y(), pos.y() + g.height(),
                                   g.title() or ""))
                except Exception:
                    pass
        except Exception:
            pass

        def section_at(y):
            for top, bottom, title in groups:
                if top <= y < bottom and title:
                    return title
            return ""

        entries = []
        # Checkboxes carry their own caption (.tmp addCheckbox).
        for x, y, t in checks:
            entries.append({"page": page, "label": t,
                            "section": section_at(y), "hint": "",
                            "x": x, "y": y})
        # Row labels: a label heads a setting row when another widget
        # sits to its right on the same line -- the control it names,
        # or (Hotkeys' action rows) the hotkey caption beside it.
        for i, (lcy, lright, lx, ly, lt) in enumerate(labels):
            headed = False
            for ccy, cx, cy2, _w in controls:
                if abs(ccy - lcy) <= 12 and cx >= lright - 5 \
                        and cx - lright <= 350:
                    headed = True
                    break
            if not headed:
                for j, (ocy, oright, ox, _oy, _ot) in enumerate(labels):
                    if j == i:
                        continue
                    if abs(ocy - lcy) <= 12 and ox >= lright - 5 \
                            and ox - lright <= 350:
                        headed = True
                        break
            if headed:
                entries.append({"page": page, "label": lt,
                                "section": section_at(ly), "hint": "",
                                "x": lx, "y": ly})
        # Controls no label claimed (service cards and the like):
        # registerSearchEntry's port -- searchable only with a hint.
        for ccy, cx, cy, w in controls:
            partnered = any(
                abs(lcy - ccy) <= 12 and lright <= cx + 40
                for lcy, lright, _lx, _ly, _lt in labels)
            if partnered:
                continue
            try:
                hint = (w.toolTip() or "").strip()
            except Exception:
                hint = ""
            if hint:
                entries.append({"page": page, "label": hint,
                                "section": section_at(cy), "hint": hint,
                                "x": cx, "y": cy})
        seen = set()
        out = []
        for e in entries:
            key = (e["page"], e["label"], e["section"], e["x"], e["y"])
            if key not in seen:
                seen.add(key)
                out.append(e)
        return out

    def _search_activate(self, item):
        """A hit was chosen: go to its page and flash the control --
        upstream's anchor reveal, minus the scroll (pages fit whole)."""
        h = item.data(Qt.UserRole) or {}
        page, x, y = h.get("page"), h.get("x"), h.get("y")
        # Choosing a hit ends the search session, the way picking a
        # sidebar row does: the rows come back for the next navigation.
        self._search_text = ""
        try:
            self._search.setText("")
        except Exception:
            pass
        if page:
            self._goto(page)
        self._flash_anchor(x, y)

    def _flash_anchor(self, x, y):
        """Brief highlight on the widget at the hit's recorded spot so
        the eye lands on the setting the search named."""
        if x is None or y is None:
            return
        target = None
        for w in self.findChildren(object):
            try:
                pos = w.mapTo(self, QPoint(0, 0))
            except Exception:
                continue
            if abs(pos.x() - x) <= 3 and abs(pos.y() - y) <= 3:
                target = w
                break
        if target is None:
            return
        try:
            target.setStyleSheet(
                "%s;background:#cfe3ff;" % (target.styleSheet() or ""))
        except Exception:
            return
        QTimer.singleShot(900, lambda: self._unflash(target))

    def _unflash(self, w):
        try:
            ss = w.styleSheet() or ""
            w.setStyleSheet(ss.replace("background:#cfe3ff;", ""))
        except Exception:
            pass

    def _goto(self, page_name):
        """Switch to another page: rebuild the body in place."""
        self._show_page(page_name)

    def build(self):
        """The page's own body. Subclasses fill it in."""


# Filled in by qtranslate.qt.options.__init__ once every page class
# exists, so a page module does not have to import its eight siblings.
PAGES: dict = {}


# ------------------------------------------------------------- persistence
def cfg_load() -> dict:
    """Options.json as a dict (defaults on a fresh install)."""
    try:
        from qtranslate import config as _C
        return _C.load() or {}
    except Exception:
        return {}


def cfg_set(section: str, key: str, value) -> None:
    """Write one setting immediately (the Extensions page's own
    write-through rule: a control that shows a value saves it)."""
    try:
        from qtranslate import config as _C
        cfg = _C.load() or {}
        cfg.setdefault(section, {})[key] = value
        _C.save(cfg)
    except Exception:
        pass


def cfg_section(section: str) -> dict:
    return cfg_load().get(section, {}) or {}


def notify_app(app):
    """Tell the running app a setting changed (theme, hotkeys, panes)."""
    try:
        if app is not None and hasattr(app, "apply_theme"):
            app.apply_theme()
    except Exception:
        pass
    try:
        win = getattr(app, "win", None)
        if win is not None and hasattr(win, "apply_pane_visibility"):
            win.apply_pane_visibility()
    except Exception:
        pass
