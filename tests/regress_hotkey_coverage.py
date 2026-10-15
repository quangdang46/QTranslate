"""Pin the global hotkey action table — 17/17 HOTKEY_NAMES, no drift.

The native HOTKEY_NAMES list (17 entries) is the authority; app.py's
`_actions` table must cover exactly those. A missing entry silently
unbinds a real hotkey. This is the functional equivalent of native's
`FUN_00405A17` RegisterHotKey loop and needs no GUI.

Offline: source parse only.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import config as C
from qtranslate.app import _hotkey_to_combo

src = io.open("qtranslate/app.py", encoding="utf-8").read()
_m = re.search(r"_actions = \{(.*?)\n    \}", src, re.S)
ck("_actions table located", _m is not None)
keys = re.findall(r'"(HotKey\w+)":', _m.group(1)) if _m else []

ck("17 actions registered", len(keys) == 17, str(len(keys)))
ck("covers every HOTKEY_NAMES entry",
   set(keys) == set(C.HOTKEY_NAMES),
   "missing=%r extra=%r" % (sorted(set(C.HOTKEY_NAMES) - set(keys)),
                            sorted(set(keys) - set(C.HOTKEY_NAMES))))
ck("no duplicate entries", len(keys) == len(set(keys)),
   str([k for k in keys if keys.count(k) > 1]))

# --- the label on the button claims the same set -------------------------
m2 = re.search(r"_register_native_hotkeys", src)
ck("app.py registers through _register_native_hotkeys", m2 is not None)
ck("registration uses _hotkey_to_combo",
   "_hotkey_to_combo" in src.split("def _register_native_hotkeys", 1)[1])

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_hotkey_coverage: all checks ok (%d assertions)" % n[0])
