"""The PySide6 application: the window, wired to the port's core.

Everything that is NOT a pixel lives in the core already --
``qtranslate.engine`` orchestrates, ``qtranslate.registry`` dispatches,
``qtranslate.config`` persists, ``qtranslate.history`` exports. This
module is the shell around them: it owns the windows, the hotkeys and
the tray, and it holds the state (the current service, the language
pair, the history list) that native keeps in its own session fields.

The window itself is in ``qtranslate.qt.main_window``.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox

from qtranslate_style import apply_style

from .main_window import MainWindow, default_source_text


class QtApp:
    """The application's state and behaviour, independent of the widgets.

    The tkinter port keeps this state on ``App``; here it lives on
    ``QtApp`` so the window classes stay dumb.
    """

    def __init__(self, argv=None):
        self.qapp = QApplication.instance() or QApplication(argv or [])
        apply_style(self.qapp)
        self.service = "google"
        self.source = "auto"
        self.target = "vi"
        self.history = []
        self.multi_services = set()
        self.win = None

    # ------------------------------------------------------------- the core
    @staticmethod
    def _core():
        from qtranslate import config, engine, registry
        return config, engine, registry

    def _load_session(self):
        """Restore native's last session: the active service and the
        language pair (General.ActiveServices / LanguageFrom / To)."""
        config, _engine, registry = self._core()
        try:
            cfg = config.load()
        except Exception:
            cfg = {}
        general = cfg.get("General", {}) or {}
        try:
            ids = config.services_order(cfg)
        except Exception:
            ids = []
        names = [config.SERVICE_NAMES.get(i) for i in ids]
        names = [n for n in names if n in registry.TRANSLATORS]
        if names:
            self.service = names[0]
        try:
            from qtranslate.services.google_translate import SUPPORTED_LANGS
            table = list(SUPPORTED_LANGS)
            self.target = table[general.get("LanguageTo", 57)]
            self.source = table[general.get("LanguageFrom", 1)]
        except Exception:
            pass

    # ------------------------------------------------------------ the lists
    def service_title(self) -> str:
        config, _engine, _registry = self._core()
        return config.SERVICE_DISPLAY.get(self.service, self.service.title())

    def service_display(self, name: str) -> str:
        """The name native shows for a service (its Service.js header)."""
        config, _engine, _registry = self._core()
        for sid, key in config.SERVICE_NAMES.items():
            if key == name:
                return config.SERVICE_DISPLAY.get(sid, name)
        return name

    def dictionary_names(self):
        """The dictionary services, in native's order."""
        config, _engine, _registry = self._core()
        try:
            cfg = config.load()
            ids = list(cfg.get("DictionariesOrder")
                       or config.DEFAULT_DICTIONARIES_ORDER)
        except Exception:
            ids = config.DEFAULT_DICTIONARIES_ORDER
        return [config.DICT_DISPLAY.get(did, str(did)) for did in ids]

    def ordered_services(self):
        config, _engine, registry = self._core()
        try:
            cfg = config.load()
            ids = config.services_order(cfg)
            disabled = set(cfg.get("DisabledServices", []))
            names = [config.SERVICE_NAMES.get(i) for i in ids
                     if i not in disabled]
            return [n for n in names if n in registry.TRANSLATORS]
        except Exception:
            return ["google", "microsoft", "promt", "babylon", "yandex",
                    "youdao", "baidu", "naver", "deepl"]

    def source_names(self):
        return [self._display("auto")] + [
            self._display(c) for c in self._lang_codes()
            if c != "auto"]

    def target_names(self):
        return [self._display(c) for c in self._lang_codes() if c != "auto"]

    def _lang_codes(self):
        try:
            from qtranslate.services.google_translate import SUPPORTED_LANGS
            return [c for c in SUPPORTED_LANGS if isinstance(c, str)]
        except Exception:
            return ["auto", "en", "vi"]

    def _display(self, code):
        from qtranslate.app import LANG_DISPLAY
        return LANG_DISPLAY.get(code, code)

    def _code_of(self, name):
        from qtranslate.app import LANG_CODES
        return LANG_CODES.get(name, "auto")

    # ----------------------------------------------------------- behaviour
    def on_go(self):
        """Translate what is in the source pane and show the result."""
        _config, engine, _registry = self._core()
        text = self.win.src.toPlainText()
        res = engine.translate(self.service, text, self.target, self.source)
        self.win.render(res.text)
        if res.text:
            self.push_hist(self.service, text[:120], res.text[:200])

    def push_hist(self, svc, src, res):
        try:
            from qtranslate import config
            if not bool(config.load().get("General", {}).get(
                    "EnableHistory", True)):
                return
        except Exception:
            pass
        self.history.append((svc, src, res))

    def on_new(self):
        self.win.src.clear()

    def on_swap(self):
        a, b = self.win.cmb_src.currentText(), self.win.cmb_tgt.currentText()
        self.win.cmb_src.setCurrentText(b)
        self.win.cmb_tgt.setCurrentText(a)
        self.source, self.target = self._code_of(b), self._code_of(a)

    def set_source_by_name(self, name):
        self.source = self._code_of(name)

    def set_target_by_name(self, name):
        self.target = self._code_of(name)

    def switch_service(self, name):
        self.service = name
        self.win.set_service_title(self.service_title())

    def on_back(self):
        pass

    def on_forward(self):
        pass

    def open_dictionary(self):
        from .dictionary import DictionaryWindow
        self._dict = DictionaryWindow(self)
        self._dict.show()

    def open_history(self):
        from .history_window import HistoryWindow
        self._hist = HistoryWindow(self)
        self._hist.show()

    def open_options(self):
        from .options import OptionsDialog
        self._opts = OptionsDialog(self)
        self._opts.show()

    def open_service_page(self):
        self.open_options()

    def render_back(self, text):
        """The back-translation pane (1018) -- the port shows it in the
        result pane when it has one."""
        self.win.out.setPlainText(
            (self.win.out.toPlainText() or "") + "\n" + text)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = QtApp(argv)
    app._load_session()
    app.win = MainWindow(app)
    app.win.show()
    return app.qapp.exec()
