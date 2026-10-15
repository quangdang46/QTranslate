"""Pin the TTS listen-URL builder + the slow flag (J4 / FUN_0046606C).

Native: ``FUN_0046606C`` builds the ``serviceListenRequest`` VARIANT args
and sets the slow argument to ``(param_3 ^ 1) - 1`` — i.e. ``slow=True``
→ ``-1`` (VT_BOOL TRUE), ``slow=False`` → ``0`` (FALSE). The port mirrors
this as an ``&ttsspeed=0.24`` suffix on the Google listen URL.

Offline: pure string construction, no fetch.
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


from qtranslate.services import google_translate as G

_fast = G.listen_url("hello", "en", slow=False)
_slow = G.listen_url("hello", "en", slow=True)

ck("fast URL omits ttsspeed", "ttsspeed" not in _fast, _fast)
ck("slow URL carries ttsspeed=0.24", "ttsspeed=0.24" in _slow, _slow)
ck("slow is the fast URL plus the speed suffix",
   _slow == _fast + "&ttsspeed=0.24", _slow)
ck("URL targets the TTS path with client=gtx",
   "/translate_tts?" in _fast and "client=gtx" in _fast, _fast)
ck("URL carries a tk token", "tk=" in _fast, _fast)
ck("language code is normalised into tl=", "tl=en" in _fast, _fast)

# The native argument mapping (param_3 ^ 1) - 1 is the evidence the port's
# boolean flag encodes: True -> -1, False -> 0. Assert the port keeps a
# boolean (not an int sentinel leaking through).
import inspect
_sig = inspect.signature(G.listen_url)
ck("slow is a boolean parameter",
   _sig.parameters["slow"].default is False, str(_sig))

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_tts_slow: all checks ok (%d assertions)" % n[0])
