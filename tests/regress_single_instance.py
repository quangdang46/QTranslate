"""Pin the single-instance guard (row A2 / FUN_00435175).

Native (decompiled 2026-10-15): without the `allow-multiple-instances`
flag, `FindWindowW("QTranslate_ApplicationWindow")` + `PostMessage(hwnd,
0x111, 0x8009)` activates the running copy and the new launch exits
(returns 1). The port mirrors this in `single_instance.ensure_single`:
True = activated another instance, caller exits; False = start up.

Offline: find/activate are faked; no window, no messages.
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


from qtranslate import single_instance as SI

# --- no existing window: start up --------------------------------------
ck("no existing window -> start up",
   SI.ensure_single([], find_window=lambda: 0) is False)

# --- existing window: activate it, caller exits ------------------------
seen = []


def _find():
    return 12345


def _act(hwnd):
    seen.append(hwnd)
    return True


ck("existing window -> caller must exit",
   SI.ensure_single([], find_window=_find, activate=_act) is True)
ck("activation posts WM_COMMAND/0x8009 to that window",
   seen == [12345], str(seen))

# --- the multi-instance flag skips the check ---------------------------
ck("allow-multiple-instances flag starts anyway",
   SI.ensure_single(["allow-multiple-instances"], find_window=_find,
                    activate=_act) is False)
ck("no activation attempted with the flag", seen == [12345], str(seen))

# --- win32 constants match the native call -----------------------------
ck("window class is the native class",
   SI.WINDOW_CLASS == "QTranslate_ApplicationWindow")
ck("activate command is 0x8009", SI.ACTIVATE_COMMAND == 0x8009)
ck("message is WM_COMMAND (0x111)", SI.WM_COMMAND == 0x111)

# --- broken find/activate degrade to start-up (never a crash loop) -----
ck("find raising -> start up",
   SI.ensure_single([], find_window=lambda: 1 / 0,
                    activate=_act) is False)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_single_instance: all checks ok (%d assertions)" % n[0])
