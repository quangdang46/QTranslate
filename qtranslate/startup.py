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
    if _wr is None:
        return False, (lambda on: None)

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
