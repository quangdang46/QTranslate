"""Regression: youdao's request sign — the third provider F9 names, untested.

F9 covers "Baidu/Youdao/Promt" MD5 signing and cites exactly two suites:
`regress_baidu_sign.py` and `regress_promt_hash.py`. **Youdao had none**, so
its key constant was never compared against anything — a typo in
`_SIGN_KEY` would have changed every request's signature and nothing would
have noticed.

Recovered from the payload, inside `serviceTranslateRequest`::

    var e = "" + (new Date).getTime() + parseInt(10*Math.random(),10),
        c = Utils.md5("fanyideskweb" + a + e + "Y2FYu%TNSbMCxc3t2u^XT")

so the digest is over ``client + prepared_text + salt + key`` — with
``prepareSource``/``limitSource`` applied to the text FIRST, which is what
makes the port's `limit_source(prepare_source(text))` ordering matter.

`Utils.md5` itself is a native helper (JScript has no MD5 built in); the
port uses `hashlib.md5`, and this suite checks the two agree on the
byte-string that matters.

Headless — the JS is read from the artifact, never executed. Skips when
the artifact is absent.
"""
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import common  # noqa: E402
from qtranslate.services import youdao  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")

# --- 1. the key, byte-verified against the payload ----------------------
if os.path.exists(PAYLOAD):
    TS = open(PAYLOAD, "rb").read().decode("utf-8", "replace")
    m = re.search(r'serviceTranslateRequest\(a,b,d\)\{a=prepareSource\(a\);'
                  r'a=limitSource\(a\);var e=""\+\(new Date\)\.getTime\(\)'
                  r'\+parseInt\(10\*Math\.random\(\),10\),'
                  r'c=Utils\.md5\("fanyideskweb"\+a\+e\+"([^"]*)"\)', TS)
    ck("the payload carries youdao's Utils.md5 call verbatim", m is not None,
       "the sign expression is not in the recovered JS")
    if m:
        native_key = m.group(1)
        ck("the port's _SIGN_KEY is the recovered key",
           youdao._SIGN_KEY == native_key,
           "port=%r native=%r" % (youdao._SIGN_KEY, native_key))
        ck("the key is non-empty and not a placeholder",
           len(native_key) >= 16, native_key)
    ck("the client literal is 'fanyideskweb'",
       '"fanyideskweb"' in TS[:TS.find("new ServiceHeader(26,") + 4000]
       or TS.count('"fanyideskweb"') >= 1)

# --- 2. the digest, against an independent reference ---------------------
# Written from the recovered expression, not from the port. NOTE: no
# normalisation here -- native's md5 sees the text AFTER
# prepareSource/limitSource have run, and the port applies those in
# translate(). Putting them in this reference too would hide a
# double-normalisation bug rather than catch one.
CLIENT = "fanyideskweb"
KEY = "Y2FYu%TNSbMCxc3t2u^XT"


def ref_sign(text, salt):
    return hashlib.md5((CLIENT + text + salt + KEY)
                       .encode("utf-8")).hexdigest()


for text, salt in (("hello", "1700000000000"),
                   ("hello world", "1700000000001"),
                   ("xin chào", "1700000000002"),
                   ("a" * 6000, "1700000000003"),   # over limitSource's cap
                   ("", "1700000000004"),
                   ("", ""),
                   ("tab\tand\nnewline", "1700000000005")):
    got = youdao.make_sign(text, salt)
    want = ref_sign(text, salt)
    ck("make_sign(%r, %r) matches the reference" % (text[:20], salt),
       got == want, "port=%r ref=%r" % (got, want))

# the salt's native shape: "" + ms + a single decimal digit
ck("translate() builds a ms+digit salt",
   re.search(r'salt = str\(int\(time\.time\(\) \* 1000\)'
             r'\s*\+\s*int\(random\.random\(\) \* 10\)\)',
             open(os.path.join(ROOT, "qtranslate", "services", "youdao.py"),
                  encoding="utf-8").read()) is not None,
   "the salt no longer matches native's ms + one-digit form")

# --- 3. the hexdigest shape --------------------------------------------
s = youdao.make_sign("hello", "1")
ck("the digest is 32 lowercase hex chars",
   len(s) == 32 and re.fullmatch(r"[0-9a-f]{32}", s) is not None, s)
ck("an empty text still signs (native does not short-circuit)",
   youdao.make_sign("", "1") == ref_sign("", "1"))
ck("a different salt gives a different digest",
   youdao.make_sign("hello", "1") != youdao.make_sign("hello", "2"))

# --- 4. the text is normalised the way native normalises ---------------
# make_sign itself does NOT normalise -- and neither does native: the
# prepareSource/limitSource calls happen in serviceTranslateRequest BEFORE
# the md5, so the port's translate() must normalise first. Check the layer
# that actually normalises, not the digest helper.
_src = open(os.path.join(ROOT, "qtranslate", "services", "youdao.py"),
            encoding="utf-8").read()
ck("translate() applies limit_source(prepare_source(text)) once",
   re.search(r"text = limit_source\(prepare_source\(text\)\)", _src) is not None,
   "the text is not normalised before the request is built")
ck("...and make_sign receives that normalised text",
   re.search(r"sign = make_sign\(text, salt\)", _src) is not None,
   "the sign is computed over text that was never normalised")
ck("the digest itself is over exactly what it is given (no re-normalising)",
   youdao.make_sign("a\r\nb", "1") == ref_sign("a\r\nb", "1"),
   "make_sign normalises when native's md5 does not")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_youdao_sign: all checks ok (%d assertions%s)"
      % (n[0], ", artifact verified" if os.path.exists(PAYLOAD)
         else ", artifact absent"))
