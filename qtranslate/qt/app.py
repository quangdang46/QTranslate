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

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox

from qtranslate.platforms import keyboard_module
from qtranslate_style import apply_style

from .main_window import MainWindow, default_source_text


class _MouseBridge(QObject):
    """Hands the mouse hook's work over to the UI thread.

    The Win32 low-level mouse hook's callback runs on the thread that
    installed it, and the port installs it on a worker so the proc
    returns fast. The panes and the popup belong to the UI thread, so
    the translation is handed over by a QUEUED signal: the slot below
    runs in the thread that owns this object.
    """

    translated = Signal(str, str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.translated.connect(self.show)

    @Slot(str, str)
    def show(self, text, result):
        self.app.show_translation(text, result)


class _UiInvoker(QObject):
    """Runs a callable on the UI thread, from any other thread.

    The ``keyboard`` package's global hotkeys fire on ITS OWN listener
    thread, not Qt's. A hotkey handler that touches a widget from there
    (``setPlainText``, opening a window) is a cross-thread access to Qt
    objects, which Qt does not guard against -- it crashes the process
    outright (an access violation) rather than raising a catchable
    exception. ``invoke`` is a QUEUED signal, so connecting to a slot on
    an object that lives on the UI thread (this one, built in
    ``QtApp.__init__``, before any thread but the UI one exists) marshals
    the call there, the same pattern ``_MouseBridge`` already uses for
    the mouse hook.
    """

    invoke = Signal(object)

    def __init__(self):
        super().__init__()
        self.invoke.connect(self._run)

    @Slot(object)
    def _run(self, fn):
        try:
            fn()
        except Exception:
            pass


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
        self.argv = list(argv or [])
        self.history = []
        self.multi_services = set()
        self.win = None
        self.tray = None
        self.hotkeys_on = True
        self.hotkeys = []
        self.mouse_mode = "Show icon"
        self._mouse_hook = False
        self._bridge = _MouseBridge(self)
        self._ui = _UiInvoker()
        # The extension manager, once the user extensions are loaded.
        # It carries the UI and theme contributions.
        self.ext_manager = None

    def apply_theme(self, name=None):
        """Apply the active theme, including one an extension registered.

        The theme is resolved through the extension manager when there is
        one, so an extension's theme wins over the built-in file with the
        same name -- the resolution order the manager documents. Without
        an extension the built-in theme is used, and an empty theme name
        leaves the measured look alone.

        ``name`` defaults to the theme the settings file names
        (Appearance.ThemeName), which is what the Appearance page writes
        when the user picks one. It can be given explicitly, so a caller
        (and a test) can apply a theme without touching the settings.
        """
        try:
            from qtranslate import theme as T
            if name is None:
                from qtranslate import config as C
                name = (C.load() or {}).get("Appearance", {}).get(
                    "ThemeName", "")
        except Exception:
            name = name or ""
        if not name:
            return
        try:
            record = T.active_theme(name, manager=self.ext_manager)
        except Exception:
            return
        try:
            apply_style(self.qapp, theme=record)
        except Exception:
            pass

    def _on_ui(self, fn):
        """Run ``fn`` on the UI thread.

        A no-op call (same thread as the caller) when the caller already
        IS the UI thread, so this is safe to wrap every hotkey handler
        in without a performance cost on the common path; it only
        crosses threads when a Qt-unaware caller (``keyboard``'s
        listener thread) actually needs it to.
        """
        from PySide6.QtCore import QThread
        if QThread.currentThread() is self.qapp.thread():
            fn()
        else:
            self._ui.invoke.emit(fn)

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
            # The four slots read the native defaults table
            # (config.LANG_DEFAULTS), not inlined constants: an unset
            # From is auto (1), not "en" (17) -- the 2026-10-15 bug.
            self.target = table[general.get(
                "LanguageTo", config.LANG_DEFAULTS["LanguageTo"])]
            self.source = table[general.get(
                "LanguageFrom", config.LANG_DEFAULTS["LanguageFrom"])]
        except Exception:
            pass
        self._apply_cli()
        # The mouse mode the last session left on (native's
        # General.MouseMode, DAT_005493F8). The capture hook itself is
        # started by main(), when the app is fully alive.
        try:
            from .tray import MOUSE_MODES
            idx = int(general.get("MouseMode", 0) or 0)
            if 0 <= idx < len(MOUSE_MODES):
                self.mouse_mode = MOUSE_MODES[idx]
        except Exception:
            pass

    def _apply_cli(self):
        """An explicit launch wins over the remembered session.

        Native's ``FUN_0043CD68`` applies the positional overrides
        (service, target, theme) OVER the restored session, so
        ``start_qt.py google vi`` selects that pair whatever the
        settings file remembers. The parse is the shared one
        (``qtranslate.cli``), so the two front ends cannot disagree
        about what a positional means.
        """
        try:
            from qtranslate.cli import parse_args
            service, target, theme, cli_service, cli_target = parse_args(
                self.argv[1:])
        except Exception:
            return
        if cli_service and service:
            self.service = service
        if cli_target and target:
            self.target = target
        if theme:
            self.theme = theme

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
        from qtranslate.languages import LANG_DISPLAY
        return LANG_DISPLAY.get(code, code)

    def _code_of(self, name):
        from qtranslate.languages import LANG_CODES
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
            from qtranslate.services.ocr import ocr_language, ocr_text
            # The service takes its OWN 3-letter codes (eng, vie, rus...),
            # not Google's 2-letter ones: the map is the service's, and
            # it is the one the native's image carries.
            text = ocr_text(data, api_key=key, lang=ocr_language(code))
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
        keyboard = keyboard_module()
        if keyboard is not None:
            for _name, _combo in list(self.hotkeys):
                try:
                    keyboard.remove_hotkey(_combo)
                except Exception:
                    pass
        self.hotkeys = []
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

    # ------------------------------------------------------- the mouse mode
    def set_mouse_mode(self, mode):
        """The mouse mode, and the hook that goes with it.

        Native's mouse mode is the one that lets you BOI DEN: select
        text in another program, click, and the selection is captured
        and translated. The three modes carry native's own names (the
        English lang.json, ids 60/70/71) and their index is native's
        General.MouseMode (DAT_005493F8) -- the key the Tk front end
        writes too, so the core and both front ends share one state.

        Mode 0 ("Show icon") is native's "an icon appears next to the
        cursor and you click it". The port cannot draw that icon (the
        native capture chain has no SetCursor of its own -- checklist
        row C10), so mode 0 is the port's off state, the same way the
        Tk front end treats it.
        """
        self.mouse_mode = mode
        self._persist_mouse_mode()
        self._sync_mouse_hook()
        self._sync_tray_state()
        if self.tray is not None:
            try:
                self.tray.set_mouse_mode(mode)
            except Exception:
                pass

    def _mouse_mode_index(self) -> int:
        """The mode's number: native's General.MouseMode (DAT_005493F8)."""
        try:
            from .tray import MOUSE_MODES
            return MOUSE_MODES.index(self.mouse_mode)
        except Exception:
            return 0

    def _persist_mouse_mode(self):
        """Write the mode to the config, the way native's tray does.

        Native keeps the mode in General.MouseMode and the "is it on"
        flag in General.MouseModeOn. The Tk front end writes the same
        two keys (tests/regress_mouse_capture.py pins that), so the two
        front ends and the core read one state.
        """
        idx = self._mouse_mode_index()
        try:
            config, _engine, _registry = self._core()
            cfg = config.load()
            general = cfg.setdefault("General", {})
            general["MouseMode"] = idx
            general["MouseModeOn"] = idx != 0
            config.save(cfg)
        except Exception:
            pass

    def _mouse_mode_off(self) -> bool:
        """True when the mode is native's "Show icon" one, which the
        port cannot draw, so it is the port's off state."""
        return self._mouse_mode_index() == 0

    def _sync_mouse_hook(self):
        """Start or stop the Win32 low-level mouse hook the way native
        does: live unless the mode is off."""
        try:
            from qtranslate import mouse_capture as mc
        except Exception:
            return
        try:
            if self._mouse_mode_off():
                if self._mouse_hook:
                    mc.stop()
                    self._mouse_hook = False
                return
            if not self._mouse_hook:
                mc.start(self._mouse_selected)
                self._mouse_hook = True
        except Exception:
            self._mouse_hook = False
        self._sync_tray_state()

    def _sync_tray_state(self):
        """The tray reflects the mouse-capture state, native's rule.

        The Tk controller owned this until the front end's removal (the
        rule lives in ``tray_state.select_state`` port of FUN_00418DA0:
        arm flag + hook-installed bit, not HotKeys). The Qt tray has the
        half that is host-independent: the state name and the tooltip.
        """
        if self.tray is None:
            return
        try:
            self.tray.sync_state(not self._mouse_mode_off(),
                                 bool(self._mouse_hook))
        except Exception:
            pass

    def _mouse_selected(self, x, y):
        """The hook's callback: a selection click arrived at (x, y).

        The hook proc must return fast, so the capture and the
        translation run on a worker thread and the result comes back
        through the bridge.
        """
        import threading
        threading.Thread(target=self._mouse_work, args=(x, y),
                         daemon=True).start()

    def _mouse_work(self, x, y):
        """Capture the text under the cursor and translate it.

        It runs on the worker's thread: the hook's proc has to return
        fast. The panes and the popup belong to the UI thread, so the
        result comes back through the bridge.
        """
        try:
            text = self._capture_selection(x, y)
            if not text:
                return
            res = self._translate(text)
            self._bridge.translated.emit(text, res.text)
            if self._mouse_mode_index() == 2:
                # native's third mode, "Show translation and read": the
                # same as the second one, plus speaking the selected
                # text aloud.
                self._speak(text)
        except Exception:
            pass

    def _mouse_gate_ok(self) -> bool:
        """Native's gates for the mouse capture, in native's order.

        The order is the one the Advanced-page audit recorded:
        Advanced.EnableGuiTranslation (DAT_005494e4) ->
        Advanced.EnableMouseModeOnCtrl (Ctrl held) -> the excluded
        applications. A setting that cannot be read is not a gate.
        """
        try:
            from qtranslate import mouse_capture as mc
            if not mc.available():
                return False
        except Exception:
            pass
        try:
            from qtranslate import config as cfg
            adv = (cfg.load() or {}).get("Advanced", {}) or {}
        except Exception:
            adv = {}
        if not bool(adv.get("EnableGuiTranslation", True)):
            return False
        if bool(adv.get("EnableMouseModeOnCtrl", False)):
            keyboard = keyboard_module()
            if keyboard is not None:
                try:
                    if not keyboard.is_pressed("ctrl"):
                        return False
                except Exception:
                    pass
        try:
            from qtranslate import exclusions
            if exclusions.foreground_excluded():
                return False
        except Exception:
            pass
        return True

    def _capture_selection(self, x, y) -> str:
        """The text of the selection the click ended.

        Native's third mode reads the text under the CURSOR (OLEACC);
        the other modes copy the selection with Ctrl+C and read the
        clipboard. The gates are native's (see _mouse_gate_ok).
        """
        if not self._mouse_gate_ok():
            return ""
        if self._mouse_mode_index() == 2:
            try:
                from qtranslate import mouse_capture as mc
                text = (mc.cursor_text(x, y) or "").strip()
            except Exception:
                text = ""
            if text:
                return text
        try:
            from qtranslate import sendkeys
            sendkeys.send("ctrl+c")
            import time
            time.sleep(0.15)
        except Exception:
            pass
        return self._clipboard_text()

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

    def show_translation(self, text, result):
        """Show one translation: the panes, the history and the popup.

        This is the step the popup hotkey and the mouse mode share, and
        it runs in the UI thread.
        """
        if self.win is not None:
            self.win.src.setPlainText(text[:2000])
            self.win.render(result)
        self.push_hist(self.service, text[:120], result[:200])
        try:
            from .popup import PopupWindow
            self._popup = PopupWindow(self)
            self._popup.set_text(text[:300], result)
            self._popup.place()
            self._popup.show()
        except Exception:
            pass

    def hotkey_popup(self):
        """Native's Ctrl+Q: translate what is on the clipboard and show
        it in the popup."""
        text = self._clipboard_text()
        if not text:
            return
        res = self._translate(text)
        self.show_translation(text, res.text)

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
        # The retype goes through sendkeys: True delivered, False when
        # there is no synthesizer (off Windows) -- never a raise.
        from qtranslate import sendkeys as _SK
        _SK.write_text(res.text)
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

    `tools/build_bundle.py` runs this against the built `.exe`. The failure
    it exists to catch is a module PyInstaller's Analysis never followed,
    which would otherwise show up as a crash in front of the user; the view
    reaches several core modules by lazy import inside a ``try``, so they
    are probed here explicitly rather than trusted to the import walk.

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

    # The toolkit itself, and the core modules the view reaches by lazy
    # import at its call sites (a cold `Engine`, the extension manager,
    # the tray-state rule, the settings writer and the hotkey writer).
    for _dep in ("PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
                 "qtranslate.engine", "qtranslate.config", "qtranslate.theme",
                 "qtranslate.extensions", "qtranslate.registry",
                 "qtranslate.providers", "qtranslate.tray_state",
                 "qtranslate.ui_slots", "qtranslate.history",
                 "qtranslate.sendkeys", "qtranslate.sdk",
                 "qtranslate.platforms"):
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
    # The startup steps the app owes the user's machine, in the order
    # native runs them. They are Core, not view: the settings file is
    # written on a fresh install, the services' options are seeded from
    # it, and the crash reporter is armed.
    try:
        from qtranslate import config as _C
        _C.write_default_options_if_missing()
        _C.seed_service_options()
    except Exception:
        pass
    # User extensions (D16), the same shared loader the Tk front end
    # uses: the per-user folder is scanned, manifests are validated,
    # the winners are committed into the live dispatch table, and a
    # bad extension never blocks startup. The loader is toolkit-free
    # by design (it lives in qtranslate.extensions, not in a view), so
    # both front ends share one mechanism.
    try:
        from qtranslate.extensions import load_user_extensions, last_manager
        _ext = load_user_extensions()
        if _ext:
            _loaded = sum(1 for r in _ext if r["status"] == "loaded")
            _disabled = sum(1 for r in _ext if r["status"] == "disabled")
            print("extensions: %d loaded, %d disabled" % (_loaded, _disabled))
        # The manager holds the UI and theme contributions, so the view
        # can actually show what an extension registered.
        app.ext_manager = last_manager()
    except Exception:
        app.ext_manager = None
    # The once-crash reporter: the previous run's crash is reported now
    # and its file is deleted, so it is reported exactly once.
    try:
        from qtranslate import crash as _CR
        _CR.consume_crash_reports()
        _CR.install_crash_hook()
        # FUN_0040345B's fail-fast: an out-of-memory condition terminates
        # without unwinding, so it must NOT fall through to the
        # crash-report excepthook installed just above (native's Q-row
        # records exactly that separation).
        _prev_hook = sys.excepthook

        def _oom_hook(typ, val, tb, _prev=_prev_hook):
            if typ is MemoryError:
                _CR.fail_fast(-0x7FF8FFF2)   # -> 0xC0000017, never returns
            return _prev(typ, val, tb)
        sys.excepthook = _oom_hook
    except Exception:
        pass
    # Single-instance guard (FUN_00435175): an existing instance is
    # activated and this launch exits.
    try:
        from qtranslate import single_instance as _SI
        if _SI.ensure_single(argv[1:]):
            print("another QTranslate instance is already running "
                  "(activated it)")
            return 0
    except SystemExit:
        raise
    except Exception:
        pass
    # The theme, now that the extension themes are known: an extension's
    # theme may override the built-in one the settings name.
    app.apply_theme()
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
    # The mouse-mode capture hook: native's mouse selection. It is
    # live only when the mode that needs it is on.
    app._sync_mouse_hook()
    # The global hotkeys, the ones the settings file binds. A machine
    # without the `keyboard` package simply has none.
    try:
        from .hotkeys import install
        app.hotkeys = install(app)
    except Exception:
        app.hotkeys = []
    return app.qapp.exec()
