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


# The history's own file (native keeps a session's history across
# restarts; the port used to hold it in memory only, so every restart
# the operator did emptied the History window). Capped at 500 entries,
# the oldest dropped.
HISTORY_PATH = None
HISTORY_LIMIT = 500


def _history_path():
    global HISTORY_PATH
    if HISTORY_PATH is None:
        try:
            from qtranslate.platforms import app_data_dir
            HISTORY_PATH = os.path.join(app_data_dir(), "History.json")
        except Exception:                   # noqa: BLE001
            HISTORY_PATH = ""
    return HISTORY_PATH


def _load_history():
    """The persisted history, oldest first like native's list."""
    try:
        import json
        with open(_history_path(), encoding="utf-8") as fh:
            items = json.load(fh)
        return [tuple(x) for x in items if isinstance(x, list)
                and len(x) >= 3][-HISTORY_LIMIT:]
    except Exception:                       # noqa: BLE001 -- fresh install
        return []


def _save_history(items):
    try:
        import json
        with open(_history_path(), "w", encoding="utf-8") as fh:
            json.dump([list(x)[:3] for x in list(items)[-HISTORY_LIMIT:]],
                      fh, ensure_ascii=False)
    except Exception:                       # noqa: BLE001 -- read-only disk
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
        self.history = _load_history()
        self.multi_services = set()
        self.win = None
        self.tray = None
        self.hotkeys_on = True
        self.hotkeys = []
        self.mouse_mode = "Show icon"
        self._mouse_enabled = False
        self._mouse_icon = None
        self._last_mouse_capture = 0.0
        self._mouse_hook = False
        self._bridge = _MouseBridge(self)
        self._ui = _UiInvoker()
        # Every background request the app starts (Translate, Ctrl+Q,
        # Alt+W, the clipboard hotkey), so ``wait_for_translation`` can
        # wait for all of them rather than one bookkeeping slot.
        self._threads = []
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
            self._mouse_enabled = bool(general.get("MouseModeOn", False))
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
        """Translate what is in the source pane and show the result.

        The request runs on a WORKER thread. ``tools/measure_translate.py``
        measured what the old synchronous call cost: a 400ms provider held
        the UI thread for 402ms, so the window was frozen for essentially
        the whole network round trip. The translation itself is not slow --
        the measurement shows ~3ms of port overhead against 400ms of
        provider -- but holding the event loop for it is what "QTranslate
        is slow" looks like from the user's side.

        Only the RESULT crosses back to the UI thread (``_on_ui``); the
        widgets are never touched from the worker.
        """
        text = self.win.src.toPlainText()
        return self._start_translation(text, self._show_main_result)

    def _show_main_result(self, text, res):
        """Show a finished translation in the main window (UI thread)."""
        if self.win is None:
            return
        self.win.render(res.text)
        if res.text:
            self.push_hist(self.service, text[:120], res.text[:200])

    def _spawn(self, name, work):
        """Run ``work`` on a tracked background thread.

        Every translation path (Translate, Ctrl+Q, Alt+W, the clipboard
        hotkey) goes through here, so ``wait_for_translation`` sees all of
        them and a test or script can observe the result deterministically.
        """
        import threading
        # Prune BEFORE adding: a thread that has not been started yet is
        # not alive, so filtering after the append dropped the very
        # thread the caller needs to wait for.
        self._threads = [t for t in self._threads if t.is_alive()]
        thread = threading.Thread(target=work, daemon=True,
                                  name="qtranslate-" + name)
        self._threads.append(thread)
        thread.start()
        return thread

    def _start_translation(self, text, on_done):
        """Run one translation off the UI thread, then hand back the result.

        A second request while one is in flight is DROPPED rather than
        queued: the native does the same (its task queue holds one
        translation), and stacking requests on a slow provider would show
        a burst of stale answers in arbitrary order.
        """
        if any(t.is_alive() for t in self._threads):
            return False

        def work():
            try:
                res = self._translate(text)
            except Exception as exc:            # noqa: BLE001
                from qtranslate.core import Result
                res = Result("", "[error] %s" % exc, self.service)
            self._on_ui(lambda: on_done(text, res))

        self._spawn("translate", work)
        return True

    def wait_for_translation(self, timeout=10.0):
        """Block until every in-flight background request has been applied.

        The UI is event-driven; a test (or a script) that must observe a
        result has to wait for the worker AND drain the queued UI update.
        Returns True when nothing is left in flight.
        """
        import time
        deadline = time.monotonic() + timeout
        for _ in range(200):
            alive = [t for t in self._threads if t.is_alive()]
            self.qapp.processEvents()
            if not alive:
                self.qapp.processEvents()
                return True
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
        self.qapp.processEvents()
        return not any(t.is_alive() for t in self._threads)

    def push_hist(self, svc, src, res):
        try:
            from qtranslate import config
            if not bool(config.load().get("General", {}).get(
                    "EnableHistory", True)):
                return
        except Exception:
            pass
        self.history.append((svc, src, res))
        _save_history(self.history)
        # Every "a translation reached the UI" path funnels through
        # here, so this is the emit point for the extensions'
        # translation.done event. A test stub without the emitter stays
        # a stub: the getattr keeps this a no-op there.
        emit = getattr(self, "_emit_extension_event", None)
        if emit is not None:
            emit("translation.done", {
                "provider": svc, "text": src, "result": res, "ok": True})

    def _emit_extension_event(self, event, payload):
        """Hand an event to the extension manager, fail-open."""
        try:
            mgr = getattr(self, "ext_manager", None)
            if mgr is not None:
                mgr.emit(event, payload)
        except Exception:                   # noqa: BLE001
            pass

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
        # The strip's highlight follows: the operator's report (2168) --
        # clicking a provider switched the service but the buttons kept
        # the FIRST one highlighted forever.
        if hasattr(self.win, "highlight_service"):
            self.win.highlight_service(name)

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

    def open_options(self, page: str = ""):
        """Open Options, optionally straight on one page.

        The pages are one window rebuilt in place (``OptionsBase``), so
        "open the Languages page" is the same dialog with a starting
        page -- not a second window, which is what the old per-page
        widget opened.
        """
        from .options import OptionsDialog, PAGES
        self._opts = OptionsDialog(self)
        if page and page in PAGES:
            try:
                self._opts._show_page(page)
            except Exception:
                pass
        self._opts.show()

    def open_languages_page(self):
        """Native's language-combo "Edit..." opens the Languages page."""
        self.open_options("Languages")

    def set_default_languages(self):
        """Native's language-combo "Reset": back to the configured pair."""
        try:
            from qtranslate import config
            general = (config.load() or {}).get("General", {})
        except Exception:
            general = {}
        src = general.get("SourceLanguage", "Auto-Detect")
        tgt = general.get("TargetLanguage", "English")
        for name, setter in (("cmb_src", self.set_source_by_name),
                             ("cmb_tgt", self.set_target_by_name)):
            combo = getattr(self.win, name, None) if self.win else None
            if combo is None:
                continue
            try:
                combo.blockSignals(True)
                combo.setCurrentText(src if name == "cmb_src" else tgt)
                combo.blockSignals(False)
            except Exception:
                pass
        self.set_source_by_name(src)
        self.set_target_by_name(tgt)

    # ------------------------------------------------- override conflicts
    def override_conflicts(self):
        """The providers more than one loaded extension replaces (D18)."""
        manager = self.ext_manager
        if manager is None:
            return {}
        try:
            return manager.override_conflicts() or {}
        except Exception:
            return {}

    def choose_override_winners(self):
        """Ask the user which extension wins a provider conflict (D18).

        Discovery order never decides. The choice is persisted through
        the core's own writer, which is what ``load_user_extensions``
        reads at the next start, so the pick survives a restart.
        """
        groups = self.override_conflicts()
        if not groups:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                None, "QTranslate",
                "No extension replaces a built-in provider, so there is "
                "nothing to choose.")
            return
        from qtranslate import extensions as _ext
        from .override_picker import OverridePicker
        try:
            saved = _ext.read_saved_overrides()
        except Exception:
            saved = {}
        dlg = OverridePicker(groups, saved, parent=None)
        from PySide6.QtWidgets import QDialog
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            _ext.write_saved_overrides(dlg.selection())
        except Exception:
            pass
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            None, "QTranslate",
            "Saved. Restart QTranslate to apply the choice.")

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
        # The result goes to native's own OCR window (menu 10's host),
        # which the region picker used to skip by writing straight into
        # the main result pane. The main pane keeps its old content.
        try:
            from .ocr_window import OcrResultWindow
            self._ocr = OcrResultWindow(self)
            self._ocr.set_text(text)
            self._ocr.show()
        except Exception:
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
        text in another program, click, and the selection is captured.
        The three modes carry native's own names (the English lang.json,
        ids 60/70/71) and their index is native's General.MouseMode
        (DAT_005493F8) -- the key the Tk front end writes too, so the
        core and both front ends share one state.

        Mode 0 ("Show icon") is native's "an icon appears under the
        selection and you click it": the port draws that icon now
        (``qt/mouse_icon.py``, checklist row C10). Whether the mouse
        capture is ON at all is the SEPARATE switch the tray's left
        click toggles (``toggle_mouse_enabled``, native's
        General.MouseModeOn) -- off means select + Ctrl+Q, on means the
        mode applies.
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

    def toggle_mouse_enabled(self):
        """The tray icon's LEFT CLICK: on/off for the whole mouse
        capture. Off = select + press Ctrl+Q yourself; on = the selected
        mode applies ("Show icon" pops the translate button under the
        selection). Persists native's General.MouseModeOn."""
        self._mouse_enabled = not self._mouse_enabled
        self._persist_mouse_mode()
        self._sync_mouse_hook()
        self._sync_tray_state()
        return self._mouse_enabled

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
        flag in General.MouseModeOn. The Tk front end wrote the same
        two keys (tests/regress_mouse_capture.py pins that), so the two
        front ends and the core read one state. MouseModeOn is now the
        tray click's own switch (all three modes are real); a mode
        change alone does not flip it.
        """
        idx = self._mouse_mode_index()
        try:
            config, _engine, _registry = self._core()
            cfg = config.load()
            general = cfg.setdefault("General", {})
            general["MouseMode"] = idx
            general["MouseModeOn"] = bool(getattr(self, "_mouse_enabled",
                                                  False))
            config.save(cfg)
        except Exception:
            pass

    def _mouse_mode_off(self) -> bool:
        """True when the mouse capture is switched OFF (the tray's left
        click). The mode index is no longer the off state -- mode 0
        ("Show icon") is a real mode with its own floating icon."""
        return not bool(getattr(self, "_mouse_enabled", False))

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

    # Native's anti-loop, decompiled 2026-10-24 (FUN_004193f6 +
    # FUN_004183bd): a capture is DROPPED unless enough time has passed
    # since the last one (its FUN_0050bc60() > 10.0 branch) and no task
    # is already running. The port fires the hook on every plain click,
    # so without this gate every click re-queued a popup ("loop auto
    # translate cực nghiêm trọng", the operator's report).
    MOUSE_CAPTURE_COOLDOWN = 10.0

    def _mouse_capture_allowed_now(self) -> bool:
        """The cooldown + one-task gates, native's own two."""
        import time
        now = time.monotonic()
        if now - self._last_mouse_capture < self.MOUSE_CAPTURE_COOLDOWN:
            return False
        if any(t.is_alive() for t in self._threads):
            return False
        self._last_mouse_capture = now
        return True

    def _mouse_work(self, x, y):
        """Act on a selection click, per the mode -- native's dispatch.

        Native (FUN_004183bd, decompiled 2026-10-24): when the mouse
        mode is ON and no task is running, mode 0 queues TaskShowIcons
        -- the small translate button at the click point, click IT to
        translate -- and modes 1/2 queue TaskShowPopupWindow at the
        cursor, IMMEDIATELY. The port does the same through its own
        pieces; the text is captured with the copy-capture engine, so a
        click with nothing selected does nothing at all.

        It runs on the worker's thread: the hook's proc has to return
        fast. The panes and the popup belong to the UI thread, so the
        result comes back through the bridge.
        """
        try:
            if not self._mouse_capture_allowed_now():
                return
            text = self._capture_selection(x, y)
            if not text:
                return
            if self._mouse_mode_index() == 0:
                self._on_ui(lambda: self._show_mouse_icon(x, y, text))
                return
            res = self._translate(text)
            self._bridge.translated.emit(text, res.text)
            if self._mouse_mode_index() == 2:
                self._speak(text)
        except Exception:
            pass

    def _show_mouse_icon(self, x, y, text):
        """The mode-0 floating translate button (UI thread)."""
        try:
            from .mouse_icon import MouseIcon
            icon_win = getattr(self, "_mouse_icon", None)
            if icon_win is None:
                icon_win = MouseIcon(self, self._translate_captured)
                self._mouse_icon = icon_win
            icon_win.pop(x, y, text)
        except Exception:                   # noqa: BLE001 -- fail-open
            pass

    def _translate_captured(self, text):
        """The floating icon's click: translate like Ctrl+Q would."""
        def done(t, res):
            if res.ok and res.text:
                self.show_translation(t, res.text,
                                      provider=res.provider_used)
        self._start_translation(text, done)

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
        """The text under the click -- native's own mouse capture.

        NATIVE (FUN_00404901, decompiled): GetCursorPos ->
        AccessibleObjectFromPoint -> get_accName, fallback get_accValue
        when the name is empty. No clipboard is touched on this path:
        the port's copy-capture made EVERY click read "a selection",
        because a clipboard manager keeps the sequence number moving
        (the operator's 'click bất cứ đâu lại lỗi', 2026-10-24). OLEACC
        answers with the text AT the point -- empty on a button, a
        panel, the desktop -- which is exactly the native behaviour:
        the icon only appears where there is something to read.

        The gates are native's (see _mouse_gate_ok).
        """
        if not self._mouse_gate_ok():
            return ""
        try:
            from qtranslate import mouse_capture as mc
            return (mc.cursor_text(x, y) or "").strip()
        except Exception:                   # noqa: BLE001 -- OLEACC may
            return ""                       # refuse; native fails open too

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

    def popup_pair(self, provider: str = "") -> str:
        """The line native puts in the popup's title row.

        Both captures read ``Vietnamese to English (Google)``: the SOURCE
        language, the word "to", the TARGET language, then the service
        that answered in brackets. It is built from the live settings, so
        it follows the pair the user picked instead of a fixed string.
        """
        src = self._display(self.source) if self.source != "auto" else "Auto"
        tgt = self._display(self.target)
        name = self.service_display(provider or self.service)
        return "%s to %s (%s)" % (src, tgt, name)

    def show_translation(self, text, result, provider: str = ""):
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
            self._popup.set_text(text[:300], result,
                                 self.popup_pair(provider),
                                 provider=provider or self.service)
            self._popup.place()
            self._popup.show()
        except Exception:
            pass

    def run_ui_contribution(self, contrib):
        """Run a menu contribution an extension registered."""
        if not callable(contrib):
            return
        try:
            result = contrib()
        except Exception as exc:                # noqa: BLE001
            result = "Extension failed: %s" % exc
        if result is None:
            return
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(None, "QTranslate", str(result))
        except Exception:
            pass

    def hotkey_popup(self):
        """Native's Ctrl+Q: translate the SELECTED text, in the popup.

        ``help.txt`` says "Translate selected text and show it in popup
        window", so the selection is copied first (``selection.
        copy_selection``, native's ``FUN_0043BF30`` copy-capture) instead
        of trusting whatever happened to be on the clipboard. Reading the
        old clipboard is what a bare ``paste()`` did, and it translated
        the wrong text whenever the user had selected something new.
        """
        # The copy-capture sleeps while it polls for the clipboard change
        # (up to ~1s on a target that ignores Ctrl+C) and the translate is
        # a network round trip, so neither belongs on the UI thread. Both
        # run on a tracked worker; only the finished translation crosses
        # back.
        def work():
            try:
                from qtranslate import selection
                text = (selection.copy_selection() or "").strip()
                if not text:
                    text = self._clipboard_text()
                if not text:
                    return
                res = self._translate(text)
            except Exception:                   # noqa: BLE001
                return
            self._on_ui(lambda: self.show_translation(text, res.text))

        self._spawn("popup", work)

    def hotkey_translate_clipboard(self):
        text = self._clipboard_text()
        if not text:
            return
        self._start_translation(text, self._show_clipboard_result)

    def _show_clipboard_result(self, text, res):
        """Show a clipboard translation in the main window (UI thread)."""
        if self.win is None:
            return
        self.win.src.setPlainText(text[:2000])
        self._show_main_result(text, res)

    def hotkey_replace_selection(self):
        """Native's Alt+W: translate the selection and type it back.

        Reads the SELECTION, not the clipboard -- the whole point of the
        action is to replace what the user has highlighted.
        """
        def work():
            try:
                from qtranslate import selection
                text = (selection.copy_selection() or "").strip()
                if not text:
                    text = self._clipboard_text()
                if not text:
                    return
                res = self._translate(text)
            except Exception:                   # noqa: BLE001
                return
            self._on_ui(lambda: self._show_replace(text, res))

        self._spawn("replace", work)

    def _show_replace(self, text, res):
        """Apply a finished Alt+W translation (UI thread)."""
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
    # The extensions' "app is up" event: emitted once, after the tray
    # and the hotkeys exist, so a listener can rely on both.
    try:
        mgr = getattr(app, "ext_manager", None)
        if mgr is not None:
            mgr.emit("app.ready", {})
    except Exception:                       # noqa: BLE001 -- fail-open
        pass
    return app.qapp.exec()
