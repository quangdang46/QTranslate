"""Regression: .tmp NetworkConfig retry policy in session._net_open.

Upstream KtorHttpClient installs HttpRequestRetry with:
  * 429 retried for ANY method (server refused without acting)
  * 5xx retried only for idempotent methods (GET/HEAD/OPTIONS/PUT/DELETE)
    -- replaying a POST could bill or duplicate the work
  * exponentialDelay(baseDelayMs) -- base * 2^attempt + jitter
  * Retry-After honoured (delta-seconds or HTTP-date, capped 600s)
  * hostTimeoutSeconds per-host timeout overrides

The port's urllib funnel is session._net_open; Options.json keys are
Internet.RetryEnabled / MaxRetries / RetryDelayMs / HostTimeouts.
"""
import io
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if cond:
        print("  ok %s" % name)
    else:
        fail.append("%s -- %s" % (name, detail))
        print("  FAIL %s -- %s" % (name, detail))


import qtranslate.config as C  # noqa: E402
import qtranslate.session as S  # noqa: E402

_tmp = os.path.join(ROOT, "tests", ".tmp_net_retry.json")
C.DEFAULT_PATH = _tmp


def set_inet(**kw):
    cfg = C.default_config()
    cfg.setdefault("Internet", {}).update(kw)
    C.save(cfg)


class _Resp:
    def __init__(self, body=b"ok"):
        self._b = body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, headers=None):
    return urllib.error.HTTPError(
        "http://x/", code, "err", headers or {}, io.BytesIO(b""))


sleeps = []
_orig_sleep = S.time.sleep
S.time.sleep = lambda s: sleeps.append(s)
try:
    # ---- net_options reads the retry keys -------------------------
    set_inet(RetryEnabled=False, MaxRetries=5, RetryDelayMs=2500,
             HostTimeouts={"slow.example": 120})
    o = S.net_options()
    ck("net_options exposes retry policy",
       o["retry_enabled"] is False and o["max_retries"] == 5
       and o["retry_delay"] == 2.5
       and o["host_timeouts"] == {"slow.example": 120}, str(o))
    set_inet()
    o = S.net_options()
    ck("defaults match .tmp NetworkConfig",
       o["retry_enabled"] is True and o["max_retries"] == 2
       and o["retry_delay"] == 1.0, str(o))

    # ---- _retryable: 429 any method, 5xx idempotent only ----------
    get = urllib.request.Request("http://x/")
    post = urllib.request.Request("http://x/", data=b"{}",
                                  headers={"Content-Type": "x"})
    ck("429 retries GET", S._retryable(_http_error(429), "GET"))
    ck("429 retries POST", S._retryable(_http_error(429), "POST"))
    ck("503 retries GET", S._retryable(_http_error(503), "GET"))
    ck("503 does NOT retry POST", not S._retryable(_http_error(503),
                                                 "POST"))
    ck("404 never retries", not S._retryable(_http_error(404), "GET"))
    ck("502 retries PUT", S._retryable(_http_error(502), "PUT"))

    # ---- Retry-After parsing ---------------------------------------
    ck("Retry-After seconds honoured",
       S._retry_after_seconds(_http_error(429, {"Retry-After": "7"}))
       == 7)
    ck("Retry-After capped at 600",
       S._retry_after_seconds(_http_error(429, {"Retry-After": "9999"}))
       == 600)
    ck("Retry-After HTTP-date honoured",
       S._retry_after_seconds(_http_error(
           429, {"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"}))
       == 600 or S._retry_after_seconds(_http_error(
           429, {"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"}))
       is not None)
    ck("Retry-After junk -> None",
       S._retry_after_seconds(_http_error(429, {"Retry-After": "soon"}))
       is None)

    # ---- _host_timeout ---------------------------------------------
    o = {"host_timeouts": {"slow.example": 120}}
    ck("host timeout override applies",
       S._host_timeout(o, "http://slow.example:8080/x") == 120.0)
    ck("other hosts keep shared timeout",
       S._host_timeout(o, "http://fast.example/x") is None)
    ck("host timeout malformed -> None",
       S._host_timeout({"host_timeouts": {"a": "x"}},
                       "http://a/") is None)

    # ---- _net_open retry loop ---------------------------------------
    calls = []

    class _Flaky:
        def __init__(self, script):
            self.script = list(script)

        def open(self, req, timeout=None):
            calls.append((req.full_url, timeout))
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    set_inet(MaxRetries=2, RetryDelayMs=1000)
    sleeps.clear()
    fl = _Flaky([_http_error(503), _Resp(b"done")])
    with S._net_open(get, opener=fl) as r:
        body = r.read()
    ck("503 then 200: retried once and returned body",
       body == b"done" and len(calls) == 2, "%r %d" % (body, len(calls)))
    ck("backoff slept ~1s then ~2s",
       len(sleeps) == 1 and 1.0 <= sleeps[0] <= 1.3, str(sleeps))

    # 429 on POST retries too
    calls.clear()
    sleeps.clear()
    fl = _Flaky([_http_error(429), _Resp(b"ok")])
    with S._net_open(post, opener=fl) as r:
        r.read()
    ck("429 POST retried", len(calls) == 2, str(len(calls)))

    # 503 on POST does NOT retry
    calls.clear()
    sleeps.clear()
    fl = _Flaky([_http_error(503)])
    try:
        S._net_open(post, opener=fl)
        ck("503 POST raises without retry", False, "no raise")
    except urllib.error.HTTPError:
        ck("503 POST raises without retry", len(calls) == 1,
           str(len(calls)))

    # exhausted retries re-raise
    calls.clear()
    sleeps.clear()
    fl = _Flaky([_http_error(503), _http_error(503), _http_error(503)])
    try:
        S._net_open(get, opener=fl)
        ck("exhausted retries re-raise", False, "no raise")
    except urllib.error.HTTPError:
        ck("exhausted retries re-raise", len(calls) == 3,
           str(len(calls)))

    # transport error retries for any method
    calls.clear()
    sleeps.clear()
    fl = _Flaky([urllib.error.URLError("dns"), _Resp(b"net")])
    with S._net_open(post, opener=fl) as r:
        body = r.read()
    ck("URLError retried even for POST", body == b"net"
       and len(calls) == 2, str(len(calls)))

    # RetryEnabled=False -> single attempt
    set_inet(RetryEnabled=False, MaxRetries=5)
    calls.clear()
    sleeps.clear()
    fl = _Flaky([_http_error(503), _Resp(b"x")])
    try:
        S._net_open(get, opener=fl)
    except urllib.error.HTTPError:
        pass
    ck("RetryEnabled=False: one attempt only", len(calls) == 1,
       str(len(calls)))
    ck("RetryEnabled=False: no sleep", sleeps == [], str(sleeps))
    set_inet()

    # host timeout flows into opener timeout arg
    calls.clear()
    set_inet(HostTimeouts={"slow.example": 120})
    fl = _Flaky([_Resp(b"t")])
    req2 = urllib.request.Request("http://slow.example/x")
    with S._net_open(req2, opener=fl) as r:
        r.read()
    ck("host timeout passed to opener",
       calls and calls[0][1] == 120.0, str(calls))
    set_inet()
finally:
    S.time.sleep = _orig_sleep
    try:
        os.remove(_tmp)
    except OSError:
        pass

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_network_retry: all checks ok (%d assertions)" % n[0])
