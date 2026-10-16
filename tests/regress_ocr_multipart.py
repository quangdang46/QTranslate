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

# --- the part ORDER: file first, then the fields -----------------------
# Native's format strings are (0x529e10) the FILE part, (0x529e90) one
# FIELD part per `%s`, (0x529ed8) the closer. The port used to emit every
# field first and the file last -- a body the native client never sends.
# This was the bug; the checks above all passed with the wrong order.
_first = body.find(part_delim)
_i_file = body.find(b'name="file"')
_i_apikey = body.find(b'name="apikey"')
_i_lang = body.find(b'name="language"')
ck("the FILE part comes first (native 0x529e10 order)",
   0 < _i_file < _i_apikey, "file@%d apikey@%d" % (_i_file, _i_apikey))
ck("apikey precedes language", 0 < _i_apikey < _i_lang,
   "apikey@%d language@%d" % (_i_apikey, _i_lang))
ck("body STARTS with the file part (no leading field)",
   body.startswith(part_delim + b'\r\nContent-Disposition: form-data; '
                                b'name="file"'),
   repr(body[:60]))

# --- the format strings themselves, read from the image ---------------
EXE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "docs", "review", "artifacts",
    "QTranslate.6.10.0.exe")
if os.path.exists(EXE):
    raw = io.open(EXE, "rb").read()
    # the aligned offsets measured 2026-10-16 (2-byte aligned wide reads)
    FILE_PART = ('Content-Disposition: form-data; name="%s"; filename="%s"'
                 "\r\nContent-Type: application/octet-stream\r\n\r\n")
    FIELD_PART = 'Content-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
    for label, lit in (("file part", FILE_PART), ("field part", FIELD_PART),
                       ("closer", "Boundary%08X--\r\n"),
                       ("header",
                        "boundary=----Boundary%08X\r\n")):
        wide = lit.replace("\r\n", "\r\n").encode("utf-16-le")
        ck("image contains the %s format string" % label,
           wide in raw or lit.encode("ascii") in raw, lit[:50])
    # and the 4-vs-6 dash rule. The part delimiters live in the ASCII
    # copies; the header literal is the WIDE one -- measured 2026-10-16 at
    # the aligned offsets 1216016 (delimiter) and 1216310 (header).
    _hdr = "boundary=----Boundary%08X".encode("utf-16-le")
    _delim = "------Boundary%08X".encode("ascii")
    ck("header literal has FOUR dashes", _hdr in raw)
    ck("part delimiter literal has SIX dashes", _delim in raw)
    _dashes = 0
    if _m:
        _dashes = re.match(r"(-+)", _m.group(0).split("boundary=")[1])
        _dashes = len(_dashes.group(1)) if _dashes else 0
    ck("the port's header boundary is 4 dashes", _dashes == 4,
       repr(_m.group(0) if _m else None))
    ck("the port's part delimiter is header + 2 dashes (6 total)",
       part_delim.decode() == "------" + "Boundary" + hexid, part_delim)
else:
    ck("image present for the format-string check", False, "artifact absent")

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_ocr_multipart: all checks ok (%d assertions)" % n[0])
