"""One-shot launcher: qtranslate-re full UI.

Usage:
  python -I start_app.py [service] [target_lang] [theme]
  uv run --with keyboard --with pyperclip -- python -I start_app.py google vi

Checks runtime deps first and tells you exactly what to install.
"""
import sys

sys.path.insert(0, ".")

missing = []
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
    print("Install with:  pip install -r requirements.txt")
    print("Or run zero-install:")
    print("  uv run --with keyboard --with pyperclip -- "
          "python -I start_app.py")
    raise SystemExit(1)

from qtranslate.app import main

if __name__ == "__main__":
    main()
