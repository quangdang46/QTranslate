"""Regression: providers that accept auto natively receive source="auto".

Native Microsoft/Bing Service.js serviceRequest sends
``fromLang=codeFromLanguage(source||AUTO_DETECT_LANGUAGE)`` = "auto" when the
source is auto-detected. The port's _t_bing previously forced "en", which
silently defeated native auto-detection for that provider.

Offline: _bing_tr is monkey-patched to capture the args it receives.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))

# Since 2026-10-15 the _t_* adapters live in qtranslate/registry.py
# (Phase 2 slice; app re-exports them). Import the canonical home, which
# needs no tkinter.
import qtranslate.registry as app  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


captured = {}


def _fake_bing(t, sl, tl):
    captured["sl"] = sl
    return "x"


_orig = app._bing_tr
app._bing_tr = _fake_bing
try:
    app._t_bing("hello", "auto", "vi")
    check("_t_bing forwards source 'auto' (not forced to en)",
          captured["sl"] == "auto", repr(captured.get("sl")))
    app._t_bing("hello", "fr", "vi")
    check("_t_bing forwards a concrete source unchanged",
          captured["sl"] == "fr", repr(captured.get("sl")))
finally:
    app._bing_tr = _orig

# microsoft/bing are in the native-auto set (no detect round-trip expected).
# Since 2026-10-15 the table lives in qtranslate/registry.py as
# USES_AUTO_DETECT (Phase 2 slice); read the canonical source so this suite
# stays tkinter-free like the rest of the file.
import io as _io
import os as _os
import re as _re
_reg_src = _io.open(_os.path.join(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))), "qtranslate", "registry.py"),
    encoding="utf-8").read()
_m = _re.search(r"USES_AUTO_DETECT\s*=\s*(\{.*?\})", _reg_src, _re.S)
_cap = eval(_m.group(1)) if _m else {}
check("microsoft/bing are native-auto services",
      _cap.get("bing") is True and _cap.get("microsoft") is True,
      repr(_cap))


# yandex / youdao / babylon must ALSO forward "auto" verbatim: native sends
# codeFromLanguage(source) = "auto" for each (serviceTranslateRequest).
from qtranslate.services import yandex as _Y  # noqa: E402
from qtranslate.services import youdao as _Yo  # noqa: E402
from qtranslate.services import babylon as _B  # noqa: E402

seen = {}
_o_y, _o_yo, _o_b = _Y.translate, _Yo.translate_web, _B.translate


def _cap(name, fn):
    def w(t, sl, tl, *a, **k):
        seen[name] = sl
        return "x"
    return w


_Y.translate = _cap("yandex", _Y.translate)
_Yo.translate_web = _cap("youdao", _Yo.translate_web)
_B.translate = _cap("babylon", _B.translate)
try:
    app._t_yandex("h", "auto", "vi")
    app._t_youdao("h", "auto", "vi")
    app._t_babylon("h", "auto", "vi")
finally:
    _Y.translate, _Yo.translate_web, _B.translate = _o_y, _o_yo, _o_b
for prov in ("yandex", "youdao", "babylon"):
    check("%s forwards 'auto' verbatim" % prov, seen.get(prov) == "auto",
          repr(seen.get(prov)))

# auto_detect flag is live (RE-closed 2026-10-15): do_translate must
# READ the flag, not just accept it. Slice 2 (2026-10-15) moved the
# orchestration into engine.py, so read the body there.
# Native: DAT_0054941f packed into FUN_004606ba forces detect even for a
# concrete source; the Options-page byte DAT_005494e6 is RemoveLineBreaks.
_app_src = _io.open(_os.path.join(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))), "qtranslate", "app.py"),
    encoding="utf-8").read()
_eng_src = _io.open(_os.path.join(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))), "qtranslate", "engine.py"),
    encoding="utf-8").read()
_m2 = _re.search(r"def translate\(.*?\n(.*?)(?=\ndef |\Z)", _eng_src, _re.S)
_body = _m2.group(1) if _m2 else ""
check("engine.translate reads auto_detect (not dead wiring)",
      _body.count("auto_detect") >= 2, "refs=%d" % _body.count("auto_detect"))
check("auto_detect forces detect for concrete src (via the request)",
      "elif req.auto_detect" in _body)
check("app.do_translate forwards to the engine (no inline branch)",
      "_ENG.translate" in _app_src.split("def do_translate", 1)[1])

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: bing/microsoft receive native 'auto' source")
