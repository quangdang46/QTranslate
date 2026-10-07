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


def foreground_excluded(disabled: list | None = None) -> bool:
    cls, exe = _fg_class_and_exe()
    return is_excluded(cls, exe, disabled)


if __name__ == "__main__":
    print(_fg_class_and_exe(), foreground_excluded())
