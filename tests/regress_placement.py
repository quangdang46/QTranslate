"""Pin the WINDOWPLACEMENT codec headlessly (row A7 / FUN_00422DDD).

The codec (`decode_placement`/`encode_placement`) was only covered through
the tkinter suite (`ui_match` decode/roundtrip/bad checks). `placement.py`
is pure stdlib, so this suite pins it without a display — including the
ptMin/ptMax = (-1,-1) sentinel that the `_encode_placement` fix
established and the 595x376 template constant (height arithmetic
fixed 2026-10-16: /8 vertically, not /4).

Offline: the live Options.json blob when present; synthetic otherwise.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import placement as P
from qtranslate import config as C

# --- live blob roundtrips ----------------------------------------------
_blob = ""
try:
    _blob = (C.load().get("General", {}) or {}).get("WindowMainPlacement",
                                                     "") or ""
except Exception:
    pass
if _blob:
    rc = P.decode_placement(_blob)
    ck("live blob decodes", rc is not None, _blob[:40])
    if rc:
        ck("live blob has a positive rect", rc[2] > 0 and rc[3] > 0,
           str(rc))
        ck("live blob roundtrips",
           P.encode_placement(rc[0], rc[1], rc[2], rc[3],
                              rc[4]).upper() == _blob.upper(),
           "roundtrip mismatch")
else:
    ck("no live blob on this machine (synthetic path covers it)", True)

# --- synthetic roundtrip ------------------------------------------------
_rt = P.encode_placement(100, 200, 530, 430, 1)
ck("synthetic roundtrip", P.decode_placement(_rt) == (100, 200, 530, 430, 1),
   _rt[:60])
ck("ptMin/ptMax sentinel is -1,-1 (FFFFFFFF pairs)",
   _rt[24:56] == "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF", _rt[24:56])
ck("length field is 44", _rt[:8] == "2C000000", _rt[:8])

# --- malformed input ----------------------------------------------------
ck("short blob decodes to None", P.decode_placement("00") is None)
ck("empty string decodes to None", P.decode_placement("") is None)
ck("None decodes to None", P.decode_placement(None) is None)
ck("garbage hex decodes to None",
   P.decode_placement("ZZZZ") is None)

# --- template constant --------------------------------------------------
# The two DLU axes use DIFFERENT divisors: /4 horizontally, /8 vertically
# (MapDialogRect). An earlier revision divided both by 4, which turned
# `201*15/4 = 753` into a window nearly twice as tall as native's.
ck("TEMPLATE_GEOMETRY is the DLG129-derived 595x376",
   P.TEMPLATE_GEOMETRY == "595x376", P.TEMPLATE_GEOMETRY)
ck("...width uses avg_char_w/4", 340 * 7 // 4 == 595,
   "%d" % (340 * 7 // 4))
ck("...height uses char_h/8, NOT /4 (the trap that made 753)",
   201 * 15 // 8 == 376 and 201 * 15 // 4 != 376,
   "201*15/8=%d but 201*15/4=%d" % (201 * 15 // 8, 201 * 15 // 4))

# win32app.py carries its OWN W, H for the native Win32 re-creation. It had
# the same wrong divisor (595, 753) and was NOT covered by any suite -- it
# is pywin32-gated and nothing reads it headlessly. Pinned here so the two
# constants cannot drift apart again.
_w32 = io.open(os.path.join(ROOT, "qtranslate", "win32app.py"),
               encoding="utf-8").read()
_m = re.search(r"^W, H = (\d+), (\d+)\s*$", _w32, re.M)
ck("win32app.py declares W, H", _m is not None, "not found")
if _m:
    ck("win32app's W, H matches the template constant (595x376)",
       (int(_m.group(1)), int(_m.group(2))) == (595, 376),
       "got %rx%r -- the two constants drifted" % (int(_m.group(1)),
                                                  int(_m.group(2))))


if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_placement: all checks ok (%d assertions)" % n[0])
