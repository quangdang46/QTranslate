"""Regression: Promt request hash ``ghcs``/``ghcd`` (E12).

``ghcs`` mirrors the CURRENT site's page-bundle hash (verified live
2026-11-08): UTF-16 code units, a forward charCodeAt pass (h1) followed
by a backward pass over the same span (h2), and a recursive split for
texts over 100 units: ``h2(u, e-50, e, h2(u, 0, 50, e))``. The >100
boundary is exactly where an implementation tends to break (off-by-one
at the 49/50/51 and 99/100/101 edges). This value is the ``h=`` field
Promt validates — the previous native-Service.js variant (codepoints,
forward-only) is rejected by the live server with HTTP 400.

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


def _u16(s):
    import array
    return array.array("H", s.encode("utf-16-le", "surrogatepass"))


def _step(r, cu):
    # JS `r=(r<<5)-r+charCodeAt(i)`: <<5 is int32 on the old r, -r is not
    return _i32(r * 32) - r + cu


def _h1(u, t, i, r):
    for k in range(t, i):
        r = _step(r, u[k])
    return r


def _h2(u, t, i, r):
    r = _h1(u, t, i, r)
    while i > t:
        i -= 1
        r = _step(r, u[i])
    return r


def _ghcs(text, b=None, d=None, c=0):
    u = _u16(text)
    if b is None:
        e = len(u)
        if e > 100:
            return _h2(u, e - 50, e, _h2(u, 0, 50, e))
        return _h2(u, 0, e, e)
    v = _u16(text[b:d])
    return _h2(v, 0, len(v), c)


# exact vectors, independently computed
ck("ghcs('') == 0", P.ghcs("") == 0, P.ghcs(""))
ck("ghcs('abc') == reference", P.ghcs("abc") == _ghcs("abc"),
   "%s != %s" % (P.ghcs("abc"), _ghcs("abc")))

# the recursion boundary is the interesting part
for length in (0, 1, 10, 49, 50, 51, 99, 100, 101, 150, 200, 301):
    txt = "x" * length
    ck("ghcs matches reference at len %d" % length,
       P.ghcs(txt) == _ghcs(txt), "%s != %s" % (P.ghcs(txt), _ghcs(txt)))

# non-BMP text hashes UTF-16 units, not codepoints
ck("ghcs handles astral chars",
   P.ghcs("a\U0001F600b") == _ghcs("a\U0001F600b"))

# the >100 path really is a different computation from the flat one
ck("a 101-char text is NOT the flat hash",
   P.ghcs("x" * 101) != _h2(_u16("x" * 101), 0, 101, 101),
   "the recursive split did not engage")
ck("a 100-char text IS the flat hash",
   P.ghcs("x" * 100) == _h2(_u16("x" * 100), 0, 100, 100))

# explicit arguments are honoured (the private form callers use)
ck("explicit (b, d, c) arguments work",
   P.ghcs("abcdef", 1, 4, 0) == _ghcs("abcdef", 1, 4, 0))
ck("default c is 0", P.ghcs("abc", 0, 3) == _ghcs("abc", 0, 3, 0))

# ghcd: hash of the composed key string (Cyrillic а in "Generаl")
ck("ghcd returns an int", isinstance(P.ghcd("hello", "en", "ru"), int))
ck("ghcd is deterministic",
   P.ghcd("hello", "en", "ru") == P.ghcd("hello", "en", "ru"))
ck("ghcd differs by language pair",
   P.ghcd("hello", "en", "ru") != P.ghcd("hello", "en", "de"))
ck("ghcd differs by text", P.ghcd("hello", "en", "ru")
   != P.ghcd("world", "en", "ru"))
ck("ghcd(empty) is stable", P.ghcd("", "en", "ru")
   == P.ghcd("", "en", "ru"))
ck("ghcd key uses the Cyrillic-a literal",
   "Gener\\u0430l" in open("qtranslate/services/promt.py",
                          encoding="utf-8").read())

# the translate request really sends this value as h=
src = open("qtranslate/services/promt.py", encoding="utf-8").read()
ck("translate() computes h via ghcd", "h = ghcd(text, sl_code, tl_code)" in src)
ck("translate() puts h in the body", "&h={3}" in src)
ck("translate() sends the opener (session cookies)",
   "common.http_open(req, opener)" in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_promt_hash: all checks ok (%d assertions)" % n[0])
