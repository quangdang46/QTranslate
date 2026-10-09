"""Mouse-selection capture — port of the native RawInput click path (B).

Native chain (REVERIFIED 2026-10-09):
  FUN_00417E4E  RawInput WM_INPUT -> normalize to WM_LBUTTONDOWN(0x201)/
                WM_LBUTTONUP(0x202) via GetSystemMetrics(0x17) handedness
                -> FUN_004193F6
  FUN_004193F6  down: WindowFromPoint; skip own window + exclusions
                (FUN_004631DE); if point inside window, record {hwnd,rect,pt}.
                up: same window + click-not-drag (rect size + double-click
                timing) -> PostMessageW(main, 0x8064|0x8069, 0, 0)
  FUN_004183bd  (main WndProc) when MouseModeOn: mode 0 -> TaskShowIcons,
                mode 1 -> TaskShowPopupWindow, mode 2 -> popup + read aloud.

This module reproduces that trigger with a Win32 WH_MOUSE_LL hook (ctypes;
no new dependency). It only decides *when* a selection click happened and
hands (x, y, hwnd) to a callback — the callback performs the actual
translate/popup, so this mirrors the native split (capture vs task).

The from-cursor icon/tooltip rendering is a Tk/other-app UI-timing behavior
that cannot be validated in this environment; the trigger + callback is the
recoverable logic.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WH_MOUSE_LL = 14
# ignore a selection/noise click smaller than this move (native: click vs drag)
CLICK_MOVE_TOL = 4

_handle = None  # keep the callback + hook alive for the hook's lifetime


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD),
                ("flags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


def _foreground_window():
    u = ctypes.windll.user32
    return u.GetForegroundWindow()


def available() -> bool:
    return sys.platform == "win32"


def start(on_select, on_click=None):
    """Install the low-level mouse hook. ``on_select(x, y)`` fires on a
    click (down+up in the same place, i.e. a text selection click).

    Returns True if installed. Safe no-op off Windows.
    """
    global _handle
    if sys.platform != "win32":
        return False
    if _handle is not None:
        return True
    u = ctypes.windll.user32
    k = ctypes.windll.kernel32

    HOOKPROC = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
    state = {"down": None}

    def _proc(ncode, wparam, lparam):
        if ncode == 0:
            info = ctypes.cast(lparam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
            pt = (info.pt.x, info.pt.y)
            if wparam == WM_LBUTTONDOWN:
                state["down"] = pt
            elif wparam == WM_LBUTTONUP and state["down"] is not None:
                dx = abs(pt[0] - state["down"][0])
                dy = abs(pt[1] - state["down"][1])
                state["down"] = None
                if dx <= CLICK_MOVE_TOL and dy <= CLICK_MOVE_TOL:
                    try:
                        on_select(pt[0], pt[1])
                    except Exception:
                        pass
        return u.CallNextHookEx(None, ncode, wparam, lparam)

    proc = HOOKPROC(_proc)
    h = u.SetWindowsHookExW(WH_MOUSE_LL, proc, k.GetModuleHandleW(None), 0)
    if not h:
        return False
    _handle = {"hook": h, "proc": proc}
    return True


def stop():
    global _handle
    if _handle is None:
        return
    try:
        ctypes.windll.user32.UnhookWindowsHookEx(_handle["hook"])
    except Exception:
        pass
    _handle = None
