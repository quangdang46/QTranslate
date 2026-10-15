"""Regression: ``encodeUriParam`` == JS ``encodeURIComponent`` (Common.js).

Recovered `Common.js` (NSIS chunk at `0x13af4`)::

    function encodeUriParam(a){return a?encodeURIComponent(a):""}
    function encodeGetParam(a){a=encodeUriParam(a);if(a.length>Const.MAX_URI_LEN)
        {a=a.slice(0,Const.MAX_URI_LEN);var b=a.lastIndexOf("%20");
         if(0<b)return a.slice(0,b)}return a}
    function encodePostParam(a){return encodeUriParam(a)}

``encodeURIComponent``'s unreserved set is
``A-Z a-z 0-9 - _ . ! ~ * ' ( )`` -- it leaves ``! ' ( ) *`` alone,
which ``urllib.parse.quote(safe="")`` percent-encodes. The port used the
latter, so every request parameter over-encoded five characters. A
provider that validates a signature computed over the encoded form sees
a different string than the web client sends.

The sweep below asserts parity over EVERY printable ASCII character, not
a hand-picked few. No network, no Tk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.common import (  # noqa: E402
    encode_get_param, encode_post_param, encode_uri_param, MAX_URI_LEN,
)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# the exact unreserved set encodeURIComponent leaves alone
UNRESERVED = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "-_.!~*'()")

# --- full printable-ASCII parity sweep -----------------------------------
mismatches = []
for cp in range(0x20, 0x7F):
    ch = chr(cp)
    expected = ch if ch in UNRESERVED else "%%%02X" % cp
    got = encode_uri_param(ch)
    if got != expected:
        mismatches.append((cp, ch, got, expected))
ck("every printable ASCII char matches encodeURIComponent",
   not mismatches, str(mismatches[:8]))

# the five that were wrong before, pinned individually
for ch in "!'()*":
    ck("%r is left unencoded (encodeURIComponent does)" % ch,
       encode_uri_param(ch) == ch, encode_uri_param(ch))
ck("'~' is left unencoded", encode_uri_param("~") == "~")
ck("space -> %20", encode_uri_param(" ") == "%20")
ck("'+' -> %2B (NOT a space)", encode_uri_param("+") == "%2B")
ck("'/' -> %2F", encode_uri_param("/") == "%2F")
ck("'?' -> %3F", encode_uri_param("?") == "%3F")
ck("'&' -> %26", encode_uri_param("&") == "%26")
ck("'=' -> %3D", encode_uri_param("=") == "%3D")
ck("'%' -> %25", encode_uri_param("%") == "%25")
ck("'#' -> %23", encode_uri_param("#") == "%23")

# --- empty / falsy semantics (native's `a?...:\"\"`) ---------------------
ck("empty string -> ''", encode_uri_param("") == "")
ck("None -> ''", encode_uri_param(None) == "")

# --- non-ASCII (UTF-8 percent-encoded) ----------------------------------
ck("'é' -> UTF-8 bytes", encode_uri_param("é") == "%C3%A9")
ck("a string mixes correctly (parens stay bare, space encoded)",
   encode_uri_param("café (v2)") == "caf%C3%A9%20(v2)",
   encode_uri_param("café (v2)"))

# --- encode_get_param: MAX_URI_LEN + %20 back-off ----------------------
ck("short values pass through",
   encode_get_param("hello") == "hello")
ck("post param is the same as uri param",
   encode_post_param("a b!") == encode_uri_param("a b!"))
ck("encode_get_param truncates at MAX_URI_LEN",
   len(encode_get_param("x" * (MAX_URI_LEN + 50))) <= MAX_URI_LEN)
ck("encode_get_param cuts back to the last %20 when one exists",
   encode_get_param("word " * 500).endswith("word"),
   encode_get_param("word " * 500)[-8:])
ck("encode_get_param leaves a value without any space simply truncated",
   encode_get_param("x" * (MAX_URI_LEN + 50)) == "x" * MAX_URI_LEN,
   len(encode_get_param("x" * (MAX_URI_LEN + 50))))
ck("MAX_URI_LEN is 1800 (Const.MAX_URI_LEN)", MAX_URI_LEN == 1800,
   str(MAX_URI_LEN))

# a truncated value must be a prefix-cut followed by %20 trimming, which
# never leaves a dangling percent escape
val = encode_get_param("word " * 500)
ck("truncation leaves no dangling escape",
   not (val.endswith("%") or val.endswith("%2")), val[-4:])

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_encode_uri: all checks ok (%d assertions)" % n[0])
