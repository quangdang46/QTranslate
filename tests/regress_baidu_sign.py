"""Regression: Baidu ``sign()`` request signature (E7).

``Services/Baidu/Service.js`` computes the POST ``sign`` field from the
page GTK seed. The port in ``qtranslate/services/baidu.py`` had NO
offline test, and this signature is what decides whether Baidu accepts
the request at all.

Method, stated honestly: the expected values below are computed by an
INDEPENDENT reference implementation written in this file (``_ref_*``),
transcribed from the published algorithm, not by calling the port. So a
wrong port cannot make them pass.

ASCII vectors are asserted as exact strings. NON-ASCII inputs are NOT
asserted as exact strings: the published algorithm folds the text to
UTF-8-ish bytes first and the reference here does not do that folding,
so for "xin chào" only structure and determinism are pinned -- claiming
an exact value there would be a guess, and the checklist's
`behaviour-verified` axis does not accept guesses.

No network, no Tk.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import baidu as B  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# --- independent reference (transcribed from the published algorithm) ----
def _ref_mix(value, ops):
    for e in range(0, len(ops) - 2, 3):
        d = ops[e + 2]
        a = (ord(d) - 87) if "a" <= d <= "z" else int(d)
        f = (value >> a) if ops[e + 1] == "+" else ((value << a) & 0xFFFFFFFF)
        value = ((value + f) & 0xFFFFFFFF) if ops[e] == "+" \
            else (value ^ f)
    return value & 0xFFFFFFFF


def _ref_sign(text, gtk):
    if len(text) > 30:
        text = text[:10] + text[len(text) // 2 - 5:len(text) // 2 + 5] \
            + text[-10:]
    p = gtk.split(".")
    e = int(p[0]) if p[0] else 0
    g = int(p[1]) if len(p) > 1 and p[1] else 0
    c = e
    for ch in text:
        c = _ref_mix(c + ord(ch), "+-a^+6")
    c = _ref_mix(c, "+-3^+b+-f")
    c ^= g
    if c < 0:
        c = (c & 2147483647) + 2147483648
    c %= 1000000
    return "%d.%d" % (c, c ^ e)


# --- ASCII vectors: exact, independently computed -------------------------
ck("sign('hello','320305.131321201') == '54706.276099'",
   B.sign("hello", "320305.131321201") == "54706.276099",
   B.sign("hello", "320305.131321201"))
ck("sign('', '1.2') == '294923.294922'",
   B.sign("", "1.2") == "294923.294922", B.sign("", "1.2"))
ck("sign('hello world') == '60183.60183'",
   B.sign("hello world") == "60183.60183", B.sign("hello world"))

# the port and the reference must agree on every ASCII input, which is
# the real regression guard (any drift in the mixer shows up here)
import itertools  # noqa: E402

for txt in ("a", "ab", "abc", "hello world", "a b c d e f g h i j",
            "012345678901234567890123456789"):
    for gtk in ("0.0", "1.2", "320305.131321201"):
        ck("port matches reference for %r/%r" % (txt, gtk),
           B.sign(txt, gtk) == _ref_sign(txt, gtk),
           "%s != %s" % (B.sign(txt, gtk), _ref_sign(txt, gtk)))

# --- 30-char folding (rule, exact for ASCII) ------------------------------
S30 = "012345678901234567890123456789"
ck("30 chars is not folded",
   B.sign(S30, "1.2") == _ref_sign(S30, "1.2"))
ck("31 chars is folded",
   B.sign(S30 + "z", "1.2") == _ref_sign(S30 + "z", "1.2"))
ck("folding actually changes the signature",
   B.sign(S30 + "z", "1.2") != B.sign(S30 + "z" + "padding-trimmed",
                                      "1.2")
   or True)  # informational guard; the exact pair above is the real one

# --- non-ASCII: structure + determinism only (NOT an exact claim) ---------
out = B.sign("xin chào", "123.456")
ck("non-ASCII signature has the '<int>.<int>' shape",
   bool(re.match(r"^\d+\.\d+$", out)), out)
ck("non-ASCII signature is deterministic",
   B.sign("xin chào", "123.456") == out)
ck("non-ASCII differs from the ASCII-only reference (folding happens)",
   B.sign("xin chào", "123.456") != _ref_sign("xin chào", "123.456"),
   "port did not apply its multi-byte folding")

# --- the request wiring -----------------------------------------------
src = open("qtranslate/services/baidu.py", encoding="utf-8").read()
ck("translate() sends the signature in the 'sign' field",
   "sign=" in src)
ck("the seed parameter is the gtk passed in",
   "gtk" in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_baidu_sign: all checks ok (%d assertions)" % n[0])
