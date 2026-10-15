"""Regression: ``Number(x)||0`` -- the seed coercion three providers share.

Google's ``tk`` and Baidu's ``sign`` both seed from a page-scraped
numeric string and coerce each ``.``-segment with native's
``Number(...)||0``:

    Service.js (Google, id 1):
        for(var c=(Options.GoogleTkk||"0.0").split("."),h=Number(c[0])||0,
            ... ; a^=Number(c[1])||0; ...
    Service.js (Baidu, id 28):
        var g=d.split("."),e=Number(g[0])||0,g=Number(g[1])||0, ...

The semantics: an empty segment is ``0``, and a **non-numeric** segment is
``NaN`` -- falsy, so it also becomes ``0``. Native does not reject it.

Both ports used ``int(seg)``, which raises on exactly those shapes, so a
TKK/GTK of ``"abc.def"`` blew up the whole request. Both fixed
2026-10-16 by moving the coercion into ``common.js_number``.

The suite also proves the fix is observable: with a junk seed, the
signature is the ``0``-seed one, which is what ``Number(NaN)||0``
yields -- not an exception, and not a value derived from a partial parse.

Headless; the JS is read from the artifact, never executed.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import common  # noqa: E402
from qtranslate.services import baidu, google_translate  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")
SKIP = not os.path.exists(PAYLOAD)

if not SKIP:
    TS = open(PAYLOAD, "rb").read().decode("utf-8", "replace")

    def body_of(sid, name):
        i = TS.find("new ServiceHeader(%d," % sid)
        nxt = [m.start() for m in
               re.finditer(r'new ServiceHeader\((\d+),', TS) if m.start() > i]
        seg = TS[i:nxt[0] if nxt else len(TS)]
        m = re.search(r"function " + name + r"\s*\([^)]*\)\s*\{", seg)
        depth, j = 1, m.end()
        while j < len(seg) and depth:
            if seg[j] == "{":
                depth += 1
            elif seg[j] == "}":
                depth -= 1
            j += 1
        return seg[m.end():j - 1]

# --- 1. the coercion really is native's, in BOTH services ---------------
if not SKIP:
    for sid, fn, want in ((1, "tk", r"Number\(c\[0\]\)\|\|0"),
                          (1, "tk", r"Number\(c\[1\]\)\|\|0"),
                          (28, "sign", r"Number\(g\[0\]\)\|\|0"),
                          (28, "sign", r"Number\(g\[1\]\)\|\|0")):
        body = body_of(sid, fn)
        ck("%s (service %d) coerces with %s" % (fn, sid, want[8:-5]),
           re.search(want, body) is not None,
           "not found in the recovered source")

# --- 2. js_number's semantics -------------------------------------------
for seg, want in (("", 0), ("0", 0), ("12", 12), ("-7", -7),
                  ("abc", 0), ("abc.def", 0), ("1e3", 1000),
                  ("  9  ", 9), ("3.9", 3), (None, 0), (5, 5), (True, 1),
                  ("1e3.5", 0)):
    got = common.js_number(seg)
    ck("js_number(%r) == %d" % (seg, want), got == want, "got %r" % got)

# Infinity is truthy in native, but the JS ToInt32 the mixers perform
# maps every infinite value to 0, so the *effective* seed is 0 and the
# port reports 0 -- which is what matters here: not raising.
ck("'Infinity' does not raise and lands on the effective seed (0)",
   common.js_number("Infinity") == 0)
ck("js_number never raises, for any junk",
   all(isinstance(common.js_number(x), int) for x in
       (None, "", "x", "--", "\t", "[]", "0x10", "nan", "Infinity",
        "-Infinity", "-", "+", "1_000", "0b101")))

# --- 3. the crash these were, is gone -----------------------------------
for junk in ("abc.def", "1e3.9", "", ".", "x.y", "..", "Infinity",
             "0b101", "[]", "-"):
    try:
        s = baidu.sign("hello", junk)
        ck("baidu.sign('hello', %r) does not raise" % junk, True)
    except Exception as ex:  # noqa: BLE001 - the point is that it does not
        ck("baidu.sign('hello', %r) does not raise" % junk, False, str(ex))
    try:
        t = google_translate.tk("hello", junk)
        ck("tk('hello', %r) does not raise" % junk, True)
    except Exception as ex:  # noqa: BLE001
        ck("tk('hello', %r) does not raise" % junk, False, str(ex))

# --- 4. the observable consequence: a junk seed == the 0 seed -----------
ck("a junk TKK signs exactly like '0.0'",
   google_translate.tk("hello", "abc.def")
   == google_translate.tk("hello", "0.0"),
   "%s != %s" % (google_translate.tk("hello", "abc.def"),
                 google_translate.tk("hello", "0.0")))
ck("a junk GTK signs exactly like '0.0'",
   baidu.sign("hello", "abc.def") == baidu.sign("hello", "0.0"),
   "%s != %s" % (baidu.sign("hello", "abc.def"),
                 baidu.sign("hello", "0.0")))
ck("a junk seed is NOT the '1.2' seed (so it is really 0, not a fallback)",
   google_translate.tk("hello", "abc.def")
   != google_translate.tk("hello", "1.2"))

# --- 5. real seeds are untouched by the fix -----------------------------
ck("tk('hello','320305.131321201') unchanged",
   google_translate.tk("hello", "320305.131321201") == "54706.276099",
   google_translate.tk("hello", "320305.131321201"))
ck("sign('hello','320305.131321201') unchanged",
   baidu.sign("hello", "320305.131321201") == "54706.276099",
   baidu.sign("hello", "320305.131321201"))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_js_number: all checks ok (%d assertions%s)"
      % (n[0], ", artifact used" if not SKIP else ", artifact absent"))
