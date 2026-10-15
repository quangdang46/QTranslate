"""Pin `_net_open`: every branch applies the Options.json timeout, and the
proxy branch builds a ProxyHandler when configured.

Native applies `Internet.Timeout` to every curl call (FUN_0045BCED /
FUN_0045BF7D). The port mirrors this in `session._net_open`; the three
branches are: explicit opener (cookie-jar sessions), proxy handler, and
plain urlopen.

Offline: opener and urlopen are faked; Options.json load is patched.
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import session as S
from qtranslate import config as C

_orig_load = C.load


class _Resp:
    def __init__(self, body=b"ok"):
        self._b = body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


C.load = lambda: {"Internet": {"Timeout": 7000}, "Proxy": {}}

# --- explicit opener branch --------------------------------------------
seen = {}


class _Opener:
    def open(self, req, timeout=None):
        seen["timeout"] = timeout
        seen["url"] = req.full_url
        return _Resp()


C.load = lambda: {"Internet": {"Timeout": 7000}, "Proxy": {}}
_req = urllib.request.Request("https://example.com/x")
with S._net_open(_req, opener=_Opener()) as r:
    ck("opener branch reads the body", r.read() == b"ok")
ck("opener branch applies the 7 s timeout", seen.get("timeout") == 7.0,
   repr(seen.get("timeout")))

# --- plain urlopen branch ----------------------------------------------
_orig_urlopen = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=None: (
    seen.__setitem__("t2", timeout) or _Resp())
try:
    with S._net_open(_req) as r2:
        r2.read()
    ck("urlopen branch applies the timeout", seen.get("t2") == 7.0,
       repr(seen.get("t2")))
finally:
    urllib.request.urlopen = _orig_urlopen

# --- absent Timeout -> 10 s fallback in every branch --------------------
C.load = lambda: {"Internet": {}, "Proxy": {}}
urllib.request.urlopen = lambda req, timeout=None: (
    seen.__setitem__("t3", timeout) or _Resp())
try:
    with S._net_open(_req) as r3:
        r3.read()
    ck("missing Timeout falls back to 10 s", seen.get("t3") == 10.0,
       repr(seen.get("t3")))
finally:
    urllib.request.urlopen = _orig_urlopen
    C.load = _orig_load

# --- proxy branch builds a ProxyHandler ---------------------------------
_made = {}
_orig_build = urllib.request.build_opener
urllib.request.build_opener = lambda *h: (
    _made.__setitem__("handlers", h) or _Opener())
C.load = lambda: {"Internet": {},
                  "Proxy": {"ProxyType": 2, "Host": "p.local",
                            "Port": 8080, "Scheme": 0}}
try:
    with S._net_open(_req) as _r4:
        pass
    _hs = [type(h).__name__ for h in _made.get("handlers", ())]
    ck("proxy branch builds a ProxyHandler", "ProxyHandler" in _hs,
       repr(_hs))
finally:
    urllib.request.build_opener = _orig_build
    C.load = _orig_load

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_net_open: all checks ok (%d assertions)" % n[0])
