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
                   "tt"]


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


def _i32(n: int) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n & 0x80000000 else n


def ghcs(text: str, b: int = None, d: int = None, c: int = 0) -> int:
    """Port of ghcs(a,b,d,c) — Java-style string hash."""
    if b is None:
        e = 0 if is_null_or_empty(text) else len(text)
        if e > 100:
            return ghcs(text, e - 50, e, ghcs(text, 0, 50, e))
        return ghcs(text, 0, e, e)
    for e in range(b, d):
        c = _i32((c << 5) - c + ord(text[e]))
    return c


def ghcd(text: str, sl, tl) -> int:
    """Port of ghcd(a,b,d). sl/tl accept indices or codes."""
    from qtranslate.common import format_q
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    inner = format_q("TranslateButton#{0}-{1}#General#{2}", sl_code,
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
    if opener is None:
        import http.cookiejar
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar))
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
    text = limit_source(text, 1000)
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
    open_ = opener.open if opener is not None else urllib.request.urlopen
    with common.http_open(req) as r:
        resp = parse_json_lenient(read_response_text(r))
    return _translate_response(resp)


def _split(header_block: str) -> dict:
    from qtranslate.common import split_headers
    return split_headers(header_block)


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
