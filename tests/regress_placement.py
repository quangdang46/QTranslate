"""Pin the WINDOWPLACEMENT codec headlessly (row A7 / FUN_00422DDD).

The codec (`decode_placement`/`encode_placement`) was only covered through
the tkinter suite (`ui_match` decode/roundtrip/bad checks). `placement.py`
is pure stdlib, so this suite pins it without a display — including the
ptMin/ptMax = (-1,-1) sentinel that the `_encode_placement` fix
established and the 595x753 template constant.

Offline: the live Options.json blob when present; synthetic otherwise.
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
ck("TEMPLATE_GEOMETRY is the DLG129-derived 595x753",
   P.TEMPLATE_GEOMETRY == "595x753", P.TEMPLATE_GEOMETRY)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_placement: all checks ok (%d assertions)" % n[0])
