"""Regression: Google ``tk()`` request token (E21, natives-derived).

``tk(a)`` computes the ``tk`` query parameter Google's translate and TTS
endpoints require. Same algorithm family as Baidu's ``sign()``, and it
carried the SAME bug: for ``ch < 128`` the loop fell through to the
shared ``g.append((f & 63) | 128)``, so every ASCII character emitted a
stray continuation byte ("a" -> [97, 161]) and every token was wrong.

Vectors here come from an INDEPENDENT reference implementation written
into this file (transcribed from the published algorithm), so a wrong
port cannot make them pass. Non-ASCII is pinned structurally only.

No network, no Tk.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import google_translate as G  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


def _b(a, ops):
    for d in range(0, len(ops) - 2, 3):
        c = ops[d + 2]
        c = (ord(c) - 87) if "a" <= c <= "z" else int(c)
        c = (a >> c) if ops[d + 1] == "+" else ((a << c) & 0xFFFFFFFF)
        a = (a + c) & 0xFFFFFFFF if ops[d] == "+" else a ^ c
    return a


def _ref_tk(text, tkk="0.0"):
    """Reference tk() with the FULL published folding, ASCII included.

    The folding must be exact: ASCII = 1 byte, U+0080..U+07FF = 2 bytes,
    above that 3 bytes. An earlier version of this helper dropped the
    continuation byte in the 2-byte branch, which made the reference
    compute the no-fold value -- the port was right and the helper was
    wrong. Pinned by the `"à"` case below.
    """
    p = tkk.split(".")
    h = int(p[0]) if p[0] else 0
    g = []
    for ch in text:
        f = ord(ch)
        if f < 128:
            g.append(f)
        elif f < 2048:
            g.append((f >> 6) | 192)
            g.append((f & 63) | 128)
        else:
            g.append((f >> 12) | 224)
            g.append(((f >> 6) & 63) | 128)
            g.append((f & 63) | 128)
    a = h
    for d in g:
        a += d
        a = _b(a, "+-a^+6")
    a = _b(a, "+-3^+b+-f")
    a ^= int(p[1]) if len(p) > 1 and p[1] else 0
    if a < 0:
        a = (a & 2147483647) + 2147483648
    a %= 1000000
    return "%d.%d" % (a, a ^ h)


# exact vectors, independently computed
ck("tk('hello') == '29979.29979'", G.tk("hello") == "29979.29979",
   G.tk("hello"))
ck("tk('hello world') == '60183.60183'",
   G.tk("hello world") == "60183.60183", G.tk("hello world"))
ck("tk('') is the seed pair", G.tk("") == "0.0", G.tk(""))

# the port must agree with the reference on every ASCII input and seed
for txt in ("a", "ab", "hello", "hello world",
            "012345678901234567890123456789",
            "the quick brown fox jumps over the lazy dog"):
    for tkk in ("0.0", "1.2", "406305.1234567890"):
        ck("port matches reference for %r/%r" % (txt, tkk),
           G.tk(txt, tkk) == _ref_tk(txt, tkk),
           "%s != %s" % (G.tk(txt, tkk), _ref_tk(txt, tkk)))

# the ASCII branch must contribute exactly one byte per character
ck("a 30-char ASCII string uses 30 bytes",
   G.tk("a" * 30) == _ref_tk("a" * 30))

# non-ASCII: structure + determinism only -- the reference does not fold,
# so an exact value here would be a guess.
out = G.tk("xin chào")
ck("token has the '<int>.<int>' shape", bool(re.match(r"^\d+\.\d+$", out)),
   out)
ck("token is deterministic", G.tk("xin chào") == out)

# A 2-byte character pins the folding: "à" (U+00E0) must go through
# [((f>>6)|192), ((f&63)|128)] = [195, 160], which yields 32343.32343.
# The no-fold value would be 711035.711035, so agreeing with the
# reference here proves the fold runs.
ck("2-byte char folds to [195,160]", G.tk("à") == "32343.32343",
   G.tk("à"))
ck("2-byte char matches the reference",
   G.tk("à") == _ref_tk("à", "0.0"),
   "%s != %s" % (G.tk("à"), _ref_tk("à", "0.0")))

# the tkk seed really drives the result (a stale token is a real bug)
ck("different seeds give different tokens",
   G.tk("hello", "1.2") != G.tk("hello", "0.0"))
ck("seed split handles a missing second part",
   G.tk("hello", "406305") == G.tk("hello", "406305.0"))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_google_tk: all checks ok (%d assertions)" % n[0])
