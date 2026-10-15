"""Regression: Promt request hash ``ghcs``/``ghcd`` (E12).

``ghcs`` is a Java-style string hash with a recursive split: texts over
100 chars are hashed as ``ghcs(text, len-50, len, ghcs(text, 0, 50, len))``,
which is exactly where an implementation tends to break (off-by-one at
the 49/50/51 and 99/100/101 boundaries). The port had no offline test,
and this value is the ``h=`` field Promt validates.

Vectors come from an INDEPENDENT reference implementation written into
this file, so a wrong port cannot make them pass.

No network, no Tk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import promt as P  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


def _i32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def _ghcs(text, b=None, d=None, c=0):
    if b is None:
        e = 0 if not text else len(text)
        if e > 100:
            return _ghcs(text, e - 50, e, _ghcs(text, 0, 50, e))
        return _ghcs(text, 0, e, e)
    for e in range(b, d):
        c = _i32(((c << 5) - c + ord(text[e])) & 0xFFFFFFFF)
    return c


# exact vectors, independently computed
ck("ghcs('') == 0", P.ghcs("") == 0, P.ghcs(""))
ck("ghcs('abc') == 185727", P.ghcs("abc") == 185727, P.ghcs("abc"))

# the recursion boundary is the interesting part
for length in (0, 1, 10, 49, 50, 51, 99, 100, 101, 150, 200, 301):
    txt = "x" * length
    ck("ghcs matches reference at len %d" % length,
       P.ghcs(txt) == _ghcs(txt), "%s != %s" % (P.ghcs(txt), _ghcs(txt)))

# the >100 path really is a different computation from the flat one
ck("a 101-char text is NOT the flat hash",
   P.ghcs("x" * 101) != _ghcs("x" * 101, 0, 101, 101),
   "the recursive split did not engage")
ck("a 100-char text IS the flat hash",
   P.ghcs("x" * 100) == _ghcs("x" * 100, 0, 100, 100))

# explicit arguments are honoured (the private form callers use)
ck("explicit (b, d, c) arguments work",
   P.ghcs("abcdef", 1, 4, 0) == _ghcs("abcdef", 1, 4, 0))
ck("default c is 0", P.ghcs("abc", 0, 3) == _ghcs("abc", 0, 3, 0))

# ghcd: hash of the composed key string
ck("ghcd returns an int", isinstance(P.ghcd("hello", "en", "ru"), int))
ck("ghcd is deterministic",
   P.ghcd("hello", "en", "ru") == P.ghcd("hello", "en", "ru"))
ck("ghcd differs by language pair",
   P.ghcd("hello", "en", "ru") != P.ghcd("hello", "en", "de"))
ck("ghcd differs by text", P.ghcd("hello", "en", "ru")
   != P.ghcd("world", "en", "ru"))
ck("ghcd(empty) is stable", P.ghcd("", "en", "ru")
   == P.ghcd("", "en", "ru"))

# the translate request really sends this value as h=
src = open("qtranslate/services/promt.py", encoding="utf-8").read()
ck("translate() computes h via ghcd", "h = ghcd(text, sl_code, tl_code)" in src)
ck("translate() puts h in the body", "&h={3}" in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_promt_hash: all checks ok (%d assertions)" % n[0])
