"""Pin Internet/Proxy option handling (row G Proxy/Timeout).

Native:
- `FUN_00442D92` receives `DAT_00549444` (Internet.Timeout) on the curl
  path — Timeout is honored per request, in milliseconds in Options.json.
- Proxy labels in the binary (read 2026-10-15): "No proxy" (0x51d1c0),
  "Use system proxy settings" (0x51d1d4), "Auto-detect proxy settings"
  (0x51d208), "Manual proxy configuration" (0x51d240). The Options page
  dropdown lists them as [system, none, manual, auto], so ProxyType
  0=system, 1=none, 2=manual, 3=auto-detect. Only manual (2) with a
  host+port builds a proxy URL; everything else yields None.

Offline: config.load is monkey-patched; no network.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import config as C
from qtranslate import session as S

# --- Timeout is seconds in code, ms in the file -------------------------
_o_load = C.load
C.load = lambda: {"Internet": {"Timeout": 15000}, "Proxy": {}}
try:
    o = S.net_options()
    ck("15000 ms -> 15.0 s", o["timeout"] == 15.0, str(o))
finally:
    C.load = _o_load

C.load = lambda: {"Internet": {}, "Proxy": {}}
try:
    ck("absent Timeout falls back to 10 s",
       S.net_options()["timeout"] == 10.0, str(S.net_options()))
finally:
    C.load = _o_load

# --- ProxyType semantics -------------------------------------------------
def _px(ptype, host="", port=0, scheme=0, user=""):
    C.load = lambda: {"Internet": {},
                      "Proxy": {"ProxyType": ptype, "Host": host,
                                "Port": port, "Scheme": scheme,
                                "Username": user, "Password": ""}}
    try:
        return S.net_options()["proxy"]
    finally:
        C.load = _o_load


ck("system proxy (0) -> None", _px(0, "h", 8080) is None)
ck("none (1) -> None", _px(1, "h", 8080) is None)
ck("manual (2) with host+port builds http URL",
   _px(2, "proxy.local", 8080) == "http://proxy.local:8080",
   repr(_px(2, "proxy.local", 8080)))
ck("manual without host -> None", _px(2, "", 8080) is None)
ck("manual without port -> None", _px(2, "h", 0) is None)
ck("Scheme 1 -> https", _px(2, "h", 8080, scheme=1) == "https://h:8080",
   repr(_px(2, "h", 8080, scheme=1)))
ck("auto-detect (3) -> None", _px(3, "h", 8080) is None)

# --- the Options page lists labels in native order -----------------------
# Phase 7 (2026-10-16): the dialog moved to qtranslate/windows.py. The
# tkinter view is gone (2026-10-22) and the Qt pages are display-only,
# so the pin follows the view that is left: the default label the proxy
# combo declares must still be native's system-proxy string.
import io
from tests._view_src import view_source
_view = view_source()
ck("the proxy combo defaults to native's system-proxy label",
   "Use system proxy settings" in _view,
   "internet.py must carry the native label")

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_proxy_options: all checks ok (%d assertions)" % n[0])
