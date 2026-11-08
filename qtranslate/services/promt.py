"""1:1 port of Services/Promt/Service.js (SERVICE_ID=12).

Covers the whole file: serviceHeader/Host/Link, isNullOrEmpty, ghcs,
ghcd, translate request/response (with stripHtml dict/phrases branches
and from/to lang resolution), SupportedLanguages.

Live status 2026-10-07: pipeline verified (HTTP 200 + correct response
schema) but the server returns "service temporarily unavailable" for
all pairs — backend-side, not a port bug. Session bootstrap (EXTENSION,
fills the Options.Promt* slots the native engine sets from the page):
scrape id="_paft"/id="_xsrf" from static HTML, send xsrf as XSRF-TOKEN
header. Note: native sends v=1; the current web client needs v=2.

Live status 2026-11-08: the site's JS changed the request hash. The
page bundle now builds `h` over UTF-16 code units with a forward pass
followed by a backward pass (h1+h2 in trru.bundle.js), and the
literal is "#Gener\u0430l#" with a CYRILLIC a — the old forward-only
codepoint hash now gets HTTP 400. ghcs/ghcd below mirror the CURRENT
site JS, not the native Service.js (same documented-deviation seam as
the v=2/headers notes). Backend still answers "service temporarily
unavailable"; the request shape is accepted again (HTTP 200).
"""
import json
import re
import urllib.parse
import urllib.request
from qtranslate import common

from qtranslate.common import (
    NL2,
    Capability,
    ServiceHeader,
    code_from_language,
    encode_post_param,
    is_language,
    language_from_code,
    limit_source,
    parse_json_lenient,
    post_header,
    read_response_text,
    strip_html,
    Options,
)

SERVICE_ID = 12
SERVICE_NAME = "Promt"
HOST = "https://www.online-translator.com"

SUPPORTED_LANGS = [-1, "au", -1, "et", -1, "ar", -1, -1, -1, -1, -1, "zhcn",
                   "zhcn", -1, -1, -1, "et", "en", "et", "fi", -1, "fr", -1,
                   "de", "el", -1, "he", -1, -1, -1, -1, "it", -1, "ja", -1,
                   "ko", -1, -1, -1, -1, -1, -1, -1, -1, "pt", -1, "ru", -1,
                   -1, -1, "es", -1, -1, -1, "tr", "uk", -1, -1, -1, -1, -1,
                   -1, -1, -1, "kk", "uz", -1, -1, -1, -1, -1, -1, -1, -1,
                   -1, "tt"]


def service_header() -> ServiceHeader:
    return ServiceHeader(
        12, "Promt",
        "PROMT.One (Online-Translator.com) is a free translator powered "
        "by PROMT NMT. Translate texts into Azerbaijan, English, Arabic, "
        "Greek, Hebrew, Spanish, Italian, Kazakh, Chinese, Korean, German, "
        "Portuguese, Russian, Tatar, Turkish, Turkmen, Uzbek, Ukrainian, "
        "Finnish, French, Estonian, Japanese with state-of-the-art neural "
        "technologies." + NL2 + service_host() + NL2 +
        "© PROMT LLC, 2010-2022",
        Capability.TRANSLATE)


def service_host() -> str:
    return "https://www.online-translator.com"


def service_link() -> str:
    return service_host()


def is_null_or_empty(text) -> bool:
    """Port of isNullOrEmpty(a)."""
    return not text or len(text) == 0


def _i32(n) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n & 0x80000000 else n


def _u16(s: str):
    """UTF-16 code units, like JS string indexing/charCodeAt."""
    import array
    return array.array("H", s.encode("utf-16-le", "surrogatepass"))


def _gh_step(r: int, cu: int) -> int:
    """One JS `r=(r<<5)-r+charCodeAt(i)` step.

    `r<<5` is a signed-int32 op on the OLD r, while `-r` subtracts the
    untruncated double; all values stay exact integers in Python.
    """
    return _i32(r * 32) - r + cu


def _gh_h1(u, t: int, i: int, r) -> int:
    """Port of h1(n,t,i,r): forward charCodeAt pass."""
    for k in range(t, i):
        r = _gh_step(r, u[k])
    return r


def _gh_h2(u, t: int, i: int, r) -> int:
    """Port of h2(n,t,i,r): h1 then a backward pass over the same span."""
    r = _gh_h1(u, t, i, r)
    while i > t:
        i -= 1
        r = _gh_step(r, u[i])
    return r


def _ghcs_u(u, b: int = None, d: int = None, c=0) -> int:
    if b is None:
        e = len(u)
        if e > 100:
            return _gh_h2(u, e - 50, e, _gh_h2(u, 0, 50, e))
        return _gh_h2(u, 0, e, e)
    return _gh_h2(u, b, d, c)


def ghcs(text: str, b: int = None, d: int = None, c=0) -> int:
    """Port of the CURRENT site's ghcs (was: native Service.js hash).

    UTF-16 code units, forward+backward accumulation, >100-char
    recursive split — verified live 2026-11-08 (HTTP 200; the old
    codepoint/forward-only variant is rejected with HTTP 400).
    """
    if b is None and d is None:
        return _ghcs_u(_u16(text))
    # explicit-range form: callers pass indices on the original text,
    # so slice first, then hash the slice's units (forward+backward)
    u = _u16(text[b:d])
    return _gh_h2(u, 0, len(u), c)


def ghcd(text: str, sl, tl) -> int:
    """Port of ghcd(a,b,d) against the current site literal."""
    from qtranslate.common import format_q
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    # "Generаl" carries a Cyrillic а (U+0430) in the live bundle —
    # copying it verbatim is load-bearing.
    inner = format_q("TranslateButton#{0}-{1}#Generаl#{2}", sl_code,
                     tl_code, str(ghcs(text)))
    return ghcs(inner)


_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def session(sl: str = "en", tl: str = "ru", opener=None):
    """Session bootstrap (EXTENSION): scrape id=_paft + id=_xsrf.

    Fills the Options.PromtPaft/PromtCookie/PromtXsrf slots the native
    engine sets by loading the page. Both live in static HTML (no
    headless needed). Returns (paft, xsrf, opener-with-cookies).
    """
    _jar = None
    if opener is None:
        import http.cookiejar
        _jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(_jar))
    # Page slugs use full language names (e.g. /translation/english-russian).
    _NAMES = {"en": "english", "ru": "russian", "de": "german",
              "fr": "french", "es": "spanish", "it": "italian",
              "pt": "portuguese", "uk": "ukrainian", "ja": "japanese",
              "zhcn": "chinese", "ar": "arabic", "tr": "turkish",
              "ko": "korean", "el": "greek", "he": "hebrew",
              "fi": "finnish", "et": "estonian", "kk": "kazakh"}
    a, b = _NAMES.get(sl, sl), _NAMES.get(tl, tl)
    url = f"{HOST}/translation/{a}-{b}"
    req = urllib.request.Request(url, headers=_UA)
    with common.http_open(req, opener) as r:
        html = read_response_text(r)
    paft = re.search(r'id="_paft"[^>]*value="([^"]+)"', html).group(1)
    xsrf = re.search(r'id="_xsrf"[^>]*value="([^"]+)"', html).group(1)
    # Native (FUN_0045f372 via the Promt EXTENSION) runs /api/pageLoad
    # with pageIx=0&v=1 immediately after this scrape, on the same cookie
    # jar. Best effort: a failed pageLoad is not fatal (native returns 0
    # but still proceeds to translation), so ignore its result.
    # When the caller supplied their own opener the jar is not visible to
    # us -- the opener already carries the cookies, so pass an empty
    # explicit Cookie and let opener's own processor attach them.
    try:
        _cookie = ("; ".join("%s=%s" % (c.name, c.value) for c in _jar)
                   if _jar is not None else "")
        page_load(paft, xsrf, _cookie, opener)
    except Exception:
        pass
    return paft, xsrf, opener


def translate(text: str, sl, tl, paft: str = "",
              cookie: str = "", xsrf: str = "", opener=None,
              version: str = "2") -> tuple:
    """Port of translate request/response.

    sl/tl accept indices or codes. Returns (text, src_index, tl_index)
    with dictHtml/phrasesHtml appended (stripped) and from/to resolved,
    exactly like serviceTranslateResponse. version="2" matches the
    current web client (native sends v=1).
    """
    from qtranslate.common import format_q
    # current client: sText().trim().replace(/\u0301/g,"") before send+hash
    text = limit_source(text.strip().replace("\u0301", ""), 1000)
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    paft = paft or Options.get("PromtPaft", "")
    xsrf = xsrf or Options.get("PromtXsrf", "")
    cookie = cookie or Options.get("PromtCookie", "")
    h = ghcd(text, sl_code, tl_code)
    # NOTE: headers below are the exact set verified live 2026-10-07
    # (HTTP 200 + correct schema). The faithful post_header()+Cookie
    # combo from Service.js gets HTTP 400 from the current server —
    # documented, not hidden.
    body = format_q(
        "eventName=TranslateButton&text={0}&dirCode={1}-{2}"
        "&useAutoDetect=true&h={3}&aft={4}&pageIx=0&v={5}",
        urllib.parse.quote(text), sl_code, tl_code, h, paft, version)
    headers = dict(_UA,
                   **{"Content-Type":
                      "application/x-www-form-urlencoded; charset=utf-8",
                      "XSRF-TOKEN": xsrf,
                      "Referer": f"{HOST}/translation/{sl_code}-{tl_code}"})
    if cookie and opener is None:
        headers["Cookie"] = cookie
    req = urllib.request.Request(HOST + "/api/getTranslation",
                                 data=body.encode("utf-8"), headers=headers)
    # the opener carries the session cookies; dropping it here gets
    # HTTP 400 from the current server (verified live 2026-11-08)
    with common.http_open(req, opener) as r:
        resp = parse_json_lenient(read_response_text(r))
    return _translate_response(resp)


def _split(header_block: str) -> dict:
    from qtranslate.common import split_headers
    return split_headers(header_block)


def page_load(paft: str = "", xsrf: str = "", cookie: str = "",
              opener=None) -> dict:
    """Port of FUN_0045f372: POST /api/pageLoad with `pageIx=0&v=1`.

    Native sends this right after the session bootstrap, using the same
    header trio from the page scrape (`Content-Type:
    application/x-www-form-urlencoded; charset=UTF-8`, `XSRF-TOKEN`,
    `Cookie`). The decompile shows the post body is the literal
    `pageIx=0&v=1` and the response is accepted only with HTTP status
    0xC8 (200); on 200 it extracts the `_ppup` field the way
    FUN_0045451a does. Returns the parsed response dict,{} on HTTP
    mismatch or transport failure (native returns false/0 either way --
    a failed pageLoad is NOT fatal to the later translation call).
    """
    if opener is None:
        import http.cookiejar
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar))
    xsrf = xsrf or Options.get("PromtXsrf", "")
    cookie = cookie or Options.get("PromtCookie", "")
    paft = paft or Options.get("PromtPaft", "")
    body = "pageIx=0&v=1"
    headers = dict(_UA,
                   **{"Content-Type":
                      "application/x-www-form-urlencoded; charset=UTF-8",
                      "Accept": "*/*",
                      "XSRF-TOKEN": xsrf,
                      "Cookie": cookie})
    # native's session bootstrap hits /translation/<a>-<b>; pageLoad rides
    # the same cookie jar (opener), so pass opener through and never
    # fall back to urlopen here.
    req = urllib.request.Request(HOST + "/api/pageLoad",
                                 data=body.encode("utf-8"), headers=headers)
    try:
        with common.http_open(req, opener) as r:
            if getattr(r, "status", 200) != 200:
                return {}
            return parse_json_lenient(read_response_text(r))
    except Exception:
        return {}


def ppup(resp: dict):
    """Port of FUN_0045451a's `_ppup` extraction: the pageLoad response's
    `_ppup` field, or None when the response carries none."""
    if isinstance(resp, dict) and "_ppup" in resp:
        return resp["_ppup"]
    return None


def _translate_response(resp: dict) -> tuple:
    b = ""
    sl_idx = tl_idx = None
    from qtranslate.common import UNKNOWN_LANGUAGE
    sl_idx = UNKNOWN_LANGUAGE
    tl_idx = UNKNOWN_LANGUAGE
    if resp and resp.get("text"):
        b = resp["text"]
        if resp.get("dictHtml"):
            b += NL2 + strip_html(resp["dictHtml"])
        if resp.get("phrasesHtml"):
            b += NL2 + strip_html(resp["phrasesHtml"])
        if resp.get("from"):
            sl_idx = language_from_code(resp["from"], SUPPORTED_LANGS)
        if resp.get("to"):
            tl_idx = language_from_code(resp["to"], SUPPORTED_LANGS)
    elif resp and resp.get("error"):
        b = resp["error"]
    return b, sl_idx, tl_idx
