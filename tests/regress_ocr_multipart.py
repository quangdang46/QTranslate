"""Pin the OCR multipart body against the native format strings.

Native `.rdata` format strings (read 2026-10-15):
  0x529e10  "------Boundary%08X\\r\\nContent-Disposition: form-data;
             name=\\"%s\\"; filename=\\"%s\\"\\r\\nContent-Type:
             application/octet-stream\\r\\n\\r\\n"      (file part)
  0x529e90  "------Boundary%08X\\r\\nContent-Disposition: form-data;
             name=\\"%s\\"\\r\\n\\r\\n%s\\r\\n"          (field part)
  0x529ed8  "------Boundary%08X--\\r\\n"                (closing)
  0x529ef0  "Content-Type: multipart/form-data;
             boundary=----Boundary%08X\\r\\n"           (header, 4 dashes)

So the header boundary is `----Boundary<hex>` (4 dashes) and each part
delimiter is `------Boundary<hex>` (6 dashes) — 2 header dashes + 4 token.
The port reproduces exactly this.

Offline: common.http_open is monkey-patched to capture the request.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate.services import ocr
from qtranslate import common

captured = {}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_open(req):
    captured["url"] = req.full_url
    captured["headers"] = dict(req.headers)
    captured["body"] = req.data
    return _Resp(b'{"ParsedResults":[{"ParsedText":"hi"}]}')


_orig = common.http_open
common.http_open = _fake_open
try:
    out = ocr.ocr_text(b"\x89PNG-fake", api_key="mykey", lang="eng")
finally:
    common.http_open = _orig

ck("returns the parsed text", out == "hi", repr(out))
ck("posts to the ocr.space parse endpoint",
   captured["url"] == ocr.OCR_HOST, captured.get("url"))

_ct = next((v for k, v in captured["headers"].items()
            if k.lower() == "content-type"), "")
_m = re.match(r"multipart/form-data; boundary=----Boundary([0-9A-F]{8})", _ct)
ck("header boundary is ----Boundary<8 hex> (native 0x529ef0)",
   _m is not None, _ct)

body = captured["body"]
hexid = _m.group(1) if _m else ""
part_delim = ("------Boundary" + hexid).encode()
# 3 field parts (apikey/language/isOverlayRequired) + 1 file part + closing.
ck("each part starts with ------Boundary<hex> (6 dashes, native 0x529e10/90)",
   body.count(part_delim) == 5, str(body.count(part_delim)))
ck("body closes with ------Boundary<hex>--",
   body.rstrip(b"\r\n").endswith(part_delim + b"--"),
   repr(body[-40:]))
ck("field parts carry name=\"...\"\\r\\n\\r\\n<value>",
   b'name="apikey"\r\n\r\nmykey\r\n' in body
   and b'name="language"\r\n\r\neng\r\n' in body, "field layout")
ck("file part declares filename + octet-stream",
   b'name="file"; filename="capture.png"\r\n'
   b'Content-Type: application/octet-stream\r\n\r\n' in body,
   "file layout")
ck("image bytes are embedded verbatim",
   b"\x89PNG-fake" in body, "payload")
ck("overlay flag is a lowercase bool string",
   b'name="isOverlayRequired"\r\n\r\nfalse\r\n' in body, "overlay")

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_ocr_multipart: all checks ok (%d assertions)" % n[0])
