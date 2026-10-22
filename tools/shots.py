"""Refresh the pictures in ``screenshots/`` from the PySide6 front end.

The old ones in ``screenshots/screens/`` were captures of the tkinter
port. They are replaced with captures of the same windows from the
PySide6 front end, so the folder shows what the app looks like NOW.

The captures are of the whole window -- frame and title bar included --
the way the OS draws it, not just the client area, so they look the way
the old ones did.

Usage:
    python -I tools/shots.py                 # write into screenshots/
    python -I tools/shots.py --out somewhere-else
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SHOTS = os.path.join(ROOT, "screenshots")
SCREENS = os.path.join(SHOTS, "screens")

# The screenshot file -> the window in qtranslate.qt that fills it.
# The name is the one the folder already used, so the old links keep
# working.
MAP = {
    "main": "main",
    "dict": "dict",
    "hist": "hist",
    "kbd": "kbd",
    "options": "options",
    "options_basics": "basics",
    "options_hotkeys": "hotkeys",
    "options_internet": "internet",
    "options_services": "services",
    "options_languages": "languages",
    "options_appearance": "appearance",
    "options_exceptions": "exceptions",
    "options_advanced": "advanced",
    "options_updates": "updates",
    "popup": "popup",
    "tray": "tray",
}


def capture(window, out_path):
    """Write the whole window -- frame and title bar -- to out_path."""
    from PySide6.QtCore import QRect
    screen = window.screen() or window.qapp.primaryScreen()
    win = window.windowHandle()
    if win is not None:
        pm = screen.grabWindow(win.winId())
        if not pm.isNull() and pm.width() > 1:
            pm.save(out_path)
            return pm.width(), pm.height()
    window.grab().save(out_path)
    return window.width(), window.height()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=SHOTS)
    args = ap.parse_args()
    out = args.out
    screens = os.path.join(out, "screens")
    os.makedirs(screens, exist_ok=True)

    os.environ.pop("QT_QPA_PLATFORM", None)
    from qtranslate.qt.app import QtApp
    from qtranslate.qt import options as options_mod

    app = QtApp([sys.argv[0]])
    app._load_session()

    made = 0
    for name, kind in MAP.items():
        try:
            if kind == "main":
                from qtranslate.qt.main_window import MainWindow
                window = MainWindow(app)
            elif name == "options" or name.startswith("options_"):
                cls = {"options": "BasicsPage",
                       "options_basics": "BasicsPage",
                       "options_hotkeys": "HotkeysPage",
                       "options_internet": "InternetPage",
                       "options_services": "ServicesPage",
                       "options_languages": "LanguagesPage",
                       "options_appearance": "AppearancePage",
                       "options_exceptions": "ExceptionsPage",
                       "options_advanced": "AdvancedPage",
                       "options_updates": "UpdatesPage"}[name]
                window = getattr(options_mod, cls)(app)
            elif kind == "dict":
                from qtranslate.qt.dictionary import DictionaryWindow
                window = DictionaryWindow(app)
            elif kind == "hist":
                from qtranslate.qt.history_window import HistoryWindow
                window = HistoryWindow(app)
            elif kind == "kbd":
                from qtranslate.qt.keyboard import KeyboardWindow
                window = KeyboardWindow(app)
            elif kind == "popup":
                from qtranslate.qt.popup import PopupWindow
                window = PopupWindow(app)
            elif kind == "tray":
                # The tray is a QSystemTrayIcon; what the picture shows
                # is its MENU, which is what the native's capture shows
                # too (the real taskbar menu, drawn by the OS).
                from qtranslate.qt.tray import Tray
                tray = Tray(app)
                window = tray.menu
            else:
                continue
        except (ImportError, AttributeError) as e:
            print("%-18s skipped (%s: %s)" % (name, type(e).__name__, e))
            continue
        window.show()
        app.qapp.processEvents()
        path = os.path.join(screens, name + ".png")
        w, h = capture(window, path)
        made += 1
        print("%-18s -> %s (%dx%d)" % (name, os.path.relpath(path, ROOT), w, h))
        window.hide()

    print("%d screenshots written" % made)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
