"""Regression: providers that accept auto natively receive source="auto".

Native Microsoft/Bing Service.js serviceRequest sends
``fromLang=codeFromLanguage(source||AUTO_DETECT_LANGUAGE)`` = "auto" when the
source is auto-detected. The port's _t_bing previously forced "en", which
silently defeated native auto-detection for that provider.

Offline: _bing_tr is monkey-patched to capture the args it receives.
"""
import sys

sys.path.insert(0, "C:/Users/ADMIN/qtranslate-re")

import qtranslate.app as app  # noqa: E402

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
_native_auto = [c for c in app.do_translate.__code__.co_consts
                if isinstance(c, frozenset)]
check("microsoft/bing are native-auto services",
      any({"bing", "microsoft"} <= c for c in _native_auto))


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

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: bing/microsoft receive native 'auto' source")
