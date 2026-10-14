"""Regression: Yandex spell request carries native's verbatim headers.

FUN_0042c968 (docs/review/SPELL_SERVICE_STRINGS_2026-10-14.md) sends
exactly three headers, in this order:
  Accept-Encoding: gzip,deflate
  Accept-Charset: utf-8
  Content-Type: application/x-www-form-urlencoded
and the host+path are verbatim strings. Pinned headlessly with a stub
opener; no network.
"""
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


class _Resp:
    headers = {}

    def read(self):
        return b"[]"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


seen = {}


class _Opener:
    def open(self, req, timeout=None):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _Resp()


out = SP.yandex_spell("helo", opener=_Opener())
ck("returns a list", isinstance(out, list))
ck("url is the verbatim host+path",
   seen.get("url", "").startswith(
       "https://speller.yandex.net/services/spellservice.json/checkText?"),
   repr(seen.get("url")))
ck("Accept-Encoding: gzip,deflate",
   seen["headers"].get("accept-encoding") == "gzip,deflate")
ck("Accept-Charset: utf-8",
   seen["headers"].get("accept-charset") == "utf-8")
ck("Content-Type: application/x-www-form-urlencoded",
   seen["headers"].get("content-type")
   == "application/x-www-form-urlencoded")
ck("User-Agent still present",
   "Mozilla/5.0" in seen["headers"].get("user-agent", ""))

SRC = open("qtranslate/services/spell.py", encoding="utf-8").read()
# The older phrase "...were \"not present verbatim ... assembled at
# runtime\"" must be gone (it now survives only inside the withdrawal
# sentence that quotes it to retract it). Assert by checking that the
# only remaining mention is inside the withdrawal paragraph.
_hits = [ln for ln in SRC.splitlines()
         if "not present verbatim" in ln.lower()]
ck("stale INFERRED claim is withdrawn",
   len(_hits) == 1 and "older note" in _hits[0].lower(), str(_hits))
ck("docstring records the open body-shape question",
   "body register was not traced" in SRC
   or "Body shape" in SRC)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_spell_headers: all checks ok (%d assertions)" % n[0])
