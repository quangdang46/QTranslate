"""Slice 5 pin: public SDK surface — translate/detect/speak/dict_lookup/
Result exported; back_translate stays internal; tkinter-free.

Offline: providers are mocked; no network, no window.
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


from qtranslate import sdk
from qtranslate.core import Result

# --- exported surface --------------------------------------------------
for api in ("translate", "detect", "speak", "dict_lookup", "Result"):
    ck("SDK exports %s" % api, hasattr(sdk, api))
    ck("%s in __all__" % api, api in sdk.__all__)
ck("back_translate NOT in __all__ (internal)",
   "back_translate" not in sdk.__all__)
# The contract says back_translate_internal is internal, so a star-import
# must not hand it to a consumer either. It stays importable by name.
ck("back_translate_internal NOT in __all__ (internal too)",
   "back_translate_internal" not in sdk.__all__)
ck("back_translate_internal is still importable by name",
   callable(getattr(sdk, "back_translate_internal", None)))
_ns = {}
exec("from qtranslate.sdk import *", _ns)
ck("a star-import exposes exactly the public surface",
   sorted(k for k in _ns if not k.startswith("__")) ==
   sorted(sdk.__all__), str(sorted(k for k in _ns if not k.startswith("__"))))

# --- translate routes through the engine -------------------------------
import qtranslate.engine as _ENG
_seen = {}


def _fake_engine(service, text, target, src="auto", auto_detect=False,
                 back_translate=False):
    _seen.update(service=service, text=text, target=target, src=src)
    return Result(service, "OK:" + text, service)


_orig = _ENG.translate
_ENG.translate = _fake_engine
try:
    r = sdk.translate("google", "hello", "vi", src="en")
    ck("sdk.translate delegates to engine", r.text == "OK:hello", repr(r.text))
    ck("sdk.translate forwards args", _seen.get("src") == "en", str(_seen))
finally:
    _ENG.translate = _orig

# --- detect routes through the registry --------------------------------
import qtranslate.registry as _RG
_d = []
_o = _RG.detect_language
_RG.detect_language = lambda t: (_d.append(t) or "vi")
try:
    ck("sdk.detect delegates to registry", sdk.detect("hola") == "vi",
       str(_d))
finally:
    _RG.detect_language = _o

# --- dict_lookup routes through DICTS ----------------------------------
from qtranslate.registry import DICTS
_dk = list(DICTS)[0]
_o_fn = DICTS[_dk]
DICTS[_dk] = lambda w, s, t: "DEF:" + w
try:
    ck("sdk.dict_lookup delegates to DICTS",
       sdk.dict_lookup("hello", service=_dk) == "DEF:hello")
    _unknown = False
    try:
        sdk.dict_lookup("x", service="__nope__")
    except KeyError:
        _unknown = True
    ck("sdk.dict_lookup raises KeyError on unknown dict", _unknown)
finally:
    DICTS[_dk] = _o_fn

# --- tkinter-free ------------------------------------------------------
_src = io.open("qtranslate/sdk.py", encoding="utf-8").read()
ck("sdk module imports no tkinter",
   re.search(r"^\s*(import|from)\s+tkinter", _src, re.M) is None)

print("regress_sdk: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
