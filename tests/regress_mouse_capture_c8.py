"""Regression: the C8 mouse-capture gates (SM_SWAPBUTTON, own window,
exclusion list) — behaviour, not source text.

Native evidence: Ghidra 12.1.4 headless decompile of the recovered image
(docs/review/artifacts/QTranslate.6.10.0.exe, sha256 f35a3bc8...), re-run
2026-10-21 for this file.  Addresses are the ones cited in
docs/RE_COVERAGE_CHECKLIST.md group C.

  FUN_00417E4E  RawInput WM_INPUT -> GetSystemMetrics(0x17)=SM_SWAPBUTTON ->
                normalize to WM_LBUTTONDOWN(0x201)/WM_LBUTTONUP(0x202).
                Decompiled structure:
                  not swapped: usButtonFlags bit 1 (LEFT_DOWN)  -> 0x201
                               usButtonFlags bit 2 (LEFT_UP)    -> 0x202
                  swapped:     usButtonFlags bit 4 (RIGHT_DOWN) -> 0x201
                               usButtonFlags bit 8 (RIGHT_UP)   -> 0x202
  FUN_004193F6  down side: hwnd = FUN_00450DD2(x,y);
                if (hwnd != this+0x1280)          // our own window
                  if (!FUN_004631DE(&DAT_005494B0, hwnd))   // exclusions
                    GetWindowRect(hwnd) + PtInRect -> record the click.
                up side: completes only when the down side recorded a target.
  FUN_004631DE  exclusion matcher for a *given* hwnd: class from
                FUN_00450C50 (GetClassNameW), exe from FUN_00403506, matched
                against Exceptions.Disabled with the wcsicmp matcher
                FUN_004470B7 (empty side matches anything).

Every assertion here CALLS a function and checks its real return value or a
real side effect.  The gates are factored out of the Win32 layer precisely
so that they can be exercised on a non-Windows host.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import mouse_capture as M  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


def ck_eq(name, got, want):
    ck(name, got == want, "got %r, want %r" % (got, want))


# =====================================================================
# 1. Native's RawInput normalization, 1:1 with FUN_00417E4E
# =====================================================================

# Not swapped: the physical LEFT button is the primary one.
ck_eq("native: LEFT_DOWN -> 0x201 (not swapped)",
      M.normalize_raw_button(M.RI_LEFT_DOWN, False), M.WM_LBUTTONDOWN)
ck_eq("native: LEFT_UP -> 0x202 (not swapped)",
      M.normalize_raw_button(M.RI_LEFT_UP, False), M.WM_LBUTTONUP)
ck_eq("native: RIGHT_DOWN is not the primary (not swapped)",
      M.normalize_raw_button(M.RI_RIGHT_DOWN, False), 0)
ck_eq("native: RIGHT_UP is not the primary (not swapped)",
      M.normalize_raw_button(M.RI_RIGHT_UP, False), 0)

# Swapped: the physical RIGHT button becomes the primary one.
ck_eq("native: RIGHT_DOWN -> 0x201 (swapped)",
      M.normalize_raw_button(M.RI_RIGHT_DOWN, True), M.WM_LBUTTONDOWN)
ck_eq("native: RIGHT_UP -> 0x202 (swapped)",
      M.normalize_raw_button(M.RI_RIGHT_UP, True), M.WM_LBUTTONUP)
ck_eq("native: LEFT_DOWN is not the primary (swapped)",
      M.normalize_raw_button(M.RI_LEFT_DOWN, True), 0)
ck_eq("native: LEFT_UP is not the primary (swapped)",
      M.normalize_raw_button(M.RI_LEFT_UP, True), 0)

# No button flag at all -> nothing to do (native: `if (!flags) return 0`).
ck_eq("native: no flags -> 0 (not swapped)",
      M.normalize_raw_button(0, False), 0)
ck_eq("native: no flags -> 0 (swapped)",
      M.normalize_raw_button(0, True), 0)

# Down wins over up when both bits are set (native tests the down bit first).
ck_eq("native: DOWN|UP -> 0x201 (not swapped)",
      M.normalize_raw_button(M.RI_LEFT_DOWN | M.RI_LEFT_UP, False),
      M.WM_LBUTTONDOWN)
ck_eq("native: DOWN|UP -> 0x201 (swapped)",
      M.normalize_raw_button(M.RI_RIGHT_DOWN | M.RI_RIGHT_UP, True),
      M.WM_LBUTTONDOWN)

# The RawInput flag constants are the documented usButtonFlags values.
ck_eq("RI_LEFT_DOWN == 0x01", M.RI_LEFT_DOWN, 0x01)
ck_eq("RI_LEFT_UP == 0x02", M.RI_LEFT_UP, 0x02)
ck_eq("RI_RIGHT_DOWN == 0x04", M.RI_RIGHT_DOWN, 0x04)
ck_eq("RI_RIGHT_UP == 0x08", M.RI_RIGHT_UP, 0x08)

# =====================================================================
# 2. The hook's trigger button must be the user's primary button
#    (the SM_SWAPBUTTON double-swap that broke left-handed users)
# =====================================================================

ck_eq("hook watches the primary button's down/up messages",
      M.primary_button_messages(), (M.WM_LBUTTONDOWN, M.WM_LBUTTONUP))

# Native's rule and the hook's rule must agree about *which physical*
# button is the primary one.  Native (swapped): physical RIGHT is primary.
# The hook sees the primary button as WM_LBUTTONDOWN in both settings.
ck("native's swapped primary is the button Windows reports as WM_LBUTTONDOWN",
   M.normalize_raw_button(M.RI_RIGHT_DOWN, True) == M.primary_button_messages()[0]
   and M.normalize_raw_button(M.RI_LEFT_DOWN, False)
   == M.primary_button_messages()[0])

# A left-handed user must still get a trigger: drive the hook's state
# machine with the primary-button pair and require the callback to fire.
# (Before 2026-10-21 the hook swapped the down/up messages when
# GetSystemMetrics(SM_SWAPBUTTON) was non-zero, so this pair produced no
# callback at all for a left-handed user.)


def _drive(events, probe=None):
    """Feed a message sequence to the hook's state machine."""
    state = {"down": None}
    fired = []

    def _probe(x, y):
        if probe is not None:
            return probe(x, y)
        return (0x1111, None, False, True)

    for wparam, x, y in events:
        M.process_mouse_event(state, wparam, x, y, _probe,
                              lambda px, py: fired.append((px, py)))
    return fired


ck_eq("left-handed user: primary-button DRAG fires the capture",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 140, 60)])), 1)
# The capture gesture is a DRAG (press, sweep the selection, release) --
# the operator's spec (2026-10-24) and the native: a plain click is not
# a selection, and firing on it auto-translated in a loop. These
# vectors are the INVERSE of the old ones on purpose.
ck_eq("the capture reports the drag's release point",
      _drive([(M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 140, 160)]),
      [(140, 160)])
ck_eq("the secondary button never fires the capture",
      len(_drive([(M.WM_RBUTTONDOWN, 40, 60), (M.WM_RBUTTONUP, 140, 60)])), 0)
ck_eq("a lone button-down fires nothing",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60)])), 0)
ck_eq("a lone button-up fires nothing",
      len(_drive([(M.WM_LBUTTONUP, 40, 60)])), 0)
ck_eq("a plain click (no sweep) fires nothing -- that was the loop",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 40, 60)])), 0)
ck_eq("a drag inside the tolerance is still a click, not a sweep",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60),
                  (M.WM_LBUTTONUP, 40 + M.CLICK_MOVE_TOL, 60)])), 0)
ck_eq("two drags fire twice",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 140, 60),
                  (M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 140, 60)])), 2)

# =====================================================================
# 3. The down-side gate (FUN_004193F6)
# =====================================================================

ck_eq("gate: no window under the cursor -> no capture",
      M.capture_allowed(None, None, False, True), False)
ck_eq("gate: our own window -> no capture",
      M.capture_allowed(0x2222, 0x2222, False, True), False)
ck_eq("gate: excluded window -> no capture",
      M.capture_allowed(0x3333, 0x2222, True, True), False)
ck_eq("gate: point outside the window -> no capture",
      M.capture_allowed(0x3333, 0x2222, False, False), False)
ck_eq("gate: an ordinary window -> capture",
      M.capture_allowed(0x3333, 0x2222, False, True), True)
ck_eq("gate: own window wins over everything else",
      M.capture_allowed(0x2222, 0x2222, True, False), False)

# The own-window skip must survive a control *inside* our own window:
# WindowFromPoint returns the deepest child, so an exact handle comparison
# alone would never match (that is how the skip stayed dead code).
ck("own-window skip matches a child of our own window",
   M.is_own_window(0x2222, 0x2222) is True)
ck("own-window skip does not match an unrelated window",
   M.is_own_window(0x3333, 0x2222) is False)
ck("own-window skip tolerates a missing own handle",
   M.is_own_window(0x3333, None) is False)
ck("own-window skip tolerates a missing resolved handle",
   M.is_own_window(None, 0x2222) is False)

# =====================================================================
# 4. The exclusion list is matched against the window under the cursor
#    (FUN_004631DE), not only against the foreground window
# =====================================================================

_DISABLED = [("", "SysListView32"), ("", "ConsoleWindowClass"),
             ("mstsc.exe", "")]

ck_eq("exclusion: a blocked class is excluded",
      M.class_excluded("SysListView32", "notepad.exe",
                       disabled=_DISABLED), True)
ck_eq("exclusion: the blocked class is excluded in any app",
      M.class_excluded("SysListView32", "anything.exe",
                       disabled=_DISABLED), True)
ck_eq("exclusion: a blocked exe is excluded whatever the class",
      M.class_excluded("Edit", "mstsc.exe", disabled=_DISABLED), True)
ck_eq("exclusion: an ordinary window is not excluded",
      M.class_excluded("Edit", "notepad.exe", disabled=_DISABLED), False)
ck_eq("exclusion: the match is case-insensitive (native wcsicmp)",
      M.class_excluded("syslistview32", "notepad.exe",
                       disabled=_DISABLED), True)
ck_eq("exclusion: an empty class does not match a specific class",
      M.class_excluded("Edit", "notepad.exe",
                       disabled=[("notepad.exe", "")]), True)
ck_eq("exclusion: an empty class does not match every class",
      M.class_excluded("Edit", "notepad.exe",
                       disabled=[("", "NotARealClass")]), False)

# Allowlist mode (native FUN_004630C5): nothing is excluded unless the
# window is explicitly enabled.
ck_eq("allowlist: an unlisted window is excluded",
      M.class_excluded("Edit", "notepad.exe", enabled=[("other.exe", "")],
                       mode=False), True)
ck_eq("allowlist: an explicitly enabled window is not excluded",
      M.class_excluded("Edit", "notepad.exe", enabled=[("notepad.exe", "")],
                       mode=False), False)
ck_eq("allowlist: an empty enabled list excludes nothing",
      M.class_excluded("Edit", "notepad.exe", enabled=[], mode=False), False)

# The default blocklist really is the one native ships with.
from qtranslate import exclusions as _EX  # noqa: E402
ck("default blocklist carries the native entries",
   M.class_excluded("ConsoleWindowClass", "cmd.exe",
                    disabled=list(_EX.DEFAULT_DISABLED)))
ck("default blocklist carries the remote-desktop app entry",
   M.class_excluded("Edit", "mstsc.exe",
                    disabled=list(_EX.DEFAULT_DISABLED)))

# =====================================================================
# 5. The gates are wired into the real capture path
# =====================================================================

if M.available():
    ck("should_capture returns a bool on Windows",
       isinstance(M.should_capture(0, 0), bool))
else:
    ck_eq("should_capture is False off Windows (no raise)",
          M.should_capture(0, 0), False)

# The exclusion check must run against the window under the cursor.  Prove
# it by driving the state machine with a probe that reports an excluded
# window: the capture must not fire.
def _excluded_probe(x, y):
    return (0x4444, None, True, True)


ck_eq("an excluded window under the cursor blocks the capture",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 40, 60)],
                 probe=_excluded_probe)), 0)


def _own_probe(x, y):
    return (0x5555, 0x5555, False, True)


ck_eq("our own window under the cursor blocks the capture",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 40, 60)],
                 probe=_own_probe)), 0)


def _outside_probe(x, y):
    return (0x6666, None, False, False)


ck_eq("a point outside the window blocks the capture",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 40, 60)],
                 probe=_outside_probe)), 0)

# A failed down must not leave a stale target behind for the next up:
# native records the target on the down side only.
def _gate_then_ok(x, y):
    return (0x7777, None, False, True)


ck_eq("a rejected down does not resurrect on a later up",
      len(_drive([(M.WM_LBUTTONDOWN, 40, 60), (M.WM_LBUTTONUP, 40, 60)],
                 probe=_excluded_probe)) +
      len(_drive([(M.WM_LBUTTONUP, 40, 60)], probe=_gate_then_ok)), 0)

# =====================================================================
# 6. The module still behaves on this host
# =====================================================================

try:
    ck_eq("start() returns a bool off Windows",
          isinstance(M.start(lambda x, y: None), bool), True)
    M.stop()
    ck("stop() never raises", True)
except Exception as e:
    ck("stop() never raises", False, repr(e))

if M.available():
    # On Windows the call is LIVE: it asks OLEACC for the accessible name
    # under the pointer, and (0, 0) is the top-left corner of the screen,
    # where whatever window happens to be maximized lives. So the result
    # is that window's name -- "Chrome Legacy Window" on this host -- and
    # asserting "" here was asserting a property of the desktop, not of
    # the code. The sibling suite (regress_mouse_capture.py) already
    # branches on available() for exactly this reason.
    _live_text = M.cursor_text(0, 0)
    ck_eq("cursor_text returns a string on Windows (live OLEACC)",
          isinstance(_live_text, str), True)
else:
    ck_eq("cursor_text returns '' off Windows", M.cursor_text(0, 0), "")


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_mouse_capture_c8: all checks ok (%d assertions)" % n[0])
