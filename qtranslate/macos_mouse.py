"""Mouse-selection capture on macOS, via a CGEventTap.

Native's mouse mode (General.MouseMode) is "drag to select, release,
get the translate icon". The Win32 port gets that from a low-level
mouse hook; on macOS the same signal comes from a listen-only
CGEventTap -- the same mechanism ``macos_tap`` uses for the keyboard
hotkeys, extended to the left button's down/dragged/up events.

The state machine mirrors ``mouse_capture.process_mouse_event``: the
down side records the point only when the press is allowed, the up
side fires ``on_select(x, y)`` only when the pointer actually moved
(a drag, i.e. a selection) -- a plain click captures nothing.

Like the keyboard tap this needs the Accessibility grant; without it
``start`` reports False and the mode simply stays off.
"""
from __future__ import annotations

import sys
import threading

# CGEventTypes for the left button (CGEventTypes.h).
KCG_LEFT_DOWN = 1
KCG_LEFT_UP = 2
KCG_LEFT_DRAGGED = 6

_CLICK_MOVE_TOL = 8          # px; mirrors mouse_capture.CLICK_MOVE_TOL


def _log(msg):
    try:
        import os
        import time
        path = os.path.join(os.path.expanduser("~"),
                            ".qtranslate_hotkeys.log")
        try:
            if os.path.getsize(path) > 1_000_000:
                os.replace(path, path + ".1")
        except OSError:
            pass
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s  [mouse] %s\n"
                    % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


class _MouseTap:
    def __init__(self):
        self._on_select = None
        self._on_click = None     # every allowed left-down, drag or not
        self._down = None          # (x, y) of an allowed press, else None
        self._lock = threading.Lock()
        self._running = False
        self._tap = None
        self._src = None
        self._cb = None
        self._Quartz = None

    # ------------------------------------------------------------- public
    def start(self, on_select, on_click=None) -> bool:
        if self._running:
            return True
        try:
            import Quartz
            from Foundation import (CFRunLoopGetCurrent,
                                    CFRunLoopAddSource,
                                    kCFRunLoopCommonModes)
        except Exception:
            return False
        try:
            from qtranslate import macos_input
            if not macos_input._ax_trusted():
                _log("no Accessibility grant; mouse tap off")
                return False
        except Exception:
            return False
        mask = (Quartz.CGEventMaskBit(KCG_LEFT_DOWN)
                | Quartz.CGEventMaskBit(KCG_LEFT_UP)
                | Quartz.CGEventMaskBit(KCG_LEFT_DRAGGED))

        def _cb(_proxy, etype, event, _refcon):
            try:
                self._handle(etype, event)
            except Exception:
                pass
            return event          # listen-only: never consume

        try:
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGHIDEventTap, Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly, mask, _cb, None)
            if not tap:
                _log("CGEventTapCreate(mouse) returned NULL")
                return False
            src = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            rl = CFRunLoopGetCurrent()
            CFRunLoopAddSource(rl, src, kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            self._Quartz = Quartz
            self._tap, self._src, self._cb = tap, src, _cb
            self._on_select = on_select
            self._on_click = on_click
            self._running = True
            _log("mouse tap running")
            return True
        except Exception as exc:                    # noqa: BLE001
            _log("mouse tap start failed: %r" % (exc,))
            return False

    def stop(self):
        if not self._running:
            return
        try:
            if self._tap is not None and self._Quartz is not None:
                self._Quartz.CGEventTapEnable(self._tap, False)
        except Exception:
            pass
        self._running = False
        self._down = None
        self._on_select = None
        self._on_click = None

    # ------------------------------------------------------------- events
    def _handle(self, etype, event):
        Q = self._Quartz
        if Q is None:
            return
        if etype == KCG_LEFT_DOWN:
            if not self._press_allowed():
                self._down = None
                return
            loc = Q.CGEventGetLocation(event)
            with self._lock:
                self._down = (loc.x, loc.y)
            # Reported before the drag bookkeeping, like .tmp's
            # onPointerPressed: the floating icon and popups dismiss on
            # an outside press even when the press starts no selection.
            cb = self._on_click
            if cb is not None:
                try:
                    cb(loc.x, loc.y)
                except Exception:
                    pass
            return
        if etype == KCG_LEFT_UP:
            with self._lock:
                rec = self._down
                self._down = None
            if not rec:
                return
            loc = Q.CGEventGetLocation(event)
            x, y = loc.x, loc.y
            if (abs(x - rec[0]) <= _CLICK_MOVE_TOL
                    and abs(y - rec[1]) <= _CLICK_MOVE_TOL):
                return                     # a click, not a selection
            _log("drag released at (%d,%d) -> on_select" % (x, y))
            cb = self._on_select
            if cb is not None:
                cb(x, y)
            return
        # KCG_LEFT_DRAGGED: nothing to record; the up side measures.

    @staticmethod
    def _press_allowed() -> bool:
        """The down-side gate, macOS edition: not our own app.

        Native gates on own-window + exclusions; off Windows the port's
        probe answers "not excluded" anyway, so the one check that
        matters -- don't capture drags that start inside QTranslate
        itself -- is the frontmost-process one.
        """
        try:
            import Quartz
            from AppKit import NSWorkspace
            front = NSWorkspace.sharedWorkspace().frontmostApplication()
            pid = front.processIdentifier() if front else -1
            import os
            return pid != os.getpid()
        except Exception:
            return True


_TABLE = None


def start(on_select, on_click=None) -> bool:
    global _TABLE
    if _TABLE is None:
        _TABLE = _MouseTap()
    return _TABLE.start(on_select, on_click)


def stop():
    global _TABLE
    if _TABLE is not None:
        _TABLE.stop()


def available() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import Quartz  # noqa: F401
        from Foundation import NSWorkspace  # noqa: F401
    except Exception:
        return False
    return True
