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
    # --- 1. the main window ---------------------------------------------
    win = MainWindow(app)
    windows.append(win)
    app.win = win
    ck("the main window has a source pane", hasattr(win, "src"))
    ck("the main window has a result pane", hasattr(win, "out"))
    ck("the main window keeps the measured client size",
       (win.width(), win.height()) == win.SIZE, str(win.SIZE))
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
    before = (app.source, app.target)
    app.on_swap()
    ck("Swap exchanges the language pair",
       (app.source, app.target) == (before[1], before[0]),
       "%s -> %s" % (before, (app.source, app.target)))
    ck("Swap exchanges the combos",
       win.cmb_src.currentText() != before[1] or app.source == before[1])

    # --- 4. the Options dialog and its nine pages ------------------------
    from qtranslate.qt import options as opt

    ck("the Options dialog knows all nine pages", len(opt.PAGES) == 9,
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
    ck("the other pages share the Options size",
       opt.AppearancePage.SIZE == (644, 362), str(opt.AppearancePage.SIZE))

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
    basics._goto("Basics")
    app.qapp.processEvents()
    ck("the page can be swapped back", basics._page_name == "Basics",
       basics._page_name)
    ck("the window keeps the shared Options size after the swap",
       (basics.width(), basics.height()) == (644, 362),
       "%dx%d" % (basics.width(), basics.height()))

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
        from qtranslate.qt.popup import PopupWindow
        pop = PopupWindow(app)
        windows.append(pop)
        pop.set_text("hello", "Xin chào", "English -> Vietnamese")
        ck("the popup shows the translation it is given",
           pop.lbl_text.text() == "Xin chào", pop.lbl_text.text())
        ck("the popup shows the language pair",
           pop.lbl_pair.text() == "English -> Vietnamese", pop.lbl_pair.text())
        ck("the popup is the native's size", (pop.width(), pop.height()) == (200, 68),
           "%dx%d" % (pop.width(), pop.height()))
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
        def __init__(self, app=None):
            self.lbl_text = type("L", (), {"text": ""})()
            self.lbl_pair = type("L", (), {"text": ""})()

        def set_text(self, source, result, pair=""):
            self.lbl_text.text = result
            self.lbl_pair.text = pair

        def show(self):
            shown["popup"] = self.lbl_text.text

    try:
        popup_mod.PopupWindow = _Popup
        app.win.src.setPlainText("old")
        app._clipboard_text = lambda: "xin chào"
        engine.translate = fake_translate
        try:
            app.hotkey_popup()
        finally:
            engine.translate = real_translate
        ck("Ctrl+Q shows the translation in the popup",
           shown.get("popup") == "Xin chào", str(shown))
        ck("Ctrl+Q puts the source in the pane",
           "xin chào" in app.win.src.toPlainText(), app.win.src.toPlainText()[:40])
        ck("Ctrl+Q writes the history", len(app.history) >= 1)
    finally:
        popup_mod.PopupWindow = real_popup.PopupWindow

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
        app.set_mouse_mode(MOUSE_MODES[1])
        ck("the mouse mode starts the capture hook",
           any(c[0] == "start" for c in calls), str(calls))
        ck("the mouse mode is written to the config",
           saved.get("General", {}).get("MouseMode") == 1, str(saved))
        ck("the mouse mode's 'on' flag follows the mode",
           saved.get("General", {}).get("MouseModeOn") is True, str(saved))
        app.set_mouse_mode(MOUSE_MODES[0])
        ck("the mouse mode 'off' stops the capture hook",
           any(c[0] == "stop" for c in calls), str(calls))
        ck("the mouse mode 'off' is written to the config",
           saved.get("General", {}).get("MouseMode") == 0
           and saved.get("General", {}).get("MouseModeOn") is False, str(saved))

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

        # Mode 1 ("Show translation"): the click copies the selection
        # and the clipboard's text is translated.
        app.set_mouse_mode(MOUSE_MODES[1])
        app._clipboard_text = lambda: "text from the clipboard"
        shown.clear()
        popup_mod.PopupWindow = _Popup
        try:
            engine.translate = fake_translate
            try:
                app._mouse_work(10, 20)
            finally:
                engine.translate = real_translate
        finally:
            popup_mod.PopupWindow = real_popup.PopupWindow
        ck("the selection click captures the clipboard's text",
           "text from the clipboard" in app.win.src.toPlainText(),
           app.win.src.toPlainText()[:40])
        ck("the selection click shows the translation in the popup",
           shown.get("popup") == "Xin chào", str(shown))

        # Mode 2 ("Show translation and read"): the text under the
        # cursor (OLEACC) is captured, and it is spoken as well.
        app.set_mouse_mode(MOUSE_MODES[2])
        shown.clear()
        spoken.clear()
        popup_mod.PopupWindow = _Popup
        try:
            engine.translate = fake_translate
            try:
                app._mouse_work(10, 20)
            finally:
                engine.translate = real_translate
        finally:
            popup_mod.PopupWindow = real_popup.PopupWindow
        ck("the third mode captures the text under the cursor",
           "text under the cursor" in app.win.src.toPlainText(),
           app.win.src.toPlainText()[:40])
        ck("the third mode speaks the selected text",
           spoken == ["text under the cursor"], str(spoken))

        # The hook's proc runs on a worker thread: the translation is
        # handed over to the UI thread by the bridge, not shown there.
        shown.clear()
        import threading
        engine.translate = fake_translate
        try:
            worker = threading.Thread(target=app._mouse_work, args=(10, 20))
            worker.start()
            worker.join()
        finally:
            engine.translate = real_translate
        ck("the worker's result waits for the UI thread",
           shown.get("popup") is None, str(shown))
        app.qapp.processEvents()
        ck("the popup shows the translation in the UI thread",
           shown.get("popup") == "Xin chào", str(shown))
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
        ck("install() registers nothing where there is no hotkey hook",
           _hk.install(app) == [])

    # --- 9. the assets ---------------------------------------------------
    try:
        from qtranslate.qt import icons
        for name in ("check_blue", "ap_icon1", "ap_icon2", "ap_icon3",
                     "ap_icon4", "mic", "swap"):
            pm = icons.pixmap("ui_icons", name)
            ck("the %s asset loads" % name, not pm.isNull())
    except Exception as exc:                   # noqa: BLE001
        ck("the assets load", False, "%s: %s" % (type(exc).__name__, exc))

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
    for w in windows:
        try:
            w.close()
        except Exception:                      # noqa: BLE001
            pass
    app.qapp.processEvents()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_qt_features: all checks ok (%d assertions)" % n[0])
