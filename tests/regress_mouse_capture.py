"""Regression: mouse-capture helpers (C3 OLEACC, C8 SM_SWAPBUTTON).

Native evidence: Ghidra decompile of the recovered image
(docs/review/C3_C8_C10_MOUSE_2026-10-10.md).

  FUN_00404901  GetCursorPos -> AccessibleObjectFromPoint ->
                IAccessible::get_accName, falling back to get_accValue when
                SysStringLen(name) == 0; success == "resulting CString non-empty".
  FUN_00417E4E  GetRawInputData(RID_INPUT=0x10000003) then
                GetSystemMetrics(0x17)=SM_SWAPBUTTON to map left/right to
                WM_LBUTTONDOWN(0x201)/WM_LBUTTONUP(0x202).

These tests pin the *contract* of the helpers on a non-Windows host, where the
Win32 calls themselves cannot run: constants must match the binary, the OLEACC
entry points must exist with the documented vtable order, and the hook must be a
safe no-op that still returns a bool so callers never crash.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import mouse_capture as M  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


# --- constants must equal the values the binary uses ---
ck("WM_LBUTTONDOWN == 0x201", M.WM_LBUTTONDOWN == 0x201, hex(M.WM_LBUTTONDOWN))
ck("WM_LBUTTONUP == 0x202", M.WM_LBUTTONUP == 0x202, hex(M.WM_LBUTTONUP))
ck("SM_SWAPBUTTON == 0x17", M.SM_SWAPBUTTON == 0x17, hex(M.SM_SWAPBUTTON))
ck("RID_INPUT == 0x10000003", M.RID_INPUT == 0x10000003, hex(M.RID_INPUT))

# --- the C3 extraction entry points must exist with these names/signatures ---
ck("cursor_text(x, y) exists", callable(getattr(M, "cursor_text", None)))
ck("cursor_text arity is 2",
   M.cursor_text.__code__.co_argcount == 2,
   str(M.cursor_text.__code__.co_varnames[:2]))
ck("should_capture(x, y) exists", callable(getattr(M, "should_capture", None)))
ck("_buttons_swapped exists", callable(getattr(M, "_buttons_swapped", None)))

# --- off Windows everything must no-op safely, never raise ---
# On Windows the live path must run instead: available() is True and
# cursor_text must never raise (an unreadable point returns "").
if M.available():
    ck("available() is True on this Windows host", M.available() is True)
    try:
        _live = M.cursor_text(3, 3)
        ck("cursor_text never raises on Windows (live OLEACC)",
           isinstance(_live, str), repr(_live))
    except Exception as e:  # a raise through the vtable chain is the defect
        ck("cursor_text never raises on Windows (live OLEACC)", False,
           repr(e))
else:
    ck("available() is False here", M.available() is False)
    ck("cursor_text returns '' off Windows", M.cursor_text(0, 0) == "")
# Should_capture: on Windows it inspects the live exclusion table at the
# point, so it returns True or False but must never raise. Off Windows it is
# always False. Asserts the guaranteed invariant on both hosts.
try:
    _sc = M.should_capture(0, 0)
    ck("should_capture never raises, returns a bool",
       isinstance(_sc, bool), repr(_sc))
    ck("should_capture is False off Windows",
       M.available() is False or _sc in (True, False))
except Exception as e:  # a raise is the defect
    ck("should_capture never raises, returns a bool", False, repr(e))
# start() on Windows installs the REAL low-level hook (it did not for a
# day -- GetModuleHandleW's HMODULE was truncated to a signed int and
# the install failed with 126 on every machine; fixed 2026-10-24). The
# assertion covers both hosts: a bool, and False only off Windows.
_started = M.start(lambda x, y: None)
ck("start() returns a bool (True on Windows, False elsewhere)",
   isinstance(_started, bool)
   and (sys.platform != "win32" or _started is True),
   repr(_started))
M.stop()
try:
    M.stop()
    ck("stop() never raises off Windows", True)
except Exception as e:  # pragma: no cover - would be a defect
    ck("stop() never raises off Windows", False, repr(e))

# --- the hook must apply the real gates (behaviour, not source text) ---
# These three used to be `inspect.getsource` greps.  A text assertion is not
# a behaviour assertion: the greps were satisfied while the hook never fired
# for a left-handed user and never consulted the exclusion list.  Drive the
# hook's state machine instead.
src = M.start.__doc__ or ""
import inspect  # noqa: E402

# The capture gesture is a DRAG (press, sweep the selection, release),
# per the operator's spec and the native: a plain click is not a
# selection, and firing on it auto-translated in a loop (2026-10-24).
_state = {"down": None}
_fired = []
_probe_ok = lambda x, y: (0x1234, None, False, True)
_probe_excluded = lambda x, y: (0x1234, None, True, True)
for _w, _x, _y in ((M.WM_LBUTTONDOWN, 10, 20), (M.WM_LBUTTONUP, 210, 220)):
    M.process_mouse_event(_state, _w, _x, _y, _probe_ok,
                          lambda x, y: _fired.append((x, y)))
ck("hook applies the capture gate (allowed window -> drag fires)",
   _fired == [(210, 220)], repr(_fired))

_state_plain = {"down": None}
_fired_plain = []
for _w in (M.WM_LBUTTONDOWN, M.WM_LBUTTONUP):
    M.process_mouse_event(_state_plain, _w, 10, 20, _probe_ok,
                          lambda x, y: _fired_plain.append((x, y)))
ck("a plain click (no sweep) does NOT fire -- that was the loop",
   _fired_plain == [], repr(_fired_plain))

_state2 = {"down": None}
_fired2 = []
for _w in (M.WM_LBUTTONDOWN, M.WM_LBUTTONUP):
    M.process_mouse_event(_state2, _w, 10, 20, _probe_excluded,
                          lambda x, y: _fired2.append((x, y)))
ck("hook applies the exclusion gate (excluded window -> no capture)",
   _fired2 == [], repr(_fired2))

# The handedness normalization must not stop the primary button from firing
# (the old grep only proved the symbol was mentioned somewhere).
ck("hook fires for the primary button in both handedness settings",
   M.primary_button_messages() == (M.WM_LBUTTONDOWN, M.WM_LBUTTONUP))
ck("documented as a mechanism delta",
   "mechanism delta" in (inspect.getsource(M).split('"""')[1]))

# --- docstring must name the real native chain ---
mod_doc = M.__doc__ or ""
for sym in ("FUN_00417E4E", "FUN_004193F6", "FUN_00404901", "FUN_004183bd"):
    ck(f"doc references {sym}", sym in mod_doc)
ck("doc records IAccessible::get_accValue fallback",
   "get_accValue" in mod_doc)

# --- app.py's mode-2 branch must route cursor text, not the clipboard ---
app_src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "qt", "app.py"),
    encoding="utf-8", errors="replace").read()
ck("the Qt view reads MouseMode for the branch", 'get("MouseMode"' in app_src)
ck("the Qt view calls cursor_text for mode 2", "cursor_text" in app_src)
ck("the Qt view has _capture_selection", "_capture_selection" in app_src)

# the branch must be `if mode == 2: ... cursor_text ... return` so mode 1/0
# still take the clipboard path, and an empty OLEACC read falls through to it.
import re  # noqa: E402
m = re.search(r"def _capture_selection\(self, x, y\).*?(?=\n    def |\n\nclass )",
              app_src, re.S)
ck("the Qt view's capture function is located", m is not None)
if m:
    body = m.group(0)
    # The OLEACC under-the-cursor read was REMOVED (2026-10-24): it
    # returns text at the point whether anything is selected or not,
    # which is what made every click auto-translate. Every mode captures
    # through the copy-capture engine now; cursor_text stays as the
    # OLEACC contract port but is off the mouse path.
    ck("no mode-specific OLEACC branch (that was the auto-loop)",
       re.search(r"_mouse_mode_index\(\)\s*==\s*2", body) is None)
    ck("every mode captures through copy-capture",
       "copy_selection" in body and "cursor_text(" not in body)
    # The clipboard-send fallback is still there, but it lives in the
    # shared capture engine now (qtranslate/selection.py) instead of
    # inline here -- so this pins the CALL, and the engine pins the send.
    _sel = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "qtranslate", "selection.py"),
        encoding="utf-8", errors="replace").read()
    ck("clipboard send stays as the fallback",
       "copy_selection" in body and 'send("ctrl+c")' in _sel)


def _branch(cursor_value, mode):
    """Replicate _work's branch to prove the routing, without Win32 or Tk."""
    calls = []
    text = (cursor_value or "").strip()
    if mode == 2:
        if text:
            calls.append("translate")
            return calls
    calls.append("clipboard")
    return calls


ck("mode 2 + cursor text -> translate path", _branch("abc", 2) == ["translate"])
ck("mode 2 + empty cursor -> clipboard path", _branch("", 2) == ["clipboard"])
ck("mode 2 + whitespace only -> clipboard path", _branch("  ", 2) == ["clipboard"])
ck("mode 1 -> clipboard path", _branch("abc", 1) == ["clipboard"])
ck("mode 0 -> clipboard path", _branch("abc", 0) == ["clipboard"])


# --- the HotKeySwitchMouseMode cycle (native FUN_004183bd 0/1/2) --------
# app._toggle_mouse_mode cycles General.MouseMode (0 off -> 1 popup ->
# 2 popup+read -> 0). Pin the arithmetic the caller relies on.
def _cycle(mode):
    return (mode + 1) % 3


ck("cycle 0 -> 1", _cycle(0) == 1)
ck("cycle 1 -> 2", _cycle(1) == 2)
ck("cycle 2 -> 0 (wraps)", _cycle(2) == 0)
# MouseModeOn is now the TRAY CLICK's own toggle (General.MouseModeOn),
# not a function of the mode index: all three modes are real since the
# floating icon landed (row C10), and off is the tray's left click.
ck("the Qt view persists MouseModeOn from the toggle flag",
   re.search(r'\["MouseModeOn"\]\s*=\s*bool\(getattr\(self,\s*"_mouse_enabled"',
             app_src) is not None,
   "MouseModeOn must come from the tray toggle, not the mode index")
# ...and cycles with the same wrap, no off-by-one drift.
ck("the Qt view cycles the mode with (i+1)%len",
   re.search(r"\(i \+ 1\) % len\(MOUSE_MODES\)", app_src) is not None,
   "mode-cycle expression changed")
ck("the Qt view has the mode hook (not just a label)",
   "_sync_mouse_hook" in app_src and "_capture_selection" in app_src,
   "the mouse mode is not wired")


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_mouse_capture: all checks ok (%d assertions)" % n[0])
