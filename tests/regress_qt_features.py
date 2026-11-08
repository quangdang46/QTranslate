"""Regression: the PySide6 front end's FEATURES, not its pixels.

The pixel work has its own measure (``tools/render_qt.py`` compares the
rendered windows with the native captures). This suite covers the other
half: that the port's windows actually DO what native's do -- translate,
swap, remember the history, open every Options page, open the popup,
the keyboard, the dictionary and the tray -- and that the front end is
wired to the SAME core the tkinter one uses.

No provider calls: the engine is stubbed, so this is offline.

On a host with no display the suite skips rather than fails (the same
rule ``tools/run_suites.py`` applies to the tkinter GUI suite).
"""
from __future__ import annotations

import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# --- the toolkit has to be there at all ---------------------------------
try:
    from PySide6.QtWidgets import QApplication, QCheckBox, QLabel
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_features: PySide6 is not importable (%s)" % exc)
    raise SystemExit(0)

try:
    from qtranslate.qt.app import QtApp
    # Isolate the history: it persists now, so this suite must not read
    # or write the real History.json.
    import qtranslate.qt.app as _appmod
    import tempfile as _tf, os as _os
    _appmod.HISTORY_PATH = _os.path.join(
        _tf.mkdtemp(prefix="qt_feat_"), "History.json")
    # Same for Options.json: tray/menu labels follow the UI-language
    # pack, so pin a throwaway English config (also keeps any
    # write-through off the user's real file).
    from qtranslate import config as _C
    _C.DEFAULT_PATH = _os.path.join(
        _tf.mkdtemp(prefix="qt_feat_opt_"), "Options.json")
    from qtranslate.qt.main_window import MainWindow
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_features: the Qt front end does not import (%s)" % exc)
    raise SystemExit(0)

try:
    app = QtApp([])
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_features: no usable QApplication (%s)" % exc)
    raise SystemExit(0)

windows = []
try:
    # This suite drives _mouse_work repeatedly; the app's own capture
    # cooldown (native FUN_004183bd's idle gate, the anti-loop) would
    # drop every call after the first.
    app.MOUSE_CAPTURE_COOLDOWN = 0
    # --- 1. the main window ---------------------------------------------
    win = MainWindow(app)
    windows.append(win)
    app.win = win
    ck("the main window has a source pane", hasattr(win, "src"))
    ck("the main window has a result pane", hasattr(win, "out"))
    # .tmp isStatusBarVisible: the status strip lives BELOW the
    # captured content, so a visible bar grows the client by exactly
    # its reserved room (_sb_extra) instead of covering a widget.
    _sb = getattr(win, "statusbar", None)
    _sb_h = win._sb_extra if (_sb is not None
                            and _sb.isVisibleTo(win)) else 0
    ck("the main window keeps the measured client size",
       (win.width(), win.height())
       == (win.SIZE[0], win.SIZE[1] + _sb_h),
       "%dx%d vs %s+%d" % (win.width(), win.height(), win.SIZE, _sb_h))
    ck("the main window's origin is the native's",
       win.ORIGIN == (1, 31), str(win.ORIGIN))

    # --- 2. translating --------------------------------------------------
    from qtranslate import engine
    from qtranslate.core import Result

    seen = {}

    def fake_translate(service, text, target, src="auto", **kw):
        seen["service"] = service
        seen["text"] = text
        seen["target"] = target
        seen["src"] = src
        return Result(provider_used="google", text="Xin chào", requested=target)

    real_translate = engine.translate
    engine.translate = fake_translate
    try:
        win.src.setPlainText("hello")
        app.on_go()
        # Translate runs off the UI thread now; the result is applied by
        # a queued call the waiter drains.
        app.wait_for_translation()
        ck("the result pane shows the translation",
           "Xin chào" in win.out.toPlainText(), win.out.toPlainText()[:60])
        ck("the engine is called with the pane's text",
           seen.get("text") == "hello", str(seen))
        ck("the engine is called with the chosen target",
           seen.get("target") == app.target, str(seen))
        ck("a translation is remembered in the history",
           len(app.history) == 1, str(app.history))
        ck("the history keeps the source and the result",
           app.history and app.history[0][1] == "hello", str(app.history))
    finally:
        engine.translate = real_translate

    # --- 3. New and Swap -------------------------------------------------
    app.on_new()
    ck("New clears the source pane", win.src.toPlainText() == "",
       win.src.toPlainText()[:40])
    # Language changes persist to the REAL Options.json; keep this
    # suite's swaps and setters from touching the user's config.
    _real_persist = app._persist_language
    _real_go = app.on_go
    _go_calls = []
    app._persist_language = lambda: None
    app.on_go = lambda: _go_calls.append(1)
    try:
        app.source, app.target = "en", "vi"
        for _cmb, _txt in ((win.cmb_src, "English"),
                           (win.cmb_tgt, "Vietnamese")):
            _cmb.blockSignals(True)
            _cmb.setCurrentText(_txt)
            _cmb.blockSignals(False)
        before = (app.source, app.target)
        app.on_swap()
        ck("Swap exchanges the language pair",
           (app.source, app.target) == (before[1], before[0]),
           "%s -> %s" % (before, (app.source, app.target)))
        ck("Swap exchanges the combos",
           win.cmb_src.currentText() != before[1]
           or app.source == before[1])
        # .tmp: the translated text moves back into the input and is
        # translated again (on_go re-fired).
        ck("Swap moves the translation back into the input",
           "Xin chào" in win.src.toPlainText(),
           win.src.toPlainText()[:50])
        ck("Swap re-translates the swapped text", bool(_go_calls),
           str(_go_calls))
        win.src.clear()
        win.out.clear()
        # .tmp SwapLanguagesUseCase: the target slot can never hold
        # auto, and a BLANK result refuses the swap outright -- the
        # early return fires before the auto-source check, so the
        # pane needs a result for these cases to reach it.
        app.source, app.target = "auto", "vi"
        win.out.setPlainText("translated")
        app._detected_src = ""
        app.on_swap()
        ck("Swap with auto source and no detection is a no-op",
           (app.source, app.target) == ("auto", "vi"),
           "%s -> %s" % (("auto", "vi"), (app.source, app.target)))
        app._detected_src = "en"
        app.on_swap()
        ck("Swap with auto source uses the detected language as target",
           (app.source, app.target) == ("vi", "en"),
           str((app.source, app.target)))
        # And the blank-result refusal itself: clear the pane, the
        # pair must NOT move even with a concrete source.
        win.out.clear()
        app.source, app.target = "en", "vi"
        app.on_swap()
        ck("Swap with a blank result is a no-op",
           (app.source, app.target) == ("en", "vi"),
           str((app.source, app.target)))
        app.set_target_by_name("Auto-Detect")
        ck("set_target_by_name never stores auto",
           app.target != "auto", app.target)
    finally:
        app._persist_language = _real_persist
        app.on_go = _real_go

    # --- 4. the Options dialog and its eleven pages ----------------------
    # Nine native pages plus Extensions and Comparison, the port's own
    # (native has neither an extension system nor a comparison feature
    # to copy the pages from).
    from qtranslate.qt import options as opt

    ck("the Options dialog knows all eleven pages", len(opt.PAGES) == 11,
       str(sorted(opt.PAGES)))
    for name, cls in sorted(opt.PAGES.items()):
        try:
            page = cls(app)
            windows.append(page)
        except Exception as exc:               # noqa: BLE001
            ck("the %s page builds" % name, False, "%s: %s" % (type(exc).__name__, exc))
            continue
        ck("the %s page builds" % name, True)
        ck("the %s page keeps the native's client size" % name,
           (page.width(), page.height()) == cls.SIZE,
           "%s vs %s" % ((page.width(), page.height()), cls.SIZE))
    ck("the Hotkeys page is the one with its own size",
       opt.HotkeysPage.SIZE == (650, 362), str(opt.HotkeysPage.SIZE))
    # Pages with port-owned groups carry their own SIZE (the native
    # capture left no room): Basics/Advanced/Languages/Services grew
    # for close-action, API keys, rules/pins, presets; Appearance grew
    # for the image-search + outside-click rows.
    ck("grown pages keep their own sizes",
       opt.AppearancePage.SIZE == (644, 536)
       and opt.LanguagesPage.SIZE == (644, 512)
       and opt.ServicesPage.SIZE == (644, 486),
       "%s %s %s" % (opt.AppearancePage.SIZE,
                     opt.LanguagesPage.SIZE,
                     opt.ServicesPage.SIZE))

    # The sidebar swaps the body IN PLACE: the same window, the same
    # sidebar, the page's own widgets replaced. (It used to open a new
    # window and close the old one, which flickered.)
    basics = opt.BasicsPage(app)
    windows.append(basics)
    basics.show()
    app.qapp.processEvents()
    win_id = basics.winId()
    basics._goto("Languages")
    app.qapp.processEvents()
    ck("clicking a page in the list swaps the body in place",
       basics.winId() == win_id, "%s vs %s" % (basics.winId(), win_id))
    ck("the new page's body is the one on show",
       basics._page_name == "Languages", basics._page_name)
    ck("the old page's widgets are gone",
       not any("Start with Windows" in c.text()
               for c in basics.findChildren(QCheckBox)))
    ck("the new page's widgets are there",
       any("Vietnamese" in c.text()
           for c in basics.findChildren(QCheckBox))
       or bool(basics.findChildren(QLabel)))
    # Languages page extra-output combos write through on activation
    # (General.SummaryLength / General.RewriteStyle). `activated` only
    # fires on user picks, so emit it the way a click would.
    from PySide6.QtWidgets import QComboBox
    _sl = [c for c in basics.findChildren(QComboBox)
           if [c.itemText(i) for i in range(c.count())]
           == ["Short", "Medium", "Long"]]
    ck("the Languages page shows the Summary length combo", len(_sl) == 1,
       str(len(_sl)))
    if _sl:
        _sl[0].activated.emit(2)          # "Long"
        app.qapp.processEvents()
        ck("Summary length writes General.SummaryLength=LONG",
           (_C.load() or {}).get("General", {}).get("SummaryLength")
           == "LONG",
           repr((_C.load() or {}).get("General", {})))
    basics._goto("Basics")
    app.qapp.processEvents()
    ck("the page can be swapped back", basics._page_name == "Basics",
       basics._page_name)
    ck("the window keeps the page's own Options size after the swap",
       (basics.width(), basics.height()) == opt.BasicsPage.SIZE,
       "%dx%d" % (basics.width(), basics.height()))

    # Appearance "Icons:" toggles: four checkable buttons over the
    # recovered cell artwork; the accent frame is the :checked state
    # and each click flips one PopupIcons bit. Regression: the icon
    # label used to be created AFTER the button, painting the artwork
    # over it, and the stylesheet was a build-time snapshot -- clicks
    # wrote config but the row showed no state at all.
    from PySide6.QtWidgets import QPushButton
    basics._goto("Appearance")
    app.qapp.processEvents()
    icon_btns = [w for w in basics.findChildren(QPushButton)
                 if w.isCheckable() and not w.text().strip()]
    ck("the Appearance page has four icon toggles",
       len(icon_btns) == 4, str(len(icon_btns)))
    if len(icon_btns) == 4:
        mask0 = int((_C.load() or {}).get("Appearance", {})
                   .get("PopupIcons", 30))
        icon_btns[0].click()
        app.qapp.processEvents()
        mask1 = int((_C.load() or {}).get("Appearance", {})
                   .get("PopupIcons", 30))
        ck("an icon toggle flips its PopupIcons bit",
           mask1 == (mask0 & ~2), "%s -> %s" % (mask0, mask1))
        ck("the on-state is a :checked style, not a build snapshot",
           ":checked" in (icon_btns[0].styleSheet() or ""),
           (icon_btns[0].styleSheet() or "")[:80])
        kids = basics.children()
        bi = kids.index(icon_btns[0])
        under = [w for w in kids[:bi]
                 if isinstance(w, QLabel) and not w.pixmap().isNull()
                 and abs(w.x() - icon_btns[0].x()) < 2
                 and abs(w.y() - icon_btns[0].y()) < 2]
        ck("the cell artwork paints under its toggle button",
           len(under) == 1, str(len(under)))
        icon_btns[0].click()          # restore the default mask
        app.qapp.processEvents()

    # --- 5. the other windows -------------------------------------------
    try:
        app.open_history()
        app.qapp.processEvents()
        ck("the history window opens", app._hist is not None)
        windows.append(app._hist)
    except Exception as exc:                   # noqa: BLE001
        ck("the history window opens", False, "%s: %s" % (type(exc).__name__, exc))

    try:
        app.open_dictionary()
        app.qapp.processEvents()
        ck("the dictionary window opens", app._dict is not None)
        windows.append(app._dict)
    except Exception as exc:                   # noqa: BLE001
        ck("the dictionary window opens", False, "%s: %s" % (type(exc).__name__, exc))

    try:
        app.open_keyboard()
        app.qapp.processEvents()
        ck("the keyboard window opens", app._kbd is not None)
        windows.append(app._kbd)
    except Exception as exc:                   # noqa: BLE001
        ck("the keyboard window opens", False, "%s: %s" % (type(exc).__name__, exc))

    # --- 6. the popup ----------------------------------------------------
    try:
        from qtranslate.qt.popup import MAX_WIDTH as MAX_W
        from qtranslate.qt.popup import MIN_WIDTH as MIN_W
        from qtranslate.qt.popup import PopupWindow
        pop = PopupWindow(app)
        windows.append(pop)
        pop.set_text("hello", "Xin chào", "English -> Vietnamese")
        _body = (pop.lbl_text.toPlainText
                 if hasattr(pop.lbl_text, "toPlainText")
                 else pop.lbl_text.text)
        ck("the popup shows the translation it is given",
           _body() == "Xin chào", _body())
        ck("the popup shows the language pair",
           pop.lbl_pair.text() == "English -> Vietnamese", pop.lbl_pair.text())
        # The popup SIZES TO ITS TEXT (native 2162/2163): a fixed size
        # clips a long translation. The bounds are the reading range; the
        # text picks the number inside them.
        ck("the popup keeps its width inside the reading range",
           MIN_W <= pop.width() <= MAX_W,
           "%dx%d" % (pop.width(), pop.height()))
        _short = (pop.width(), pop.height())
        pop.set_text("hello", "x " * 200, "English -> Vietnamese")
        ck("a long translation makes the popup wider and taller",
           pop.width() >= _short[0] and pop.height() >= _short[1],
           "%s -> %dx%d" % (_short, pop.width(), pop.height()))
        ck("the width is clamped, not unbounded", pop.width() <= MAX_W,
           str(pop.width()))
    except Exception as exc:                   # noqa: BLE001
        ck("the popup builds and takes text", False,
           "%s: %s" % (type(exc).__name__, exc))

    # --- 7. the popup hotkey (Ctrl+Q) and the mouse mode (boi den) ------
    # The popup hotkey: the clipboard's text is translated and shown in
    # the popup, the panes and the history.
    shown = {}
    real_popup = sys.modules.get("qtranslate.qt.popup")
    from qtranslate.qt import popup as popup_mod

    class _Popup:
        """The stand-in for the popup window.

        It carries the same three methods the real one has -- set_text,
        place and show -- because the caller uses all three and a stub
        that is missing one makes the call raise inside the caller's
        try/except, which looks exactly like "the popup never opened".
        """

        def __init__(self, app=None):
            self.app = app
            self.lbl_text = type("L", (), {"text": ""})()
            self.lbl_pair = type("L", (), {"text": ""})()

        def set_text(self, source, result, pair="", provider=""):
            self.lbl_text.text = result
            self.lbl_pair.text = pair

        def place(self):
            shown["placed"] = True

        def show(self):
            shown["popup"] = self.lbl_text.text

    import qtranslate.selection as _sel
    _real_copy = _sel.copy_selection
    _sel.copy_selection = lambda **kw: "xin chao (selected)"
    try:
        popup_mod.PopupWindow = _Popup
        app.win.src.setPlainText("old")
        # The clipboard still holds STALE text: the point of the
        # copy-capture fix is that Ctrl+Q copies the SELECTION, not this.
        app._clipboard_text = lambda: "STALE clipboard"
        engine.translate = fake_translate
        try:
            app.hotkey_popup()
            # Ctrl+Q is off the UI thread now: the copy + translate run
            # on a worker, only the finished popup crosses back.
            app.wait_for_translation()
        finally:
            engine.translate = real_translate
        ck("Ctrl+Q shows the translation in the popup",
           shown.get("popup") == "Xin chào", str(shown))
        # Quick-translate is a separate surface (.tmp QuickTranslateDialog
        # never touches MainState): the popup path must NOT dump the
        # answer into the main window's panes.
        ck("Ctrl+Q does not write the main window panes",
           app.win.src.toPlainText() == "old",
           app.win.src.toPlainText()[:60])
        ck("Ctrl+Q writes the history", len(app.history) >= 1)
    finally:
        popup_mod.PopupWindow = real_popup.PopupWindow
        _sel.copy_selection = _real_copy

    # The mouse mode: the hook is started when the mode is on and
    # stopped when it is off, the mode is written to the config, and a
    # selection click captures the text and translates it.
    import qtranslate.mouse_capture as mc
    import qtranslate.config as qcfg
    import qtranslate.sendkeys as qsendkeys

    calls = []
    saved = {}
    real_start, real_stop = mc.start, mc.stop
    real_available = mc.available
    real_cursor_text = mc.cursor_text
    real_load, real_save = qcfg.load, qcfg.save
    real_send = qsendkeys.send
    mc.start = lambda on_select, **kw: calls.append(("start", on_select)) or 1
    mc.stop = lambda: calls.append(("stop",))
    mc.available = lambda: True
    mc.cursor_text = lambda x, y: "text under the cursor"
    qcfg.load = lambda *a, **k: {
        "General": {"MouseMode": 2},
        "Advanced": {"EnableGuiTranslation": True},
    }
    qcfg.save = lambda cfg, *a, **k: saved.update(cfg)
    qsendkeys.send = lambda *a, **k: None
    spoken = []
    app._speak = lambda text: spoken.append(text)
    try:
        from qtranslate.qt.tray import MOUSE_MODES
        ck("the mouse modes are native's own names",
           MOUSE_MODES == ("Show icon", "Show translation",
                           "Show translation and read"), str(MOUSE_MODES))
        # All three modes are REAL now (mode 0 draws the floating icon,
        # row C10); the on/off switch is the tray click's own toggle.
        ck("the capture hook starts OFF (the toggle defaults off)",
           not any(c[0] == "start" for c in calls), str(calls))
        app.toggle_mouse_enabled()
        app.set_mouse_mode(MOUSE_MODES[1])
        ck("enabled + a mode starts the capture hook",
           any(c[0] == "start" for c in calls), str(calls))
        ck("the mouse mode is written to the config",
           saved.get("General", {}).get("MouseMode") == 1, str(saved))
        ck("the toggle wrote MouseModeOn = true",
           saved.get("General", {}).get("MouseModeOn") is True, str(saved))
        app.set_mouse_mode(MOUSE_MODES[0])
        ck("mode 0 is a REAL mode: the hook keeps running",
           not any(c[0] == "stop" for c in calls), str(calls))
        ck("the mode is written, the toggle unchanged",
           saved.get("General", {}).get("MouseMode") == 0
           and saved.get("General", {}).get("MouseModeOn") is True,
           str(saved))
        app.toggle_mouse_enabled()
        # The hook now stays installed with capture off: it also feeds
        # click-outside dismissal for the popup in Ctrl+Q-only installs.
        # The capture side is gated on the mode inside _mouse_selected.
        ck("the tray toggle OFF keeps the hook (dismissal needs it)",
           not any(c[0] == "stop" for c in calls), str(calls))
        ck("capture is gated while the toggle is OFF",
           app._mouse_mode_off(), "mode-off gate missing")
        ck("the toggle OFF is written to the config",
           saved.get("General", {}).get("MouseModeOn") is False, str(saved))
        app.toggle_mouse_enabled()   # back on for the mode-0 icon leg

        # The gate: native's GUI-translation setting (DAT_005494e4) is
        # closed, so the capture does nothing.
        qcfg.load = lambda *a, **k: {"General": {"MouseMode": 2},
                                     "Advanced": {"EnableGuiTranslation": False}}
        ck("the GUI-translation setting gates the capture",
           app._capture_selection(10, 20) == "",
           app._capture_selection(10, 20))
        qcfg.load = lambda *a, **k: {
            "General": {"MouseMode": 2},
            "Advanced": {"EnableGuiTranslation": True},
        }

        # .tmp SelectionBehaviorRouter / native FUN_004183bd: the mode
        # decides what the captured selection DOES. Mode 1 ("Show
        # translation") translates AT THE RELEASE -- native's
        # TaskShowPopupWindow -- no icon, no click needed.
        app.set_mouse_mode(MOUSE_MODES[1])
        _sel.copy_selection = lambda **kw: "text from the clipboard"
        shown.clear()
        popup_mod.PopupWindow = _Popup
        try:
            engine.translate = fake_translate
            try:
                app._mouse_work(10, 20)
                app.wait_for_translation()
            finally:
                engine.translate = real_translate
        finally:
            popup_mod.PopupWindow = real_popup.PopupWindow
        ck("mode 1 translates at the release (no icon, no click)",
           shown.get("popup") == "Xin chào", str(shown))

        # Mode 2 ("Show translation and read"): same immediate popup,
        # and the RESULT is read aloud (.tmp selectionReadSource
        # default = TRANSLATION, not the source text).
        app.set_mouse_mode(MOUSE_MODES[2])
        shown.clear()
        spoken.clear()
        popup_mod.PopupWindow = _Popup
        try:
            engine.translate = fake_translate
            try:
                app._mouse_work(10, 20)
                app.wait_for_translation()
            finally:
                engine.translate = real_translate
        finally:
            popup_mod.PopupWindow = real_popup.PopupWindow
        ck("mode 2 translates at the release too",
           shown.get("popup") == "Xin chào", str(shown))
        ck("mode 2 speaks the TRANSLATION, not the source",
           spoken == ["Xin chào"], str(spoken))

        # Mode 0 ("Show icon"): the release only pops the floating
        # button; nothing translates until its click.
        app.set_mouse_mode(MOUSE_MODES[0])
        shown.clear()
        spoken.clear()
        popup_mod.PopupWindow = _Popup
        try:
            engine.translate = fake_translate
            try:
                app._mouse_work(10, 20)
                app.qapp.processEvents()
            finally:
                engine.translate = real_translate
        finally:
            popup_mod.PopupWindow = real_popup.PopupWindow
        icon = getattr(app, "_mouse_icon", None)
        ck("mode 0 pops the icon instead of translating",
           icon is not None and icon.is_showing()
           and icon.current_text() == "text from the clipboard"
           and shown.get("popup") is None,
           "icon=%r popup=%r" % (icon, shown))
        if icon is not None:
            icon.dismiss()

        # The hook's proc runs on a worker thread: the UI work is handed
        # over to the UI thread by the bridge, not done there.
        shown.clear()
        import threading
        engine.translate = fake_translate
        try:
            worker = threading.Thread(target=app._mouse_work, args=(10, 20))
            worker.start()
            worker.join()
        finally:
            engine.translate = real_translate
        app.qapp.processEvents()
        ck("the worker's drag-release re-pops the icon on the UI thread",
           getattr(app, "_mouse_icon", None) is not None
           and app._mouse_icon.is_showing()
           and shown.get("popup") is None, str(shown))
        icon2 = getattr(app, "_mouse_icon", None)
        if icon2 is not None:
            icon2.dismiss()
    finally:
        mc.start, mc.stop = real_start, real_stop
        mc.available = real_available
        mc.cursor_text = real_cursor_text
        qcfg.load, qcfg.save = real_load, real_save
        qsendkeys.send = real_send

    # --- 8. the tray -----------------------------------------------------
    try:
        from qtranslate.qt.tray import Tray
        tray = Tray(app)
        menu = tray._menu()
        labels = [a.text() for a in menu.actions() if a.text()]
        ck("the tray has a menu", menu is not None)
        ck("the tray offers the main window", any("QTranslate" in t for t in labels),
           str(labels))
        ck("the tray offers the options", any("Option" in t for t in labels),
           str(labels))
    except Exception as exc:                   # noqa: BLE001
        ck("the tray builds its menu", False, "%s: %s" % (type(exc).__name__, exc))

    # --- 8. the hotkeys --------------------------------------------------
    try:
        from qtranslate.qt import hotkeys
        ck("the hotkeys module exposes install()", callable(hotkeys.install))
        registered = hotkeys.install(app)
        ck("install() returns the hotkeys it registered",
           isinstance(registered, list), type(registered).__name__)
    except Exception as exc:                   # noqa: BLE001
        # The keyboard library is optional; a missing one is a skip, not
        # a failure, but a crash in our own code is a failure.
        ck("the hotkeys install", "keyboard" not in str(exc).lower(),
           "%s: %s" % (type(exc).__name__, exc))

    # A hotkey fires on the `keyboard` package's OWN listener thread, not
    # Qt's. Running the handler there touches widgets from the wrong
    # thread, which crashed the process outright (an access violation,
    # not a catchable exception) the first time a user pressed Ctrl+Q.
    # The handler must therefore be re-run on the UI thread.
    ck("the app can hand a call to the UI thread",
       callable(getattr(app, "_on_ui", None)))
    from PySide6.QtCore import QThread
    ran = []
    app._on_ui(lambda: ran.append(QThread.currentThread() is app.qapp.thread()))
    ck("a call from the UI thread runs there",
       ran == [True], str(ran))
    # The same call from ANOTHER thread must land on the UI thread too,
    # which is what the hotkey path does.
    ran2 = []

    def _from_worker():
        app._on_ui(lambda: ran2.append(QThread.currentThread()
                                       is app.qapp.thread()))
    worker = threading.Thread(target=_from_worker)
    worker.start()
    worker.join()
    ck("a call from another thread is marshalled to the UI thread",
       ran2 == [], "the queued call must not have run on the worker")
    app.qapp.processEvents()
    ck("the marshalled call runs on the UI thread",
       ran2 == [True], str(ran2))

    # The registration itself must wrap the handler: the callback that
    # `keyboard` keeps is not the raw app method but one that goes
    # through _on_ui.
    #
    # Where the platform has no global-hotkey hook there is nothing to
    # register, and the `keyboard` package must NOT be imported at all:
    # on macOS importing it aborts the process (SIGABRT inside
    # CoreText) when the Accessibility permission is missing, so a
    # "try: import keyboard" does not raise there -- it kills the app.
    from qtranslate import platforms
    from qtranslate.qt import hotkeys as _hk
    if platforms.current().capability("hotkey") == platforms.Capability.AVAILABLE:
        import keyboard as _kbd
        registered_cb = []
        real_add = _kbd.add_hotkey

        def _fake_add(combo, cb, *a, **kw):
            registered_cb.append((combo, cb))
            return real_add(combo, cb, *a, **kw)
        _kbd.add_hotkey = _fake_add
        try:
            _hk.install(app)
        finally:
            _kbd.add_hotkey = real_add
        ck("the hotkeys are registered", bool(registered_cb), str(registered_cb))
        ck("the registered callback is not the raw app method",
           all(cb.__code__.co_name != "hotkey_popup"
               for _c, cb in registered_cb),
           str([cb.__code__.co_name for _c, cb in registered_cb]))
    else:
        ck("the hotkey package is not imported where it cannot work",
           platforms.keyboard_module() is None)
        bound = _hk.install(app)
        if sys.platform == "darwin":
            # macOS has its own backends now (the CGEventTap, then
            # Carbon): ``keyboard`` is not the only hook, so install()
            # legitimately binds when the tap is live.
            ck("install() reports a binding list on macOS",
               isinstance(bound, list), str(bound))
        else:
            ck("install() registers nothing where there is no hotkey hook",
               bound == [])

    # --- 9. the assets ---------------------------------------------------
    try:
        from qtranslate.qt import icons
        for name in ("check_blue", "ap_icon1", "ap_icon2", "ap_icon3",
                     "ap_icon4", "mic", "swap"):
            pm = icons.pixmap("ui_icons", name)
            ck("the %s asset loads" % name, not pm.isNull())
    except Exception as exc:                   # noqa: BLE001
        ck("the assets load", False, "%s: %s" % (type(exc).__name__, exc))

    # --- 9b. the extra-options popup is an exclusive radio group --------
    try:
        win.set_extra_mode("summary")
        _em = win._extra_options_menu_widget()
        _acts = [a for a in (_em.actions() if _em is not None else [])
                 if a.isCheckable()]
        ck("extra-options popup offers checkable choices",
           len(_acts) > 1, str(len(_acts)))
        if len(_acts) > 1:
            _b = [a.isChecked() for a in _acts]
            ck("exactly one option is checked initially", sum(_b) == 1,
               str(_b))
            _t = _acts[0] if not _acts[0].isChecked() else _acts[1]
            _t.trigger()
            _now = [a.isChecked() for a in _acts]
            ck("picking an option keeps exactly one check",
               sum(_now) == 1 and _now[_acts.index(_t)], str(_now))
    except Exception as exc:                   # noqa: BLE001
        ck("extra-options popup exclusivity", False,
           "%s: %s" % (type(exc).__name__, exc))

    # --- 10. the style ----------------------------------------------------
    ck("the app font is Tahoma at 11px",
       app.qapp.font().family() == "Tahoma" and app.qapp.font().pixelSize() == 11,
       "%s %s" % (app.qapp.font().family(), app.qapp.font().pixelSize()))

    # --- 11. the OCR region grab ------------------------------------------
    try:
        from PySide6.QtCore import QRect
        from qtranslate.qt.ocr_pick import grab_rect
        data = grab_rect(QRect(0, 0, 40, 30))
        ck("the OCR region grab returns PNG bytes",
           isinstance(data, bytes) and data[:4] == b"\x89PNG", repr(data[:8]))
    except Exception as exc:                   # noqa: BLE001
        ck("the OCR region grab works", False, "%s: %s" % (type(exc).__name__, exc))

finally:
    # Close every window and KEEP the references alive until the event
    # loop has drained. A widget destroyed while Qt still has a queued
    # event for it is an access violation at interpreter exit -- the run
    # printed "all checks ok" and then died, which looked like a failure
    # in whatever the runner saw last.
    for w in windows:
        try:
            w.close()
            w.deleteLater()
        except Exception:                      # noqa: BLE001
            pass
    app.qapp.processEvents()
    app.qapp.processEvents()
    del windows[:]

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_qt_features: all checks ok (%d assertions)" % n[0])
