"""Mouse-selection capture — port of the native mouse paths (B / C3 / C8).

Native chain (re-decompiled 2026-10-21 with Ghidra 12.1.4 headless from
``docs/review/artifacts/QTranslate.6.10.0.exe``, sha256 ``f35a3bc8…``; the
addresses are the ones cited in ``docs/RE_COVERAGE_CHECKLIST.md`` group C):

  FUN_00417E4E  RawInput WM_INPUT -> normalize to WM_LBUTTONDOWN(0x201) /
                WM_LBUTTONUP(0x202) using GetSystemMetrics(0x17)=
                SM_SWAPBUTTON handedness -> FUN_004193F6
  FUN_004193F6  down side: FUN_00450DD2(x,y) (WindowFromPoint, then the
                smallest visible child holding the point, then walk up past
                invisible parents); skip our own window (this+0x1280);
                exclusion check FUN_004631DE(&DAT_005494B0, hwnd) — or
                FUN_004630C5 when DAT_005494D0 — against *that* handle;
                GetWindowRect + PtInRect; record {pt, hwnd, rect} at
                this+0x17f8 / this+0x1804 / this+0x1808..0x1814.  Up side:
                only completes a capture when the down side recorded a
                target (this+0x1804 != 0).
  FUN_00404901  (mode 2, gated by DAT_005494e4) GetCursorPos ->
                AccessibleObjectFromPoint -> IAccessible::get_accName,
                falling back to get_accValue when the name is empty; the
                result lands in a CString whose emptiness gates success.
  FUN_004183bd  (main WndProc) MouseModeOn: mode 0 -> TaskShowIcons,
                mode 1 -> TaskShowPopupWindow, mode 2 -> popup + read aloud.

This module reproduces the trigger and both text-extractions with ctypes
(no new dependency). It only decides *when* a selection click happened and
hands (x, y) to a callback — the callback performs the actual translate /
popup, so this mirrors the native split (capture vs task).

Two mechanism deltas from native are deliberate and recorded:

  * native uses WM_INPUT/RawInput, this uses WH_MOUSE_LL (SetWindowsHookExW
    has 0 callers in the real image); and
  * the handedness normalization is **not** re-applied to the hook. Windows
    applies the mouse-button swap when it turns a raw button byte into a
    window message, so WH_MOUSE_LL already reports the user's primary
    button as WM_LBUTTONDOWN. RawInput sits *below* that layer and still
    names the physical button, which is why native needs
    GetSystemMetrics(0x17) at all. Re-applying the swap here (as this
    module did until 2026-10-21) double-swaps and leaves a left-handed user
    with no capture trigger at all.

Fidelity gaps closed 2026-10-21, per §C8 of
``docs/review/C3_C8_C10_MOUSE_2026-10-10.md``:

  * the SM_SWAPBUTTON double-swap that killed the trigger for left-handed
    users — see ``normalize_raw_button`` (native's rule, 1:1) and
    ``primary_button_messages`` (the hook's equivalent);
  * the own-window skip — ``is_own_window`` compares against our own
    toplevel; the old code produced a handle that was destroyed again
    immediately, so it could never match;
  * the exclusion list — ``class_excluded`` matches the window *under the
    cursor* (native FUN_004193F6 -> FUN_004631DE), not only the foreground
    window (that one is native's hotkey path, FUN_00418E1A).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WH_MOUSE_LL = 14
SM_SWAPBUTTON = 0x17
RID_INPUT = 0x10000003
# ignore a selection/noise click smaller than this move (native: click vs drag)
CLICK_MOVE_TOL = 4

# RAWMOUSE.usButtonFlags — the four flags native reads at FUN_00417E4E.
RI_LEFT_DOWN = 0x0001
RI_LEFT_UP = 0x0002
RI_RIGHT_DOWN = 0x0004
RI_RIGHT_UP = 0x0008

# GetAncestor
GA_ROOT = 2

_handle = None  # keep the callback + hook alive for the hook's lifetime
_own_hwnd = None  # cached handle of our own toplevel (native this+0x1280)
_excl_cache = {"at": -1.0, "dis": None, "ena": None, "mode": True}


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD),
                ("flags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


def available() -> bool:
    return sys.platform == "win32"


def _buttons_swapped() -> bool:
    """GetSystemMetrics(SM_SWAPBUTTON) — native handedness check (FUN_00417E4E).

    Native asks this because RawInput reports the *physical* button index.
    See ``normalize_raw_button`` and ``primary_button_messages``.
    """
    try:
        return bool(ctypes.windll.user32.GetSystemMetrics(SM_SWAPBUTTON))
    except Exception:
        return False


# ---------------------------------------------------------------- normalization


def normalize_raw_button(flags: int, swapped: bool) -> int:
    """Native FUN_00417E4E's RawInput -> WM_LBUTTONDOWN/UP normalization.

    1:1 with the decompiled branch structure (Ghidra 12.1.4, 2026-10-21)::

        GetRawInputData(hRawInput, RID_INPUT, buf, &0x28, 0x10);
        if (GetSystemMetrics(0x17) == 0) {        // buttons NOT swapped
            if (flags & 0x01) goto DOWN;           // physical left down
            flags &= 0x02;                        // physical left up
        } else {                                  // buttons swapped
            if (flags & 0x04) goto DOWN;           // physical right down
            flags &= 0x08;                        // physical right up
        }
        if (!flags) return 0;
        DOWN: iVar2 = 0x201;
        UP:   iVar2 = 0x202;

    So the *physical* button that the user has made primary is what native
    turns into WM_LBUTTONDOWN/WM_LBUTTONUP: the left one normally, the right
    one when the buttons are swapped.

    Returns WM_LBUTTONDOWN, WM_LBUTTONUP, or 0 for "not a primary-button
    event".
    """
    if not swapped:
        if flags & RI_LEFT_DOWN:
            return WM_LBUTTONDOWN
        flags &= RI_LEFT_UP
    else:
        if flags & RI_RIGHT_DOWN:
            return WM_LBUTTONDOWN
        flags &= RI_RIGHT_UP
    if not flags:
        return 0
    return WM_LBUTTONUP


def primary_button_messages() -> tuple:
    """The WM_* pair the low-level hook reports for the user's primary button.

    Windows applies the mouse-button swap when it turns a raw button byte
    into a window message, so ``WM_LBUTTONDOWN`` *is* the primary button in
    both handedness settings; RawInput sits below that layer and still
    names the physical button, which is exactly why native has to consult
    ``GetSystemMetrics(0x17)`` (FUN_00417E4E) and this port does not.

    Consequence: swapping the down/up pair here (as this module did until
    2026-10-21) double-swaps and stops the trigger from ever firing for a
    left-handed user.
    """
    return WM_LBUTTONDOWN, WM_LBUTTONUP


# ------------------------------------------------------------------- the gates


def is_own_window(resolved, own) -> bool:
    """True when ``resolved`` is our own window (or a control inside it).

    Native compares the resolved handle with its own main window
    (FUN_004193F6: ``WindowFromPoint(...) != this+0x1280``). The port also
    compares the top-level ancestors, because WindowFromPoint returns the
    deepest child under the cursor while Tk hands out the handle of its
    toplevel's inner window: an exact comparison alone would never match,
    which is how the previous own-window skip stayed dead code.
    """
    if not resolved or not own:
        return False
    if resolved == own:
        return True
    return _root_ancestor(resolved) == _root_ancestor(own)


def _root_ancestor(hwnd):
    """GetAncestor(hwnd, GA_ROOT) — the top-level window that owns hwnd."""
    try:
        root = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
        return root or hwnd
    except Exception:
        return hwnd


def capture_allowed(resolved, own, excluded, inside) -> bool:
    """Native's down-side gate (FUN_004193F6) as a pure decision.

    ``resolved``  handle of the window under the cursor (FUN_00450DD2)
    ``own``       our own window handle, or None when the skip is off
    ``excluded``  the exclusion list matched that window (FUN_004631DE)
    ``inside``    the point is inside the window's rect (PtInRect)

    Native records the click only when all four hold.
    """
    if not resolved:
        return False
    if own and is_own_window(resolved, own):
        return False
    if excluded:
        return False
    return bool(inside)


def _live_lists_cached():
    """The live Exceptions lists, cached for a second.

    ``exclusions._live_lists()`` re-reads Options.json from disk on every
    call, and this runs inside the low-level mouse hook, which has to
    return fast (Windows drops a hook that blocks too long).
    """
    now = time.monotonic()
    cache = _excl_cache
    if cache["dis"] is None or now - cache["at"] > 1.0:
        from qtranslate import exclusions as _ex
        dis, ena, mode = _ex._live_lists()
        cache["dis"] = dis
        cache["ena"] = ena
        cache["mode"] = mode
        cache["at"] = now
    return cache["dis"], cache["ena"], cache["mode"]


def class_excluded(cls_name: str, exe_name: str, disabled=None,
                   enabled=None, mode: bool = True) -> bool:
    """Native's exclusion decision for a window's (class, exe) pair.

    FUN_004631DE reads the window's class with FUN_00450C50 (GetClassNameW)
    and its exe with FUN_00403506 (GetWindowThreadProcessId ->
    OpenProcess -> QueryFullProcessImageNameW -> basename), then matches
    every ``Exceptions.Disabled`` entry with the wcsicmp matcher
    FUN_004470B7; an empty side matches anything.  ``mode=False`` selects
    native's allowlist variant FUN_004630C5: nothing is excluded unless the
    window is explicitly listed in ``Exceptions.Enabled``.
    """
    from qtranslate import exclusions as _ex
    if disabled is None and enabled is None:
        disabled, enabled, mode = _live_lists_cached()
    if mode:
        return _ex.is_excluded(cls_name, exe_name,
                               disabled or list(_ex.DEFAULT_DISABLED))
    if not enabled:
        return False
    for app, cl in enabled:
        app_hit = (not app) or (app.lower() == exe_name.lower())
        cls_hit = (not cl) or (cl.lower() == cls_name.lower())
        if app_hit and cls_hit:
            return False
    return True


def _window_class_and_exe(hwnd):
    """Class name + process exe for an arbitrary hwnd.

    Native: FUN_00450C50 (GetClassNameW) + FUN_00403506 (exe basename).
    """
    if not hwnd:
        return "", ""
    user32 = ctypes.windll.user32
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    exe = ""
    try:
        pid = wt.DWORD()
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


def window_excluded(hwnd, disabled=None) -> bool:
    """Native's exclusion check for the window under the cursor.

    FUN_004193F6 calls ``FUN_004631DE(&DAT_005494B0, hwnd)`` with the handle
    WindowFromPoint returned, so the list is matched against the window the
    cursor is over — not against the foreground window (that check belongs
    to native's hotkey path, FUN_00418E1A).
    """
    cls, exe = _window_class_and_exe(hwnd)
    return class_excluded(cls, exe, disabled=disabled)


# ------------------------------------------------------------------ Win32 glue


def _foreground_window():
    u = ctypes.windll.user32
    return u.GetForegroundWindow()


def _window_from_point(x: int, y: int):
    """FUN_00450DD2 — the window under the cursor.

    Native: WindowFromPoint, then the smallest visible child holding the
    point, then walk up past invisible parents.  The smallest-visible-child
    tie-break is not reproduced here (WindowFromPoint already returns the
    deepest window under the point); the walk up past invisible parents is.
    """
    try:
        u = ctypes.windll.user32
        pt = wt.POINT(x, y)
        hwnd = u.WindowFromPoint(pt)
        if not hwnd:
            return None
        while hwnd and not u.IsWindowVisible(hwnd):
            hwnd = u.GetParent(hwnd)
        return hwnd or None
    except Exception:
        return None


def _own_window():
    """Our own toplevel's handle (native ``this+0x1280``), or None.

    Resolved once and cached: the hook proc must not call into the window
    manager (it runs on the thread that installed the hook). The Qt
    app's main window is looked up through the toolkit instead of the
    throwaway ``tk.Tk()`` handle the tkinter front end used -- a handle
    that can never match once the front end is gone.
    """
    global _own_hwnd
    if _own_hwnd:
        return _own_hwnd
    try:
        try:
            from PySide6.QtWidgets import QApplication  # noqa: F401
            from qtranslate.qt.app import QtApp  # noqa: F401
            from qtranslate.qt.main_window import MainWindow  # noqa: F401
            _app = QApplication.instance()
            _main = getattr(_app, "_topLevelWindows", [])
            for _w in _main:
                if _w.metaObject().className() == b"MainWindow":
                    _own_hwnd = int(_w.winId())
                    break
            if _own_hwnd:
                return _own_hwnd
        except Exception:
            pass
    except Exception:
        return None
    return _own_hwnd


def _point_inside(hwnd, x: int, y: int) -> bool:
    """PtInRect(GetWindowRect(hwnd), pt) — native's down-side confirmation."""
    try:
        rc = wt.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc))
        return (rc.left <= x <= rc.right) and (rc.top <= y <= rc.bottom)
    except Exception:
        return True


def probe_point(x: int, y: int, own: bool = True) -> tuple:
    """The four facts native's down side needs about a point.

    Returns ``(resolved_hwnd, own_hwnd, excluded, inside)``.
    """
    resolved = _window_from_point(x, y)
    own_hwnd = _own_window() if own else None
    excluded = bool(resolved) and window_excluded(resolved)
    inside = bool(resolved) and _point_inside(resolved, x, y)
    return resolved, own_hwnd, excluded, inside


def should_capture(x: int, y: int, own: bool = True) -> bool:
    """Native's down-side gate: not our own window, not excluded, and the
    point really inside the window under the cursor.

    FUN_004193F6 (decompiled 2026-10-21)::

        hwnd = FUN_00450DD2(x, y);
        if (hwnd != this+0x1280) {                       // skip our own
            if (!FUN_004631DE(&DAT_005494B0, hwnd)) {    // not excluded
                GetWindowRect(hwnd, &rc);
                if (PtInRect(&rc, pt)) { ...record the click... }
            }
        }
    """
    if sys.platform != "win32":
        return False
    return capture_allowed(*probe_point(x, y, own=own))


# ------------------------------------------------------------- the click state


def process_mouse_event(state, wparam, x, y, probe, on_select) -> bool:
    """The hook's state machine, factored out of the hook proc.

    ``probe(x, y)`` must return ``(resolved, own, excluded, inside)`` for a
    point; ``on_select(x, y)`` is called when a selection click completes.
    Returns True when a selection fired.

    Native FUN_004193F6 is a two-sided state machine: the down side applies
    every gate and records the target only if they all pass, and the up
    side completes the capture only when the down side recorded one.  The
    old port applied the gate on the *up* side, so a click that started on
    an excluded window and ended on an allowed one was captured.
    """
    down_msg, up_msg = primary_button_messages()
    if wparam == down_msg:
        resolved, own, excluded, inside = probe(x, y)
        state["down"] = (x, y) if capture_allowed(
            resolved, own, excluded, inside) else None
        return False
    if wparam == up_msg:
        rec = state.get("down")
        state["down"] = None
        if not rec:
            return False
        # NATIVE (decompiled 2026-10-24, FUN_004193f6): a PLAIN CLICK
        # fires the capture -- down and up in the same place, on an
        # allowed window, no scrollbar. The anti-loop does NOT live
        # here: native gates on the idle time since the last capture
        # (its FUN_0050bc60() > 10.0 branch) and on "no task already
        # running", both applied at the dispatch (FUN_004183bd). A drag
        # (moving > CLICK_MOVE_TOL) is NOT the native gesture.
        if abs(x - rec[0]) > CLICK_MOVE_TOL or abs(y - rec[1]) > CLICK_MOVE_TOL:
            return False
        on_select(x, y)
        return True
    return False


class _VARIANT(ctypes.Structure):
    """VARIANT (16 bytes). get_accName/Value take a VARIANT by pointer."""
    _fields_ = [("vt", ctypes.c_ushort),
                ("wReserved1", ctypes.c_ushort),
                ("wReserved2", ctypes.c_ushort),
                ("wReserved3", ctypes.c_ushort),
                ("_pad", ctypes.c_ulonglong * 2)]


VT_I4 = 3  # the child id gauge AccessibleObjectFromPoint fills


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
    user32 = ctypes.windll.user32

    pt = wt.POINT(x, y)
    pacc = ctypes.c_void_p()
    var_child = _VARIANT()
    # AccessibleObjectFromPoint(POINT, IAccessible**, VARIANT*)
    hr = oleacc.AccessibleObjectFromPoint(
        pt, ctypes.byref(pacc), ctypes.byref(var_child))
    if hr < 0 or not pacc:
        return ""
    try:
        # pacc.value is the IAccessible* address; the vtable pointer lives
        # at [0] of that address, so slots read as vtbl_ptr[0][k]. A single
        # cast(pacc, POINTER(c_void_p))[k] dereferences one level too few:
        # slots 10/11 came back None and WINFUNCTYPE raised TypeError
        # (measured live against oleacc on this host).
        vtbl_ptr = ctypes.cast(pacc, ctypes.POINTER(
            ctypes.POINTER(ctypes.c_void_p)))
        vtbl = vtbl_ptr[0]
        # Verified E2E against live oleacc on this host
        # (tools probe: hr=0, child.vt=3, real text read, release clean):
        # the entry point takes NO argtypes (restype default) + byref args;
        # the vtable callables are HRESULT(this, VARIANT*, BSTR*) with the
        # child passed BY POINTER. Passing the VARIANT by value segfaults;
        # declaring argtypes on the entry point segfaults too.
        _acc_fn = ctypes.WINFUNCTYPE(
            ctypes.HRESULT,
            ctypes.c_void_p,
            ctypes.POINTER(_VARIANT), ctypes.POINTER(ctypes.c_void_p))
        fn_get_name = _acc_fn(vtbl[10])
        fn_get_value = _acc_fn(vtbl[11])
        bstr = ctypes.c_void_p()
        # IAccessible vtable: get_accName at 10, get_accValue at 11 (0-based).
        if fn_get_name(pacc, ctypes.byref(var_child),
                       ctypes.byref(bstr)) >= 0 and bstr:
            try:
                if oleaut.SysStringLen(bstr):
                    return ctypes.wstring_at(bstr).strip()
            finally:
                oleaut.SysFreeString(bstr)
        bstr = ctypes.c_void_p()
        if fn_get_value(pacc, ctypes.byref(var_child),
                        ctypes.byref(bstr)) >= 0 and bstr:
            try:
                if oleaut.SysStringLen(bstr):
                    return ctypes.wstring_at(bstr).strip()
            finally:
                oleaut.SysFreeString(bstr)
        return ""
    finally:
        # Native frees via IUnknown::Release — vtable slot 2 at byte
        # offset 0x08 (`CALL dword ptr [EDX+0x8]` at 0x504a02), NOT via an
        # ole32.dll export (ole32.dll exports no such function; the old
        # `ole32.Release(pacc)` raised AttributeError on every call).
        # IUnknown::Release(pacc) takes only `this`.
        if pacc:
            try:
                fn_release = ctypes.WINFUNCTYPE(ctypes.c_ulong,
                                                ctypes.c_void_p)(vtbl[2])
                fn_release(pacc)
            except Exception:
                pass


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
    # Resolve our own window here, on the installing thread: the hook proc
    # runs on the thread that installed it and must not call into Tk.
    if own_window:
        _own_window()

    def _proc(ncode, wparam, lparam):
        if ncode == 0:
            info = ctypes.cast(lparam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
            pt = (info.pt.x, info.pt.y)
            try:
                process_mouse_event(
                    state, wparam, pt[0], pt[1],
                    lambda x, y: probe_point(x, y, own=own_window),
                    on_select)
            except Exception:
                pass
        return u.CallNextHookEx(None, ncode, wparam, lparam)

    proc = HOOKPROC(_proc)
    # GetModuleHandleW's HMODULE is pointer-sized; ctypes' default c_int
    # return TRUNCATES it to a signed 32-bit int, and the hook install
    # then fails with ERROR_MOD_NOT_FOUND (126) -- the operator's
    # "bôi đen chả thấy gì" (2026-10-24): the hook never installed, on
    # any machine, in any run. Declare the restype and both handles are
    # the real pointers.
    k.GetModuleHandleW.restype = ctypes.c_void_p
    u.SetWindowsHookExW.restype = ctypes.c_void_p
    u.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC,
                                    ctypes.c_void_p,
                                    ctypes.c_uint]
    h = u.SetWindowsHookExW(WH_MOUSE_LL, proc,
                            k.GetModuleHandleW(None), 0)
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
