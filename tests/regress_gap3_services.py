"""Regression: GAP_AUDIT_3 rows 1, 2, 4 -- the three REAL-GAPs.

1. MyMemory segmentation (.tmp Utf8SegmenterTest.kt:9-24): splits at
   \\n\\n paragraph boundaries EVEN under the 500-byte cap, lossless
   join, 500-byte UTF-8 cap. Port was qtranslate/services/mymemory.py
   ``_segments`` (byte-size only).

2. Bing/Microsoft auth recovery (.tmp BingAuthRecoveryTest.kt:48-201):
   HTTP 401/403 or a body ``statusCode`` of 401/403 -> drop the rejected
   session, refresh once, retry once, NEVER loop; non-auth rejections
   are not retried; surfaced errors never carry token/key/MUID/user
   text. Port was microsoft.py ``_service_request`` (statusCode==205
   only) and session.bing_translate (silent "").

3. Retry-After error hint (.tmp KtorHttpClientRetryTest.kt:175-258): a
   retried-then-failed 429 reports Retry-After seconds ON the error
   (past-date/absent/negative -> unset). Port was session.py
   ``_retry_after_seconds`` feeding only the sleep; the hint now rides
   ``HTTPError.retry_after_seconds`` -> ``reliability.Failure.retry_after``.

Headless: every HTTP call is stubbed through session._net_open /
opener doubles; config DEFAULT_PATH points at a temp file.
"""
import io
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import qtranslate.config as C  # noqa: E402
import qtranslate.reliability as R  # noqa: E402
import qtranslate.session as S  # noqa: E402
from qtranslate.services import microsoft as MS  # noqa: E402
from qtranslate.services import mymemory as MM  # noqa: E402

C.DEFAULT_PATH = os.path.join(ROOT, "tests", ".tmp_gap3_services.json")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if cond:
        print("  ok %s" % name)
    else:
        fail.append("%s -- %s" % (name, detail))
        print("  FAIL %s -- %s" % (name, detail))


class _Headers(dict):
    def get_all(self, key, default=None):
        value = self.get(key)
        return [value] if value is not None else list(default or [])


class _Resp:
    def __init__(self, body=b"ok", headers=None):
        self._b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.headers = headers if headers is not None else _Headers()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, headers=None, url="http://x/"):
    return urllib.error.HTTPError(url, code, "err", headers or {},
                                  io.BytesIO(b""))


# ============================================================ 1. MyMemory
# Utf8SegmenterTest: paragraphs split even when they fit one request.
segs = MM._segments("First paragraph.\n\nSecond paragraph.")
ck("paragraphs split even under the byte cap",
   segs == ["First paragraph.\n\n", "Second paragraph."], repr(segs))

text = "Arabic: " + "مرحبا " * 120 + "\n\n" + "English text"
segs = MM._segments(text)
ck("long text still splits and joins losslessly",
   "".join(segs) == text and len(segs) > 1, "%d segs" % len(segs))
ck("every segment within the 500-byte UTF-8 cap",
   all(len(s.encode("utf-8")) <= MM.MAX_QUERY_BYTES for s in segs),
   [len(s.encode("utf-8")) for s in segs])

ck("plain short text stays one segment",
   MM._segments("hello world") == ["hello world"])
ck("empty text -> one empty segment", MM._segments("") == [""])
ck("\\r\\n\\r\\n counts as a paragraph break for the split path",
   MM._segments("a\r\n\r\nb") == ["a\r\n\r\nb"])
# ...but the flush trigger is the literal "\n\n" ending, exactly like
# Kotlin's `current.endsWith("\n\n")`: "\r\n\r\n" never ends with it.
ck("a paragraph break mid-overflow still flushes at \\n\\n",
   MM._segments("x" * 490 + "\n\n" + "y" * 100)
   == ["x" * 490 + "\n\n", "y" * 100])

# translate() must issue one request PER segment.
calls = []
_orig_seg_translate = MM._translate_segment
_orig_pace = MM._pace
MM._translate_segment = lambda t, a, b: calls.append(t) or "T"
MM._pace = lambda: None
try:
    MM.translate("First.\n\nSecond.", sl="en", tl="fr")
finally:
    MM._translate_segment = _orig_seg_translate
    MM._pace = _orig_pace
ck("translate() sends one request per paragraph segment",
   calls == ["First.\n\n", "Second."], repr(calls))


# ===================================================== 2. Bing auth recovery
# Stub the whole HTTP funnel: bing.com/translator -> session page HTML,
# everything else -> the scripted translate responses.
def _page():
    """A bing.com/translator page whose scraped credentials are unique
    per scrape, so a test can prove the RETRIED post carried the fresh
    token and not the rejected one."""
    k = len(scrapes)
    return ('<html>data-iid="translator.5023.3" IG:"IG%d" '
            'params_AbusePreventionHelper = [170000000%d,"TOK%d",600] '
            'muid":"MUID%d"</html>' % (k, k, k, k))


post_script = []
scrapes = []
TEXT = "Hello, how are you?"
_orig_net_open = S._net_open
_orig_session = S.bing_session


def _fake_net_open(req, opener=None, data=None, timeout=None):
    url = req.full_url
    if url.rstrip("/").endswith("https://www.bing.com/translator"):
        scrapes.append(url)
        return _Resp(_page())
    if opener is not None and getattr(opener, "_is_test_opener", False):
        return opener.open(req, timeout=timeout)
    item = post_script.pop(0)
    if isinstance(item, BaseException):
        raise item
    return item


S._net_open = _fake_net_open
try:
    SUCCESS = _Resp('[{"translations":[{"text":"Hola"}]}]')

    # 2a. body statusCode "401" (STRING, as the endpoint sends) ->
    # refresh once, retry once, success.
    scrapes.clear()
    post_script[:] = [_Resp('{"statusCode":"401","errorMessage":""}'),
                      SUCCESS]
    out = S.bing_translate(TEXT, "en", "es")
    ck("body 401 -> refresh + retry -> translated",
       out == "Hola", repr(out))
    ck("body 401 -> exactly two session scrapes (one refresh)",
       len(scrapes) == 2, str(len(scrapes)))
    ck("body 401 -> exactly two translate posts",
       len(post_script) == 0, "script left: %r" % (post_script,))

    # 2b. HTTP 403 -> same recovery.
    scrapes.clear()
    post_script[:] = [_http_error(403, url="https://www.bing.com/ttranslatev3"),
                      _Resp('[{"translations":[{"text":"Bonjour"}]}]')]
    out = S.bing_translate(TEXT, "en", "fr")
    ck("HTTP 403 -> refresh + retry -> translated",
       out == "Bonjour", repr(out))
    ck("HTTP 403 -> two scrapes", len(scrapes) == 2, str(len(scrapes)))

    # 2c. second rejection -> surfaces, never loops.
    scrapes.clear()
    post_script[:] = [_Resp('{"statusCode":"401"}'),
                      _Resp('{"statusCode":"401"}')]
    err = None
    try:
        S.bing_translate(TEXT, "en", "es")
    except urllib.error.HTTPError as e:
        err = e
    ck("second body 401 raises HTTPError-shaped auth failure",
       err is not None and err.code == 401, repr(err))
    ck("second 401 -> exactly two scrapes, no loop",
       len(scrapes) == 2, str(len(scrapes)))
    ck("auth error classifies AUTH_EXPIRED",
       err is not None
       and R.classify(err) is R.ErrorKind.AUTH_EXPIRED)
    msg = str(err) if err is not None else ""
    ck("auth error leaks no token/MUID/user text",
       "TOK" not in msg and "MUID" not in msg and TEXT not in msg, msg)

    # 2d. non-auth rejection is NOT retried.
    scrapes.clear()
    post_script[:] = [_Resp('{"statusCode":"400","errorMessage":"bad"}')]
    out = S.bing_translate(TEXT, "en", "es")
    ck("body 400 -> empty, no retry, no refresh",
       out == "" and len(scrapes) == 1
       and len(post_script) == 0, "%r scrapes=%d" % (out, len(scrapes)))

    # 2e. microsoft._service_request: same contract on the Service.js
    # port. opener doubles feed the POST; bing_session scrape is stubbed
    # through the same _net_open fake (translator URL -> PAGE).
    translate_posts = []

    class _Opener:
        _is_test_opener = True

        def open(self, req, timeout=None):
            translate_posts.append(req)
            item = post_script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

    opener = _Opener()
    scrapes.clear()
    post_script[:] = [_Resp('{"statusCode":"403","errorMessage":""}'),
                      _Resp('[{"translations":[{"text":"Hola"}]}]')]
    # stale seeded credentials: the refresh must replace them
    obj = MS._service_request(TEXT, "en", "es", ig="IGSTALE",
                              token="STALETOK", key="0", opener=opener)
    ck("_service_request body 403 -> refresh + retry -> list",
       isinstance(obj, list) and obj[0]["translations"][0]["text"]
       == "Hola", repr(obj))
    ck("_service_request 403 -> two translate posts",
       len(translate_posts) == 2, str(len(translate_posts)))
    ck("_service_request 403 -> session refreshed once",
       len(scrapes) == 1, str(len(scrapes)))

    # retried request carries the FRESH token (TOK1 from scrape #1),
    # not the rejected STALETOK
    ck("first post carried the stale token",
       b"STALETOK" in translate_posts[0].data,
       translate_posts[0].data[:200])
    ck("retried post carried the refreshed token, not the rejected one",
       b"TOK1" in translate_posts[1].data
       and b"STALETOK" not in translate_posts[1].data,
       translate_posts[1].data[:200])

    # second auth rejection -> raise, no loop
    scrapes.clear()
    translate_posts.clear()
    post_script[:] = [_Resp('{"statusCode":"401"}'),
                      _Resp('{"statusCode":"401"}')]
    err = None
    try:
        MS._service_request(TEXT, "en", "es", opener=opener)
    except urllib.error.HTTPError as e:
        err = e
    ck("_service_request second 401 raises AUTH_EXPIRED",
       err is not None and err.code == 401
       and R.classify(err) is R.ErrorKind.AUTH_EXPIRED, repr(err))
    ck("_service_request second 401 -> exactly two posts",
       len(translate_posts) == 2, str(len(translate_posts)))

    # non-auth rejection returns the error object untouched (the
    # get_response_obj guard downstream reports the empty translation)
    scrapes.clear()
    translate_posts.clear()
    post_script[:] = [_Resp('{"statusCode":"400","errorMessage":"bad"}')]
    obj = MS._service_request(TEXT, "en", "es", opener=opener)
    ck("_service_request body 400 -> returned, not retried",
       isinstance(obj, dict) and MS._status_code(obj) == 400
       and len(translate_posts) == 1 and len(scrapes) == 0,
       repr(obj))
finally:
    S._net_open = _orig_net_open
    S.bing_session = _orig_session
    try:
        os.remove(C.DEFAULT_PATH)
    except OSError:
        pass


# ============================================= 3. Retry-After error hint
# 3a. session._net_open stamps the hint on the raised 429.
sleeps = []
_orig_sleep = S.time.sleep
S.time.sleep = lambda s: sleeps.append(s)
try:
    C.save(C.default_config())  # ensure a readable config exists

    class _Flaky:
        def __init__(self, script):
            self.script = list(script)

        def open(self, req, timeout=None):
            item = self.script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

    get = urllib.request.Request("http://x/")

    # retried-then-failed 429 carries the hint (retries enabled -> 3 tries)
    sleeps.clear()
    fl = _Flaky([_http_error(429, {"Retry-After": "7"}),
                 _http_error(429, {"Retry-After": "7"}),
                 _http_error(429, {"Retry-After": "7"})])
    err = None
    try:
        S._net_open(get, opener=fl)
    except urllib.error.HTTPError as e:
        err = e
    ck("retried-then-failed 429 -> error carries retry_after_seconds=7",
       err is not None and getattr(err, "retry_after_seconds", None) == 7,
       repr(getattr(err, "retry_after_seconds", "missing")))
    ck("hint also drove the retry sleeps",
       sleeps and all(s == 7 for s in sleeps), repr(sleeps))

    # absent header -> unset (3 scripted failures = max_retries+1 tries)
    fl = _Flaky([_http_error(429)] * 3)
    err = None
    try:
        S._net_open(get, opener=fl)
    except urllib.error.HTTPError as e:
        err = e
    ck("429 without Retry-After -> hint unset",
       err is not None and getattr(err, "retry_after_seconds", None) is None)

    # past HTTP-date -> unset
    fl = _Flaky([_http_error(
        429, {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})] * 3)
    err = None
    try:
        S._net_open(get, opener=fl)
    except urllib.error.HTTPError as e:
        err = e
    ck("429 past-date Retry-After -> hint unset",
       err is not None and getattr(err, "retry_after_seconds", None) is None)

    # negative -> unset; absurd -> clamped to 600
    fl = _Flaky([_http_error(429, {"Retry-After": "-1"})] * 3)
    err = None
    try:
        S._net_open(get, opener=fl)
    except urllib.error.HTTPError as e:
        err = e
    ck("429 negative Retry-After -> hint unset",
       err is not None and getattr(err, "retry_after_seconds", None) is None)

    fl = _Flaky([_http_error(429, {"Retry-After": "9999"})] * 3)
    err = None
    try:
        S._net_open(get, opener=fl)
    except urllib.error.HTTPError as e:
        err = e
    ck("429 absurd Retry-After -> clamped to 600",
       err is not None and getattr(err, "retry_after_seconds", None) == 600)

    # 3b. reliability.run_provider surfaces the hint on Failure.
    def _raise_429():
        raise _http_error(429, {"Retry-After": "7"})

    slept = []
    out = R.run_provider(_raise_429, "google",
                         policy=R.RetryPolicy(base_delay=0.0, max_delay=0.0),
                         sleep=lambda d: slept.append(d))
    ck("run_provider Failure carries retry_after hint",
       isinstance(out, R.Failure) and out.retry_after == 7.0,
       repr(getattr(out, "retry_after", "missing")))
    ck("hint appears in the §7 log line",
       "retry_after=7s" in out.log_line(), out.log_line())

    def _raise_429_nh():
        raise _http_error(429)

    out = R.run_provider(_raise_429_nh, "google",
                         policy=R.RetryPolicy(base_delay=0.0, max_delay=0.0),
                         sleep=lambda d: None)
    ck("429 without header -> Failure.retry_after unset",
       isinstance(out, R.Failure) and out.retry_after is None)

    def _raise_429_past():
        raise _http_error(
            429, {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})

    out = R.run_provider(_raise_429_past, "google",
                         policy=R.RetryPolicy(base_delay=0.0, max_delay=0.0),
                         sleep=lambda d: None)
    ck("429 past-date -> Failure.retry_after unset",
       isinstance(out, R.Failure) and out.retry_after is None,
       repr(out.retry_after))

    def _raise_500():
        raise _http_error(500, {"Retry-After": "7"})

    out = R.run_provider(_raise_500, "google",
                         policy=R.RetryPolicy(base_delay=0.0, max_delay=0.0),
                         sleep=lambda d: None)
    ck("non-429 failure carries no retry_after hint",
       isinstance(out, R.Failure) and out.retry_after is None)
finally:
    S.time.sleep = _orig_sleep
    try:
        os.remove(C.DEFAULT_PATH)
    except OSError:
        pass


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_gap3_services: all checks ok (%d assertions)" % n[0])
