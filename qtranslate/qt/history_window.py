"""The History window (native DLG 178) on PySide6.

The geometry is measured off ``docs/review/native_screens/2133.png`` (the
real QTranslate 6.10.0 history window, 476x320, client area 474x288 at
``(1, 31)``):

  * a search field across the top, x 4..471, y 34..55, with a small
    clear button at its right end (x 456..465, y 40..49);
  * a white list panel under it, x 4..471, y 60..287, in which each
    entry is a FACE-coloured header row (a star and the source text)
    with the translation on an indented white row under it;
  * the bottom row: Clear, Save as..., the star toggle, and OK.

Right-clicking an entry opens native's own history-item menu I6
(FUN_004287B6, builder FUN_00404055 LoadMenuW): Open, Copy text, Copy
translation, Delete, Listen to text. Each handler is the same operation
the window (or the app) already performs elsewhere, so no new semantics
are invented -- only the menu entry point.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from qtranslate_style import FACE

from .widgets import Base, button, icon, label, panel, put, rect

# The menu's labels come from the shipped locale packs (menu 3, the
# history item menu) with native's strings as the fallback for an
# untranslated id.
HIST_MENU = (("open", "Open", 10),
             ("copy_tr", "Copy translation", 20),
             ("copy_src", "Copy text", 30),
             ("listen", "Listen to text", 40),
             ("delete", "Delete", 50))


def menu_text(pack, menu_id, idx, default) -> str:
    try:
        from qtranslate.locale import menu_labels
        for k, v in menu_labels(pack, menu_id):
            if isinstance(k, int) and k == idx:
                return v
    except Exception:
        pass
    return default


class HistoryWindow(Base):
    """The History window: the search field, the list, the bottom row."""

    ORIGIN, SIZE = (1, 31), (474, 288)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("History")
        self._sel = -1
        self._build()

    def _build(self):
        # The search field, and the small clear button at its right.
        field = self._field()
        self.btn_clear_search = button(self, 456, 40, 10, "")
        self.btn_clear_search.setObjectName("flat")

        # The list panel. Custom context menu: the I6 entry menu.
        self.list = panel(self, 4, 60, 468, 228)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(
            self._entry_menu_requested)
        self._fill()

        # The bottom row.
        self.btn_clear = button(self, 5, 294, 71, "Clear", 21)
        self.btn_save = button(self, 84, 294, 107, "Save as...", 21)
        self.btn_star = button(self, 199, 294, 19, "", 21)
        self.btn_ok = button(self, 399, 294, 71, "OK", 21)

        self.btn_ok.clicked.connect(self.close)
        self.btn_clear.clicked.connect(self._clear)

    # ------------------------------------------------------- the I6 menu
    def _entry_menu_requested(self, gpos):
        """Right-click in the list.

        On an ENTRY: native's I6 menu (menu id 6), with the five entries
        enabled only on a row that exists. On EMPTY space: native's
        window menu (menu id 9) -- Clear history, Show services pane,
        Exact search, Options. They are two different native menus and
        the port showed only the first, so menu 9 had no host at all.
        """
        try:
            y = self.list.mapFromGlobal(gpos).y()
        except Exception:
            return
        idx = self._entry_at(y)
        if not (0 <= idx < len(self.app.history)):
            self._window_menu(gpos)
            return
        ent = list(self.app.history)[idx]
        m = QMenu(self)
        try:
            from qtranslate.locale import load_pack
            pack = load_pack("English")
        except Exception:
            pack = {}
        ops = {"open": self._open_entry, "copy_tr": self._copy_tr,
               "copy_src": self._copy_src, "listen": self._listen,
               "delete": self._delete}
        for key, default, mid in HIST_MENU:
            text = menu_text(pack, 3, mid, default)
            act = QAction(text, m)
            act.setEnabled(ent is not None)
            act.triggered.connect(lambda _c=False, k=key, i=idx, e=ent:
                                  ops[k](i, e))
            m.addAction(act)
        # The history item menu is native's menu id 6 (ui_slots
        # "history_ctx").
        from .widgets import extension_menu_entries
        entries = extension_menu_entries(self, self.app, "history_ctx")
        if entries:
            m.addSeparator()
        for label, contrib in entries:
            act = QAction(label, m)
            act.triggered.connect(
                lambda _c=False, f=contrib: self.app.run_ui_contribution(f))
            m.addAction(act)
        m.exec(gpos)

    # the five operations (each is the same op elsewhere in the window)
    def _open_entry(self, idx, ent):
        """Open = native's load_sel: into the main window's panes."""
        try:
            _svc, src, _res = ent[:3]
            if getattr(self.app, "win", None) is not None:
                self.app.win.src.setPlainText(src)
        except Exception:
            pass

    def _copy(self, text):
        try:
            from PySide6.QtWidgets import QApplication as _QA
            _QA.clipboard().setText((text or "").strip())
        except Exception:
            pass

    def _copy_src(self, idx, ent):
        self._copy(ent[1])

    def _copy_tr(self, idx, ent):
        self._copy(ent[2])

    def _delete(self, idx, ent):
        try:
            del self.app.history[idx]
            self._fill()
        except Exception:
            pass

    def _listen(self, idx, ent):
        try:
            _svc, src, _res = ent[:3]
            import threading as _th
            _th.Thread(target=self._speak, args=(src,), daemon=True).start()
        except Exception:
            pass

    def _speak(self, text):
        try:
            from qtranslate import config as _C
            slow = bool(_C.load().get("Advanced", {})
                        .get("EnableSlowerListening", False))
        except Exception:
            slow = False
        try:
            from qtranslate.player import play_text
            play_text(text[:500], getattr(self.app, "target", "vi") or "vi",
                      slow=slow)
        except Exception:
            pass
    # ------------------------------------------------------------ the rest

    def _entry_at(self, y):
        """The history index at the list's ``y`` -- ``_fill``'s own
        arithmetic (rows start at 65, one row per 30px), so the menu
        targets the row the user right-clicked. -1 past the last."""
        try:
            idx = (int(y) - 65) // 30
        except Exception:
            return -1
        if idx < 0:
            return -1
        return idx if idx < len(self.app.history) else -1

    def _field(self):
        from PySide6.QtWidgets import QLineEdit
        e = QLineEdit()
        e.setStyleSheet("QLineEdit{background:#fff;border:none;}")
        put(self, e, 4, 34, 467, 21)
        return e

    def _fill(self):
        """The list: one header row per entry, with its translation
        under it."""
        y = 66
        for entry in list(self.app.history)[:12]:
            service, src, res = entry[:3]
            rect(self.list, 5, y - 1, 466, 13, FACE, "histrow")
            icon(self.list, 8, y - 3, "ui_icons", "star")
            label(self.list, 31, y + 5, src[:60])
            icon(self.list, 27, y + 15, "service_icons", service)
            label(self.list, 51, y + 20, res[:60])
            y += 30

    def _clear(self):
        self.app.history = []
        self._fill()

    # ------------------------------------------------- native's menu 9
    def _window_menu(self, gpos=None):
        """Native's window menu (id 9), shown on empty list space.

        Clear history is the window's own Clear; Show services pane,
        Exact search and Options are the native entries, with the two
        settings-backed ones writing the same keys the Settings pages
        write so the menu is not a decorative copy.
        """
        from .context_menus import build as build_menu
        m = build_menu(self, self.app, "history_menu", 9, [
            (10, "Clear history", self._clear_and_reload),
            (20, "Show services pane", self._toggle_services_pane),
            (30, "Exact search", self._toggle_exact_search),
            (40, "Options", lambda: self.app.open_options("Advanced")),
        ])
        m.exec(gpos if gpos is not None else self.mapToGlobal(
            self.list.rect().center()))

    def _clear_and_reload(self):
        self._clear()
        self.app.history = []

    def _toggle_services_pane(self):
        """Flip native's ShowServicesPane setting and apply it."""
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            general = cfg.setdefault("General", {})
            general["ShowServicesPane"] = not bool(
                general.get("ShowServicesPane", True))
            _C.save(cfg)
            win = getattr(self.app, "win", None)
            if win is not None and hasattr(win, "apply_pane_visibility"):
                win.apply_pane_visibility()
        except Exception:
            pass

    def _toggle_exact_search(self):
        """Flip native's DictionaryExactSearch setting."""
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            cfg["DictionaryExactSearch"] = not bool(
                cfg.get("DictionaryExactSearch", True))
            _C.save(cfg)
        except Exception:
            pass
