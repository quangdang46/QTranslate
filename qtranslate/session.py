"""Scrape ephemeral session tokens the native QTranslate.exe obtains by
loading each provider's web page through its embedded Chakra/JS engine
before calling serviceTranslateRequest (see docs/NATIVE_ARCH.md, UtilsDispatch).
This module reproduces that bootstrap step with plain urllib + regex so the
Python ports of Microsoft/Promt/Baidu/Youdao can run standalone.
"""
import datetime
import email.utils
import random
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# .tmp KtorHttpClient retry contract: 429 retries any method; 5xx only
# for RFC 9110-idempotent methods (a retried POST could bill twice).
_IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}
_MAX_RETRY_AFTER_SECONDS = 600


def net_options() -> dict:
    """Internet + Proxy sections of Options.json (Timeout ms, proxy).

    Native FUN_0045BCED/FUN_0045BF7D apply Internet.Timeout to every
    curl call; Proxy* configures the curl proxy. Falls back to
    Timeout=10000 / no proxy when Options.json is absent.
    """
    try:
        from qtranslate import config as _C
        cfg = _C.load()
    except Exception:
        cfg = {}
        inet, px = {}, {}
    else:
        inet = cfg.get("Internet", {})
        px = cfg.get("Proxy", {})
    try:
        timeout = float(inet.get("Timeout", 10000)) / 1000.0
    except Exception:
        timeout = 10.0
    # .tmp NetworkConfig: shared retry policy for every provider.
    # RetryEnabled/MaxRetries/RetryDelayMs/HostTimeouts are the port's
    # keys for upstream's retryEnabled/maxRetries/
    # retryInitialDelaySeconds/hostTimeoutSeconds.
    try:
        retry_enabled = bool(inet.get("RetryEnabled", True))
    except Exception:
        retry_enabled = True
    try:
        max_retries = max(0, min(10, int(inet.get("MaxRetries", 2))))
    except Exception:
        max_retries = 2
    try:
        retry_delay = max(0.1, float(inet.get("RetryDelayMs", 1000))
                          / 1000.0)
    except Exception:
        retry_delay = 1.0
    try:
        host_timeouts = dict(inet.get("HostTimeouts") or {})
    except Exception:
        host_timeouts = {}
    proxy = None
    try:
        # Native ProxyType (W11/1135): 0=system, 1=none, 2=manual,
        # 3=auto-detect. Only manual (2) uses Host/Port; Scheme picks
        # http vs socks5 (native distinguishes in the manual dialog).
        ptype = int(px.get("ProxyType", 0))
        host = (px.get("Host") or "").strip()
        port = int(px.get("Port", 0))
        if ptype == 2 and host and port:
            scheme = "https" if int(px.get("Scheme", 0)) else "http"
            if "socks" in host.lower():
                scheme = "socks5"
            auth = ""
            if px.get("Username"):
                import urllib.parse as _up
                auth = _up.quote(px.get("Username", "")) + ":" + \
                    _up.quote(px.get("Password", "")) + "@"
            proxy = f"{scheme}://{auth}{host}:{port}"
    except Exception:
        proxy = None
    return {"timeout": timeout, "proxy": proxy,
            "retry_enabled": retry_enabled, "max_retries": max_retries,
            "retry_delay": retry_delay, "host_timeouts": host_timeouts}


def _host_timeout(opts: dict, url: str):
    """.tmp hostTimeoutSeconds: per-host request timeout override, in
    seconds. Returns None when the URL's host names no override."""
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        secs = (opts.get("host_timeouts") or {}).get(host)
        if secs is not None:
            return max(1.0, float(secs))
    except Exception:
        pass
    return None


def _retry_after_seconds(err: urllib.error.HTTPError):
    """Retry-After in whole seconds, capped at .tmp's 600. Accepts the
    delta-seconds and HTTP-date forms; anything else is no hint."""
    try:
        raw = (err.headers or {}).get("Retry-After")
    except Exception:
        raw = None
    if not raw:
        return None
    raw = raw.strip()
    try:
        secs = int(raw)
        if secs >= 0:
            return min(secs, _MAX_RETRY_AFTER_SECONDS)
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(raw)
        secs = (when - datetime.datetime.now(
            when.tzinfo)).total_seconds()
        if secs > 0:
            return min(int(secs), _MAX_RETRY_AFTER_SECONDS)
    except Exception:
        pass
    return None


def _retryable(err: urllib.error.HTTPError, method: str) -> bool:
    """.tmp retryIf: 429 retries ANY method (the server refused without
    acting); 5xx retries only idempotent methods -- replaying a POST
    could bill or duplicate the work."""
    code = getattr(err, "code", 0) or 0
    return code == 429 or (500 <= code <= 599
                           and method.upper() in _IDEMPOTENT_METHODS)


def _open_once(req, opener, proxy, timeout):
    if opener is not None:
        return opener.open(req, timeout=timeout)
    if proxy:
        import urllib.parse as _up
        scheme = _up.urlparse(proxy).scheme
        ph = {scheme: proxy}
        return urllib.request.build_opener(
            urllib.request.ProxyHandler(ph)).open(
                req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _net_open(req, opener=None, data=None):
    """Open with Options.json Timeout + Proxy (native curl behavior),
    plus .tmp's shared retry policy: exponential backoff honouring
    Retry-After, 429 any-method / 5xx idempotent-only."""
    opts = net_options()
    if data is not None:
        req.data = data
    timeout = _host_timeout(opts, req.full_url) or opts["timeout"]
    attempts = 1 + (opts["max_retries"] if opts["retry_enabled"] else 0)
    proxy = opts["proxy"]
    method = (req.get_method() or "GET").upper()
    for i in range(attempts):
        try:
            return _open_once(req, opener, proxy, timeout)
        except urllib.error.HTTPError as e:
            if i == attempts - 1 or not _retryable(e, method):
                raise
            wait = _retry_after_seconds(e)
            if wait is None:
                # exponentialDelay: base * 2^attempt + jitter, like
                # upstream's "twice the last, plus jitter".
                wait = (opts["retry_delay"] * (2 ** i)
                        + random.uniform(0, opts["retry_delay"] * 0.25))
            time.sleep(min(wait, _MAX_RETRY_AFTER_SECONDS))
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                socket.timeout, OSError) as e:
            # Network-level failures (DNS, refused, reset, read timeout)
            # are safe to retry for every method -- nothing reached the
            # server to duplicate. HTTPError is a URLError subclass and
            # is handled above, so this only sees transport failures.
            if i == attempts - 1:
                raise
            wait = (opts["retry_delay"] * (2 ** i)
                    + random.uniform(0, opts["retry_delay"] * 0.25))
            time.sleep(min(wait, _MAX_RETRY_AFTER_SECONDS))


def _jar_opener():
    """Shared cookie-jar opener — mirrors native libcurl cookie engine.

    Decompiled finding (FUN_00465A92): cookie *values* are set by the service
    JS itself via addOption() from prior page loads inside the same engine,
    i.e. cookies accumulate in one jar across scrape + translate calls.
    Our earlier failure used a fresh jar per call; this shares one.
    """
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _get(url: str, opener=None) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with _net_open(req, opener) as r:
        data = r.read()
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace")


def bing_session() -> dict:
    """Scrape IG + token + key + MUID cookie for Microsoft Translator.

    ttranslatev3 returns HTTP 401 without the MUID/_EDGE_* cookies Bing sets
    on the translator page response (verified live 2026-10-07) — anonymous
    (no-cookie) calls are rejected, unlike the gtx-era behaviour.

    The markers are byte-verified from the recovered image
    (`tests/regress_session_markers.py`). Native's `.rdata` holds, adjacent
    to each other::

        var params_RichTranslateHelper = [IG:"
        text=car&fromLang=en&to=ru&token=%s&key=%s&isAuthv2=true
        https://www.bing.com/ttranslatev3

    so the helper array's **first member is the IG marker itself**, not a
    number. This port used to look for
    ``params_AbusePreventionHelper = [(\\d+),"…",(\\d+)`` — a name the image
    does not contain and a first member it never has, which could only ever
    end in "page layout changed?".
    """
    opener = _jar_opener()
    req = urllib.request.Request("https://www.bing.com/translator", headers=_UA)
    with _net_open(req, opener) as r:
        html = r.read().decode("utf-8", errors="replace")
        set_cookie = r.headers.get_all("Set-Cookie") or []
    cookie = "; ".join(c.split(";")[0] for c in set_cookie)
    ig = re.search(r'IG:"(\w+)"', html)
    # Layout history: the helpers used to sit ADJACENT to the IG marker
    # (`IG:"<ig>","<token>",<key>`), which is what one combined regex
    # could match. The 2026-10 page moved the credentials into
    # params_AbusePreventionHelper alone, as [<expiry-ts>,"<token>",<TTL>].
    # The POST's `key=` is the EXPIRY TIMESTAMP (the first member), not
    # the trailing TTL -- key=3600000 answers statusCode:205 live
    # (2026-10-24), key=<timestamp> translates. IG and the abuse array
    # are scraped separately now.
    abuse = re.search(
        r'params_AbusePreventionHelper\s*=\s*\[(\d+),"([^"]+)",\d+\]', html)
    # IID format changed: page now has translator.5024/5023/5026
    # (was translator.5023.3). data-iid values feed ttranslatev3 (.3)
    # and tlookupv3 (.2) — keep both, defaulting live.
    _iids = re.findall(r'data-iid="(translator\.[\w.]+)"', html)
    iid = _iids[0] if _iids else "translator.5023"
    # tspellcheckv3 wants the page-embedded MUID as its ONLY cookie
    # (.tmp BingAuthManager.parseAuthFromHtml scrapes `muid":"..."`;
    # verified live 2026-11: the full Set-Cookie jar answers
    # {"correctedText":""}, MUID alone returns corrections).
    _muid = re.search(r'muid":\s*"(.*?)"', html)
    if not ig or not abuse:
        raise RuntimeError("Could not scrape Bing session (page layout changed?)")
    return {
        "IG": ig.group(1),
        # the abuse array is [<expiry>,"<token>",<TTL>]: the POST wants
        # token=group 2, key=the expiry timestamp (group 1).
        "token": abuse.group(2),
        "key": abuse.group(1),
        "cookie": cookie,
        "iid": iid,
        "iids": _iids,
        "muid": _muid.group(1) if _muid else "",
        "opener": opener,  # reuse: same cookie jar for the translate call
    }


def bing_translate(text: str, sl: str = "en", tl: str = "vi") -> str:
    """End-to-end Microsoft translate sharing one cookie jar (native-like).

    Scrape + translate through the SAME opener so engine-set cookies
    (MUID/_EDGE_*) persist — this is what plain per-call urllib missed.
    """
    import json
    import urllib.parse
    s = bing_session()
    path = ("/ttranslatev3?isVertical=1&IG={}&IID={}"
            .format(s["IG"], s["iid"]))
    body = ("text={}&fromLang={}&to={}&token={}&key={}"
            "&tryFetchingGenderDebiasedTranslations=true").format(
        urllib.parse.quote(text[:1000], safe=""), sl, tl,
        s["token"], s["key"])
    req = urllib.request.Request(
        "https://www.bing.com" + path, data=body.encode(),
        headers={**_UA,
                 "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                 "Origin": "https://www.bing.com",
                 "Referer": "https://www.bing.com/translator"})
    with _net_open(req, s["opener"]) as r:
        obj = json.loads(r.read().decode("utf-8"))
    try:
        return obj[0]["translations"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return ""


def baidu_session() -> dict:
    """Scrape the Baidu translate page's ``token``/``gtk`` pair + BAIDUID.

    The image's `.rdata` carries, next to each other
    (`tests/regress_session_markers.py` reads them out)::

        http://fanyi.baidu.com
        BAIDUID
        Accept-Encoding:gzip,deflate\nCookie:
        'token: ''gtk = '

    i.e. the page is fetched, the ``BAIDUID`` cookie is kept, and the page
    source is scanned for the two JS assignments whose quotes are already
    open -- so the value runs to the next quote. This port read
    ``Options.BaiduGtk``/``BaiduToken`` but had **nothing that filled them**,
    so every Baidu request signed with the default ``0.0`` seed, which is
    the ``dead:needs-session-token`` state the checklist records.
    """
    opener = _jar_opener()
    req = urllib.request.Request("http://fanyi.baidu.com", headers=_UA)
    with _net_open(req, opener) as r:
        html = r.read().decode("utf-8", errors="replace")
        set_cookie = r.headers.get_all("Set-Cookie") or []
    cookie = "; ".join(c.split(";")[0] for c in set_cookie)
    token = re.search(r"token:\s*'([^']+)'", html)
    gtk = re.search(r"gtk\s*=\s*'([^']+)'", html)
    return {
        "token": token.group(1) if token else "",
        "gtk": gtk.group(1) if gtk else "",
        "cookie": cookie,
        "opener": opener,
    }


def promt_session() -> dict:
    """Scrape XSRF-TOKEN cookie + PromtPaft for online-translator.com.

    The hidden inputs are byte-verified from the image
    (`tests/regress_session_markers.py`), which spells both by **id**::

        id="_paft" type="hidden" value="
        id="_xsrf" type="hidden" value="
        pageIx=0&v=1
        https://www.online-translator.com/api/pageLoad

    This port used to look for ``name="aft" value="`` — the wrong attribute
    AND the wrong value — so the paft it returned was always empty on a page
    that carries one.
    """
    req = urllib.request.Request(
        "https://www.online-translator.com", headers=_UA)
    with _net_open(req) as r:
        html = r.read().decode("utf-8", errors="replace")
        set_cookie = r.headers.get_all("Set-Cookie") or []
    xsrf = next((c.split(";")[0].split("=", 1)[1]
                 for c in set_cookie if c.startswith("XSRF-TOKEN=")), "")
    cookie = "; ".join(c.split(";")[0] for c in set_cookie)
    paft = re.search(r'id="_paft" type="hidden" value="([^"]+)"', html)
    xsrf_page = re.search(r'id="_xsrf" type="hidden" value="([^"]+)"', html)
    return {
        "xsrf": xsrf,
        "cookie": cookie,
        # the cookie is what the request actually sends; the hidden input is
        # the page's own copy, kept for parity with native's scrape.
        "xsrf_page": xsrf_page.group(1) if xsrf_page else "",
        "paft": paft.group(1) if paft else "",
    }


if __name__ == "__main__":
    import json
    s = bing_session()
    print("bing:", json.dumps({k: v for k, v in s.items() if k != "opener"}))
    try:
        print("promt:", json.dumps(promt_session()))
    except Exception as e:
        print("promt: ERROR", e)
