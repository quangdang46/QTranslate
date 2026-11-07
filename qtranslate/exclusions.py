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
    import sys
    if sys.platform == "darwin":
        return _darwin_fg()
    if sys.platform != "win32":
        # No Win32 foreground-window query off Windows; return the
        # empty pair so the matchers simply do not fire (nothing is
        # excluded) instead of crashing on ctypes.windll.
        return "", ""
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


def _darwin_fg():
    """The macOS pair for the same question.

    There is no HWND class on macOS; the honest equivalents are the
    frontmost app's bundle identifier (the "window class" slot) and its
    localized name (the "program" slot). An Exceptions row written for
    macOS is therefore ``("Safari", "com.apple.Safari")`` -- and a row
    written for Windows simply never matches, which is correct: those
    class names do not exist here.
    """
    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return "", ""
        bundle = app.bundleIdentifier() or ""
        name = app.localizedName() or ""
        if not name:
            try:
                name = app.executableURL().lastPathComponent() or ""
            except Exception:
                name = ""
        return bundle, name
    except Exception:
        return "", ""


def _side_hit(pattern: str, value: str) -> bool:
    """One side of an Exceptions row. Empty matches anything (native's
    wcsicmp rule); the UI's sentinel rows '* All Programs *' / '* All
    Windows *' are wildcards too -- comparing them literally never
    matched, so saving the default list silently disabled every
    exclusion (the Exceptions-page audit)."""
    if not pattern:
        return True
    if pattern in ("* All Programs *", "* All Windows *"):
        return True
    return pattern.lower() == (value or "").lower()


def is_excluded(cls_name: str, exe_name: str,
                disabled: list | None = None) -> bool:
    """Port of the FUN_004631DE loop with FUN_004470B7 wcsicmp matcher."""
    for app, cls in (disabled or DEFAULT_DISABLED):
        if _side_hit(app, exe_name) and _side_hit(cls, cls_name):
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
    if not cls and not exe:
        # The frontmost app could not be determined (headless, test
        # harness, permission gap): exclusion is a DENY-list, so an
        # unknown foreground must fail OPEN -- otherwise every hotkey
        # silently dies on machines where the lookup returns nothing.
        return False
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
