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
        self.tray = None
        self.hotkeys_on = True
        self.hotkeys = []
        self.mouse_mode = "Show icon"

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

    # ------------------------------------------------- the tray's actions
    def show_main_window(self):
        """Bring the main window up, the way the tray's first item does."""
        if self.win is not None:
            self.win.show()
            self.win.raise_()
            self.win.activateWindow()

    def open_ocr(self):
        """Native's "Text recognition": pick a region of the screen and
        OCR it. The capture and the OCR call are the core's; only the
        region picker belongs to the front end."""
        from .ocr_pick import RegionPicker, grab_rect

        def _picked(rect):
            if rect is None:
                return
            try:
                data = grab_rect(rect)
            except Exception as exc:            # noqa: BLE001
                self.win.render("[ocr error] %s" % exc)
                return
            self.ocr_bytes(data)

        picker, _result = RegionPicker.pick()
        picker._picked = _picked

    def ocr_bytes(self, data: bytes):
        """OCR an image and show the text in the result pane."""
        config, _engine, _registry = self._core()
        try:
            cfg = config.load()
        except Exception:
            cfg = {}
        key = (cfg.get("Advanced", {}) or {}).get("OcrApiKey", "") or "helloworld"
        index = (cfg.get("Ocr", {}) or {}).get("OcrLanguage", 17)
        try:
            from qtranslate.services.google_translate import SUPPORTED_LANGS
            table = list(SUPPORTED_LANGS)
        except Exception:
            table = []
        code = table[index] if 0 <= index < len(table) else "en"
        try:
            from qtranslate.services.ocr import ocr_text
            text = ocr_text(data, api_key=key, lang=code)
        except Exception as exc:                # noqa: BLE001
            self.win.render("[ocr error] %s" % exc)
            return
        self.win.render(text)

    def open_keyboard(self):
        from .keyboard import KeyboardWindow
        self._kbd = KeyboardWindow(self)
        self._kbd.show()

    def show_about(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self.win, "About QTranslate",
                          "QTranslate 6.10.0\n\nA clean-room Python port.")

    def set_hotkeys_enabled(self, on):
        """The tray's checkable item: the hotkeys are UNREGISTERED and
        the setting is written, the way native's does it."""
        self.hotkeys_on = bool(on)
        try:
            import keyboard
            for _name, _combo in list(self.hotkeys):
                try:
                    keyboard.remove_hotkey(_combo)
                except Exception:
                    pass
            self.hotkeys = []
        except Exception:
            pass
        if self.hotkeys_on:
            try:
                from .hotkeys import install
                self.hotkeys = install(self)
            except Exception:
                self.hotkeys = []
        config, _engine, _registry = self._core()
        try:
            cfg = config.load()
            cfg.setdefault("HotKeys", {})["EnableHotKeys"] = bool(on)
            config.save(cfg)
        except Exception:
            pass

    def set_mouse_mode(self, mode):
        self.mouse_mode = mode

    def quit(self):
        self.qapp.quit()

    # ------------------------------------------------------- the hotkeys
    def _clipboard_text(self) -> str:
        try:
            import pyperclip
            return (pyperclip.paste() or "").strip()
        except Exception:
            return ""

    def _translate(self, text: str):
        """Translate a piece of text with the current service and pair."""
        from qtranslate import engine
        res = engine.translate(self.service, text[:5000], self.target,
                               self.source)
        return res

    def hotkey_popup(self):
        """Native's Ctrl+Q: translate what is on the clipboard and show
        it in the popup."""
        text = self._clipboard_text()
        if not text:
            return
        res = self._translate(text)
        self.win.src.setPlainText(text[:2000])
        self.win.render(res.text)
        self.push_hist(self.service, text[:120], res.text[:200])
        try:
            from .popup import PopupWindow
            self._popup = PopupWindow(self)
            self._popup.set_text(text[:300], res.text)
            self._popup.show()
        except Exception:
            pass

    def hotkey_translate_clipboard(self):
        text = self._clipboard_text()
        if not text:
            return
        res = self._translate(text)
        self.win.src.setPlainText(text[:2000])
        self.win.render(res.text)
        self.push_hist(self.service, text[:120], res.text[:200])

    def hotkey_replace_selection(self):
        """Native's Alt+W: translate the selection and type it back."""
        text = self._clipboard_text()
        if not text:
            return
        res = self._translate(text)
        try:
            import keyboard
            keyboard.write(res.text)
        except Exception:
            pass
        self.push_hist(self.service, text[:120], res.text[:200])

    def hotkey_copy_translation(self):
        """Copy the result pane's text to the clipboard."""
        text = self.win.out.toPlainText() if self.win else ""
        if not text:
            return
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception:
            pass

    def hotkey_dictionary_clipboard(self):
        text = self._clipboard_text()
        if text:
            self._dict_word = text
        self.open_dictionary()

    def hotkey_listen_text(self):
        """Speak the text that is on the clipboard."""
        text = self._clipboard_text()
        if text:
            self._speak(text)

    def hotkey_listen_translation(self):
        text = self.win.out.toPlainText() if self.win else ""
        if text:
            self._speak(text)

    def _speak(self, text: str):
        try:
            from qtranslate import player
            player.play_text(text, self.target)
        except Exception:
            pass

    def hotkey_convert_layout(self):
        """Native's "fix the layout" hotkey: the wrong text direction is
        corrected before the translation goes out."""
        try:
            from qtranslate import layout
            text = self._clipboard_text()
            fixed = layout.convert_layout(text)
            if fixed and fixed != text:
                import pyperclip
                pyperclip.copy(fixed)
        except Exception:
            pass

    def hotkey_speech_input(self):
        """The offline SAPI recogniser, when it is available.

        Native's chain is mic -> FLAC -> Google's full-duplex speech
        URL, and that API is retired, so the live path is
        dead:native-unavailable (the RE artifact for it is
        `qtranslate/speech_input.py`). The offline fallback is the
        Windows SAPI shared recogniser, which needs comtypes; without
        it the app says so rather than failing silently.
        """
        try:
            import comtypes.client  # type: ignore
        except ImportError:
            self.win.render("[speech input -- needs: pip install comtypes "
                            "(offline SAPI) -- Google voice API key retired]")
            return
        try:
            reco = comtypes.client.CreateObject("SAPI.SpSharedRecognizer")
            context = reco.CreateRecoContext()
            grammar = context.CreateGrammar()
            grammar.DictationLoad("", 0)
            grammar.DictationSetState(1)
            grammar.DictationRegister("text", 2)
            text = []
            while True:
                result = context.RecoState.GetResult(
                    0xFFFFFFFF, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                if result is not None and result.Hypothesis:
                    text.append(result.Hypothesis)
                    break
            if text:
                self.win.src.setPlainText(" ".join(text))
        except Exception as exc:            # noqa: BLE001
            self.win.render("[speech input error] %s" % exc)

    def hotkey_switch_mouse_mode(self):
        """Cycle the mouse mode, the way native's tray item does."""
        from .tray import MOUSE_MODES
        try:
            i = MOUSE_MODES.index(self.mouse_mode)
        except ValueError:
            i = 0
        mode = MOUSE_MODES[(i + 1) % len(MOUSE_MODES)]
        self.set_mouse_mode(mode)
        if self.tray is not None:
            self.tray.set_mouse_mode(mode)

    def render_back(self, text):
        """The back-translation pane (1018) -- the port shows it in the
        result pane when it has one."""
        self.win.out.setPlainText(
            (self.win.out.toPlainText() or "") + "\n" + text)


def _frozen_selftest():
    """``--selftest``: prove the frozen import graph, open no window.

    The tkinter front end has one of these (`qtranslate.app._frozen_selftest`)
    and `tools/build_bundle.py` runs it against the built `.exe`. This is
    the same probe for the PySide6 front end: the failure it exists to
    catch is a module PyInstaller's Analysis never followed, which would
    otherwise show up as a crash in front of the user.

    Returns the process exit code; raises nothing. Prints one machine
    marker line (``SELFTEST ...``) so a tool can parse it.
    """
    checks = []

    def _ck(name, fn):
        try:
            fn()
            checks.append((name, True, ""))
        except Exception as exc:            # noqa: BLE001 -- report, don't die
            checks.append((name, False, "%s: %s"
                           % (type(exc).__name__, exc)))

    _ck("qtranslate.qt.app", lambda: __import__("qtranslate.qt.app"))
    _ck("qtranslate_style", lambda: __import__("qtranslate_style"))

    # Every window module, so a page that PyInstaller did not follow is
    # caught here rather than when the user opens it.
    for _mod in ("main_window", "widgets", "icons", "options",
                 "dictionary", "history_window", "keyboard", "popup",
                 "tray", "ocr_pick", "hotkeys"):
        _ck("import qtranslate.qt.%s" % _mod,
            lambda m=_mod: __import__("qtranslate.qt." + m, fromlist=["*"]))

    # The Qt toolkit itself, and the asset files the icons come from.
    for _dep in ("PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"):
        _ck("bundled dep %s" % _dep, lambda d=_dep: __import__(d))

    def _assets():
        # A QPixmap cannot be built before a QApplication exists -- Qt
        # aborts the process rather than raising -- so the application
        # is created here. It opens no window: the selftest never calls
        # show() on anything.
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            QApplication([])
        from qtranslate.qt import icons
        pm = icons.pixmap("ui_icons", "mic")
        if pm.isNull():
            raise AssertionError("the mic icon did not load from the bundle")
    _ck("the recovered icons load", _assets)

    bad = [(n, d) for n, ok, d in checks if not ok]
    print("SELFTEST %s %d/%d" % ("PASS" if not bad else "FAIL",
                                 len(checks) - len(bad), len(checks)))
    for name, ok, detail in checks:
        if not ok:
            print("  MISSING %s -- %s" % (name, detail))
    return 0 if not bad else 1


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv[1:]:
        return _frozen_selftest()
    app = QtApp(argv)
    app._load_session()
    app.win = MainWindow(app)
    app.win.show()
    # The tray: native is a tray app, and its tray menu is the real
    # taskbar menu (the spec's rule 6 -- Qt draws it, not us).
    try:
        from .tray import Tray
        app.tray = Tray(app)
        app.tray.show()
    except Exception:
        # A machine with no system tray must not stop the app from
        # starting; the main window is the whole of the UI then.
        app.tray = None
    # The global hotkeys, the ones the settings file binds. A machine
    # without the `keyboard` package simply has none.
    try:
        from .hotkeys import install
        app.hotkeys = install(app)
    except Exception:
        app.hotkeys = []
    return app.qapp.exec()
