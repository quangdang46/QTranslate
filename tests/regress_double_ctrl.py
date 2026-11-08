#!/usr/bin/env python3
"""Double Ctrl hotkey (HotKeyMainWindow=0x8000, bit15 "Double" prefix).

The last REAL-GAP from docs/GAP_AUDIT_3.md: the port persisted and
displayed the gesture but nothing detected it. This suite pins:

* the ported ``DoubleCtrlDetector`` state machine against .tmp's
  ``DoubleCtrlDetectorTest`` contract (two genuine taps <400 ms fire
  once; single taps, slow pairs, Ctrl+key chords and orphan releases
  never do; ``active`` gates firing, not tracking);
* the wiring in ``qt.hotkeys``: install() feeds a raw-key observer to
  the macOS tap (or the ``keyboard`` hook off-darwin), a double-tap
  calls ``app.show_main_window`` exactly once, uninstall() tears the
  feed down, and EnableHotKeys=off binds nothing;
* the tap-side event translation (flagsChanged -> ctrl/other edges);
* the display label and the Options.json persistence round-trip.

Offline: the tap and app are fakes; no Quartz, no real key events.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate.qt import hotkeys as HK  # noqa: E402

D = HK.DoubleCtrlDetector

# --- the state machine (mirrors DoubleCtrlDetectorTest.kt) -------------
d = D()
d.on_control_pressed()
ck("first tap does not fire", d.on_control_released(1000.0, True) is False)
d.on_control_pressed()
ck("second tap inside window fires once",
   d.on_control_released(1200.0, True) is True)
d.on_control_pressed()
ck("pair consumed: next lone tap only arms",
   d.on_control_released(1300.0, True) is False)

d = D()
d.on_control_pressed()
ck("single tap never fires", d.on_control_released(1000.0, True) is False)

d = D()
d.on_control_pressed()
ck("first tap at t=0 does not self-pair",
   d.on_control_released(0.0, True) is False)
d = D()
d.on_control_pressed()
ck("early tap under threshold does not self-pair",
   d.on_control_released(399.0, True) is False)
d = D()
d.on_control_pressed()
ck("tap at origin arms", d.on_control_released(1.0, True) is False)
d.on_control_pressed()
ck("genuine pair at origin fires",
   d.on_control_released(50.0, True) is True)

d = D()
ck("orphan release ignored", d.on_control_released(1000.0, True) is False)
ck("second orphan release ignored",
   d.on_control_released(1100.0, True) is False)
d.on_control_pressed()
ck("orphans did not arm: lone tap only arms",
   d.on_control_released(1200.0, True) is False)

d = D()
d.on_control_pressed()
ck("valid tap arms", d.on_control_released(1000.0, True) is False)
ck("orphan release after tap ignored",
   d.on_control_released(1100.0, True) is False)
d.on_control_pressed()
ck("armed tap still completes",
   d.on_control_released(1200.0, True) is True)

for combo_key in ("c", "v"):
    d = D()
    d.on_control_pressed()
    d.on_other_key_pressed()          # the 'c'/'v' keyDown while Ctrl held
    ck("ctrl+%s release is not a tap" % combo_key.upper(),
       d.on_control_released(1000.0, True) is False)
    d.on_control_pressed()
    ck("combination cleared the armed tap (%s)" % combo_key,
       d.on_control_released(1100.0, True) is False)

d = D()
d.on_control_pressed()
d.on_other_key_pressed()
d.on_control_released(1000.0, True)
d.on_control_pressed()
ck("combination then tap does not trigger",
   d.on_control_released(1100.0, True) is False)

d = D()
d.on_control_pressed()
ck("tap arms", d.on_control_released(1000.0, True) is False)
d.on_control_pressed()
d.on_other_key_pressed()
ck("tap then combination does not trigger",
   d.on_control_released(1100.0, True) is False)
d.on_control_pressed()
ck("combination cleared the armed tap",
   d.on_control_released(1200.0, True) is False)

d = D()
d.on_control_pressed()
d.on_other_key_pressed()
d.on_control_pressed()               # repeated ctrl-down while held
d.on_control_released(1000.0, True)
d.on_control_pressed()
ck("held ctrl + repeat keeps combination state",
   d.on_control_released(1100.0, True) is False)

d = D()
d.on_control_pressed()
ck("slow first tap arms", d.on_control_released(1000.0, True) is False)
d.on_control_pressed()
ck("second tap outside 400 ms does not fire",
   d.on_control_released(1500.0, True) is False)

d = D()
d.on_control_pressed()
d.on_control_released(1000.0, True)
d.reset()
d.on_control_pressed()
ck("reset forgets an armed tap",
   d.on_control_released(1100.0, True) is False)

d = D()
d.on_control_pressed()
d.on_control_released(1000.0, False)   # inactive: tracked, not fired
d.on_control_pressed()
d.on_control_released(1100.0, False)
d.on_control_pressed()
ck("inactive taps do not arm",
   d.on_control_released(1200.0, True) is False)
d.on_control_pressed()
ck("then a genuine pair still fires",
   d.on_control_released(1300.0, True) is True)

# --- config packing / display -----------------------------------------
from qtranslate import config as C  # noqa: E402

ck("hotkey_combo(0x8000) is no chord", C.hotkey_combo(0x8000) == "")
ck("hotkey_combo ignores bit15 on a chord",
   C.hotkey_combo(0x8000 | 0x251) == "ctrl+q")

try:
    from PySide6.QtWidgets import QApplication  # noqa: E402
    QApplication.instance() or QApplication([])
except Exception:
    pass
from qtranslate.qt.options import hotkeys as OK  # noqa: E402
ck("bare double-ctrl row label", OK._binding_label(0x8000) == "Double Ctrl")
ck("chord row label unchanged", OK._binding_label(0x251) == "Ctrl + Q")
ck("unbound row label", OK._binding_label(0) == "(none)")
ck("double+chord keeps chord display",
   "Q" in OK._binding_label(0x8000 | 0x251))

# --- persistence round-trip ---------------------------------------------
_saved = C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
C.DEFAULT_PATH = _tmp
try:
    cfg = C.load() or {}
    cfg.setdefault("HotKeys", {})["HotKeyMainWindow"] = 0x8000
    C.save(cfg)
    back = (C.load() or {}).get("HotKeys", {}).get("HotKeyMainWindow")
    ck("0x8000 survives Options.json round-trip", back == 0x8000,
       repr(back))
finally:
    C.DEFAULT_PATH = _saved
    try:
        os.unlink(_tmp)
    except OSError:
        pass

# --- wiring through install() with a fake tap backend -------------------
class _FakeApp:
    def __init__(self):
        self.fired = []
        self._opts = None

    def _on_ui(self, fn):
        fn()

    def show_main_window(self):
        self.fired.append("show-main")

    def hotkey_main_window(self):
        # The ACTIONS target the gesture dispatches to (same as the
        # HotKeyMainWindow chord): capture + translate + show.
        self.fired.append("show")


class _FakeTap:
    """Stands in for macos_tap.table(): captures the key observer and
    answers 'live' so install() believes the feed is up."""

    def __init__(self):
        self.observer = None
        self.started = True
        self.cleared = 0

    def add(self, name, combo, cb):
        return True

    def clear(self):
        self.cleared += 1

    def ensure(self):
        return self.started

    def set_key_observer(self, fn):
        self.observer = fn
        return self.started


def _fresh_config(**hk_over):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    C.DEFAULT_PATH = path
    cfg = C.default_config()
    hk = dict(cfg.get("HotKeys") or {})
    hk.update(hk_over)
    cfg["HotKeys"] = hk
    C.save(cfg)
    return path


_paths = []
_real_table = HK._macos_table
_real_kb = HK._keyboard
_fake = _FakeTap()
HK._macos_table = lambda: ("tap", _fake)
HK._keyboard = lambda: None
try:
    # LEGACY preset default: HotKeyMainWindow=0x8000, hotkeys enabled.
    _paths.append(_fresh_config())
    app = _FakeApp()
    bound = HK.install(app)
    ck("install binds the double-ctrl gesture",
       "HotKeyMainWindow=double-ctrl" in bound, repr(bound))
    ck("observer installed on the tap", _fake.observer is not None)

    # A genuine double-tap through the observer fires once. The fake
    # clock is in SECONDS, like time.monotonic(); the detector sees ms.
    t = [100000.0]
    real_time = HK.time
    HK.time = type("T", (), {"monotonic": staticmethod(lambda: t[0])})
    try:
        obs = _fake.observer
        obs("ctrl", True)
        t[0] += 0.05
        obs("ctrl", False)
        ck("first tap does not fire", app.fired == [])
        t[0] += 0.10
        obs("ctrl", True)
        t[0] += 0.05
        obs("ctrl", False)
        ck("double-tap fires show_main_window once", app.fired == ["show"])

        # Slow presses (>400 ms apart) do not fire.
        app.fired.clear()
        t[0] += 1.0
        obs("ctrl", True)
        t[0] += 0.05
        obs("ctrl", False)
        t[0] += 1.0
        obs("ctrl", True)
        t[0] += 0.05
        obs("ctrl", False)
        ck("slow presses do not fire", app.fired == [])

        # Ctrl held, another key down, Ctrl up: a chord, not a tap.
        app.fired.clear()
        obs("ctrl", True)
        obs("other", True)          # the 'q' keyDown while Ctrl held
        obs("ctrl", False)
        t[0] += 0.05
        obs("ctrl", True)
        obs("ctrl", False)
        ck("Ctrl+key chord does not fire", app.fired == [])

        # A bare modifier press while Ctrl is held is also a chord.
        obs("ctrl", True)
        t[0] += 0.6
        obs("other", True)          # e.g. Shift flagsChanged
        obs("ctrl", False)
        t[0] += 0.05
        obs("ctrl", True)
        obs("ctrl", False)
        ck("Ctrl+modifier does not fire", app.fired == [])

        # Orphan releases (no observed press) never fire.
        app.fired.clear()
        t[0] += 0.05
        obs("ctrl", False)
        t[0] += 0.05
        obs("ctrl", False)
        ck("orphan releases do not fire", app.fired == [])
    finally:
        HK.time = real_time

    # uninstall() tears the feed down.
    HK.uninstall()
    ck("uninstall removes the tap observer", _fake.observer is None)

    # EnableHotKeys=off: nothing binds, no observer.
    _paths.append(_fresh_config(EnableHotKeys=False))
    bound2 = HK.install(_FakeApp())
    ck("hotkeys disabled binds nothing", bound2 == [], repr(bound2))
    ck("disabled install installs no observer", _fake.observer is None)

    # bit15 cleared (CUSTOM-style): the gesture is gone.
    _paths.append(_fresh_config(HotKeyMainWindow=0))
    bound3 = HK.install(_FakeApp())
    ck("HotKeyMainWindow=0 binds no double-ctrl",
       "HotKeyMainWindow=double-ctrl" not in bound3, repr(bound3))
    ck("cleared bit15 installs no observer", _fake.observer is None)
finally:
    HK._macos_table = _real_table
    HK._keyboard = _real_kb
    HK._stop_double_ctrl()
    for p in _paths:
        try:
            os.unlink(p)
        except OSError:
            pass
    C.DEFAULT_PATH = _saved

# --- tap-side event translation (no Quartz needed) ----------------------
from qtranslate import macos_tap as MT  # noqa: E402


class _FakeQuartz:
    kCGEventFlagsChanged = 12
    kCGEventKeyDown = 10
    kCGEventKeyUp = 11


tap = MT._Tap()
tap._lib = _FakeQuartz()
edges = []
tap._key_observer = lambda kind, pressed: edges.append((kind, pressed))

# Control press: flagsChanged, kVK_Control, FLAG_CONTROL now set.
tap._notify_observer(_FakeQuartz.kCGEventFlagsChanged, 0x3B, MT.FLAG_CONTROL)
ck("ctrl press edge", edges == [("ctrl", True)], repr(edges))
# Control release: same keycode, FLAG_CONTROL now clear.
tap._notify_observer(_FakeQuartz.kCGEventFlagsChanged, 0x3B, 0)
ck("ctrl release edge", edges[-1] == ("ctrl", False), repr(edges))
# Right control works the same.
tap._notify_observer(_FakeQuartz.kCGEventFlagsChanged, 0x3E, MT.FLAG_CONTROL)
ck("right ctrl press edge", edges[-1] == ("ctrl", True), repr(edges))
# A regular keyDown is an 'other' press.
tap._notify_observer(_FakeQuartz.kCGEventKeyDown, 0x0C, MT.FLAG_CONTROL)
ck("keyDown is an other-press", edges[-1] == ("other", True), repr(edges))
# Shift going down (flagsChanged, bit now set) is an other-press...
edges.clear()
tap._notify_observer(_FakeQuartz.kCGEventFlagsChanged, 0x38, MT.FLAG_SHIFT)
ck("shift press is an other-press", edges == [("other", True)], repr(edges))
# ...but Shift coming UP (bit clear) reports nothing.
tap._notify_observer(_FakeQuartz.kCGEventFlagsChanged, 0x38, 0)
ck("shift release reports nothing", edges == [("other", True)], repr(edges))
# A flagsChanged for a non-modifier keycode reports nothing.
tap._notify_observer(_FakeQuartz.kCGEventFlagsChanged, 0x0C, 0)
ck("non-modifier flagsChanged ignored", edges == [("other", True)], repr(edges))
# KeyUp of a regular key reports nothing (upstream: pressed only).
tap._notify_observer(_FakeQuartz.kCGEventKeyUp, 0x0C, 0)
ck("keyUp reports nothing", edges == [("other", True)], repr(edges))
# No observer -> nothing happens, nothing raises.
tap._key_observer = None
tap._notify_observer(_FakeQuartz.kCGEventFlagsChanged, 0x3B, MT.FLAG_CONTROL)
ck("no observer is a no-op", edges == [("other", True)], repr(edges))

# --- _start_keyboard_feed: the keyboard.hook contract ------------------
# keyboard.hook(cb) is NOT a context manager -- it registers the
# callback (auto-starting the listener) and returns a remove function.
# The feed used `with hook(cb)`, which raised TypeError, killed the
# thread before ready.set() and left the gesture unbound on Windows
# (found live 2026-11-08). This fake mirrors the real API exactly.
class _FakeKeyboard:
    def __init__(self):
        self.hooked = []
        self.removed = []

    def hook(self, cb):
        self.hooked.append(cb)

        def _remove():
            self.removed.append(cb)
        return _remove


class _FakeEvent:
    def __init__(self, name, event_type):
        self.name = name
        self.event_type = event_type


fk = _FakeKeyboard()
feed_seen = []
feed_ok = HK._start_keyboard_feed(
    fk, lambda kind, down: feed_seen.append((kind, down)))
ck("keyboard feed installs", feed_ok is True)
ck("hook() called once with a callback", len(fk.hooked) == 1)
if fk.hooked:
    ev = fk.hooked[0]
    ev(_FakeEvent("left ctrl", "down"))
    ev(_FakeEvent("left ctrl", "up"))
    ev(_FakeEvent("q", "down"))
ck("feed translates hook events",
   feed_seen == [("ctrl", True), ("ctrl", False), ("other", True)],
   repr(feed_seen))
HK._stop_double_ctrl()
# The worker thread removes the handler asynchronously after stop.set().
import time as _time
_deadline = _time.time() + 2.0
while not fk.removed and _time.time() < _deadline:
    _time.sleep(0.02)
ck("stop removes the hook handler",
   fk.removed == fk.hooked and len(fk.removed) == 1)

# A keyboard module without hook() -> honest False, no thread.
class _NoHookKeyboard:
    pass

ck("no hook() -> feed unbound",
   HK._start_keyboard_feed(_NoHookKeyboard(), lambda *a: None) is False)

if FAIL:
    print("\nregress_double_ctrl: %d FAILURES" % len(FAIL))
    for f in FAIL:
        print("  -", f)
    raise SystemExit(1)
print("\nregress_double_ctrl: all checks ok")
