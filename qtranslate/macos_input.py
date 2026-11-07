"""Key synthesis and text typing on macOS — CoreGraphics CGEvent taps.

The ``keyboard`` package cannot be used here: importing it on macOS
ABORTS the process inside CoreFoundation (``__CFDataValidateRange``,
SIGABRT — not a catchable exception), which is why every call site
routes through ``platforms.keyboard_module()`` and lands here instead.

CGEvent posting needs the Accessibility permission; the port checks it
honestly (``available()`` reports False rather than letting the OS
drop the events silently) and callers degrade to the clipboard read,
which is exactly what ``selection.copy_selection`` already does when
``sendkeys.send`` reports False.

Modifier mapping: the app's combo strings are the Windows-native
vocabulary (``config.hotkey_combo`` emits ``ctrl+shift+q``). On macOS
the user-facing chord for those actions is Command, not Control —
Control+letter is a system/terminal chord (Ctrl+C is SIGINT in every
terminal). So ``ctrl``/``control`` in a combo is delivered as
kCGEventFlagMaskCommand, ``alt``/``option`` as Alternate, ``shift`` as
Shift, ``cmd``/``win``/``windows`` also as Command. This mirrors what
the native's Windows Ctrl+C copy means on macOS: Cmd+C.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import sys
import time

# CGEventFlags (CGEventTypes.h).
KCG_EVENT_FLAG_MASK_SHIFT = 0x00020000
KCG_EVENT_FLAG_MASK_CONTROL = 0x00040000
KCG_EVENT_FLAG_MASK_ALTERNATE = 0x00080000
KCG_EVENT_FLAG_MASK_COMMAND = 0x00100000

KCG_HID_EVENT_TAP = 0          # post where HID events enter the system
KCG_SESSION_EVENT_TAP = 1      # post into the login session

# kVK_ANSI_A — a neutral keycode for unicode-string typing; the
# unicode payload overrides whatever the keycode would produce.
KCG_KEYSTROKE_KEYCODE = 0x00

# Virtual keycodes of the LEFT modifiers (Events.h kVK_Command etc.).
# Posting the modifier's own down/up is what toggles the HID flags
# state: setting the flag only on the letter's event leaves the
# modifier "held" afterwards, and the next typed character inherits
# it (the '∑'-class bugs and stuck-Cmd typing).
_MOD_KEYCODE = {
    KCG_EVENT_FLAG_MASK_COMMAND: 0x37,     # kVK_Command
    KCG_EVENT_FLAG_MASK_SHIFT: 0x38,       # kVK_Shift
    KCG_EVENT_FLAG_MASK_ALTERNATE: 0x3A,   # kVK_Option
    KCG_EVENT_FLAG_MASK_CONTROL: 0x3B,     # kVK_Control
}


def _cg():
    """CoreGraphics with every signature declared, or None."""
    if sys.platform != "darwin":
        return None
    path = ("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
            if ctypes.util.find_library("CoreGraphics") is None
            else ctypes.util.find_library("CoreGraphics"))
    try:
        lib = ctypes.CDLL(path)
        lib.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
        lib.CGEventCreateKeyboardEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
        lib.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        lib.CGEventSetFlags.restype = None
        lib.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        lib.CGEventPost.restype = None
        lib.CGEventKeyboardSetUnicodeString.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ushort)]
        lib.CGEventKeyboardSetUnicodeString.restype = None
        lib.CFRelease.argtypes = [ctypes.c_void_p]
        lib.CFRelease.restype = None
        return lib
    except Exception:
        return None


def _ax_trusted() -> bool:
    """AXIsProcessTrusted — CGEvent posting is dropped without it."""
    try:
        lib = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/"
            "ApplicationServices")
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        lib.AXIsProcessTrusted.argtypes = []
        return bool(lib.AXIsProcessTrusted())
    except Exception:
        # Cannot prove trust; assume the common case (a dev machine or
        # an installed app the user granted Accessibility to).
        return True


def available() -> bool:
    return sys.platform == "darwin" and _cg() is not None


def _flag_for(part: str):
    p = part.strip().lower()
    if p in ("ctrl", "control", "cmd", "command", "win", "windows",
             "super"):
        # See module docstring: the portable chord's primary modifier is
        # Command on macOS.
        return KCG_EVENT_FLAG_MASK_COMMAND
    if p in ("alt", "option", "opt"):
        return KCG_EVENT_FLAG_MASK_ALTERNATE
    if p == "shift":
        return KCG_EVENT_FLAG_MASK_SHIFT
    return None


def parse_combo(combo: str):
    """``"ctrl+shift+q"`` -> ``(keycode, flags)``, or ``None``.

    Key names come from ``macos_hotkeys.KEYCODES`` so the two modules
    cannot disagree about which physical key a letter is.
    """
    if not combo:
        return None
    from qtranslate import macos_hotkeys
    flags = 0
    key = None
    for part in str(combo).split("+"):
        part = part.strip().lower()
        if not part:
            continue
        flag = _flag_for(part)
        if flag is not None:
            flags |= flag
        else:
            key = part
    if key is None:
        return None
    code = macos_hotkeys.KEYCODES.get(key)
    if code is None:
        return None
    return code, flags


def _post(lib, keycode: int, flags: int, down: bool):
    ev = lib.CGEventCreateKeyboardEvent(None, keycode, down)
    if not ev:
        return False
    try:
        lib.CGEventSetFlags(ev, flags)
        lib.CGEventPost(KCG_HID_EVENT_TAP, ev)
        return True
    finally:
        lib.CFRelease(ev)


def send(combo: str, hold: float = 0.02) -> bool:
    """Deliver one key combo (``"ctrl+c"``) as a real key event.

    Returns False — never raises — when the platform, the key name or
    the Accessibility grant is missing, so callers keep their existing
    degrade-to-clipboard behaviour.
    """
    try:
        lib = _cg()
        if lib is None or not _ax_trusted():
            return False
        parsed = parse_combo(combo)
        if parsed is None:
            return False
        code, flags = parsed
        # Real modifier down/up around the key: the flags on the letter
        # event alone do not move the HID modifier state, so without
        # this the chord's modifier stays logically held and the next
        # keystroke -- including a later type_text -- inherits it.
        mod_codes = [kc for f, kc in _MOD_KEYCODE.items() if flags & f]
        try:
            for kc in mod_codes:
                if not _post(lib, kc, flags, True):
                    return False
                time.sleep(0.01)
            if not _post(lib, code, flags, True):
                return False
            time.sleep(hold)
            # The key-up carries the same flags: some apps read the chord
            # from the release event, and a bare release looks like a plain
            # "c" key-up.
            ok = _post(lib, code, flags, False)
        finally:
            for kc in reversed(mod_codes):
                _post(lib, kc, 0, False)
                time.sleep(0.01)
        return ok
    except Exception:
        return False


def type_text(text: str, chunk: int = 400) -> bool:
    """Type ``text`` into the frontmost app via unicode-string events.

    ``CGEventKeyboardSetUnicodeString`` carries arbitrary unicode, so no
    per-key layout table is needed — the same reason the native's
    retype engine can paste any script back. Posted in chunks so a
    very long result does not build one oversized event.
    """
    lib = _cg()
    if lib is None or not _ax_trusted() or not text:
        return False
    try:
        for i in range(0, len(text), chunk):
            piece = text[i:i + chunk]
            # CGEventKeyboardSetUnicodeString takes UTF-16 code UNITS:
            # astral characters (emoji, rare CJK ext) must be split into
            # surrogate pairs -- ord(ch) > 0xFFFF overflowed c_ushort and
            # crashed mid-string, leaving partial text in the target.
            units = []
            for ch in piece:
                o = ord(ch)
                if o > 0xFFFF:
                    o -= 0x10000
                    units.append(0xD800 + (o >> 10))
                    units.append(0xDC00 + (o & 0x3FF))
                else:
                    units.append(o)
            arr = (ctypes.c_ushort * len(units))(*units)
            down = lib.CGEventCreateKeyboardEvent(
                None, KCG_KEYSTROKE_KEYCODE, True)
            if not down:
                return False
            try:
                # Clear inherited modifier flags: a fresh event picks up
                # the HID flags state, and a stuck modifier (the send()
                # bug this guards against) would turn the typed text
                # into a chord the app ignores.
                lib.CGEventSetFlags(down, 0)
                lib.CGEventKeyboardSetUnicodeString(
                    down, len(units), arr)
                lib.CGEventPost(KCG_HID_EVENT_TAP, down)
            finally:
                lib.CFRelease(down)
            up = lib.CGEventCreateKeyboardEvent(
                None, KCG_KEYSTROKE_KEYCODE, False)
            if up:
                try:
                    lib.CGEventSetFlags(up, 0)
                    lib.CGEventPost(KCG_HID_EVENT_TAP, up)
                finally:
                    lib.CFRelease(up)
            time.sleep(0.005)
        return True
    except Exception:
        return False


def paste() -> bool:
    """Cmd+V — used by callers that put text on the clipboard first."""
    return send("cmd+v")


def modifiers() -> int:
    """The currently-held modifier flags (CGEventSourceFlagsState).

    The ``EnableMouseModeOnCtrl`` gate asks "is Ctrl held"; off Windows
    ``keyboard.is_pressed`` does not exist, so the mouse gate reads the
    real HID state here instead. Returns 0 when the query fails.
    """
    lib = _cg()
    if lib is None:
        return 0
    try:
        lib.CGEventSourceFlagsState.restype = ctypes.c_uint64
        lib.CGEventSourceFlagsState.argtypes = [ctypes.c_int]
        # kCGEventSourceStateHIDSystemState = 1
        return int(lib.CGEventSourceFlagsState(1))
    except Exception:
        return 0


def control_held() -> bool:
    """True while the Control key is down (either Control)."""
    return bool(modifiers() & KCG_EVENT_FLAG_MASK_CONTROL)
