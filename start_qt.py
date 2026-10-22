"""One-shot launcher: the PySide6 front end.

The port has two views over the same core. `start_app.py` starts the
tkinter one, which is the app that has shipped so far; this one starts
the PySide6 one, the parity port whose windows are drawn on the
geometry measured off the native QTranslate 6.10.0.

Usage:
  python -I start_qt.py [service] [target_lang] [theme]
  uv run --with PySide6 --with keyboard --with pyperclip -- python -I start_qt.py google vi

Checks the runtime deps first and tells you exactly what to install.
"""
import sys

sys.path.insert(0, ".")

missing = []
try:
    import PySide6  # noqa: F401
except Exception:
    missing.append("PySide6")
# `keyboard` aborts the process on macOS Cocoa (not a catchable ImportError),
# so only import it where the app actually uses global hotkeys: Windows.
if sys.platform == "win32":
    try:
        import keyboard  # noqa: F401
    except Exception:
        missing.append("keyboard")
try:
    import pyperclip  # noqa: F401
except Exception:
    missing.append("pyperclip")

if missing:
    print("Missing: " + ", ".join(missing))
    print("Install with:  pip install PySide6")
    print("Or run zero-install:")
    print("  uv run --with PySide6 --with keyboard --with pyperclip -- "
          "python -I start_qt.py")
    raise SystemExit(1)

from qtranslate.qt.app import main

if __name__ == "__main__":
    main()
