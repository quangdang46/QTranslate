"""Single-instance guard — port of `FUN_00435175` (row A2).

Native (decompiled 2026-10-15): if the command line does NOT contain
``allow-multiple-instances``, find the existing window by class
``QTranslate_ApplicationWindow``; when found, ``PostMessage(hwnd,
WM_COMMAND=0x111, 0x8009)`` to activate it and return 1 (caller exits
without starting a second copy).

The port mirrors this: ``ensure_single(argv)`` returns ``True`` when the
caller should exit (an existing instance was activated), ``False`` when
startup may continue. ``find_window``/``activate``/``argv_has_flag`` are
injectable so the logic is testable headless; on non-Windows (or a
missing win32 API) it honestly reports "no existing instance".

The tk UI registers the class name through the root window title; the
exact HWND discovery uses ``FindWindowW`` with the same class string the
native binary uses.
"""
from __future__ import annotations

WINDOW_CLASS = "QTranslate_ApplicationWindow"
ACTIVATE_COMMAND = 0x8009
WM_COMMAND = 0x111
MULTI_FLAG = "allow-multiple-instances"


def _default_find():
    try:
        from ctypes import windll as _wd
        hwnd = _wd.user32.FindWindowW(WINDOW_CLASS, None)
        return int(hwnd or 0)
    except Exception:
        return 0


def _default_activate(hwnd):
    try:
        from ctypes import windll as _wd
        return bool(_wd.user32.PostMessageW(hwnd, WM_COMMAND,
                                           ACTIVATE_COMMAND, 0))
    except Exception:
        return False


def ensure_single(argv=None, find_window=None, activate=None):
    """``True`` = another instance was activated; caller must exit.

    ``argv`` carries the command line (checked for the multi-instance
    flag); ``find_window``/``activate`` default to the Win32 calls and
    are fakeable in tests.
    """
    args = list(argv) if argv is not None else []
    if any(MULTI_FLAG in a for a in args):
        return False
    find = find_window if find_window is not None else _default_find
    act = activate if activate is not None else _default_activate
    try:
        hwnd = find()
    except Exception:
        hwnd = 0
    if not hwnd:
        return False
    try:
        act(hwnd)
    except Exception:
        pass
    return True
