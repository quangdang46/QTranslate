"""Regression: Naver/Papago ``buildAuthData`` (E6, HMAC-MD5).

Native `Services/Naver/Service.js` signs every request with
HmacMD5(key="v1.6.5_956d74858f", message="deviceId\\nurl\\ntimestamp"),
base64s it into `Authorization:PPG <deviceId>:<sig>` and sends the
timestamp alongside. The port had no test beyond "does not crash" in
smoke_dict.py, and this signature is what decides whether Papago accepts
the request.

Pinned by recomputing the HMAC INDEPENDENTLY in this file (not by
calling the port's own hmac call) and decoding the header the port
emits. Headless: no network, no Tk.
"""
import base64
import hashlib
import hmac
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import naver as N  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


URL = "https://papago.naver.com/apis/n2mt/translate"
header, dev = N._auth(URL)

ck("returns a header and a device id", bool(header) and bool(dev))
ck("header has CRLF between the two fields",
   "\r\n" in header and header.count("\r\n") == 1, repr(header))

lines = header.split("\r\n")
auth = lines[0]
ts_line = lines[1]

ck("Authorization uses the PPG scheme", auth.startswith("Authorization:PPG "),
   auth)
ck("Timestamp field is second", ts_line.startswith("Timestamp:"), ts_line)

# Authorization:PPG <deviceId>:<base64 sig>
body = auth[len("Authorization:PPG "):]
ck("PPG payload is '<deviceId>:<sig>'", body.count(":") == 1, body)
dev2, sig_b64 = body.split(":", 1)
ck("the device id in the header is the one returned",
   dev2 == dev, "%r != %r" % (dev2, dev))

# --- recompute the signature independently ------------------------------
ts = int(ts_line[len("Timestamp:"):])
ck("timestamp is a plausible ms epoch (13 digits, not absurd)",
   10**12 <= ts < 10**14, str(ts))

expected = hmac.new(N._AUTH_KEY.encode(),
                    ("%s\n%s\n%d" % (dev, URL, ts)).encode(),
                    hashlib.md5).digest()
got = base64.b64decode(sig_b64)
ck("signature is the HMAC-MD5 of 'deviceId\\nurl\\ntimestamp'",
   got == expected, "%r != %r" % (got.hex(), expected.hex()))
ck("signature is 16 bytes (MD5)", len(got) == 16, str(len(got)))

# the algorithm's constants, as native publishes them
ck("auth key is the native 'v1.6.5_956d74858f'",
   N._AUTH_KEY == "v1.6.5_956d74858f", N._AUTH_KEY)

# each call gets a fresh device id + timestamp (no reuse across requests)
_h2, _d2 = N._auth(URL)
ck("device id is regenerated per call", _d2 != dev)
ck("timestamp advances or stays close",
   abs(int(_h2.split("\r\n")[1].split(":", 1)[1]) - ts) < 60_000)

# header shape the request layer needs
_hdr = dict(
    line.split(":", 1) for line in header.split("\r\n") for _ in [0]
    if ":" in line)
ck("Authorization key present", "Authorization" in _hdr, str(list(_hdr)))
ck("Timestamp key present", "Timestamp" in _hdr)

src = open("qtranslate/services/naver.py", encoding="utf-8").read()
ck("_auth signs with hashlib.md5", "hashlib.md5" in src)
ck("_auth builds the message as dev\\nurl\\nts",
   'f"{dev}\\n{url}\\n{ts}"' in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_naver_auth: all checks ok (%d assertions)" % n[0])
