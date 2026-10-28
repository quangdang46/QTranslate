"""Global hotkeys on macOS: Carbon ``RegisterEventHotKey``.

The ``keyboard`` package cannot be used here. It is a pyobjc shim over a
CGEventTap, and on macOS 26 its import ABORTS the process inside
CoreFoundation::

    Assertion failed: (range.location <= dataLength),
    function __CFDataValidateRange, file CFData.c, line 219.

That is a SIGABRT, not an exception -- ``import keyboard`` inside a
``try`` does not save the process. So the macOS front end needs its own
registration path, and the one the OS provides for exactly this is
Carbon's ``RegisterEventHotKey``: the application asks the WindowServer
for a key combination and receives ``kEventHotKeyPressed`` in its event
queue. It needs NO Accessibility permission (unlike an event tap), which
matters because the operator runs an unsigned bundle.

The handler is installed on ``GetApplicationEventTarget()``. Qt on macOS
runs its loop on the main CFRunLoop, so the handler fires on the UI
thread and the callback may touch widgets directly -- the same guarantee
``_on_ui`` gives on the Win32 path.

Key codes are the Carbon ``kVK_*`` virtual key codes, not characters:
``kVK_ANSI_Q`` is 0x0C on every layout, which is why the table below is
keyed by the ASCII character the settings file already produced.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import sys

# Carbon modifier masks (Events.h).
CMD_KEY = 0x0100
SHIFT_KEY = 0x0200
OPTION_KEY = 0x0800
CONTROL_KEY = 0x1000

# Carbon virtual key codes (HIToolbox/Events.h, kVK_*).
KEYCODES = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05,
    "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C,
    "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10, "t": 0x11,
    "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16,
    "5": 0x17, "=": 0x18, "9": 0x19, "7": 0x1A, "-": 0x1B,
    "8": 0x1C, "0": 0x1D, "]": 0x1E, "o": 0x1F, "u": 0x20,
    "[": 0x21, "i": 0x22, "p": 0x23, "return": 0x24, "enter": 0x24,
    "l": 0x25, "j": 0x26, "'": 0x27, "k": 0x28, ";": 0x29,
    "\\": 0x2A, ",": 0x2B, "/": 0x2C, "n": 0x2D, "m": 0x2E,
    ".": 0x2F, "tab": 0x30, "space": 0x31, "`": 0x32,
    "delete": 0x33, "backspace": 0x33, "esc": 0x35, "escape": 0x35,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76, "f5": 0x60,
    "f6": 0x61, "f7": 0x62, "f8": 0x64, "f9": 0x65, "f10": 0x6D,
    "f11": 0x67, "f12": 0x6F,
    "left": 0x7B, "right": 0x7C, "down": 0x7D, "up": 0x7E,
}

kEventClassKeyboard = 0x6B657962   # 'keyb'
kEventHotKeyPressed = 1
typeEventHotKeyID = 0x686B6964     # 'hkid'
# kEventParamDirectObject ('----'): where kEventHotKeyPressed carries its
# EventHotKeyID. Reading it under any other name returns an error, and a
# handler that only *looks* up the parameter therefore fires silently and
# does nothing -- the bug this module shipped with until it was measured.
kEventParamDirectObject = 0x2D2D2D2D


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


def _log(msg):
    """Temporary diagnostic: append to ~/.qtranslate_hotkeys.log."""
    try:
        import os
        import time
        path = os.path.join(os.path.expanduser("~"),
                            ".qtranslate_hotkeys.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s  [carbon] %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32),
                ("eventKind", ctypes.c_uint32)]


SIGNATURE = 0x5154524E  # 'QTRN' -- ours, so a foreign hotkey id is ignored.


def parse_combo(combo: str):
    """``"ctrl+shift+q"`` -> ``(keycode, modifiers)``, or ``None``.

    The combo string is the core's own (``config.hotkey_combo``), so the
    spelling is whatever that produces. Ctrl maps to Carbon's CONTROL
    key, not Command: the setting says Ctrl+Q and the native's Windows
    behaviour is Ctrl+Q, so the Mac binding is the same chord.
    """
    if not combo:
        return None
    parts = [p.strip().lower() for p in str(combo).split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    key = None
    for part in parts:
        if part in ("ctrl", "control"):
            mods |= CONTROL_KEY
        elif part in ("shift",):
            mods |= SHIFT_KEY
        elif part in ("alt", "option", "opt"):
            mods |= OPTION_KEY
        elif part in ("cmd", "command", "win", "windows", "super"):
            mods |= CMD_KEY
        else:
            key = part
    if key is None:
        return None
    code = KEYCODES.get(key)
    if code is None:
        return None
    return code, mods


def _carbon():
    """HIToolbox, bound with every signature declared, or ``None``.

    Two traps, both measured on this host (2026-10-28):

    * **The framework to load is HIToolbox, not Carbon.** Carbon is an
      umbrella that only forwards; the hotkey entry points live in
      HIToolbox, and linking the umbrella gives ``dlsym`` misses.
    * **Every pointer-returning call needs an explicit ``restype``.**
      ctypes defaults to ``c_int``, which TRUNCATES a 64-bit pointer --
      the same bug this repo already hit with ``GetModuleHandleW`` in
      ``mouse_capture.start``, where it silently broke the hook. Here it
      is a segfault: the truncated ``EventTargetRef`` is passed straight
      back into ``InstallEventHandler``.
    """
    candidates = (
        "/System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/"
        "HIToolbox.framework/Versions/A/HIToolbox",
        ctypes.util.find_library("HIToolbox"),
        "/System/Library/Frameworks/Carbon.framework/Carbon",
    )
    for path in candidates:
        if not path:
            continue
        try:
            lib = ctypes.CDLL(path)
            lib.RegisterEventHotKey
        except Exception:
            continue
        try:
            lib.GetApplicationEventTarget.restype = ctypes.c_void_p
            lib.GetApplicationEventTarget.argtypes = []
            lib.RegisterEventHotKey.restype = ctypes.c_int32
            lib.RegisterEventHotKey.argtypes = [
                ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID,
                ctypes.c_void_p, ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_void_p)]
            lib.UnregisterEventHotKey.restype = ctypes.c_int32
            lib.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
            lib.InstallEventHandler.restype = ctypes.c_int32
            lib.GetEventParameter.restype = ctypes.c_int32
            return lib
        except Exception:
            continue
    return None


def available() -> bool:
    if sys.platform != "darwin":
        return False
    return _carbon() is not None


class MacHotkeyTable:
    """Registered hotkeys, kept alive for the life of the process."""

    def __init__(self):
        self._lib = _carbon()
        self._refs = []        # (EventHotKeyRef, callback, name, combo)
        self._by_id = {}       # hotkey id -> callback
        self._next_id = 1
        self._handler = None
        self._installed = False
        if self._lib is not None:
            self._install_handler()

    def _install_handler(self):
        """Install the one handler that receives every hotkey press."""
        lib = self._lib
        HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p,
                                   ctypes.c_void_p, ctypes.c_void_p)

        def _on_event(_call_ref, event, _user):
            try:
                hk = _EventHotKeyID()
                status = lib.GetEventParameter(
                    event, kEventParamDirectObject, typeEventHotKeyID, None,
                    ctypes.sizeof(hk), None, ctypes.byref(hk))
                _log("handler: status=%s sig=%#x id=%s"
                     % (status, hk.signature, hk.id))
                if status == 0 and hk.signature == SIGNATURE:
                    fn = self._by_id.get(hk.id)
                    _log("handler: callback %s" % ("found" if fn else "MISSING"))
                    if fn is not None:
                        fn()
            except Exception as exc:            # noqa: BLE001
                _log("handler: raised %r" % (exc,))
            return 0

        self._handler = HANDLER(_on_event)
        spec = _EventTypeSpec(kEventClassKeyboard, kEventHotKeyPressed)
        try:
            target = lib.GetApplicationEventTarget()
            lib.InstallEventHandler.argtypes = [
                ctypes.c_void_p, HANDLER, ctypes.c_uint32,
                ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p)]
            lib.InstallEventHandler.restype = ctypes.c_int32
            lib.GetEventParameter.argtypes = [
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
                ctypes.c_void_p]
            lib.GetEventParameter.restype = ctypes.c_int32
            status = lib.InstallEventHandler(target, self._handler, 1,
                                             ctypes.byref(spec), None, None)
            self._installed = (status == 0)
            _log("InstallEventHandler -> %s" % (status,))
        except Exception as exc:                # noqa: BLE001
            _log("InstallEventHandler raised %r" % (exc,))
            self._installed = False

    def add(self, name, combo, callback):
        """Register one hotkey. Returns True when the OS accepted it."""
        if self._lib is None or not self._installed:
            return False
        parsed = parse_combo(combo)
        if parsed is None:
            return False
        code, mods = parsed
        hk_id = _EventHotKeyID(SIGNATURE, self._next_id)
        ref = ctypes.c_void_p()
        try:
            status = self._lib.RegisterEventHotKey(
                code, mods, hk_id, self._lib.GetApplicationEventTarget(),
                0, ctypes.byref(ref))
        except Exception:
            return False
        if status != 0 or not ref:
            _log("RegisterEventHotKey %s -> status=%s" % (combo, status))
            return False
        self._next_id += 1
        self._by_id[hk_id.id] = callback
        self._refs.append((ref, callback, name, combo))
        _log("registered %s id=%s" % (combo, hk_id.id))
        return True

    def clear(self):
        for ref, _cb, _name, _combo in self._refs:
            try:
                self._lib.UnregisterEventHotKey(ref)
            except Exception:
                pass
        self._refs = []
        self._by_id = {}

    def bound(self):
        return ["%s=%s" % (name, combo) for _r, _c, name, combo in self._refs]


_TABLE = None


def table() -> MacHotkeyTable:
    """The process's hotkey table, created once."""
    global _TABLE
    if _TABLE is None:
        _TABLE = MacHotkeyTable()
    return _TABLE
