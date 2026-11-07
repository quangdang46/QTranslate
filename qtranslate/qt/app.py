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

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
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


def _frontmost():
    try:
        from AppKit import NSWorkspace
        a = NSWorkspace.sharedWorkspace().frontmostApplication()
        return a.localizedName() if a else "?"
    except Exception:
        return "?"


def _dbg(msg):
    import time as _t
    msg = "%s  %s" % (_t.strftime("%H:%M:%S"), msg)
    """TEMPORARY trace of the mouse-icon chain to %TEMP% (the operator's
    'click vào icon không thấy gì', 2026-10-24). Removed once the cause
    is in hand."""
    try:
        import os as _os
        with open(_os.path.join(_os.environ.get("TEMP", "/tmp"),
                                "qt_mouse_debug.log"), "a",
                  encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass
    # The persistent app log: /tmp is wiped on reboot and the mouse log
    # mixes unrelated traces, so the operator could not tell "hotkey
    # never fired" from "popup failed silently". One rotating file in
    # the config dir keeps every stage of the Ctrl+Q chain.
    try:
        import os as _os
        path = _os.path.join(_os.path.expanduser("~/.config/QTranslate"),
                             "app.log")
        try:
            if _os.path.getsize(path) > 1_000_000:
                _os.replace(path, path + ".1")
        except OSError:
            pass
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


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
            # [:4] keeps the history window's favourite flag -- [:3]
            # stripped every star on the next translation (history
            # audit). Legacy 3-slot entries still round-trip.
            json.dump([list(x)[:4] for x in list(items)[-HISTORY_LIMIT:]],
                      fh, ensure_ascii=False)
    except Exception:                       # noqa: BLE001 -- read-only disk
        pass


def _apply_ui_scale():
    """Port of .tmp AppearancePanel ``uiScale`` (75-300, step 25).

    Qt's equivalent is QT_SCALE_FACTOR, which Qt reads once when the
    QApplication is created -- so the options combo is honoured on the
    NEXT start and the page says so. An explicit QT_SCALE_FACTOR in the
    environment wins over the stored setting.
    """
    if "QT_SCALE_FACTOR" in os.environ:
        return
    try:
        from qtranslate import config as _C
        ap = (_C.load() or {}).get("Appearance") or {}
        scale = int(ap.get("UiScale", 100))
    except Exception:
        return
    scale = max(75, min(300, scale))
    if scale != 100:
        os.environ["QT_SCALE_FACTOR"] = "%.2f" % (scale / 100.0)


class QtApp:
    """The application's state and behaviour, independent of the widgets.

    The tkinter port keeps this state on ``App``; here it lives on
    ``QtApp`` so the window classes stay dumb.
    """

    def __init__(self, argv=None):
        _apply_ui_scale()
        self.qapp = QApplication.instance() or QApplication(argv or [])
        apply_style(self.qapp)
        self.service = "google"
        self.source = "auto"
        self.target = "vi"
        self.argv = list(argv or [])
        self.history = _load_history()
        # History-nav cursor: len(history) means "the live panes". The
        # snapshot below holds what the live panes showed before the
        # first step away, so stepping forward past the newest entry
        # restores it instead of leaving the last-browsed entry up.
        self._nav_idx = len(self.history)
        self._nav_live = None
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
        # The notification surface (port of .tmp NotificationBus): every
        # feature posts through ``self.notify`` / ``qtranslate.notify``,
        # and the toast stack below surfaces it on the UI thread.
        from . import notify as _qt_notify
        _qt_notify.attach(self)
        # Every background request the app starts (Translate, Ctrl+Q,
        # Alt+W, the clipboard hotkey), so ``wait_for_translation`` can
        # wait for all of them rather than one bookkeeping slot.
        self._threads = []
        import threading
        self._translation_lock = threading.Lock()
        # The extension manager, once the user extensions are loaded.
        # It carries the UI and theme contributions.
        self.ext_manager = None
        # Spell check (.tmp PerformSpellCheckUseCase): corrections for
        # the current source text, refreshed on a debounce; the source
        # pane's context menu offers them as "Spelling suggestions".
        self._spell_corrections = []
        self._spell_timer = None
        self._spell_sig = None

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
        try:
            if name:
                record = T.active_theme(name, manager=self.ext_manager)
            else:
                # "--- Default ---" means no theme file: restore the
                # measured base look instead of leaving the previous
                # theme's stylesheet applied for the session.
                record = None
        except Exception:
            return
        try:
            apply_style(self.qapp, theme=record)
        except Exception:
            pass

    def notify(self, severity, title, body, code=None, source=None):
        """Post a user-facing notification (port of .tmp's
        ``ScopedPluginContext.notify`` -> ``NotificationBus.post``).

        Safe from any thread: the bus fans out on the posting thread and
        the toast surface marshals to the UI thread itself. ``severity``
        is a ``qtranslate.notify.Severity`` or its string value.
        """
        from qtranslate import notify as _N
        _N.notify(severity, title, body, code=code, source=source)

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
            # General.ActiveService: the last service the user (or an
            # applied preset) picked -- names[0] is only the fallback
            # priority order, not a remembered choice.
            active = str(general.get("ActiveService") or "")
            if active in names:
                self.service = active
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
            # The target can never be auto: auto-detect is a SOURCE-only
            # concept (.tmp SwapLanguagesUseCase / TO_LANGS both exclude
            # it). A persisted or swapped-in "auto" target silently echoes
            # the input back as the "translation" -- the vi->auto pair this
            # produced is what made Translate look dead. Recover to the
            # native default pair instead.
            if self.target == "auto":
                self.target = table[config.LANG_DEFAULTS["LanguageTo"]]
                if self.source == self.target:
                    self.source = table[config.LANG_DEFAULTS["LanguageFrom"]]
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
        # Options -> Apply/OK lands here via _notify_app: pinned
        # languages (and any other picker-list change) take effect on
        # the combos without rebuilding the window.
        try:
            self._refresh_language_combos()
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
        return config.EXTRA_SERVICE_DISPLAY.get(name, name)

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
            # Entries may be numeric ids (native) or provider NAMES --
            # id-less providers (extension-registered, the .tmp plugin
            # ports) have no ServicesOrder id to disable by.
            disabled_names = {config.SERVICE_NAMES.get(d, d)
                              for d in disabled}
            names = [config.SERVICE_NAMES.get(i) for i in ids
                     if i not in disabled]
            names = [n for n in names
                     if n in registry.TRANSLATORS
                     and n not in disabled_names]
            # Extension-registered providers have no ServicesOrder id --
            # they join the strip AFTER the native order (the same
            # "TRANSLATORS-appended" rule router_order uses for the
            # fallback chain), deduped by callable identity so an alias
            # never shows twice. Without this the strip could never
            # select an extension provider: it stayed fallback-only.
            seen = {id(registry.TRANSLATORS[n]) for n in names}
            # A disabled service's ALIASES must stay disabled too --
            # "bing" shares microsoft's callable, so without this the
            # alias would resurrect a service the user turned off.
            disabled_callables = {
                id(registry.TRANSLATORS[n])
                for n in disabled_names if n in registry.TRANSLATORS}
            for n, fn in registry.TRANSLATORS.items():
                if (n in names or n in disabled_names
                        or id(fn) in seen or id(fn) in disabled_callables):
                    continue
                names.append(n)
                seen.add(id(fn))
            return names
        except Exception:
            return ["google", "microsoft", "promt", "babylon", "yandex",
                    "youdao", "baidu", "naver", "deepl"]

    def _disabled_lang_names(self):
        """Options->Languages unchecked set. The page wrote
        ``DisabledLanguages`` for years while nothing read it -- the
        combos must not offer a language the user disabled."""
        try:
            from qtranslate import config as _C
            return set((_C.load() or {}).get("DisabledLanguages", [])
                       or [])
        except Exception:
            return set()

    def _pinned_codes(self):
        """.tmp Configuration.pinnedLanguages: non-empty means ONLY these
        language codes appear in the pickers ("cannot disable all
        languages and keep only 3-4" -- Yan's request). Empty = all."""
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            v = (cfg.get("General", {}) or {}).get("PinnedLanguages")
            if v is None:
                v = cfg.get("PinnedLanguages")
            if isinstance(v, str):
                v = [s for s in v.replace("|", ",").split(",") if s.strip()]
            return {str(c).strip() for c in (v or []) if str(c).strip()}
        except Exception:
            return set()

    def source_names(self):
        dis = self._disabled_lang_names()
        pinned = self._pinned_codes()
        return [self._display("auto")] + [
            self._display(c) for c in self._lang_codes()
            if c != "auto" and self._display(c) not in dis
            and (not pinned or c in pinned)]

    def target_names(self):
        dis = self._disabled_lang_names()
        pinned = self._pinned_codes()
        return [self._display(c) for c in self._lang_codes()
                if c != "auto" and self._display(c) not in dis
                and (not pinned or c in pinned)]

    def _refresh_language_combos(self):
        """Repopulate the main window's language combos after a settings
        change (.tmp MainAppFrame re-renders withPinnedLanguages on every
        state emission). A selection the filter hides stays put --
        .tmp LanguageComboBox leaves selectedItem untouched rather than
        silently swapping the pair."""
        win = getattr(self, "win", None)
        if win is None:
            return
        for combo, names in (
                (getattr(win, "cmb_src", None), self.source_names()),
                (getattr(win, "cmb_tgt", None), self.target_names())):
            if combo is None:
                continue
            try:
                cur = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                for n in names:
                    combo.addItem(n)
                if cur:
                    if combo.findText(cur) < 0:
                        combo.addItem(cur)
                    combo.setCurrentText(cur)
                combo.blockSignals(False)
            except Exception:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass

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
        return self._start_translation(text, self._show_main_result,
                                       apply_rules=True)

    def _show_main_result(self, text, res):
        """Show a finished translation in the main window (UI thread)."""
        if self.win is None:
            return
        # A translation rule that re-resolved the AUTO source moved the
        # session target (.tmp updates targetLanguage state); apply it
        # on the UI thread without persisting LanguageTo.
        rt = getattr(self, "_pending_rule_target", None)
        self._pending_rule_target = None
        if rt:
            self.target = rt
            try:
                cmb = getattr(self.win, "cmb_tgt", None)
                if cmb is not None:
                    name = self._display(rt)
                    cmb.blockSignals(True)
                    if cmb.findText(name) >= 0:
                        cmb.setCurrentText(name)
                    cmb.blockSignals(False)
            except Exception:
                pass
        self._last_src_text = text or ""
        # The result string can carry the back-translation marker --
        # downstream consumers (extra output, inline gloss) judge the
        # visible translation only.
        _disp_out = res.text or ""
        try:
            from qtranslate import reliability as _REL
            _disp_out = _REL.split_backtranslation(_disp_out)[0]
        except Exception:
            pass
        self._last_out_text = _disp_out
        self.win.render(res.text)
        if res.text:
            self.push_hist(self.service, text[:2000], res.text[:4000])
            # AutoCopyGuard copies translatedText -- the visible
            # translation, without the back-translation block.
            self._maybe_auto_copy(_disp_out, "main")
        self.refresh_extra_output()
        self._refresh_inline_definition(text, _disp_out)
        # .tmp ParallelComparisonUseCase fires alongside the primary
        # answer whenever comparison translators are configured; the
        # rows land in the extra pane's Compare mode whenever it's on.
        try:
            self._run_comparison(text)
        except Exception:
            pass

    # ------------------------------------------- inline dictionary gloss
    # .tmp FetchInlineDefinitionUseCase + DictionaryAutoSource
    # (OFF/TRANSLATED/SOURCE, default TRANSLATED): when the chosen side
    # of the pair is a single word, a quiet background lookup puts a
    # one-line definition under the result. Every failure is silent.
    def _inline_pick(self, src_text, out_text):
        """(.tmp DictionaryAutoSource OFF/TRANSLATED/SOURCE) -> the
        single word to gloss plus the fallback side, or ("", "") when
        the mode is off or neither side is one word."""
        try:
            gen_cfg = self._extra_cfg()
            mode = (gen_cfg.get("DictionaryAutoSource")
                    or "TRANSLATED")
            # .tmp isDictionaryAutoPopupEnabled gates the WHOLE
            # AutoLookupCoordinator -- inline gloss included, not just
            # the dictionary panel.
            if not gen_cfg.get("DictionaryAutoPopup", True):
                return "", ""
        except Exception:
            mode = "TRANSLATED"
        if mode == "OFF":
            return "", ""
        prefer_source = mode == "SOURCE"
        primary = (src_text if prefer_source else out_text) or ""
        alternate = (out_text if prefer_source else src_text) or ""

        def single(t):
            t = (t or "").strip()
            return t if len(t) >= 2 and not any(
                c.isspace() for c in t) else ""

        word = single(primary)
        alt = single(alternate)
        if not word and alt:
            word, alt = alt, ""
        return word, alt

    def _inline_lookup(self, word, alt, done):
        """Shared worker for the main window and the popup gloss: the
        dictionary fan-out can take seconds, so it runs UNTRACKED --
        _start_translation drops new requests while any tracked thread
        lives and a glance must never block the next translate."""
        def work():
            gloss = ""
            try:
                from qtranslate import dictionary_search as _DS
                gloss = _DS.inline_definition(word)
                if not gloss and alt:
                    gloss = _DS.inline_definition(alt)
            except Exception:
                gloss = ""
            try:
                self._on_ui(lambda: done(gloss or ""))
            except Exception:
                pass
        import threading
        threading.Thread(target=work, daemon=True,
                         name="qtranslate-inline-def").start()

    def _refresh_inline_definition(self, src_text, out_text):
        win = getattr(self, "win", None)
        if win is None or not hasattr(win, "set_inline_definition"):
            return
        word, alt = self._inline_pick(src_text, out_text)
        self._inline_gen = getattr(self, "_inline_gen", 0) + 1
        gen = self._inline_gen
        if not word:
            try:
                win.set_inline_definition("")
            except Exception:
                pass
            return
        # .tmp AutoLookupCoordinator: a VISIBLE dictionary panel
        # follows the picked word; it never opens one, and the same
        # word is not re-sent.
        self._auto_dict_refresh(word)
        self._inline_lookup(word, alt, lambda gloss: self._inline_done(
            gen, gloss))

    def _auto_dict_refresh(self, word):
        """Point an already-open DictionaryWindow at ``word``.

        .tmp AutoLookupCoordinator calls setDictionarySearchWord +
        LookupWord only when the dictionary panel is visible AND the
        main window is visible -- automatic lookup refreshes, it never
        opens. ``_auto_dict_word`` mirrors upstream's dictionaryWord
        dedup so repeat translations of the same word do not re-query.
        """
        d = getattr(self, "_dict", None)
        if d is None or not word:
            return
        try:
            if not d.isVisible():
                return
            if getattr(self, "_auto_dict_word", "") == word:
                return
            self._auto_dict_word = word
            d.inp.setText(word)
            d.do_search()
        except Exception:
            pass

    def _inline_done(self, gen, gloss):
        if gen != getattr(self, "_inline_gen", 0):
            return          # a newer translation superseded this one
        win = getattr(self, "win", None)
        if win is None:
            return
        try:
            win.set_inline_definition(gloss or "")
        except Exception:
            pass

    def _popup_inline_definition(self, src_text, out_text):
        """The same gloss for the quick popup (.tmp QuickTranslateDialog
        state.definition = mainState.inlineDefinition). Same settings,
        same single-word rule, same silent failure -- only the target
        widget differs."""
        pop = getattr(self, "_popup", None)
        if pop is None or not hasattr(pop, "set_inline_definition"):
            return
        word, alt = self._inline_pick(src_text, out_text)
        self._popup_defn_gen = getattr(self, "_popup_defn_gen", 0) + 1
        gen = self._popup_defn_gen
        if not word:
            try:
                pop.set_inline_definition("")
            except Exception:
                pass
            return
        def done(gloss):
            if gen != getattr(self, "_popup_defn_gen", 0):
                return          # a newer popup translation superseded
            if getattr(self, "_popup", None) is not pop:
                return
            try:
                pop.set_inline_definition(gloss)
            except Exception:
                pass
        self._inline_lookup(word, alt, done)

    # -------------------------------------------------------- comparison
    # .tmp ParallelComparisonUseCase + ServicePreset.comparisonTranslatorIds:
    # the configured comparison translators re-translate the SAME source
    # in parallel, independently of the primary answer. The port keeps
    # the flat General.ComparisonServices list (no preset system) and
    # renders the rows in the extra pane's "Compare" mode.
    def _comparison_services(self):
        """Enabled translator keys configured for comparison, minus the
        primary -- .tmp TranslatorSet drops repeats and the Primary."""
        try:
            from qtranslate import config as _C
            v = ((_C.load() or {}).get("General", {}) or {}
                 ).get("ComparisonServices")
            if isinstance(v, str):
                v = [s for s in v.replace("|", ",").split(",") if s.strip()]
            wanted = [str(s).strip() for s in (v or []) if str(s).strip()]
        except Exception:
            return []
        if not wanted:
            return []
        try:
            enabled = set(self.ordered_services())
        except Exception:
            enabled = set()
        return [s for s in dict.fromkeys(wanted)
                if s != self.service and (not enabled or s in enabled)]

    def _run_comparison(self, text):
        """Fan the source text out to every comparison translator.

        One untracked daemon per service -- the same rule as the
        inline-definition lookup: N side requests must never hold the
        single-flight translation lock, and a stale generation's rows
        are dropped on arrival."""
        svcs = self._comparison_services()
        self._compare_gen = getattr(self, "_compare_gen", 0) + 1
        gen = self._compare_gen
        self._compare_rows = {s: {"status": "loading", "text": "",
                                  "error": ""} for s in svcs}
        if not svcs or not (text or "").strip():
            self._compare_render()
            return
        self._compare_render()
        for svc in svcs:
            def work(s=svc):
                out, err = self._compare_fetch(s, text)
                try:
                    self._on_ui(lambda: self._compare_row_done(
                        gen, s, out, err))
                except Exception:
                    pass
            import threading
            threading.Thread(target=work, daemon=True,
                             name="qtranslate-compare-" + svc).start()

    def _compare_fetch(self, svc, text):
        """One comparison row's (text, error) -- shared by the main
        window's Compare mode and the quick popup's cards."""
        out, err = "", ""
        try:
            from qtranslate import engine
            res = engine.translate(svc, (text or "")[:5000],
                                   self.target, self.source)
            if res.ok and res.text:
                out = res.text
            else:
                err = res.text or "Translation failed"
        except Exception as exc:            # noqa: BLE001
            err = str(exc) or "Translation failed"
        return out, err

    def _popup_compare(self, text):
        """.tmp quickTranslationComparisonPolicy: the QUICK popup
        compares whenever >=2 effective translators exist --
        independent of the saved layout, which only gates the main
        window. Same untracked-daemon + generation-guard rules as
        _run_comparison; rows render into the popup's compare strip."""
        pop = getattr(self, "_popup", None)
        if pop is None or not hasattr(pop, "set_comparison"):
            return
        svcs = self._comparison_services()
        self._popup_cmp_gen = getattr(self, "_popup_cmp_gen", 0) + 1
        gen = self._popup_cmp_gen
        if not svcs or not (text or "").strip():
            try:
                pop.set_comparison("")
            except Exception:
                pass
            return
        rows = {s: {"status": "loading", "text": "", "error": ""}
                for s in svcs}

        def render():
            if gen != getattr(self, "_popup_cmp_gen", 0):
                return                      # superseded
            if getattr(self, "_popup", None) is not pop:
                return
            blocks = []
            for svc in svcs:
                row = rows.get(svc) or {"status": "loading"}
                try:
                    name = self.service_display(svc)
                except Exception:
                    name = svc
                if row.get("status") == "loading":
                    body = "Translating…"
                elif row.get("status") == "ok":
                    body = row.get("text") or ""
                else:
                    body = row.get("error") or "Translation failed"
                blocks.append("%s\n%s" % (name, body))
            try:
                pop.set_comparison("\n\n".join(blocks))
            except Exception:
                pass

        render()
        for svc in svcs:
            def work(s=svc):
                out, err = self._compare_fetch(s, text)

                def done():
                    if gen != getattr(self, "_popup_cmp_gen", 0):
                        return
                    rows[s] = {"status": "ok" if out else "error",
                               "text": out, "error": err}
                    render()
                try:
                    self._on_ui(done)
                except Exception:
                    pass
            import threading
            threading.Thread(target=work, daemon=True,
                             name="qt-popup-cmp-" + svc).start()

    def _compare_row_done(self, gen, svc, out, err):
        if gen != getattr(self, "_compare_gen", 0):
            return                      # a newer translation superseded
        rows = getattr(self, "_compare_rows", None)
        if rows is None or svc not in rows:
            return
        rows[svc] = {"status": "ok" if out else "error",
                     "text": out or "", "error": err or ""}
        self._compare_render()

    def _compare_render(self):
        """Paint the comparison rows into the extra pane (Compare mode).

        Blocks read "Service name / result" -- the port's card grid is
        flattened into the one pane the extra-output surface already
        owns; the information (per-provider answer + failure) is the
        same."""
        win = getattr(self, "win", None)
        if win is None:
            return
        svcs = self._comparison_services()
        if not svcs:
            try:
                win.set_extra_text(
                    "No comparison services configured "
                    "(Options > Comparison).", visible=True)
            except Exception:
                pass
            return
        rows = getattr(self, "_compare_rows", {}) or {}
        blocks = []
        for svc in svcs:
            row = rows.get(svc) or {"status": "loading"}
            try:
                name = self.service_display(svc)
            except Exception:
                name = svc
            if row.get("status") == "loading":
                body = "Translating…"
            elif row.get("status") == "ok":
                body = row.get("text") or ""
            else:
                body = row.get("error") or "Translation failed"
            blocks.append("%s\n%s\n%s" % (name, "-" * 12, body))
        try:
            win.set_extra_text("\n\n".join(blocks), visible=True)
        except Exception:
            pass

    # ------------------------------------------------------ extra output
    # .tmp's ExtraOutputPanel: one lower pane, three modes. "back" is
    # the native EditBackTranslation flow (handled inside
    # win.render/set_result); "summary"/"rewrite" call the ai-services
    # ports on a worker -- the same SummarizeUseCase/RewriteUseCase
    # shape: pick the input (Output = translated text, Input = source),
    # run with the stored option id, show the answer or the failure in
    # the pane itself.
    def _extra_cfg(self):
        try:
            from qtranslate import config as _C
            return (_C.load() or {}).get("General", {}) or {}
        except Exception:
            return {}

    def _maybe_auto_copy(self, text, origin):
        """AutoCopyGuard port (.tmp workspace/translation): copy the
        finished translation per ``General.AutoCopyTranslation`` —
        "off" never, "quick" only for the quick-translate surface,
        "all" for main/quick/OCR. Blank results never copy; instant
        translation is excluded upstream in every mode (the port has
        no instant pipeline feeding this hook)."""
        try:
            mode = str(self._extra_cfg().get(
                "AutoCopyTranslation", "off") or "off").lower()
        except Exception:
            mode = "off"
        if mode == "off" or not text:
            return
        if mode == "quick" and origin != "quick":
            return
        try:
            QApplication.clipboard().setText(text)
        except Exception:
            pass

    def refresh_extra_output(self):
        """Re-derive the extra pane for the current mode/texts.

        UI-thread entry (called after a translation lands and whenever
        the mode/options/source change). In "back" mode this is a
        no-op -- the back-translation already rode inside the result.
        """
        win = getattr(self, "win", None)
        if win is None:
            return
        try:
            mode = win.extra_mode()
        except Exception:
            mode = "back"
        if mode == "back":
            return
        if mode == "compare":
            self._compare_render()
            return
        g = self._extra_cfg()
        use_input = g.get("ExtraOutputSource") == "Input"
        source_text = ((getattr(self, "_last_src_text", "") if use_input
                        else getattr(self, "_last_out_text", "")) or "")
        length = g.get("SummaryLength") or "MEDIUM"
        style = g.get("RewriteStyle") or "FORMAL"
        try:
            win.set_extra_text(
                "Summarizing…" if mode == "summary" else "Rewriting…",
                visible=True)
        except Exception:
            pass
        if not source_text.strip():
            try:
                win.set_extra_text("", visible=False)
            except Exception:
                pass
            return

        def work():
            try:
                from qtranslate.services import ai_translate as _AI
                if mode == "summary":
                    out = _AI.summarize(source_text, length)
                else:
                    out = _AI.rewrite(source_text, style)
            except Exception as exc:
                out = "[error] %s" % exc
            try:
                self._on_ui(lambda: self._extra_done(out))
            except Exception:
                pass
        self._spawn("extra-output", work)

    def _extra_done(self, text):
        win = getattr(self, "win", None)
        if win is None:
            return
        try:
            win.set_extra_text(text or "", visible=True)
        except Exception:
            pass

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

    def _spawn_translation(self, name, work):
        """Run at most one selection/translation request at a time."""
        lock = self._translation_lock
        if not lock.acquire(blocking=False):
            return False

        def guarded_work():
            try:
                work()
            finally:
                lock.release()

        try:
            self._spawn(name, guarded_work)
        except Exception:
            lock.release()
            return False
        return True

    def _start_translation(self, text, on_done, apply_rules=False):
        """Run one translation off the UI thread, then hand back the result.

        A second request while one is in flight is DROPPED rather than
        queued: the native does the same (its task queue holds one
        translation), and stacking requests on a slow provider would show
        a burst of stale answers in arbitrary order.
        """
        try:
            if any(t.is_alive() for t in self._threads):
                return False
        except Exception:
            pass

        def work():
            try:
                res = self._translate(
                    text, back_translate=self._back_translation_enabled(),
                    apply_rules=apply_rules)
            except Exception as exc:            # noqa: BLE001
                try:
                    from qtranslate.core import Result
                    res = Result("", "[error] %s" % exc, self.service)
                except Exception:
                    return
            try:
                self._on_ui(lambda: on_done(text, res))
            except Exception:
                pass

        return self._spawn_translation("translate", work)

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

    def push_hist(self, svc, src, res, src_lang=None, tgt_lang=None):
        try:
            from qtranslate import config
            if not bool(config.load().get("General", {}).get(
                    "EnableHistory", True)):
                return
        except Exception:
            pass
        # Slot layout: (service, src, res, fav, src_lang, tgt_lang). The
        # History window owns slot 3 (the favourite flag) and reads
        # entry[:3]; slots 4/5 carry the language pair the entry was
        # translated with so history nav can restore the combos. They
        # ride in memory only -- _save_history still writes [:4], so a
        # persisted entry simply has no pair and nav falls back to the
        # live one (the HistorySnapshot shape is qt-mef's bead).
        # getattr, not attribute access: tests drive push_hist on bare
        # stubs that carry only `history` (regress_enable_history).
        if src_lang is None:
            src_lang = getattr(self, "source", "") or ""
        if tgt_lang is None:
            tgt_lang = getattr(self, "target", "") or ""
        # A translation made while the user is browsing BACK in history
        # forks the timeline: entries after the nav cursor are "future"
        # and must be dropped, the way a browser discards forward
        # history on a new navigation -- keeping them would resurrect
        # stale results on the next step-forward.
        nav_idx = getattr(self, "_nav_idx", None)
        if nav_idx is not None and nav_idx < len(self.history):
            del self.history[nav_idx:]
        self.history.append(
            (svc, src, res, False, src_lang, tgt_lang))
        _save_history(self.history)
        # A fresh translation puts the nav cursor past the newest entry:
        # back walks into history, forward returns to "now". Any browse
        # snapshot is stale now -- the live state it held is gone.
        self._nav_idx = len(self.history)
        self._nav_live = None
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
        # New leaves the history walk: the cursor goes back to "now" so
        # the browsing guard (main_window._browsing_history) cannot stay
        # latched on a pane the user just cleared.
        self._nav_idx = len(getattr(self, "history", []) or [])
        self._nav_live = None
        self.win.src.clear()

    def on_swap(self):
        """Exchange the pair (.tmp SwapLanguagesUseCase).

        The target can never hold auto: when the source is auto the swap
        uses the DETECTED source language instead, and with nothing
        detected yet the swap is a no-op -- there is no concrete language
        to move into the target slot.
        """
        try:
            # .tmp SwapLanguagesUseCase early-returns when the result
            # pane is blank: there is no translation to move back into
            # the input, so the languages do NOT swap either (the
            # main-window audit). Check BEFORE touching the pair.
            win = self.win
            translated = ""
            if win is not None:
                try:
                    translated = win.out.toPlainText().strip()
                    try:
                        from .main_window import EMPTY_RESULT as _ER
                        if translated == _ER:
                            translated = ""
                    except Exception:
                        pass
                except Exception:
                    translated = ""
            if not translated:
                return
            src = self.source
            if src == "auto":
                src = getattr(self, "_detected_src", "") or ""
                if not src:
                    return
            self.source, self.target = self.target, src
            # .tmp clears detectedSourceLanguage on swap: the detection
            # belonged to the pre-swap direction.
            self._detected_src = ""
            if win is not None:
                for combo, code in ((win.cmb_src, self.source),
                                    (win.cmb_tgt, self.target)):
                    try:
                        combo.blockSignals(True)
                        combo.setCurrentText(self._display(code))
                        combo.blockSignals(False)
                    except Exception:
                        pass
            self._persist_language()
            try:
                win.src.setPlainText(translated)
                win.set_result("")
                self._refresh_detected_label()
                self.on_go()
            except Exception:
                pass
        except Exception:
            pass

    def _persist_language(self):
        try:
            config, _engine, _registry = self._core()
            cfg = config.load() or {}
            general = cfg.setdefault("General", {})
            # Save language indices as native expects
            from qtranslate.services.google_translate import SUPPORTED_LANGS
            table = list(SUPPORTED_LANGS)
            try:
                general["LanguageFrom"] = table.index(self.source)
            except Exception:
                pass
            try:
                # Never persist an auto TARGET: the slot is concrete-only,
                # and a bad write here is what poisoned LanguageTo=1.
                general["LanguageTo"] = table.index(
                    self.target if self.target != "auto"
                    else self._default_target_code())
            except Exception:
                pass
            config.save(cfg)
        except Exception:
            pass

    def set_source_by_name(self, name):
        self.source = self._code_of(name)
        self._refresh_detected_label()
        try:
            self._persist_language()
        except Exception:
            pass

    def set_target_by_name(self, name):
        code = self._code_of(name)
        if code == "auto":
            # Auto-detect is source-only (.tmp TO_LANGS). An unrecognised
            # combo name also lands here via _code_of's "auto" fallback --
            # either way the target must stay a concrete language.
            code = self._default_target_code()
        self.target = code
        try:
            self._persist_language()
        except Exception:
            pass

    def _default_target_code(self):
        try:
            from qtranslate.services.google_translate import SUPPORTED_LANGS
            from qtranslate import config as _cfg
            table = list(SUPPORTED_LANGS)
            return table[_cfg.LANG_DEFAULTS["LanguageTo"]]
        except Exception:
            return "vi"

    def switch_service(self, name):
        self.service = name
        self.win.set_service_title(self.service_title())
        # The strip's highlight follows: the operator's report (2168) --
        # clicking a provider switched the service but the buttons kept
        # the FIRST one highlighted forever.
        if hasattr(self.win, "highlight_service"):
            self.win.highlight_service(name)
        try:
            # Persist the pick (General.ActiveService) and detach any
            # active preset -- a manual switch means "custom" now.
            # Preset application writes ActivePresetId AFTER this runs,
            # so apply_preset's ordering stays intact.
            from qtranslate import config as _C, presets as _P
            cfg = _C.load() or {}
            g = cfg.setdefault("General", {})
            g[_P.SERVICE_KEY] = name
            _P.clear_active(cfg)
            _C.save(cfg)
        except Exception:
            pass

    def apply_preset(self, preset):
        """Apply a service preset (.tmp PresetManager.activate).

        Writes translator + comparison set + ActivePresetId, then moves
        the live app: switch_service persists ActiveService (and clears
        the preset marker) BEFORE presets.apply rewrites all three keys,
        so the final state keeps the preset active.
        """
        from qtranslate import config as _C, presets as _P
        try:
            cfg = _C.load() or {}
            probe = _P.apply(cfg, preset)
            if probe is None:
                return False
            translator = probe["translator"]
            if translator in self.ordered_services():
                self.switch_service(translator)
            _P.apply(cfg, preset)
            _C.save(cfg)
            return True
        except Exception:
            return False

    def on_back(self):
        self._nav_history(-1)

    def on_forward(self):
        self._nav_history(+1)

    def _nav_history(self, delta):
        """Walk the session's translation history in the main window.

        Back shows older entries, forward newer ones; stepping past the
        newest restores the LIVE panes. The first step away snapshots
        the live state (texts, service, language pair) so the return
        trip lands exactly where the user left off instead of leaving
        the last-browsed entry on screen (qt-lg6).
        """
        hist = list(getattr(self, "history", []) or [])
        if not hist or self.win is None:
            return
        cur = getattr(self, "_nav_idx", len(hist))
        new = cur + delta
        if new < 0 or new > len(hist):
            return
        if cur == len(hist) and new < len(hist):
            self._nav_live = self._live_snapshot()
        self._nav_idx = new
        if new == len(hist):
            self._restore_live()
            return
        try:
            self._show_history_entry(hist[new])
        except Exception:
            pass

    def _live_snapshot(self):
        """What the live panes show right now, for the return trip."""
        win = self.win
        return {
            "src": win.src.toPlainText() if win is not None else "",
            "out": win.out.toPlainText() if win is not None else "",
            "service": self.service,
            "source": self.source,
            "target": self.target,
        }

    def _apply_nav_pair(self, src, tgt):
        """Point the pair state and combos at (src, tgt).

        Unlike ``set_source_by_name``/``set_target_by_name`` this does
        NOT persist: browsing history is a view change, and rewriting
        Options.json's LanguageFrom/To on every Alt+Left would lose the
        user's real pair to whatever entry they happened to look at.
        Combo signals are blocked so the change handlers cannot fire
        the persisting setters either.
        """
        if tgt == "auto":
            # The target slot is concrete-only (same rule
            # set_target_by_name enforces); a corrupt entry must not
            # put auto back into it.
            tgt = self._default_target_code()
        self.source, self.target = src, tgt
        win = self.win
        if win is None:
            return
        for combo, code in ((getattr(win, "cmb_src", None), src),
                            (getattr(win, "cmb_tgt", None), tgt)):
            if combo is None:
                continue
            try:
                combo.blockSignals(True)
                combo.setCurrentText(self._display(code))
                combo.blockSignals(False)
            except Exception:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass

    def _show_history_entry(self, entry):
        """Restore one history entry: service, pair, and both panes."""
        svc, src, res = entry[:3]
        win = self.win
        # The entry's provider drives the strip highlight and the
        # service title through the same path a strip click takes.
        if svc and svc != self.service:
            try:
                self.switch_service(svc)
            except Exception:
                pass
        # Slots 4/5 (src_lang, tgt_lang) exist only on entries pushed
        # by this session; a persisted triple keeps the current pair.
        src_lang = entry[4] if len(entry) > 4 else ""
        tgt_lang = entry[5] if len(entry) > 5 else ""
        if src_lang or tgt_lang:
            self._apply_nav_pair(src_lang or self.source,
                                 tgt_lang or self.target)
        # Signals blocked: the panes' textChanged would arm the
        # instant-translation debounce for text the user is only
        # browsing (_browsing_history already guards the fire, but a
        # blocked write never arms it at all).
        try:
            win.src.blockSignals(True)
            win.out.blockSignals(True)
            win.src.setPlainText(str(src))
            win.set_result(str(res))
        finally:
            try:
                win.src.blockSignals(False)
                win.out.blockSignals(False)
            except Exception:
                pass

    def _restore_live(self):
        """Step forward past the newest entry: the live state returns."""
        snap = getattr(self, "_nav_live", None)
        self._nav_live = None
        if not snap:
            return
        win = self.win
        if win is None:
            return
        try:
            if snap.get("service") and snap["service"] != self.service:
                self.switch_service(snap["service"])
            self._apply_nav_pair(snap.get("source") or self.source,
                                 snap.get("target") or self.target)
            win.src.blockSignals(True)
            win.out.blockSignals(True)
            win.src.setPlainText(snap.get("src") or "")
            win.set_result(snap.get("out") or "")
        finally:
            try:
                win.src.blockSignals(False)
                win.out.blockSignals(False)
            except Exception:
                pass

    def open_dictionary(self):
        from .dictionary import DictionaryWindow
        self._dict = DictionaryWindow(self)
        # The popup's dictionary button stashes the looked-up word in
        # _dict_word -- consume it so the window opens with a live
        # search instead of an empty field the user must retype.
        word = getattr(self, "_dict_word", "") or ""
        self._dict_word = ""
        if word:
            try:
                self._dict.inp.setText(word)
                self._dict.do_search()
            except Exception:
                pass
        self._dict.show()

    def open_image_search(self, term=""):
        """Open the image search dialog (Wikimedia Commons).

        Native seeds the dialog with the source pane's text when it is
        a single word and opens it empty otherwise -- same rule
        ``showImageSearchDialog`` uses in MainAppFrame.kt.
        """
        from .image_search import open_image_search
        if not (term or "").strip():
            term = self._image_search_term()
        self._img_search = open_image_search(self, term=term)
        self._img_search.show()
        return self._img_search

    def _image_search_term(self):
        """Single-word seed for the image search dialog, or "".

        The source pane's text wins when it is one word; a multi-word
        input opens the dialog empty, exactly like native's
        ``inputText.trim().takeIf { !it.contains(' ') }``.
        """
        try:
            win = self.win
            text = (win.src.toPlainText() or "").strip()
        except Exception:
            text = ""
        return text if text and " " not in text and "\n" not in text \
            else ""

    def open_history(self):
        from .history_window import HistoryWindow
        self._hist = HistoryWindow(self)
        self._hist.show()

    def open_document_translation(self, path=None):
        """TrayPopupMenu.translateDocument / document drop: one reused
        dialog like upstream's lazy documentTranslationDialog."""
        from .document_dialog import DocumentTranslationDialog
        dlg = getattr(self, "_doc_dlg", None)
        if dlg is None:
            dlg = DocumentTranslationDialog(self)
            self._doc_dlg = dlg
        if path:
            dlg.open_with(path)
        else:
            dlg.open()

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
        # The configured pair is LanguageFrom/LanguageTo INDICES into
        # the shared SupportedLanguages table -- the same keys
        # _load_session and _persist_language use (the old code read
        # SourceLanguage/TargetLanguage, which nothing writes).
        try:
            from qtranslate.services.google_translate import \
                SUPPORTED_LANGS
            table = list(SUPPORTED_LANGS)
            fi = int(general.get(
                "LanguageFrom", config.LANG_DEFAULTS["LanguageFrom"]))
            ti = int(general.get(
                "LanguageTo", config.LANG_DEFAULTS["LanguageTo"]))
            src = self._display(table[fi]) if 0 <= fi < len(table) \
                else "Auto-Detect"
            tgt = self._display(table[ti]) if 0 <= ti < len(table) \
                else "English"
        except Exception:
            src, tgt = "Auto-Detect", "English"
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
        region picker belongs to the front end. The .tmp snipping tool
        floats an action row over the selection -- Translate, Copy
        Text, Copy Image, Save Image -- so the picker gets all four."""
        from .ocr_pick import RegionPicker, grab_pixmap, grab_rect

        def _picked(rect):
            if rect is None:
                return
            try:
                data = grab_rect(rect)
            except Exception as exc:            # noqa: BLE001
                self.win.render("[ocr error] %s" % exc)
                return
            self.ocr_bytes(data)

        def _copy_text(rect):
            try:
                data = grab_rect(rect)
            except Exception:
                return
            key, code = self._ocr_settings()
            try:
                from qtranslate.services.ocr import (ocr_language,
                                                     ocr_text)
                text = ocr_text(data, api_key=key,
                                lang=ocr_language(code))
            except Exception:
                return
            if text:
                from PySide6.QtWidgets import QApplication
                QApplication.clipboard().setText(text)

        def _copy_image(rect):
            try:
                from PySide6.QtWidgets import QApplication
                QApplication.clipboard().setPixmap(grab_pixmap(rect))
            except Exception:
                pass

        def _save_image(rect):
            try:
                data = grab_rect(rect)
            except Exception:
                return
            self._save_ocr_png(data)

        picker, _result = RegionPicker.pick(actions={
            "Translate": lambda r: _picked(r),
            "Copy Text": _copy_text,
            "Copy Image": _copy_image,
            "Save Image": _save_image,
        })
        picker._picked = lambda r: None if r is None else _picked(r)

    def _ocr_settings(self):
        """(api_key, google-lang-code) for the OCR service, shared by
        the window flow and the picker's Copy Text action."""
        try:
            cfg = self._core()[0].load()
        except Exception:
            cfg = {}
        key = (cfg.get("Advanced", {}) or {}).get(
            "OcrApiKey", "") or "helloworld"
        index = (cfg.get("Ocr", {}) or {}).get("OcrLanguage", 17)
        try:
            from qtranslate.services.google_translate import SUPPORTED_LANGS
            table = list(SUPPORTED_LANGS)
        except Exception:
            table = []
        code = table[index] if 0 <= index < len(table) else "en"
        return key, code

    @staticmethod
    def _save_ocr_png(data: bytes):
        """Write OCR grab PNGs under Ocr.SaveImagePath (or ~)."""
        import datetime as _dt
        import os as _o
        _dir = _o.path.expanduser("~")
        try:
            from qtranslate import config as _C
            _dir = _C.load().get(
                "Ocr", {}).get("SaveImagePath", "") or _dir
        except Exception:
            pass
        _fn = "ocr_%s.png" % _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(_o.path.join(_dir, _fn), "wb") as _fh:
            _fh.write(data)

    def ocr_bytes(self, data: bytes):
        """OCR an image and show the text in the result pane."""
        # Keep the grab as a pixmap so the result window's Copy/Save
        # image items have something real to move.
        try:
            from PySide6.QtGui import QImage, QPixmap
            img = QImage()
            if img.loadFromData(data):
                self._ocr_image = QPixmap.fromImage(img)
        except Exception:
            self._ocr_image = None
        key, code = self._ocr_settings()

        def work():
            # ocr.space is a network upload -- it must not hold the UI
            # thread (the OCR audit's Critical: the app froze for the
            # whole request). Result crosses back via _on_ui.
            try:
                from qtranslate.services.ocr import (ocr_language,
                                                     ocr_text)
                # The service takes its OWN 3-letter codes (eng, vie,
                # rus...), not Google's 2-letter ones.
                text = ocr_text(data, api_key=key,
                                lang=ocr_language(code))
            except Exception as exc:            # noqa: BLE001
                self._on_ui(lambda e=exc: (
                    self.win.render("[ocr error] %s" % e)
                    if self.win is not None else None))
                return
            self._on_ui(lambda t=text: self._ocr_done(t))
        import threading
        threading.Thread(target=work, daemon=True,
                         name="qtranslate-ocr").start()

    def _ocr_done(self, text: str):
        # The result goes to native's own OCR window (menu 10's host),
        # which the region picker used to skip by writing straight into
        # the main result pane. The main pane keeps its old content.
        # One window, reused: a fresh OcrResultWindow per OCR orphaned
        # the previous one (hidden reference dropped, window stayed up
        # forever with stale text).
        try:
            from .ocr_window import OcrResultWindow
            win = getattr(self, "_ocr", None)
            if win is None:
                win = OcrResultWindow(self)
                self._ocr = win
            win._image = getattr(self, "_ocr_image", None)
            win.set_text(text)
            win.show()
            win.raise_()
            win.activateWindow()
        except Exception:
            if self.win is not None:
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
            from .hotkeys import uninstall
            uninstall()
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
        """Keep the low-level mouse hook installed whenever it can be.

        The hook does two jobs: selection capture (mouse mode ON) and
        click-outside dismissal for the popup/icon (needed in EVERY
        mode -- a Ctrl+Q-only install still has to close the popup when
        the user clicks elsewhere, which is exactly the state where the
        hook used to be switched off). The hook therefore stays up even
        with capture off; ``_mouse_selected`` gates the capture side on
        the mode itself.
        """
        try:
            from qtranslate import mouse_capture as mc
        except Exception:
            return
        try:
            if not self._mouse_hook:
                mc.start(self._mouse_selected,
                         on_click=self._mouse_pressed)
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
        """The hook's callback: a selection drag released at (x, y).

        The hook proc must return fast, so the capture and the
        translation run on a worker thread and the result comes back
        through the bridge. The hook is installed even with mouse mode
        OFF (it also feeds click-outside dismissal), so the capture
        side is gated here on the mode itself.
        """
        if self._mouse_mode_off():
            return
        import threading
        threading.Thread(target=self._mouse_work, args=(x, y),
                         daemon=True).start()

    def _mouse_pressed(self, x, y):
        """Every allowed left-down, drag or not (.tmp onPointerPressed).

        The floating icon and the popups dismiss on a press OUTSIDE
        them; a press inside the icon is its own click and must not
        hide it first.
        """
        # .tmp PopupDismissalPolicy: a press outside the popup closes it
        # (the Qt eventFilter can only see clicks inside our own
        # windows; the global mouse hook sees every press). This check
        # must NOT sit behind the icon early-return -- a pinned popup
        # also survives the outside press.
        try:
            pop = getattr(self, "_popup", None)
            if (pop is not None and pop.isVisible()
                    and not getattr(pop, "_pinned", False)):
                g = pop.geometry()
                if not (g.left() <= x <= g.right()
                        and g.top() <= y <= g.bottom()):
                    self._on_ui(pop.hide)
        except Exception:
            pass
        try:
            icon = getattr(self, "_mouse_icon", None)
            if icon is None or not icon.is_showing():
                return
            if icon.contains_point(x, y):
                return
            # The tap sees this press BEFORE Qt delivers the click to
            # the icon. Dismissing synchronously raced _clicked: a press
            # ON the icon could be judged outside (or the dismiss landed
            # first), clearing _text so the click translated nothing --
            # "click icon, it just vanishes". Defer the outside-dismiss
            # one beat: a real icon click hides the icon itself inside
            # _clicked, and the deferred check then sees it gone.
            def _defer_dismiss(icon=icon, x=x, y=y):
                try:
                    if icon.is_showing() and not icon.contains_point(x, y):
                        icon.dismiss()
                except Exception:
                    pass
            self._on_ui(lambda: QTimer.singleShot(100, _defer_dismiss))
        except Exception:
            pass

    # Native's anti-loop, decompiled 2026-10-24 (FUN_004193f6 +
    # FUN_004183bd): a capture is DROPPED unless enough time has passed
    # since the last one (its FUN_0050bc60() > 10.0 branch) and no task
    # is already running. The port fires the hook on every plain click,
    # so without this gate every click re-queued a popup ("loop auto
    # translate cực nghiêm trọng", the operator's report).
    # 1.5s, not native's 10: the operator re-selects right after a
    # translation and the icon never came back ("bôi đen lại không có
    # icon", 2026-10-24). The no-task gate below carries most of the
    # anti-loop weight anyway.
    MOUSE_CAPTURE_COOLDOWN = 1.5

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
            # .tmp SELECTION_SETTLE_DELAY_MS: the source app needs a
            # beat to finish writing the selection before the copy is
            # synthesized.
            import time as _t
            _t.sleep(0.08)
            _dbg("mouse_work: enter (%d,%d) front=%s" % (x, y,
                                                        _frontmost()))
            if not self._mouse_capture_allowed_now():
                _dbg("mouse_work: gated (cooldown/task)")
                return
            _dbg("mouse_work: pre-gate front=%s" % _frontmost())
            text = self._capture_selection(x, y)
            _dbg("mouse_work: captured len=%d front=%s"
                 % (len(text or ""), _frontmost()))
            if not text:
                _dbg("mouse_work: no captured text at (%d,%d)" % (x, y))
                return
            # .tmp SelectionBehaviorRouter: the mode decides what the
            # captured selection DOES -- "Show icon" pops the button
            # and waits for its click; "Show translation" opens the
            # popup at once; "...and read" translates AND speaks the
            # result. (Native's TaskShowIcons/TaskShowPopupWindow split,
            # decompiled FUN_004183bd, routes the same three ways.)
            idx = self._mouse_mode_index()
            if idx == 0:
                self._on_ui(lambda: self._show_mouse_icon(x, y, text))
            else:
                self._translate_captured(text, speak=(idx == 2))
        except Exception:
            pass

    def _show_mouse_icon(self, x, y, text):
        """The floating translate button (UI thread), every mode."""
        try:
            from .mouse_icon import MouseIcon
            icon_win = getattr(self, "_mouse_icon", None)
            if icon_win is None:
                icon_win = MouseIcon(self, self._translate_captured)
                self._mouse_icon = icon_win
            icon_win.pop(x, y, text)
            # Length only -- the selection text itself is user data and
            # must never land in a world-readable log (AGENTS.md rule).
            _dbg("icon popped at (%d,%d) len=%d front=%s"
                 % (x, y, len(text or ""), _frontmost()))
            # Post-pop state: distinguishes z-order/opacity/geometry
            # failures -- all three looked identical in the logs.
            try:
                QTimer.singleShot(300, lambda w=icon_win: _dbg(
                    "icon state visible=%s geo=%s opacity=%.2f"
                    % (w.isVisible(), w.geometry().getRect(),
                       w._opacity.opacity())))
            except Exception:
                pass
        except Exception:                   # noqa: BLE001 -- fail-open
            pass

    def _translate_captured(self, text, speak=False):
        """Translate captured selection text and show the popup.

        Called by the floating icon's click (icon mode) and directly by
        the drag release in the "Show translation" modes. ``speak`` is
        mode 2's read-aloud: .tmp's selectionReadSource picks WHICH
        text is spoken -- TRANSLATION (default) reads the result after
        it lands, SOURCE reads the captured selection immediately in
        the source language while the translation still runs.
        """
        if speak and self._read_source() == "source":
            try:
                lang = (self.source if self.source != "auto"
                        else (getattr(self, "_detected_src", "") or ""))
                self._speak(text, lang)
            except Exception:
                pass
            speak = False
        try:
            self._on_ui(lambda t=text: self._popup_loading(t))
        except Exception:
            pass
        def done(t, res):
            try:
                _dbg("icon-click done: ok=%s len=%d provider=%s"
                     % (res.ok, len(res.text or ""), res.provider_used))
            except Exception:
                pass
            # Terminal state always renders: a failed request shows the
            # failure text in the popup instead of leaving the loading
            # marker/popup stranded (.tmp publishes translationFailed
            # and still reaches a render).
            try:
                self._on_ui(lambda: self.show_translation(
                    t, res.text or "Translation failed",
                    provider=res.provider_used))
            except Exception:
                try:
                    self.show_translation(
                        t, res.text or "Translation failed",
                        provider=res.provider_used)
                except Exception:
                    pass
            try:
                pop = getattr(self, "_popup", None)
                _dbg("popup after show: %s visible=%s"
                     % (pop is not None,
                        pop.isVisible() if pop else "-"))
            except Exception:
                pass
            if res.ok and res.text and speak:
                try:
                    self._speak(res.text)
                except Exception:
                    pass
        try:
            started = self._start_translation(text, done)
            _dbg("icon-click: start=%s len=%d" % (started, len(text or "")))
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
            elif sys.platform == "darwin":
                # No ``keyboard`` package on macOS; read the real HID
                # modifier state through CoreGraphics instead.
                try:
                    from qtranslate import macos_input
                    if not macos_input.control_held():
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
        """The selection the drag swept -- native's own mouse capture.

        NATIVE (decompiled 2026-10-24): TaskShowIcons.run ->
        FUN_004543c6 -> **FUN_0043bf30**, the same copy-capture engine
        the Ctrl+Q hotkey uses (synthesize Ctrl+C, poll the clipboard's
        sequence number with the 8ms..320ms backoff), then a trim. The
        engine is safe HERE because the only way in is a selection
        DRAG's release -- the selection exists, so the Ctrl+C the
        engine sends changes the clipboard for real. A plain click
        never reaches this function (the hook fires nothing for it),
        which is what keeps a clipboard manager's sequence chatter from
        reading as "a selection" on every click.

        The gates are native's (see _mouse_gate_ok).
        """
        if not self._mouse_gate_ok():
            _dbg("mouse_work: gate_ok=False")
            return ""
        from qtranslate import selection
        text = (selection.copy_selection() or "").strip()
        if not text:
            try:
                _dbg("mouse_work: capture empty reason=%s"
                     % selection.last_reason())
            except Exception:
                pass
        return text

    def quit(self):
        # General.ClearHistoryOnExit (Basics page) -- consumed here so
        # the setting finally does what its checkbox promises.
        try:
            from qtranslate import history as _hist
            _hist.clear_history_on_exit(self)
        except Exception:
            pass
        self._persist_contents()
        self.qapp.quit()

    # ------------------------------------------------- Contents.* persist
    #
    # Native keeps the editor contents across sessions in three separate
    # Options.json fields -- Contents.EditSource, Contents.EditTranslation
    # and Contents.EditBackTranslation, each truncated to 5000 chars on
    # save (D10 spotcheck). The port's back-translation lives in its own
    # pane, so the three fields map one-to-one onto src/out/back.
    _CONTENTS_LIMIT = 5000

    def _persist_window_state(self):
        """Record whether the main window was visible at quit -- the
        "Restore previous state" startup action (menu 1 item 88) reads
        ``General.LastWindowVisible`` on the next start. Runs on EVERY
        quit path, independent of SaveContentsOnExit."""
        try:
            from qtranslate import config as _C
            win = getattr(self, "win", None)
            visible = bool(win is not None and win.isVisible())
            cfg = _C.load() or {}
            cfg.setdefault("General", {})["LastWindowVisible"] = visible
            _C.save(cfg)
        except Exception:
            pass

    def _contents_enabled(self):
        """Menu-1 item 62 "Save contents on exit"
        (``General.SaveContentsOnExit``, default on -- the behaviour
        before the toggle existed)."""
        try:
            from qtranslate import config as _C
            return bool((_C.load() or {}).get("General", {})
                        .get("SaveContentsOnExit", True))
        except Exception:
            return True

    def _persist_contents(self):
        win = getattr(self, "win", None)
        if win is None or not self._contents_enabled():
            return
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            contents = cfg.setdefault("Contents", {})
            def _clip(w):
                try:
                    return (w.toPlainText() or "")[:self._CONTENTS_LIMIT]
                except Exception:
                    return ""
            contents["EditSource"] = _clip(getattr(win, "src", None))
            contents["EditTranslation"] = _clip(getattr(win, "out", None))
            # EditBackTranslation belongs to the "back" extra mode --
            # in the AI modes the pane holds a derived summary/rewrite
            # that must not be persisted as a back-translation.
            try:
                _mode = win.extra_mode()
            except Exception:
                _mode = "back"
            if _mode == "back":
                contents["EditBackTranslation"] = _clip(
                    getattr(win, "back", None))
            _C.save(cfg)
        except Exception:
            pass

    def _restore_contents(self):
        """Put Contents.* back into the panes on boot."""
        win = getattr(self, "win", None)
        if win is None or not self._contents_enabled():
            return
        try:
            from qtranslate import config as _C
            contents = (_C.load() or {}).get("Contents", {}) or {}
            src = contents.get("EditSource") or ""
            trans = contents.get("EditTranslation") or ""
            back = contents.get("EditBackTranslation") or ""
            if not (src or trans or back):
                return
            if src:
                win.src.setPlainText(src)
            if trans or back:
                win.out.setPlainText(trans)
                try:
                    _mode = win.extra_mode()
                except Exception:
                    _mode = "back"
                if _mode == "back" and back:
                    win.back.setPlainText(back)
                    try:
                        win.set_extra_visible(True)
                    except Exception:
                        win.back.setVisible(True)
        except Exception:
            pass

    # ------------------------------------------------------------ spell check
    #
    # .tmp MainStore collects spellCheckInputs(state, isSpellCheckingEnabled)
    # and runs PerformSpellCheckUseCase on every input change; the source
    # pane's context menu then offers "Spelling suggestions" for the
    # correction under the cursor. The port debounces the same way the
    # instant-translation observer does and keeps the result list on the
    # app so the menu can reach it.

    def _read_source(self):
        """General.SelectionReadSource (.tmp selectionReadSource):
        which text mouse-mode-3 reads aloud -- "source" or
        "translation" (the default, and the only pre-feature value)."""
        try:
            from qtranslate import config as _C
            v = str((_C.general_setting("SelectionReadSource", "")
                     or "")).strip().lower()
            return "source" if v == "source" else "translation"
        except Exception:
            return "translation"

    def _spell_check_enabled(self):
        try:
            from qtranslate import config as _C
            return bool((_C.load() or {}).get("General", {})
                        .get("SpellChecking", True))
        except Exception:
            return True

    def _schedule_spell_check(self):
        """src.textChanged -> debounce -> _run_spell_check
        (AppConstants.SPELL_CHECK_DEBOUNCE_MS = 750)."""
        try:
            if self._spell_timer is None:
                from PySide6.QtCore import QTimer
                self._spell_timer = QTimer(self.qapp)
                self._spell_timer.setSingleShot(True)
                self._spell_timer.setInterval(750)
                self._spell_timer.timeout.connect(self._run_spell_check)
            self._spell_timer.start()
        except Exception:
            pass

    def _spell_lang(self):
        """Resolved source language for the check: detected beats the
        AUTO slot, exactly like resolvedSourceLanguage upstream --
        which then falls back to the USER's locale (and its base
        language) when nothing is known."""
        det = getattr(self, "_detected_src", "") or ""
        if det and det != "auto":
            return det
        src = getattr(self, "source", "auto") or "auto"
        if src != "auto":
            return src
        try:
            import locale as _loc
            tag = (_loc.getlocale()[0] or "").replace("_", "-")
            if tag and tag != "und":
                return tag
        except Exception:
            pass
        return ""

    def _run_spell_check(self):
        win = getattr(self, "win", None)
        if win is None:
            return
        text = ""
        try:
            text = win.src.toPlainText() or ""
        except Exception:
            pass
        if not self._spell_check_enabled() or not text.strip():
            self._spell_corrections = []
            return
        lang = self._spell_lang()

        class _Sig(QObject):
            done = Signal(object)
        if self._spell_sig is None:
            self._spell_sig = _Sig()
            self._spell_sig.done.connect(self._spell_done)
        sig = self._spell_sig

        def work():
            try:
                # .tmp runs the system-services spell backends as the
                # SpellChecker role; port prefers the on-device macOS
                # NSSpellChecker (private, no key) and falls back to
                # the Bing spell endpoint when it is unavailable.
                # General.PreferredServices.spell promotes one backend.
                backends = []
                try:
                    from qtranslate.services import system_spell as SS
                    backends.append(("system", lambda: SS.check(
                        text, lang or "en")))
                except Exception:
                    pass
                try:
                    from qtranslate.services import bing_spell as BS
                    backends.append(("bing", lambda: BS.check(
                        text, lang or "en")))
                except Exception:
                    pass
                try:
                    from qtranslate.services import google_spell as GS
                    backends.append(("google", lambda: GS.check(
                        text, lang or "en")))
                except Exception:
                    pass
                try:
                    from qtranslate.services import ai_translate as AI
                    backends.append(("ai", lambda: AI.spell_check(
                        text, lang or "")))
                except Exception:
                    pass
                try:
                    from qtranslate import config as _C
                    pref = ((_C.general_setting("PreferredServices", {})
                             or {}).get("spell") or "")
                except Exception:
                    pref = ""
                backends.sort(key=lambda kv: kv[0] != pref)
                res = None
                for _name, fn in backends:
                    try:
                        res = fn()
                    except Exception:
                        res = None
                    if res is not None:
                        break
                sig.done.emit((res or {}).get("corrections") or [])
            except Exception:
                sig.done.emit([])
        import threading
        threading.Thread(target=work, daemon=True).start()

    def _spell_done(self, corrections):
        # Drop stale results: the text may have changed while Bing
        # answered -- re-check against the live pane before storing.
        win = getattr(self, "win", None)
        if win is None:
            return
        try:
            live = win.src.toPlainText() or ""
        except Exception:
            live = ""
        if not live.strip() or not self._spell_check_enabled():
            self._spell_corrections = []
            return
        self._spell_corrections = list(corrections or [])

    def spell_correction_at(self, pos):
        """The correction covering ``pos`` in the source text, or None."""
        for c in self._spell_corrections:
            try:
                if c["startIndex"] <= pos < c["endIndex"]:
                    return c
            except Exception:
                continue
        return None

    def apply_spell_correction(self, correction, suggestion):
        """MainIntent.ApplyCorrection: swap the span for the suggestion
        and clear the list -- upstream clears spellCheckCorrections on
        apply so the menu rebuilds from the next check."""
        win = getattr(self, "win", None)
        if win is None or not correction:
            return
        try:
            cur = win.src.textCursor()
            cur.setPosition(int(correction["startIndex"]))
            cur.setPosition(int(correction["endIndex"]),
                            cur.MoveMode.KeepAnchor)
            cur.insertText(suggestion or "")
            win.src.setTextCursor(cur)
        except Exception:
            pass
        self._spell_corrections = []
        self._schedule_spell_check()

    # ------------------------------------------------------- the hotkeys
    def _clipboard_text(self) -> str:
        try:
            import pyperclip
            return (pyperclip.paste() or "").strip()
        except Exception:
            return ""

    def _translation_rules(self):
        """General.TranslationRules -> {source_code: target_code}.

        .tmp Configuration.translationRules: per-source-language forced
        target, applied by TranslateTextUseCase (the MAIN workspace --
        quick translate uses TranslateStringUseCase and skips rules).
        Entries are {"source","target"} dicts or [src, tgt] pairs."""
        out = {}
        try:
            rules = self._extra_cfg().get("TranslationRules") or []
        except Exception:
            return out
        for r in rules:
            try:
                if isinstance(r, dict):
                    s, t = r.get("source"), r.get("target")
                else:
                    s, t = (list(r) + [None, None])[:2]
            except Exception:
                continue
            if s and t:
                out[str(s)] = str(t)
        return out

    def _rule_target(self, src_code):
        rules = self._translation_rules()
        if not rules or not src_code:
            return None
        return (rules.get(src_code)
                or rules.get(src_code.split("-", 1)[0])
                or rules.get(src_code.split("_", 1)[0]))

    def _translate(self, text: str, back_translate: bool = False,
                   apply_rules: bool = False):
        """Translate a piece of text with the current service and pair.

        ``back_translate`` is opt-in per call site: only the main-window
        task honours General.BackTranslation. The popup and Alt+W paths
        must NOT get it -- Alt+W types ``res.text`` verbatim into the
        target app, so an appended back-translation would be typed too.

        ``apply_rules`` opts into .tmp TranslationRule resolution
        (TranslateTextUseCase only): an explicit source pre-resolves
        the target before the request; an AUTO source re-resolves from
        the detected language and re-translates once when a rule
        changes the target.
        """
        from qtranslate import engine
        service = self.service
        try:
            # A disabled provider must not serve even as the PRIMARY --
            # ordered_services() already applies DisabledServices, so a
            # service missing from it falls back to the first enabled.
            enabled = self.ordered_services()
            if enabled and service not in enabled:
                service = enabled[0]
        except Exception:
            pass
        target = self.target
        if apply_rules and self.source != "auto":
            rt = self._rule_target(self.source)
            if rt:
                target = rt
        res = engine.translate(service, text[:5000], target,
                               self.source, back_translate=back_translate)
        if apply_rules and self.source == "auto":
            try:
                det = res.source_language_code or ""
            except Exception:
                det = ""
            rt = self._rule_target(det)
            if rt and rt != target:
                # Upstream handleReTranslation + targetLanguage state
                # update: re-translate to the rule's target and move
                # the target combo with it (UI side applied in
                # _show_main_result via _pending_rule_target).
                self._pending_rule_target = rt
                res = engine.translate(service, text[:5000], rt,
                                       det or self.source,
                                       back_translate=back_translate)
        # The concrete source auto-detect resolved to -- the swap use
        # case (.tmp) needs it to give the target slot a real language.
        try:
            self._detected_src = res.source_language_code or ""
        except Exception:
            pass
        self._refresh_detected_label()
        return res

    def _refresh_detected_label(self):
        """Show the detected source inside the AUTO combo.

        .tmp LanguageComboBox renders ``"English (Auto-Detect)"`` -- the
        detected language's display name followed by the auto label --
        whenever the source slot is AUTO and a detection exists. The
        pseudo-item is managed: exactly one at a time, removed when the
        source slot leaves AUTO or the detection changes.
        """
        win = getattr(self, "win", None)
        combo = getattr(win, "cmb_src", None) if win else None
        if combo is None:
            return
        detected = getattr(self, "_detected_src", "") or ""
        is_auto = getattr(self, "source", "") == "auto"
        label = ("%s (Auto-Detect)" % self._display(detected)
                 if is_auto and detected else "Auto-Detect")
        try:
            combo.blockSignals(True)
            prev = getattr(self, "_detected_label", None)
            if prev and prev != label:
                i = combo.findText(prev)
                if i >= 0:
                    combo.removeItem(i)
            if not is_auto:
                # A concrete source shows its own name -- the refresh
                # only manages the AUTO slot's pseudo-item.
                self._detected_label = None
                return
            if label != "Auto-Detect" and combo.findText(label) < 0:
                combo.addItem(label)
            idx = combo.findText(label)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            self._detected_label = label if label != "Auto-Detect" else None
        except Exception:
            pass
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass

    def _back_translation_enabled(self) -> bool:
        """General.BackTranslation (native menu 1/30): append the
        translation-of-translation section to main-window results."""
        try:
            from qtranslate import config
            return bool((config.load() or {}).get("General", {})
                        .get("BackTranslation", False))
        except Exception:
            return False

    def popup_lang_changed(self, which, name):
        """Quick popup language pickers (.tmp onSourceLanguageSelected
        / onTargetLanguageSelected): update the pair, persist the
        preferred languages, sync the main window's combos, and
        retranslates the popup's stored text (RetranslateQuickTranslate).
        """
        code = self._code_of(name or "")
        if which == "src":
            self.source = code or "auto"
        else:
            # The target combo never offers auto (.tmp's target
            # LanguageComboBox excludes it the same way).
            if code in ("", "auto"):
                code = self.target
            self.target = code
        try:
            # LanguageFrom/LanguageTo IS the port's preferred* pair --
            # the same "remember the last choice" upstream writes.
            self._persist_language()
            self._refresh_language_combos()
            self._refresh_detected_label()
        except Exception:
            pass
        self._popup_retranslate()

    def popup_swap(self):
        """Quick popup swap (.tmp onSwapLanguages -> SwapLanguages +
        RetranslateQuickTranslate): AUTO source uses the detected
        language, same rule as the main window's on_swap."""
        src = self.source
        if src == "auto":
            src = getattr(self, "_detected_src", "") or ""
            if not src:
                return
        self.source, self.target = self.target, src
        self._detected_src = ""
        try:
            self._persist_language()
            self._refresh_language_combos()
            self._refresh_detected_label()
            pop = getattr(self, "_popup", None)
            if pop is not None:
                pop.sync_languages()
        except Exception:
            pass
        self._popup_retranslate()

    def _popup_retranslate(self):
        """Retranslate the popup's stored source with the current pair
        (.tmp RetranslateQuickTranslate -> TranslateTextUseCase
        QUICK)."""
        text = getattr(self, "_popup_src_full", "") or ""
        if not text.strip():
            return
        try:
            self._translate_captured(text)
        except Exception:
            pass

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

    def _popup_loading(self, text):
        """.tmp's loading state: the popup opens with a spinner as soon
        as the selection text is captured, while the translation is
        still in flight -- the user gets immediate feedback instead of
        a dead-feeling delay."""
        try:
            # .tmp withholds the popup entirely and shows a small
            # pointer-following marker instead -- opening the full
            # popup here meant sub-second translations replaced the
            # "Translating…" state before it ever painted a frame.
            # The in-popup spinner is gone too: the external marker is
            # the single loading surface (operator feedback).
            mark = getattr(self, "_loading_mark", None)
            if mark is None:
                from .loading_indicator import LoadingIndicator
                # No parent: QtApp is not a QWidget, and this is a
                # top-level window anyway. Passing `self` crashed with
                # TypeError and the marker never appeared.
                mark = LoadingIndicator()
                self._loading_mark = mark
            mark.show_at_cursor()
            _dbg("loading marker shown (popup deferred)")
        except Exception as exc:
            try:
                _dbg("popup loading err %r" % (exc,))
            except Exception:
                pass

    def _loading_hide(self):
        """Dismiss the cursor marker; the 350 ms minimum lives inside
        ``LoadingIndicator.hide`` so a fast result still leaves the
        marker perceptible (.tmp's MINIMUM_VISIBLE_MS)."""
        try:
            mark = getattr(self, "_loading_mark", None)
            if mark is not None:
                mark.hide()
        except Exception:
            pass

    def show_translation(self, text, result, provider: str = "",
                         origin: str = "quick"):
        """Show one POPUP translation: history and the popup window.

        Quick-translate (Ctrl+Q, the mouse icon, the clipboard hotkey)
        is a separate surface from the main window -- .tmp's
        QuickTranslateDialog never writes MainState.inputText /
        translatedText, and neither does native's popup. Writing the
        panes here used to dump every Ctrl+Q answer into the main
        window, which is the "dịch tự điền vào main screen" bug. The
        main window's own Translate button goes through
        ``_show_main_result`` instead.
        """
        try:
            try:
                _dbg("show_translation called len=%d" % len(result or ""))
            except Exception:
                pass
            try:
                self.push_hist(self.service, text[:2000], result[:4000])
                self._maybe_auto_copy(result, origin)
            except Exception:
                pass
            try:
                from .popup import PopupWindow
                # REUSE one popup. Creating a fresh PopupWindow per
                # translation and dropping the old wrapper let Qt GC a
                # top-level widget with a pending QTimer -- the
                # activateTimers->sendEvent SIGBUS that killed the app
                # after a few Ctrl+Q in a row. Native keeps one popup
                # window too.
                pop = getattr(self, "_popup", None)
                if pop is None:
                    pop = PopupWindow(self)
                    self._popup = pop
                pop.set_text(text[:300], result,
                             self.popup_pair(provider),
                             provider=provider or self.service)
                # .tmp QuickTranslateDialog retranslates inputText on
                # language/swap changes -- keep the FULL source (the
                # widget only displays the first 300 chars).
                self._popup_src_full = text
                try:
                    pop.sync_languages()
                except Exception:
                    pass
                self._popup_inline_definition(text, result)
                # .tmp quickTranslationComparisonPolicy: quick compare
                # is independent of the layout preset.
                try:
                    self._popup_compare(text)
                except Exception:
                    pass
                try:
                    _dbg("popup set_text done, placing")
                except Exception:
                    pass
                pop.place()
                try:
                    pop.raise_()
                    pop.show()
                    if pop._auto_focus():
                        pop.activateWindow()
                        pop.setFocus()
                    try:
                        _dbg("popup shown visible=%s geo=%s"
                             % (pop.isVisible(),
                                pop.geometry().getRect()))
                    except Exception:
                        pass
                except Exception as exc:
                    try:
                        _dbg("popup show err %r" % (exc,))
                    except Exception:
                        pass
                    try:
                        pop.show()
                    except Exception:
                        pass
            except Exception as e:
                try:
                    _dbg("show_translation err %s" % e)
                except Exception:
                    pass
            finally:
                # Result (or failure text) reached a terminal state --
                # release the cursor marker. hide() enforces .tmp's
                # 350 ms minimum so even instant translations leave a
                # perceptible loading beat.
                self._loading_hide()
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

        Operator rule (2026-11-07): the selection-translate triggers are
        one-or-the-other -- while the mouse-capture mode is ON (icon /
        translate-on-select), Ctrl+Q is inert. It only works when the
        user has switched mouse capture OFF and drives selection
        translate by hotkey alone."""
        try:
            if not self._mouse_mode_off():
                _dbg("hotkey_popup: mouse mode on, hotkey muted")
                return
            _dbg("hotkey_popup triggered")
        except Exception:
            pass
        def work():
            try:
                # Native gates the selection hotkeys on the foreground
                # app too (the Exceptions list is not mouse-mode-only --
                # the exceptions-page audit): an excluded app must not
                # get its selection copied out from under it.
                from qtranslate import exclusions as _ex
                if _ex.foreground_excluded():
                    _dbg("hotkey_popup: foreground excluded, skip")
                    return
                from qtranslate import selection
                text = ""
                try:
                    text = (selection.copy_selection() or "").strip()
                    try:
                        _dbg("hotkey_popup copied text len=%d" % len(text))
                    except Exception:
                        pass
                except Exception:
                    text = ""
                # NO bare-clipboard fallback here: copy_selection only
                # returns clipboard text when the copy could not be
                # attempted at all (no synthesizer / no sequence
                # counter). A delivered copy whose sequence never moved
                # means "no selection" -- and Ctrl+Q is "translate the
                # SELECTED text", so stale clipboard content must not
                # be translated (native keeps clipboard translation on
                # its own hotkeys for exactly this reason).
                if not text:
                    try:
                        _dbg("hotkey_popup no text reason=%s"
                             % selection.last_reason())
                    except Exception:
                        pass
                    return
                try:
                    self._on_ui(lambda t=text: self._popup_loading(t))
                except Exception:
                    pass
                try:
                    res = self._translate(text)
                    try:
                        _dbg("hotkey_popup translated ok=%s" % getattr(res, 'ok', False))
                    except Exception:
                        pass
                except Exception:
                    try:
                        _dbg("hotkey_popup translate error")
                    except Exception:
                        pass
                    try:
                        self._on_ui(lambda t=text:
                                    self.show_translation(
                                        t, "Translation failed"))
                    except Exception:
                        pass
                    return
                try:
                    out = (getattr(res, 'text', '') or '') \
                        or "Translation failed"
                    provider = (getattr(res, 'provider_used', '')
                                or self.service)
                    self._on_ui(lambda t=text, o=out, p=provider:
                                self.show_translation(t, o, p))
                except Exception:
                    try:
                        _dbg("hotkey_popup could not queue result")
                    except Exception:
                        pass
            except Exception:
                try:
                    _dbg("hotkey_popup work error")
                except Exception:
                    pass
                return

        try:
            self._spawn_translation("popup", work)
        except Exception:
            pass

    def hotkey_translate_clipboard(self):
        text = self._clipboard_text()
        if not text:
            return
        self._start_translation(text, self._show_clipboard_result,
                                apply_rules=True)

    def _show_clipboard_result(self, text, res):
        """Show a clipboard translation in the main window (UI thread)."""
        if self.win is None:
            return
        self.win.src.setPlainText(text[:2000])
        self._show_main_result(text, res)

    def hotkey_popup_clipboard(self):
        """Native's 'translate clipboard in popup window': the CLIPBOARD
        text (not the selection) lands in the popup. Distinct from
        hotkey_popup (Ctrl+Q = selection) and from
        hotkey_translate_clipboard (result into the main window)."""
        text = self._clipboard_text()
        if not text:
            return
        try:
            self._on_ui(lambda t=text: self._popup_loading(t))
        except Exception:
            pass

        def done(t, res):
            # Always reach a terminal render so the loading marker is
            # released and failures are visible (.tmp parity).
            try:
                self._on_ui(lambda: self.show_translation(
                    t, res.text or "Translation failed",
                    provider=res.provider_used))
            except Exception:
                pass
        self._start_translation(text, done)

    def hotkey_replace_selection(self):
        """Native's Alt+W: translate the selection and type it back.

        Reads the SELECTION, not the clipboard -- the whole point of the
        action is to replace what the user has highlighted.
        """
        def work():
            try:
                from qtranslate import exclusions as _ex
                if _ex.foreground_excluded():
                    _dbg("replace: foreground excluded, skip")
                    return
                from qtranslate import selection
                # Same rule as Ctrl+Q: the SELECTION only. "" means no
                # selection landed -- there is nothing to replace, and
                # clipboard text must not be typed over the user's
                # cursor.
                text = (selection.copy_selection() or "").strip()
                _dbg("replace: copied len=%d" % len(text))
                if not text:
                    return
                res = self._translate(text)
                _dbg("replace: translated ok=%s len=%d"
                     % (getattr(res, "ok", "?"),
                        len(getattr(res, "text", "") or "")))
            except Exception as exc:           # noqa: BLE001
                _dbg("replace: work error %r" % (exc,))
                return
            self._on_ui(lambda: self._show_replace(text, res))

        self._spawn_translation("replace", work)

    def _show_replace(self, text, res):
        """Apply a finished Alt+W translation (UI thread)."""
        # NEVER type an engine failure into the user's document: on a
        # dead provider res.text is the "No data returned…" placeholder,
        # and typing that over their selection is data loss, not a
        # translation. Same rule as on_swap's EMPTY_RESULT guard.
        if not getattr(res, "ok", False):
            _dbg("replace: skipped -- translation failed")
            return
        payload = (res.text or "").strip()
        if not payload or payload.startswith("[") \
                or payload.startswith("No data returned"):
            _dbg("replace: skipped -- empty/placeholder result")
            return
        # The retype goes through sendkeys: True delivered, False when
        # there is no synthesizer (off Windows) -- never a raise.
        from qtranslate import sendkeys as _SK
        _dbg("replace: typing back len=%d" % len(payload))
        # Native retypes the translation over the selection (SendInput
        # unicode). write_text reports honestly and never raises.
        try:
            _ok = _SK.write_text(payload)
            _dbg("replace: write_text -> %s" % (_ok,))
        except Exception as exc:               # noqa: BLE001
            _dbg("replace: write_text raised %r" % (exc,))
        self.push_hist(self.service, text[:2000], res.text[:4000])

    def hotkey_copy_translation(self):
        """Copy the result pane's text to the clipboard."""
        text = self.win.out.toPlainText() if self.win else ""
        if not text:
            return
        try:
            from qtranslate import clipboard as _cb
            _cb.write_text(text)
        except Exception:
            pass

    def hotkey_dictionary_clipboard(self):
        text = self._clipboard_text()
        if text:
            self._dict_word = text
        self.open_dictionary()

    def hotkey_listen_text(self):
        """Speak the text that is on the clipboard (SOURCE language)."""
        text = self._clipboard_text()
        if text:
            lang = (getattr(self, "_detected_src", "")
                    or (self.source if self.source != "auto" else ""))
            self._speak(text, lang)

    def _speak_extra(self):
        """Speak the extra-output pane (.tmp ListenToText
        TextSource.ExtraOutput). Its language follows
        ExtraOutputSource exactly like upstream determineLanguage:
        Input -> source (detected when auto), Output -> target."""
        win = getattr(self, "win", None)
        if win is None:
            return
        try:
            text = win.back.toPlainText()
        except Exception:
            return
        if not (text or "").strip():
            return
        lang = ""
        try:
            if str(self._extra_cfg().get(
                    "ExtraOutputSource", "Output")) == "Input":
                lang = (self._detected_src
                        if self.source == "auto"
                        else self.source) or ""
            else:
                lang = self.target or ""
        except Exception:
            lang = ""
        self._speak(text, lang)

    def hotkey_listen_translation(self):
        text = self.win.out.toPlainText() if self.win else ""
        if text:
            self._speak(text)

    def _speak(self, text: str, lang: str = ""):
        # Playback blocks for the length of the audio; it must not hold
        # the UI thread (the same reason translations run on workers).
        # ``lang`` is the language of THE TEXT being spoken: a
        # translation is spoken in the target, source text (clipboard
        # listen, popup source) in the detected/source language --
        # passing self.target for everything spoke English text with a
        # Vietnamese voice (the TTS audit's High finding).
        def work():
            try:
                from qtranslate import player, registry as _RG
                # An empty lang means "the caller could not name it"
                # (source=auto with no detection cached). Detecting the
                # text's language beats defaulting to the TARGET voice,
                # which spoke Vietnamese text with whatever voice the
                # target happened to be (the TTS audit's AUTO finding).
                use_lang = lang
                if not use_lang:
                    try:
                        use_lang = _RG.detect_language(text)
                    except Exception:
                        use_lang = ""
                if use_lang in ("", "auto"):
                    use_lang = self.target
                player.play_text(text, use_lang)
            except Exception:
                pass
        # A plain daemon thread, NOT _spawn: playback can run for many
        # seconds and must not hold the one-translation-at-a-time gate
        # (_start_translation drops requests while a tracked thread is
        # alive).
        import threading
        threading.Thread(target=work, daemon=True,
                         name="qtranslate-speak").start()

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

        On macOS the port's own path is `qtranslate.speech_macos`
        (SFSpeechRecognizer + AVAudioEngine, TCC-gated). recognize()
        blocks up to its timeout, so it runs on a worker and the result
        is applied on the UI thread -- same pattern as _start_translation.
        """
        if sys.platform == "darwin":
            try:
                from qtranslate import speech_macos
            except Exception:
                speech_macos = None
            if speech_macos is not None and speech_macos.available():
                import threading

                def work():
                    try:
                        text = speech_macos.recognize(timeout_s=10.0)
                        reason = speech_macos.last_reason()
                    except Exception as exc:        # noqa: BLE001
                        text, reason = "", "recognition-error: %s" % exc

                    def apply():
                        if text:
                            self.win.src.setPlainText(text)
                        else:
                            self.win.render("[speech input] %s"
                                            % (reason or "no speech"))
                    self._on_ui(apply)

                threading.Thread(target=work, daemon=True,
                                 name="qtranslate-speech").start()
                return
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
        """The back-translation pane -- its own QTextEdit under the
        result, shown only while it holds text. In the AI extra modes
        the pane belongs to the extra-output worker, so this is a
        no-op there."""
        win = self.win
        back = getattr(win, "back", None) if win is not None else None
        if back is None:
            return
        try:
            if win.extra_mode() != "back":
                return
        except Exception:
            pass
        back.setPlainText(text or "")
        try:
            win.set_extra_visible(bool((text or "").strip()))
        except Exception:
            back.setVisible(bool((text or "").strip()))


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
            # A disabled extension is exactly the kind of thing the
            # notification surface exists for: it failed validation or
            # registration, the user did not ask for silence, and the
            # report used to live only in this stdout line.
            try:
                for _r in _ext:
                    if _r.get("status") == "disabled":
                        app.notify(
                            "warning", "Extension disabled",
                            "%s: %s" % (_r.get("id") or _r.get("path"),
                                        _r.get("reason") or "unknown"),
                            code="extension.disabled", source="extensions")
            except Exception:
                pass                    # notifications never block startup
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
    # Contents.EditSource/EditTranslation/EditBackTranslation: restore
    # what the last session left in the panes, and persist on EVERY
    # quit path (tray Exit, window close, signal) -- not only app.quit.
    try:
        app._restore_contents()
        app.qapp.aboutToQuit.connect(app._persist_contents)
        app.qapp.aboutToQuit.connect(app._persist_window_state)
        # Spell check rides the source pane's textChanged, debounced
        # inside _schedule_spell_check (.tmp spellCheckInputs flow).
        app.win.src.textChanged.connect(app._schedule_spell_check)
    except Exception:
        pass
    # Native's "Show main window on load": the app is a tray resident --
    # the window only appears when the user asks for it (tray, hotkey,
    # second instance). An unconditional show() here used to pop the
    # main window on every start even with the setting off.
    # Native's startup action (menu 1 items 85-88): General.
    # MainWindowStartupAction 0=Show window, 1=Minimize to tray,
    # 2=Restore previous state. Configs written before the key existed
    # only carry MainWindowShowOnLoad -- derive the action from it.
    try:
        from qtranslate import config as _cfg
        _g = (_cfg.load() or {}).get("General", {})
        _action = _g.get("MainWindowStartupAction")
        if _action is None:
            _action = 0 if _g.get("MainWindowShowOnLoad", True) else 1
        _action = int(_action)
    except Exception:
        _action = 0
    _show = (_action == 0)
    if _action == 2:
        # Restore previous state: reopen however the last run left the
        # window -- visible means show, tray-resident means stay hidden.
        try:
            _show = bool((_cfg.load() or {}).get("General", {})
                         .get("LastWindowVisible", True))
        except Exception:
            _show = True
    if _show:
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
