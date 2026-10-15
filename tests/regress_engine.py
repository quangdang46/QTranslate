"""Slice 2 pin: engine.translate is behavior-identical to the old inline
do_translate — signature, Result shape, detect/auto_detect branches,
shaping-once, alias compatibility.

Offline, no window, no network: providers are monkey-patched to record
calls; the reliability layer is exercised with a zero-delay policy.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import engine as E
from qtranslate import app as A
from qtranslate import registry as RG

# --- 1. signature / forwarder -----------------------------------------
import inspect
_sig = str(inspect.signature(A.do_translate))
ck("do_translate signature preserved",
   _sig == "(service, text, target, src='auto', auto_detect=False, "
   "back_translate=False)", _sig)
ck("engine.translate signature matches",
   str(inspect.signature(E.translate)) == _sig, str(inspect.signature(E.translate)))

# --- 2. short-circuit branches -----------------------------------------
_r = A.do_translate("google", "hello", "vi", src="vi")
ck("src == target echoes without a provider call",
   _r.ok and _r.text == "hello" and "echo" in _r.note, repr(_r.note))
_e = A.do_translate("", "  ", "vi")
ck("empty text returns empty Result",
   _e.text == "" and "empty" in _e.note, repr(_e.note))

# --- 3. provider call + call order ------------------------------------
# engine reads ``registry.TRANSLATORS`` at call time and the router
# singleton is built from it, so patch registry (not app's alias) and
# reset the singleton so the new table is used.
_calls = {}


def _mk(name, fail=False):
    def _f(t, s, g, **_kw):
        # google's clone calls with _sink= (J7 sink); accept and ignore.
        _calls.setdefault(name, []).append((t, s, g))
        return "" if fail else f"{name}:{t}:{s}>{g}"
    return _f


_orig = dict(RG.TRANSLATORS)
_orig_singleton = getattr(RG, "_ROUTER_SINGLETON", None)
_orig_t_google = RG._t_google


def _patch(table):
    # The per-call clone's google entry is a closure that calls the
    # module-global ``_t_google`` (not the table value), so patch both.
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(table)
    RG._t_google = table.get("google", _orig_t_google)
    RG._ROUTER_SINGLETON = None


_patch({k: _mk(k, fail=(k == "google")) for k in _orig})
try:
    res = A.do_translate("google", "hello", "vi", src="auto")
    ck("route falls back after a failed provider", res.ok, str(res.note))
    ck("only one provider called for a clean first fallback",
       len(_calls) == 2, str(sorted(_calls)))
finally:
    _patch(_orig)
    RG._ROUTER_SINGLETON = _orig_singleton

# --- 4. detect branch counting -----------------------------------------
from qtranslate import registry as RG
_det_calls = []
_orig_det = RG.detect_language
RG.detect_language = lambda t, _d=_det_calls: (_d.append(t) or "en")
try:
    _det_calls.clear()
    A.do_translate("yandex", "hi", "vi", src="auto")
    ck("auto source on a non-auto service triggers one detect",
       len(_det_calls) == 1, str(len(_det_calls)))
    _det_calls.clear()
    A.do_translate("yandex", "hi", "vi", src="en")
    ck("concrete source on a non-auto service triggers no detect",
       len(_det_calls) == 0, str(len(_det_calls)))
    _det_calls.clear()
    A.do_translate("google", "hi", "vi", src="en", auto_detect=True)
    ck("auto_detect forces detection for a concrete source",
       len(_det_calls) == 1, str(len(_det_calls)))
finally:
    RG.detect_language = _orig_det

# --- 5. back-translation via the answering provider --------------------
_patch({"google": _mk("google", fail=True), "yandex": _mk("yandex")})
try:
    res2 = A.do_translate("google", "hello", "vi", src="en",
                         back_translate=True)
    ck("back-translation appended when enabled",
       "back-translation" in res2.text, repr(res2.text))
finally:
    _patch(_orig)
    RG._ROUTER_SINGLETON = _orig_singleton

# --- 6. native error string on total failure ---------------------------
_patch({k: _mk(k, fail=True) for k in _orig})
try:
    res3 = A.do_translate("google", "hello", "vi", src="en")
    ck("total failure yields the native no-data string",
       "No data returned" in res3.text, repr(res3.text))
finally:
    _patch(_orig)
    RG._ROUTER_SINGLETON = _orig_singleton

# --- 7. app.py does not inline orchestration anymore -------------------
import re as _re
_src = io.open("qtranslate/app.py", encoding="utf-8").read()
_fn = _src.split("def do_translate(", 1)[1].split("\n\n\n", 1)[0]
ck("app.do_translate is a thin forwarder",
   "_ENG.translate" in _fn, _fn[:160])
ck("app.do_translate no longer inlines the router call",
   "phonetics_sink" not in _fn, _fn[:160])
_eng_src = io.open("qtranslate/engine.py", encoding="utf-8").read()
ck("engine module imports no tkinter",
   _re.search(r"^\s*(import|from)\s+tkinter", _eng_src, _re.M) is None)
ck("engine owns the auto_detect branch",
   "auto_detect" in _eng_src)
ck("engine imports registry.detect_language (detect stays in registry)",
   "RG.detect_language" in _eng_src and "def detect_language" not in _eng_src)

print("regress_engine: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    try:
        print("FAIL:", f)
    except UnicodeEncodeError:
        print("FAIL:", f.encode("ascii", "replace").decode("ascii"))
sys.exit(1 if fails else 0)
