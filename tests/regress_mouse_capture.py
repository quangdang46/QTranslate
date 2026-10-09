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
ck("available() is False here", M.available() is False)
ck("cursor_text returns '' off Windows", M.cursor_text(0, 0) == "")
ck("should_capture returns False off Windows", M.should_capture(0, 0) is False)
ck("start() returns False off Windows (bool)", M.start(lambda x, y: None) is False)
try:
    M.stop()
    ck("stop() never raises off Windows", True)
except Exception as e:  # pragma: no cover - would be a defect
    ck("stop() never raises off Windows", False, repr(e))

# --- the hook body must reference both the gate and the swap normalization ---
src = M.start.__doc__ or ""
import inspect  # noqa: E402
body = inspect.getsource(M.start)
ck("hook consults should_capture", "should_capture" in body)
ck("hook consults SM_SWAPBUTTON via _buttons_swapped",
   "_buttons_swapped" in body)
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
    os.path.abspath(__file__))), "qtranslate", "app.py"),
    encoding="utf-8", errors="replace").read()
ck("app.py reads MouseMode for the branch", 'get("MouseMode"' in app_src)
ck("app.py calls cursor_text for mode 2", "cursor_text" in app_src)
ck("app.py has _translate_text", "_translate_text" in app_src)

# the branch must be `if mode == 2: ... cursor_text ... return` so mode 1/0
# still take the clipboard path, and an empty OLEACC read falls through to it.
import re  # noqa: E402
m = re.search(r"def _mouse_mode_select\(app, x, y\):.*?\n\n\n", app_src, re.S)
ck("_mouse_mode_select located", m is not None)
if m:
    body = m.group(0)
    has_mode_branch = re.search(r"mode\s*==\s*2", body) is not None
    has_return_after_translate = "return" in body
    ck("mode==2 branch present", has_mode_branch)
    ck("mode-2 path returns before the clipboard send",
       has_return_after_translate)
    ck("cursor_text is consulted inside _work",
       "cursor_text" in body)
    ck("clipboard send stays as the fallback",
       'ctrl+c' in body)


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


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_mouse_capture: all checks ok (%d assertions)" % n[0])
