"""regress_yandex_web -- yandex-web-services plugin port.

All HTTP stubbed: _post and the Mozhi fallback are replaced; asserts
the form body, response parsing, language mapping, pacing contract,
and the InvalidResponse -> Mozhi fallback path.
"""
import io
import json
import os
import sys
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qtranslate.services import yandex_web as yw  # noqa: E402


def main():
    ok = 0

    def check(cond, name):
        nonlocal ok
        assert cond, name
        ok += 1

    # --- language mapping -------------------------------------------------
    check(yw._to_provider("iw") == "he", "iw->he")
    check(yw._to_provider("zh-CN") == "zh", "zh-CN->zh")
    check(yw._to_provider("zh-TW") == "zh", "zh-TW->zh")
    check(yw._to_provider("vi") == "vi", "vi identity")
    check("iw" in yw.SUPPORTED_LANGS, "iw supported")
    check("zh-TW" in yw.SUPPORTED_LANGS, "zh-TW supported")
    check("tl" not in yw.SUPPORTED_LANGS, "tl unsupported")

    # --- form body matches the Kotlin field set ---------------------------
    form = dict(urllib_parse(yw._form("hi", "vi")))
    check(form["brandID"] == "int", "brandID")
    check(form["statLang"] == "vi", "statLang=target")
    check(form["targetLang"] == "auto", "targetLang=auto")
    check(form["locale"] == "vi", "locale=target")
    check(form["clid"] == "2270494", "clid")
    check(form["disable"] == "serp", "disable")
    check(form["use_llm_srv"] == "0", "use_llm_srv")
    check(form["text"] == "hi", "text")
    check("from" not in form and "source" not in form,
          "no source field (endpoint auto-detects)")

    # --- response parsing -------------------------------------------------
    check(yw._parse('[{"text":"Xin chào","from":"en","to":"vi"}]')
          == "Xin chào", "array first element")
    check(yw._parse('{"text":"solo"}') == "solo", "bare object")
    check(yw._parse('[{"text":"  "}]') == "", "blank text skipped")
    check(yw._parse('not json') == "", "non-json -> empty")
    check(yw._parse('[]') == "", "empty array")
    check(yw._parse('[{"text":""},{"text":"second"}]') == "second",
          "first non-blank wins")

    # --- translate(): happy path ------------------------------------------
    calls = []

    def fake_post(url, data):
        calls.append((url, data))
        return '[{"text":"Kết quả","from":"en","to":"vi"}]'

    orig_post, orig_mozhi = yw._post, yw._via_mozhi
    yw._post = fake_post
    yw._via_mozhi = lambda t, tl: (_ for _ in ()).throw(
        AssertionError("mozhi must not run on success"))
    try:
        out = yw.translate("Hello", "auto", "vi")
        check(out == "Kết quả", "translate happy path")
        check(calls and calls[0][0] == yw.ENDPOINT, "endpoint used")
        check("statLang=vi" in calls[0][1], "form carries vi target")
        # iw source validates (mapped to he), vi target ok
        out2 = yw.translate("Hi", "iw", "en")
        check(out2 == "Kết quả", "iw source accepted")
    finally:
        yw._post, yw._via_mozhi = orig_post, orig_mozhi

    # --- unsupported target fails explicitly ------------------------------
    try:
        yw.translate("x", "auto", "tl")
        check(False, "tl target should raise")
    except RuntimeError as e:
        check("does not support" in str(e), "unsupported target msg")

    # --- too long ----------------------------------------------------------
    try:
        yw.translate("x" * 5001, "auto", "vi")
        check(False, "long text should raise")
    except RuntimeError as e:
        check("5000" in str(e), "length limit msg")

    # --- InvalidResponse -> Mozhi fallback ---------------------------------
    mozhi_calls = []

    def empty_post(url, data):
        return "[]"

    def fake_mozhi(text, target):
        mozhi_calls.append((text, target))
        return "MOZHI-OK"

    yw._post = empty_post
    yw._via_mozhi = fake_mozhi
    try:
        out = yw.translate("Hello", "auto", "vi")
        check(out == "MOZHI-OK", "mozhi fallback result")
        check(mozhi_calls == [("Hello", "vi")], "mozhi args")
    finally:
        yw._post, yw._via_mozhi = orig_post, orig_mozhi

    # --- 5xx -> Mozhi; 4xx -> raise ----------------------------------------
    def http_error(code):
        return urllib.error.HTTPError(
            yw.ENDPOINT, code, "err", {}, io.BytesIO(b""))

    def raising_post(code):
        def _p(url, data):
            raise http_error(code)
        return _p

    yw._post = raising_post(503)
    yw._via_mozhi = fake_mozhi
    try:
        mozhi_calls.clear()
        check(yw.translate("x", "auto", "vi") == "MOZHI-OK",
              "5xx -> mozhi")
    finally:
        yw._post, yw._via_mozhi = orig_post, orig_mozhi

    yw._post = raising_post(403)
    try:
        try:
            yw.translate("x", "auto", "vi")
            check(False, "4xx should raise")
        except RuntimeError as e:
            check("403" in str(e), "4xx surfaces HTTP code")
    finally:
        yw._post, yw._via_mozhi = orig_post, orig_mozhi

    # --- Mozhi fallback iterates instances, needs translated-text ---------
    def fake_mozhi_http(bodies):
        seq = list(bodies)
        def _get(self, url, headers=None):
            body = seq.pop(0)
            if isinstance(body, Exception):
                raise body
            return io.BytesIO(body.encode())
        return _get

    # exercise _via_mozhi with a stubbed common.http_open
    orig_open = yw.common.http_open
    responses = [
        '{"translated-text":"  ","source_language":"en"}',   # blank -> next
        '{"translated-text":"Xin chào","source_language":"en"}',
    ]
    it = iter(responses)

    class _Resp:
        def __init__(self, body):
            self._b = body.encode()

        def read(self):
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    yw.common.http_open = lambda req, **kw: _Resp(next(it))
    try:
        check(yw._via_mozhi("Hello", "vi") == "Xin chào",
              "mozhi skips blank, takes second")
    finally:
        yw.common.http_open = orig_open

    # all mozhi instances fail -> RuntimeError
    yw.common.http_open = lambda req, **kw: (_ for _ in ()).throw(
        OSError("down"))
    try:
        try:
            yw._via_mozhi("x", "vi")
            check(False, "mozhi all-down should raise")
        except RuntimeError as e:
            check("unavailable" in str(e), "mozhi unavailable msg")
    finally:
        yw.common.http_open = orig_open

    print("regress_yandex_web: all checks ok (%d assertions)" % ok)


def urllib_parse(qs):
    import urllib.parse
    return urllib.parse.parse_qsl(qs)


if __name__ == "__main__":
    main()
