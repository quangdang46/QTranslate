"""Regression: the Yandex spell request's shape, settled from `.rdata`.

`regress_spell_headers.py` pins the three headers. This suite pins the
thing those headers imply: the **shape of the request** (POST form body,
not a GET query), and the byte-level evidence that closes the question.

The recovered image's `.rdata` holds, adjacent to each other (offsets are
where each literal was found, so they are not reconstructed from memory):

    text=                                                    @1172340
    Accept-Encoding: gzip,deflate\\r\\nAccept-Charset: utf-8\\r\\n
    Content-Type: application/x-www-form-urlencoded\\r\\n
    /services/spellservice.json/checkText
    speller.yandex.net
    pos  len  s                                                @1172360

The port GETs with `?text=` for two days on the grounds that the
decompile showed the Content-Type header but its body register was never
traced. Reading the string table settles it without the decompile: a
query-less path + a form-urlencoded header + a literal `text=` beside them
is a form body, and `pos`/`len`/`s` (the response's suggestion fields)
sit right after the host, confirming this is the spell block.

Headless: the image is READ, never executed. The request itself is pinned
through a stub opener, so no network.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import spell as SP  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(REPO, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")

if not os.path.exists(EXE):
    print("SKIP: recovered image not present (%s)" % EXE)
    raise SystemExit(0)

RAW = io.open(EXE, "rb").read()
IW = RAW.decode("utf-16-le", "replace")


def find_wide(lit):
    return IW.find(lit)


def present(lit):
    """Is ``lit`` in the image, wide or ascii?"""
    return lit in IW or lit.encode("ascii") in RAW


# --- 1. the literals are there, and in the order claimed ----------------
I_TEXT = find_wide("text=")
I_HDR = find_wide("Accept-Encoding: gzip,deflate\r\nAccept-Charset: utf-8")
I_CT = I_HDR + len("Accept-Encoding: gzip,deflate\r\nAccept-Charset: utf-8")
I_PATH = find_wide("/services/spellservice.json/checkText")
I_HOST = find_wide("speller.yandex.net")
I_FIELDS = find_wide("pos")

for label, literal, offset in (
        ("text=", "text=", I_TEXT),
        ("the urlencoded header block", "Accept-Charset: utf-8", I_HDR),
        ("the path", "/services/spellservice.json/checkText", I_PATH),
        ("the host", "speller.yandex.net", I_HOST),
        ("the response fields", "pos", I_FIELDS)):
    ck("image contains %s (off %d)" % (label, offset), offset >= 0)

# The order is what settles POST-not-GET.
ck("text= comes before the header block", 0 <= I_TEXT < I_HDR,
   "text=@%d hdr@%d" % (I_TEXT, I_HDR))
ck("the header block immediately precedes the path",
   I_PATH > I_CT and I_PATH - I_CT < 64,
   "hdr@%d path@%d (gap %d)" % (I_CT, I_PATH, I_PATH - I_CT))
ck("the host follows the path", I_HOST > I_PATH and I_HOST - I_PATH < 48)

# --- 2. the path carries no query separator ----------------------------
ck("the path has no '?' (a GET would carry one)",
   "?" not in "/services/spellservice.json/checkText")
ck("the Content-Type says form-urlencoded, i.e. a BODY",
   I_CT < I_PATH and
   IW[I_CT - len("Content-Type: application/x-www-form-urlencoded")
      : I_CT].startswith("Content-Type: application/x-www-form-urlencoded")
   or "application/x-www-form-urlencoded" in IW[I_HDR:I_PATH])

# --- 3. the port now POSTs that form body ------------------------------
captured = {}


class _R:
    def __init__(self):
        self.headers = {}

    def read(self):
        return b"[]"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _O:
    def open(self, req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["data"] = req.data
        captured["ct"] = req.get_header("Content-type")
        return _R()


SP.yandex_spell("helo world", lang="ru", opener=_O())
ck("the request targets the query-less path",
   captured.get("url", "").endswith(
       "/services/spellservice.json/checkText"),
   repr(captured.get("url")))
ck("the request is a POST", captured.get("method") == "POST",
   repr(captured.get("method")))
ck("the body is text=...&lang=...",
   captured.get("data") == b"text=helo+world&lang=ru",
   repr(captured.get("data")))
ck("the body's Content-Type is form-urlencoded, as native's is",
   captured.get("ct") == "application/x-www-form-urlencoded",
   repr(captured.get("ct")))
ck("the module docstring says the question is closed",
   "closed 2026-10-16" in io.open(
       os.path.join(REPO, "qtranslate", "services", "spell.py"),
       encoding="utf-8").read())

# --- the Google suggest path, and its encoder -------------------------
# `.rdata` carries `/complete/search?client=firefox&q=` immediately followed
# by `https://www.google.com`, in the same block as the spellcheck strings.
ck("the image carries the suggest path",
   present("/complete/search?client=firefox&q="))
ck("...and its host", present("https://www.google.com"))
SUGGEST = io.open(os.path.join(REPO, "qtranslate", "services", "spell.py"),
                  encoding="utf-8").read()
ck("the port's suggest path and host match",
   "/complete/search?client=firefox&q=" in SUGGEST
   and "https://www.google.com" in SUGGEST)
ck("google_suggest encodes with encode_get_param, not quote",
   "encode_get_param(text)" in SUGGEST)
ck("the two encoders really differ on a slash",
   "quote(text" not in SUGGEST.split("def google_suggest")[1]
   .split("\ndef ")[0])
captured2 = {}


class _R2:
    def read(self):
        return b'["q",["alpha","beta"]]'

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _O2:
    def open(self, req, timeout=None):
        captured2["url"] = req.full_url
        return _R2()


SP.google_suggest("a/b", opener=_O2())
ck("google_suggest encodes the slash", "%2F" in captured2.get("url", ""),
   captured2.get("url"))
ck("...and returns the second array element",
   SP.google_suggest("a/b", opener=_O2()) == ["alpha", "beta"])

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_spell_request: all checks ok (%d assertions)" % n[0])
