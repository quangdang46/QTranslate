"""Pin start-with-Windows (row G) via an injectable winreg double.

The UI wiring (Options Basics page) reads ``startup_entry()`` and calls
the returned setter on toggle; this suite proves the logic against a
fake registry: read reports presence, set(True) writes the executable
path under HKCU ...\\Run\\QTranslate, set(False) deletes it. A missing
winreg honestly reports (False, no-op).

Offline: no real registry touched, no window.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _FakeReg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 1
    REG_SZ = 1

    def __init__(self, values=None):
        self.values = dict(values or {})

    # The port only calls OpenKey/QueryValueEx/SetValueEx/DeleteValue.
    def OpenKey(self, _root, _path, _reserved=0, _access=0):
        return ("key", _path)

    def QueryValueEx(self, _key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], 1

    def SetValueEx(self, _key, name, _reserved, _typ, value):
        self.values[name] = value

    def DeleteValue(self, _key, name):
        try:
            del self.values[name]
        except KeyError:
            raise FileNotFoundError(name)


fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


import qtranslate.app as A

# --- absent entry ------------------------------------------------------
fr = _FakeReg()
present, setter = A.startup_entry(winreg_mod=fr,
                                  executable="C:\\app\\qtranslate.exe")
ck("absent entry reports False", present is False)
setter(True)
ck("set(True) writes the executable path",
   fr.values.get("QTranslate") == "C:\\app\\qtranslate.exe",
   str(fr.values))

# --- present entry, then toggle off ------------------------------------
present2, setter2 = A.startup_entry(winreg_mod=fr,
                                    executable="C:\\app\\qtranslate.exe")
ck("present entry reports True", present2 is True)
setter2(False)
ck("set(False) deletes the value", "QTranslate" not in fr.values)

# --- deleting an absent value does not raise ---------------------------
try:
    setter2(False)
    ck("set(False) on absent value is silent", True)
except Exception as e:
    ck("set(False) on absent value is silent", False, repr(e))

# --- direct unit check of the toggle contract --------------------------
# set(True) then set(False) returns to absent; the toggle is symmetric.
fr2 = _FakeReg()
_, w = A.startup_entry(winreg_mod=fr2, executable="x")
w(True)
w(False)
ck("toggle on then off returns to absent", "QTranslate" not in fr2.values)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_startup_entry: all checks ok (%d assertions)" % n[0])
