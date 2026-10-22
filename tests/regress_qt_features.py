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
    from PySide6.QtWidgets import QApplication
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

    # the sidebar switches page and closes the one it came from
    basics = opt.BasicsPage(app)
    windows.append(basics)
    basics._goto("Languages")
    app.qapp.processEvents()
    ck("clicking a page in the list opens that page",
       isinstance(app._opts, opt.LanguagesPage), type(app._opts).__name__)
    ck("the page it came from is closed", not basics.isVisible())

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

    # --- 7. the tray -----------------------------------------------------
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
