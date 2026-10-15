"""Pin tray icon state selection (row G Tray / FUN_00418B69 + FUN_00418DA0).

Native (decompiled 2026-10-15):
  FUN_00418B69(param_1, param_2): 0 -> icon 199, 2 -> icon 0x8A, else 0x84.
  FUN_00418DA0(param_1, param_2): state = 0 if flag clear, else
    (available != 0) + 1.
  FUN_00418E85: the flag comes from the MOUSE-HOOK state, so the tray
    icon reflects mouse capture, not bound hotkeys.

Offline: pure integer selection, no pystray/Tk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import tray_state as T

# --- FUN_00418DA0 state rule -------------------------------------------
ck("flag clear -> state 0 (off)", T.select_state(False, False) == 0)
ck("flag clear ignores availability", T.select_state(False, True) == 0)
ck("flag set + unavailable -> state 1", T.select_state(True, False) == 1)
ck("flag set + available -> state 2", T.select_state(True, True) == 2)

# --- names --------------------------------------------------------------
ck("0 -> off", T.state_name(0) == "off")
ck("1 -> on", T.state_name(1) == "on")
ck("2 -> partial", T.state_name(2) == "partial")
ck("unknown index -> off (safe)", T.state_name(9) == "off")

# --- FUN_00418B69 icon indices -----------------------------------------
ck("state 0 -> icon 199", T.native_icon(0) == 199)
ck("state 2 -> icon 0x8A", T.native_icon(2) == 0x8A)
ck("state 1 -> icon 0x84", T.native_icon(1) == 0x84)
ck("unknown index -> icon 0x84 (native else branch)",
   T.native_icon(7) == 0x84)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_tray_state: all checks ok (%d assertions)" % n[0])
