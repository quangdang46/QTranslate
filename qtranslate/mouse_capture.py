"""Mouse-selection capture — port of the native mouse paths (B / C3).

Native chain (REVERIFIED 2026-10-10 against the recovered image, Ghidra
12.1.4 decompile — see docs/review/C3_C8_C10_MOUSE_2026-10-10.md):

  FUN_00417E4E  RawInput WM_INPUT -> normalize to WM_LBUTTONDOWN(0x201)/
                WM_LBUTTONUP(0x202) via GetSystemMetrics(0x17)=SM_SWAPBUTTON
                handedness -> FUN_004193F6
  FUN_004193F6  down: WindowFromPoint; skip own window + exclusions
                (FUN_004631DE / FUN_004630C5); if point inside window, record
                {hwnd,rect,pt} at this+0x17f8 / this+0x1804.
  FUN_00404901  (mode 2, gated by DAT_005494e4) GetCursorPos ->
                AccessibleObjectFromPoint -> IAccessible::get_accName, falling
                back to get_accValue when the name is empty; result lands in a
                CString whose emptiness gates success (return `len != 0`).
  FUN_004183bd  (main WndProc) MouseModeOn: mode 0 -> TaskShowIcons,
                mode 1 -> TaskShowPopupWindow, mode 2 -> popup + read aloud.

This module reproduces the trigger and both text-extractions with ctypes
(no new dependency). It only decides *when* a selection click happened and
hands (x, y) to a callback — the callback performs the actual translate/popup,
so this mirrors the native split (capture vs task).

Two mechanism deltas from native are deliberate and recorded: native uses
WM_INPUT/RawInput, this uses WH_MOUSE_LL (SetWindowsHookExW has 0 callers in
the real image); and the SM_SWAPBUTTON normalization is applied here even
though the LL hook already reports physical buttons, so a left-handed user
sees the same mapping native does.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WH_MOUSE_LL = 14
SM_SWAPBUTTON = 0x17
RID_INPUT = 0x10000003
# ignore a selection/noise click smaller than this move (native: click vs drag)
CLICK_MOVE_TOL = 4

_handle = None  # keep the callback + hook alive for the hook's lifetime


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD),
                ("flags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


def available() -> bool:
    return sys.platform == "win32"


def _buttons_swapped() -> bool:
    """GetSystemMetrics(SM_SWAPBUTTON) — native handedness check (FUN_00417E4E)."""
    try:
        return bool(ctypes.windll.user32.GetSystemMetrics(SM_SWAPBUTTON))
    except Exception:
        return False


def cursor_text(x: int, y: int) -> str:
    """C3 — read the text under the cursor via MSAA/OLEACC.

    Port of FUN_00404901: GetCursorPos -> AccessibleObjectFromPoint ->
    IAccessible::get_accName, falling back to get_accValue when the name comes
    back empty (native checks SysStringLen == 0 first). Returns "" when
    nothing is there — native likewise returns 'CString is empty'.
    """
    if sys.platform != "win32":
        return ""
    oleacc = ctypes.windll.oleacc
    oleaut = ctypes.windll.oleaut32
    ole32 = ctypes.windll.ole32
    user32 = ctypes.windll.user32

    pt = wt.POINT(x, y)
    pacc = ctypes.c_void_p()
    var_child = ctypes.c_void_p()
    # AccessibleObjectFromPoint(POINT, IAccessible**, VARIANT*)
    hr = oleacc.AccessibleObjectFromPoint(
        pt, ctypes.byref(pacc), ctypes.byref(var_child))
    if hr < 0 or not pacc:
        return ""
    try:
        vtbl = ctypes.cast(pacc, ctypes.POINTER(ctypes.c_void_p)).contents
        fn_get_name = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p)(vtbl[10])
        fn_get_value = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p)(vtbl[11])
        bstr = ctypes.c_void_p()
        # IAccessible vtable: get_accName at 10, get_accValue at 11 (0-based).
        if fn_get_name(pacc, var_child, ctypes.byref(bstr)) >= 0 and bstr:
            try:
                if oleaut.SysStringLen(bstr):
                    return ctypes.wstring_at(bstr).strip()
            finally:
                oleaut.SysFreeString(bstr)
        bstr = ctypes.c_void_p()
        if fn_get_value(pacc, var_child, ctypes.byref(bstr)) >= 0 and bstr:
            try:
                if oleaut.SysStringLen(bstr):
                    return ctypes.wstring_at(bstr).strip()
            finally:
                oleaut.SysFreeString(bstr)
        return ""
    finally:
        if pacc:
            ole32.Release(pacc)


def _foreground_window():
    u = ctypes.windll.user32
    return u.GetForegroundWindow()


def _window_from_point(x: int, y: int):
    """WindowFromPoint — native FUN_004193F6's down-side lookup."""
    try:
        pt = wt.POINT(x, y)
        return ctypes.windll.user32.WindowFromPoint(pt)
    except Exception:
        return None


def _own_window():
    """Tk's HWND, so a click on our own window can be skipped like native."""
    try:
        import tkinter as tk
        r = tk._default_root if hasattr(tk, "_default_root") else None
    except Exception:
        r = None
    try:
        if r is not None:
            return r.winfo_id()
        root = tk.Tk()
        hwnd = root.winfo_id()
        root.destroy()
        return hwnd
    except Exception:
        return None


def should_capture(x: int, y: int, own: bool = True) -> bool:
    """Native's down-side gate: not our own window, and point really inside it.

    FUN_004193F6 skips when WindowFromPoint == the app's own window (this+0x1280)
    and records only when PtInRect(GetWindowRect(hwnd), pt) holds. The exclusion
    (blocked app/class) check is the caller's job — native does it here, the port
    keeps it with the other gates in the task callback.
    """
    if sys.platform != "win32":
        return False
    hwnd = _window_from_point(x, y)
    if not hwnd:
        return False
    if own:
        mine = _own_window()
        if mine and hwnd == mine:
            return False
    try:
        rc = wt.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc))
        return (rc.left <= x <= rc.right) and (rc.top <= y <= rc.bottom)
    except Exception:
        return True


def start(on_select, on_click=None, own_window: bool = True):
    """Install the low-level mouse hook. ``on_select(x, y)`` fires on a
    click (down+up in the same place, i.e. a text selection click), with the
    native down-side gate applied first.

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
    swapped = _buttons_swapped()

    def _proc(ncode, wparam, lparam):
        if ncode == 0:
            info = ctypes.cast(lparam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
            pt = (info.pt.x, info.pt.y)
            # WH_MOUSE_LL reports physical buttons already; native reads RawInput
            # flags and re-maps them through SM_SWAPBUTTON, so a swapped-button
            # user gets the same trigger here. Recorded as a mechanism delta.
            down, up = (WM_LBUTTONUP, WM_LBUTTONDOWN) if swapped \
                else (WM_LBUTTONDOWN, WM_LBUTTONUP)
            if wparam == down:
                state["down"] = pt
            elif wparam == up and state["down"] is not None:
                dx = abs(pt[0] - state["down"][0])
                dy = abs(pt[1] - state["down"][1])
                state["down"] = None
                if dx <= CLICK_MOVE_TOL and dy <= CLICK_MOVE_TOL:
                    if should_capture(pt[0], pt[1], own=own_window):
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

