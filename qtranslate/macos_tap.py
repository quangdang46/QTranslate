"""Global hotkeys on macOS via a CGEventTap (listen-only).

Carbon ``RegisterEventHotKey`` registers fine but its events are never
delivered under Qt's run loop on this host -- the handler installs, the
OS accepts the registration, and no ``kEventHotKeyPressed`` ever
arrives. A CGEventTap is the mechanism that demonstrably fires (it is
what the ``keyboard`` package and every macOS hotkey tool use), and it
needs the same Accessibility grant the copy/replace keystroke synthesis
(``macos_input``) already requires -- so it adds no new permission the
core Ctrl+Q flow does not already depend on.

The tap observes keyDown AND consumes a matched chord: returning
``None`` for the event keeps it away from the frontmost app. That is
not optional on macOS -- ``alt+w`` IS ``option+w``, which types '∑'
into the target and destroys the selection before the handler can
copy it. Native's Carbon ``RegisterEventHotKey`` consumes matches the
same way, so swallowing the chord IS the faithful behaviour; every
other keystroke still passes through untouched. While the Hotkeys
options page is RECORDING a binding the guard is lowered: the chord
being pressed is the new binding, so it must reach the recorder.

Matching is done in Python: a registered combo becomes (keycode,
required modifier mask) and a keyDown fires when its flags carry
exactly those modifiers.

PyObjC does the CoreGraphics/CoreFoundation bridging -- the raw-ctypes
version of this segfaulted inside ``CFMachPortCreateRunLoopSource``
(an undocumented signature quirk), and PyObjC is already a runtime
dependency of the macOS path (``macos_hotkeys`` loads the same
frameworks). Without PyObjC ``available()`` is False and the caller
falls back to the Carbon table.
"""
from __future__ import annotations

import os
import sys
import threading
import time

_DEBUG = os.environ.get("QTRANSLATE_HK_DEBUG") == "1"

# CGEventFlags as CGEventGetFlags reports them (CGEventTypes.h).
FLAG_COMMAND = 0x00100000
FLAG_SHIFT = 0x00020000
FLAG_CONTROL = 0x00040000
FLAG_ALTERNATE = 0x00080000
_ALL_MODS = FLAG_COMMAND | FLAG_SHIFT | FLAG_CONTROL | FLAG_ALTERNATE


def _log(msg):
    try:
        import os
        import time
        path = os.path.join(os.path.expanduser("~"),
                            ".qtranslate_hotkeys.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s  [tap] %s\n"
                    % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


class _Tap:
    """One listen-only event tap feeding registered combos."""

    def __init__(self):
        self._combos = {}        # (keycode, mods) -> callback
        self._lock = threading.Lock()
        self._last_fire = {}     # (keycode, mods) -> monotonic ts
        self._started = False
        self._lib = None         # Quartz module, once loaded
        self._tap = None         # the CFMachPort; kept alive for the tap's life
        self._src = None         # its run-loop source
        # hotkeys.install lowers this while the options page records a
        # new binding: the chord must reach the recorder unconsumed.
        self.consume_guard = lambda: True

    # ------------------------------------------------------------ matching
    def add(self, name, combo: str, callback) -> bool:
        """Register ``combo`` (``"ctrl+shift+q"`` vocabulary).

        ``name`` is kept for symmetry with the Carbon table's ``add``;
        the match key is the parsed (keycode, modifiers) pair.
        """
        parsed = self._parse(combo)
        if parsed is None:
            return False
        with self._lock:
            self._combos[parsed] = callback
        self._ensure_running()
        # ``add`` reports whether the tap is actually LIVE, not merely
        # whether the combo parsed: without the Accessibility grant the
        # tap never starts, and a hotkey that registers-but-never-fires
        # is worse than one install() honestly reports as unbound.
        return self._started

    def clear(self):
        with self._lock:
            self._combos.clear()

    @staticmethod
    def _parse(combo: str):
        """``"ctrl+alt+q"`` -> ``(keycode, modifier_mask)`` or None."""
        if not combo:
            return None
        from qtranslate import macos_hotkeys
        mods = 0
        key = None
        for part in str(combo).split("+"):
            part = part.strip().lower()
            if not part:
                continue
            if part in ("ctrl", "control"):
                mods |= FLAG_CONTROL
            elif part in ("shift",):
                mods |= FLAG_SHIFT
            elif part in ("alt", "option", "opt"):
                mods |= FLAG_ALTERNATE
            elif part in ("cmd", "command", "win", "windows", "super"):
                mods |= FLAG_COMMAND
            else:
                key = part
        if key is None:
            return None
        code = macos_hotkeys.KEYCODES.get(key)
        if code is None:
            return None
        return code, mods

    # ------------------------------------------------------------ the tap
    def _ensure_running(self):
        if self._started:
            return
        try:
            import Quartz
            from Foundation import (CFRunLoopGetCurrent,
                                    CFRunLoopAddSource,
                                    kCFRunLoopCommonModes)
        except Exception:
            _log("PyOsis/Quartz unavailable; tap cannot start")
            return
        if not self._ax_ok():
            _log("no Accessibility grant; tap cannot start")
            return
        try:
            mask = (Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
                    | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
                    | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged))

            def _cb(_proxy, etype, event, _refcon):
                try:
                    if etype in (Quartz.kCGEventKeyDown,
                                 Quartz.kCGEventKeyUp):
                        keycode = Quartz.CGEventGetIntegerValueField(
                            event, Quartz.kCGKeyboardEventKeycode)
                        raw = Quartz.CGEventGetFlags(event)
                        flags = raw & _ALL_MODS
                        # QTRANSLATE_HK_DEBUG=1 logs every keyDown's
                        # keycode+modifiers -- the diagnostic for "my
                        # real keypress does not fire" reports.
                        if _DEBUG and etype == Quartz.kCGEventKeyDown:
                            _log("keyDown kc=%d mods=%#x raw=%#x"
                                 % (keycode, flags, raw))
                        with self._lock:
                            combos = dict(self._combos)
                        consume = False
                        for (code, mods) in combos:
                            if code == keycode and flags == mods:
                                consume = True
                                break
                        if consume and self.consume_guard():
                            if etype == Quartz.kCGEventKeyDown:
                                now = time.monotonic()
                                for (code, mods), cb in combos.items():
                                    if code == keycode and flags == mods:
                                        # Key repeat: a held chord
                                        # re-fires keyDown ~30x/s; one
                                        # action per press.
                                        last = self._last_fire.get(
                                            (code, mods), 0)
                                        if now - last < 0.4:
                                            continue
                                        self._last_fire[(code, mods)] = now
                                        try:
                                            cb()
                                        except Exception:
                                            pass
                            # Swallow the chord's down AND up: the 'w'
                            # of alt+w must never reach the app as '∑'.
                            return None
                except Exception:
                    pass
                return event      # not a hotkey: pass through untouched

            tap = Quartz.CGEventTapCreate(
                Quartz.kCGHIDEventTap, Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault, mask, _cb, None)
            if not tap:
                _log("CGEventTapCreate returned NULL")
                return
            src = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            rl = CFRunLoopGetCurrent()
            CFRunLoopAddSource(rl, src, kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            self._lib = Quartz
            # The run loop retains the source but NOT necessarily the
            # port behind it; both stay referenced for the app's life.
            self._tap = tap
            self._src = src
            self._cb = _cb
            self._started = True
            _log("tap running, %d combos" % len(self._combos))
        except Exception as exc:            # noqa: BLE001
            _log("tap start failed: %r" % (exc,))

    @staticmethod
    def _ax_ok() -> bool:
        try:
            from qtranslate import macos_input
            return macos_input._ax_trusted()
        except Exception:
            return False


_TABLE = None


def table() -> _Tap:
    global _TABLE
    if _TABLE is None:
        _TABLE = _Tap()
    return _TABLE


def available() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import Quartz  # noqa: F401
        from Foundation import CFRunLoopGetCurrent  # noqa: F401
    except Exception:
        return False
    return True
