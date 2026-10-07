"""Foreground exclusion check — port of FUN_004631DE + FUN_004470B7.

Skips capture when the foreground window's class (or process) is in the
Options.json Exceptions.Disabled blocklist. Matcher is case-insensitive
exact (wcsicmp); empty side matches anything.
"""
import ctypes
from ctypes import wintypes

# Default blocklist from a real Options.json (Exceptions.Disabled)
DEFAULT_DISABLED = [
    ("", "SysListView32"), ("", "SysTreeView32"), ("", "ListBox"),
    ("", "ScrollBar"), ("", "ComboBox"), ("", "msctls_hotkey32"),
    ("", "ConsoleWindowClass"), ("mstsc.exe", ""),
]


def _fg_class_and_exe():
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", ""
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    exe = ""
    try:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
        if h:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.psapi.GetModuleFileNameExW(h, None, buf, 260)
            exe = buf.value.split("\\")[-1]
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        pass
    return cls.value, exe


def is_excluded(cls_name: str, exe_name: str,
                disabled: list | None = None) -> bool:
    """Port of the FUN_004631DE loop with FUN_004470B7 wcsicmp matcher."""
    for app, cls in (disabled or DEFAULT_DISABLED):
        app_hit = (not app) or (app.lower() == exe_name.lower())
        cls_hit = (not cls) or (cls.lower() == cls_name.lower())
        if app_hit and cls_hit:
            return True
    return False


def _live_lists():
    """Read Exceptions section live (Disabled/Enabled/DisabledMode).

    DisabledMode=true (native default): Disabled = blocklist.
    false: Enabled = allowlist (everything else blocked).
    """
    try:
        from qtranslate import config as _C
        _ex = _C.load().get("Exceptions", {})
        dis = [tuple(p) for p in _ex.get("Disabled", [])
               if isinstance(p, (list, tuple)) and len(p) >= 2]
        ena = [tuple(p) for p in _ex.get("Enabled", [])
               if isinstance(p, (list, tuple)) and len(p) >= 2]
        return dis, ena, bool(_ex.get("DisabledMode", True))
    except Exception:
        return list(DEFAULT_DISABLED), [], True


def foreground_excluded(disabled: list | None = None) -> bool:
    cls, exe = _fg_class_and_exe()
    if disabled is not None:
        return is_excluded(cls, exe, disabled)
    dis, ena, mode = _live_lists()
    if mode:
        return is_excluded(cls, exe, dis or list(DEFAULT_DISABLED))
    # allowlist mode: blocked unless explicitly enabled
    if not ena:
        return False
    for app, cl in ena:
        app_hit = (not app) or (app.lower() == exe.lower())
        cls_hit = (not cl) or (cl.lower() == cls.lower())
        if app_hit and cls_hit:
            return False
    return True


if __name__ == "__main__":
    print(_fg_class_and_exe(), foreground_excluded())
