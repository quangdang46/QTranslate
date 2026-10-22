"""The PySide6 front end's source, as one string.

The tkinter front end is gone (2026-10-22). The suites that pin "this
wiring is in the view" used to read ``qtranslate/app.py`` (and, after
the Phase 7 split, ``qtranslate/windows.py``); they read the view that
is left now.

The view is several modules, so the source is concatenated -- the pins
are "does this string appear in the view", not "which file is it in".
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QT_DIR = os.path.join(ROOT, "qtranslate", "qt")


def view_source() -> str:
    """Every ``.py`` file of the PySide6 front end, as one string."""
    out = []
    for dirpath, dirnames, filenames in os.walk(QT_DIR):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8", errors="replace") as fh:
                out.append(fh.read())
    return "\n".join(out)
