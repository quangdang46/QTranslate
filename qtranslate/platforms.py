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
        import os
        return os.path.join(os.environ.get("APPDATA", ""), "QTranslate")

    def extensions_dir(self):
        """Where QTranslate looks for user extensions (D16).

        Never the install directory: extensions survive app updates and
        need no admin rights. Discovery is fail-open (see ``extensions``).
        """
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
    """The adapter for this machine (Windows behavior today)."""
    try:
        import sys
        if sys.platform == "win32":
            return WindowsAdapter()
    except Exception:
        pass
    return UnavailableAdapter()
