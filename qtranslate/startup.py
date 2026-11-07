"""Start-with-Windows: the HKCU Run entry (native's row G).

The native keeps a ``QTranslate`` value under
``HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
and the Options/Basics page's "Start with Windows" checkbox reads and
writes it.

It lives here, in Core, rather than in a view: the setting is the
APP's, and both the Qt front end and anything else that wants to know
whether the app starts with Windows have to be able to ask.

``winreg_mod`` is injectable so the logic can be tested headless; where
there is no winreg (anywhere but Windows) the answer is
``(False, no-op)`` -- honest, rather than pretending.
"""
from __future__ import annotations

import os
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "QTranslate"


def startup_entry(winreg_mod=None, executable=None):
    """Read/write the HKCU Run entry for start-with-Windows.

    Returns ``(present, set_present)``: ``present`` is whether the
    ``QTranslate`` value exists under the Run key; ``set_present(True)``
    writes it and ``set_present(False)`` deletes it.
    """
    try:
        import winreg as _wr
    except Exception:
        _wr = None
    if winreg_mod is not None:
        _wr = winreg_mod
    if _wr is not None:
        return _windows_entry(_wr, executable)
    if sys.platform == "darwin":
        return _darwin_entry(executable)
    return False, (lambda on: None)


def _windows_entry(_wr, executable):

    def _read():
        try:
            _rk = _wr.OpenKey(_wr.HKEY_CURRENT_USER, RUN_KEY)
            _wr.QueryValueEx(_rk, VALUE_NAME)
            return True
        except Exception:
            return False

    def _write(on):
        try:
            _rk2 = _wr.OpenKey(_wr.HKEY_CURRENT_USER, RUN_KEY,
                               0, _wr.KEY_SET_VALUE)
            if on:
                _wr.SetValueEx(_rk2, VALUE_NAME, 0, _wr.REG_SZ,
                               executable or sys.executable)
            else:
                try:
                    _wr.DeleteValue(_rk2, VALUE_NAME)
                except Exception:
                    pass
        except Exception:
            pass

    return _read(), _write


# --------------------------------------------------------------- macOS
#
# The macOS equivalent of the Run key is a per-user LaunchAgent:
# ``~/Library/LaunchAgents/com.cognition.qtranslate.plist`` loaded into
# the gui domain. Presence is the plist file itself; toggling writes or
# removes it and asks launchd to (un)load it. The command is the frozen
# bundle when there is one, else the repo's start_qt.py under the same
# interpreter -- the honest "start this app at login" either way.

_DARWIN_LABEL = "com.cognition.qtranslate"


def _darwin_plist_path() -> str:
    return os.path.join(os.path.expanduser("~/Library/LaunchAgents"),
                        _DARWIN_LABEL + ".plist")


def _darwin_command(executable):
    """The argv launchd runs: the bundle binary, or repo + interpreter."""
    exe = executable or sys.executable
    if getattr(sys, "frozen", False) or os.path.basename(exe).lower() \
            in ("qtranslate", "qtranslate.exe"):
        return [exe]
    # A source checkout: run start_qt.py with this interpreter.
    start = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "start_qt.py")
    if os.path.exists(start):
        return [sys.executable, "-I", start]
    return [exe]


def _darwin_entry(executable=None):
    import os
    import plistlib
    import subprocess

    path = _darwin_plist_path()

    def _present():
        return os.path.exists(path)

    def _write(on):
        try:
            if on:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                uid = os.getuid()
                plist = {
                    "Label": _DARWIN_LABEL,
                    "ProgramArguments": _darwin_command(executable),
                    "RunAtLoad": True,
                }
                with open(path, "wb") as fh:
                    plistlib.dump(plist, fh)
                subprocess.run(
                    ["launchctl", "bootstrap",
                     "gui/%d" % uid, path],
                    capture_output=True, timeout=10)
            else:
                uid = os.getuid()
                subprocess.run(
                    ["launchctl", "bootout",
                     "gui/%d/%s" % (uid, _DARWIN_LABEL)],
                    capture_output=True, timeout=10)
                try:
                    os.unlink(path)
                except OSError:
                    pass
        except Exception:
            pass

    return _present(), _write
