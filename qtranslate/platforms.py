"""Platform interfaces + Windows adapter — Slice 4 (approved 2026-10-15).

Per ``ARCHITECTURE.md`` §4: Core talks to Clipboard/Hotkey/Capture/Audio/
Window/Paths/SpeechInput through these interfaces, never through
concrete Windows calls. The Windows adapter wraps current behavior;
any other platform reports capabilities honestly as unavailable until
a real adapter exists.

tkinter-free (pinned by ``tests/regress_platforms.py``).
"""
from __future__ import annotations


class Capability:
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NEEDS_PERMISSION = "needs-permission"


class Clipboard:
    def read_text(self):
        raise NotImplementedError

    def write_text(self, text):
        raise NotImplementedError

    def sequence(self):
        """Monotonic change counter (native: GetClipboardSequenceNumber)."""
        raise NotImplementedError


class Hotkey:
    def add(self, spec, callback):
        raise NotImplementedError

    def remove(self, spec):
        raise NotImplementedError


class Capture:
    def grab_region(self, box):
        raise NotImplementedError


class Audio:
    def play_text(self, text, lang, slow=False):
        raise NotImplementedError


class Window:
    def flash(self, hwnd=None):
        raise NotImplementedError


class Paths:
    def app_data(self):
        raise NotImplementedError

    def extensions_dir(self):
        raise NotImplementedError


def app_data_dir() -> str:
    """The per-user data directory (D16).

    Windows: ``%APPDATA%\\QTranslate``. Everywhere else:
    ``~/.config/QTranslate``.

    The native keeps its ``Options.json`` in the Windows location; the
    port keeps the same shape everywhere, so its settings file does not
    land in the CURRENT WORKING DIRECTORY. It used to: ``%APPDATA%`` is
    empty off Windows, ``os.path.join("", "QTranslate", "Options.json")``
    is a RELATIVE path, and on macOS -- where the filesystem is
    case-insensitive -- that resolved to ``qtranslate/Options.json``
    *inside the package directory*.
    """
    import os
    base = os.environ.get("APPDATA", "")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "QTranslate")


class SpeechInput:
    def recognize_once(self, lang):
        raise NotImplementedError


class WindowsAdapter:
    """Current Windows behavior behind the interfaces."""

    clipboard = Capability.AVAILABLE
    hotkey = Capability.AVAILABLE
    capture = Capability.AVAILABLE
    audio = Capability.AVAILABLE
    window = Capability.AVAILABLE
    paths = Capability.AVAILABLE
    speech = Capability.NEEDS_PERMISSION  # SAPI/COM recognizer

    def read_text(self):
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            return ""

    def write_text(self, text):
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def sequence(self):
        try:
            import ctypes
            return int(ctypes.windll.user32.GetClipboardSequenceNumber())
        except Exception:
            return -1

    def app_data(self):
        """Per-user app-data dir (D16): ``%APPDATA%/QTranslate``."""
        return app_data_dir()

    def extensions_dir(self):
        """Where QTranslate looks for user extensions (D16).

        Never the install directory: extensions survive app updates and
        need no admin rights. Discovery is fail-open (see ``extensions``).
        """
        import os
        return os.path.join(self.app_data(), "extensions")

    def capability(self, name):
        return getattr(self, name, Capability.UNAVAILABLE)


class MacOSAdapter:
    """The platform pieces that need no Win32: clipboard, paths.

    The Win32-only halves (the global-hotkey hook, the low-level mouse
    hook, the clipboard sequence counter, SAPI speech) stay unavailable
    honestly -- a caller that asks for one still gets the
    ``NotImplementedError``, the same as before. But the two pieces that
    are pure Python work everywhere: ``pyperclip`` reads and writes the
    clipboard on macOS too, and the per-user folder is
    ``~/.config/QTranslate`` (what ``app_data_dir()`` already resolves
    to off Windows). Extensions therefore resolve and load on macOS;
    only the Win32 capture hooks do not.
    """

    clipboard = Capability.AVAILABLE
    paths = Capability.AVAILABLE

    def read_text(self):
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            return ""

    def write_text(self, text):
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def app_data(self):
        return app_data_dir()

    def extensions_dir(self):
        """``~/.config/QTranslate/extensions`` (see ``app_data_dir``)."""
        import os
        return os.path.join(self.app_data(), "extensions")

    def capability(self, name):
        return getattr(self, name, Capability.UNAVAILABLE)


class UnavailableAdapter:
    """Honest fallback: every capability reports unavailable."""

    def __getattr__(self, name):
        if name == "capability":
            return lambda _n: Capability.UNAVAILABLE
        raise NotImplementedError("unavailable on this platform: %s" % name)


def current():
    """The adapter for this machine."""
    try:
        import sys
        if sys.platform == "win32":
            return WindowsAdapter()
        if sys.platform == "darwin":
            return MacOSAdapter()
    except Exception:
        pass
    return UnavailableAdapter()
