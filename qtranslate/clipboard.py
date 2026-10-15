"""Clipboard helpers — port of the native clipboard primitives.

- `FUN_0043BE56` = clipboard WRITE: `OpenClipboard` → `EmptyClipboard` →
  `SetClipboardData(CF_UNICODETEXT=0xD)`.
- `FUN_0043BF30` = clipboard SEQUENCE poll: `GetClipboardSequenceNumber`
  (the Ctrl+C+C engine uses it to prove the copy landed).

The port uses `pyperclip` for read/write (equivalent to CF_UNICODETEXT)
and `ctypes` for the sequence number. Both are wrapped so the contract is
testable and so callers get an honest False / -1 on a missing backend
instead of an exception.
"""
from __future__ import annotations

CF_UNICODETEXT = 0xD  # 13, the format FUN_0043BE56 writes


def write_text(text) -> bool:
    """Write text to the clipboard; True on success (native FUN_0043BE56)."""
    try:
        import pyperclip
        pyperclip.copy("" if text is None else str(text))
        return True
    except Exception:
        return False


def read_text() -> str:
    """Read the clipboard as text; "" when unavailable/empty."""
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        return ""


def sequence() -> int:
    """Monotonic clipboard change counter (native FUN_0043BF30); -1 if
    the Win32 call is unavailable."""
    try:
        from ctypes import windll as _wd
        return int(_wd.user32.GetClipboardSequenceNumber())
    except Exception:
        return -1
