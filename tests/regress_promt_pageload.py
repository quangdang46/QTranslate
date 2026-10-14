"""Regression: Promt session runs native's /api/pageLoad (FUN_0045f372).

Ghidra decompile (REA 6.4.0/Ghidra 12.1.4, snapshot qt6):
  FUN_0045f372 POSTs `pageIx=0&v=1` to
  `https://www.online-translator.com/api/pageLoad` with the exact header
  trio `Content-Type: application/x-www-form-urlencoded; charset=UTF-8`,
  `XSRF-TOKEN: <xsrf>`, `Cookie: <cookies>`; accepts HTTP 200 only and
  extracts the `_ppup` field (FUN_0045451a). Verified headless: URL, body
  and headers are pinned through a stub opener, no network call.
"""
import io
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import promt as P  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


class _Resp:
    # mirrors what common.read_response_text touches: .read() + .headers.
    status = 200

    def __init__(self, payload):
        self._b = payload.encode("utf-8")
        self.headers = {}

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


seen = {}


class _Opener:
    def open(self, req, timeout=None):
        seen["url"] = req.full_url
        seen["data"] = req.data.decode("utf-8")
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _Resp('{"_ppup": 7, "ok": true}')


out = P.page_load("PAFT", "XSRF", "a=b; c=d", _Opener())
ck("requests /api/pageLoad", seen.get("url") == P.HOST + "/api/pageLoad",
   repr(seen.get("url")))
ck("literal body pageIx=0&v=1", seen.get("data") == "pageIx=0&v=1",
   repr(seen.get("data")))
_hdrs = seen.get("headers", {})
ck("content-type header is native's",
   _hdrs.get("content-type")
   == "application/x-www-form-urlencoded; charset=UTF-8",
   repr(_hdrs))
ck("xsrf-token header", _hdrs.get("xsrf-token") == "XSRF")
ck("cookie header", _hdrs.get("cookie") == "a=b; c=d")
ck("parses the response dict", out.get("_ppup") == 7)
ck("ppup() extracts _ppup", P.ppup(out) == 7)
ck("ppup() is None when absent", P.ppup({"ok": True}) is None)


class _Bad:
    status = 500
    headers = {}

    def read(self):
        return b"{}"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _BadOpener:
    def open(self, req, timeout=None):
        return _Bad()


ck("non-200 returns {}", P.page_load("p", "x", "c", _BadOpener()) == {})


class _Boom:
    def open(self, req, timeout=None):
        raise OSError("offline")


ck("transport failure returns {}", P.page_load("p", "x", "c", _Boom()) == {})

SRC = open("qtranslate/services/promt.py", encoding="utf-8").read()
ck("session() chains page_load after the scrape",
   "page_load(paft, xsrf, _cookie, opener)" in SRC)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_promt_pageload: all checks ok (%d assertions)" % n[0])
