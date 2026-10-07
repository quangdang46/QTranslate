"""Port of C:/Program Files (x86)/QTranslate/Services/Promt/Service.js (SERVICE_ID=12).

Live status 2026-10-07: pipeline verified (HTTP 200 + correct response
schema: text/dictHtml/phrasesHtml/...). Server returns
"service temporarily unavailable" for en-ru right now — backend-side,
not a port bug. Fixes applied: scrape id="_paft"/id="_xsrf" (hidden
inputs, static HTML — no headless needed), send xsrf as XSRF-TOKEN
*header*, v=2.

PROMT.One /api/getTranslation. Signing: ghcs() Java-style hash over
"TranslateButton#{sl}-{tl}#General#{ghcs(text)}" then ghcs() again.
"""
import json
import re
import urllib.parse
import urllib.request

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


def _i32(n: int) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n & 0x80000000 else n


def ghcs(text: str, b: int = None, d: int = None, c: int = 0) -> int:
    if b is None:
        e = 0 if not text else len(text)
        if e > 100:
            return ghcs(text, e - 50, e, ghcs(text, 0, 50, e))
        return ghcs(text, 0, e, e)
    for e in range(b, d):
        c = _i32((c << 5) - c + ord(text[e]))
    return c


_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def session(sl: str = "en", tl: str = "ru", opener=None):
    """Scrape id=_paft + id=_xsrf from the translation page.

    Both live in static HTML (no headless needed). Returns
    (paft, xsrf, opener-with-cookies).
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
    with opener.open(req, timeout=20) as r:
        html = r.read().decode("utf-8", errors="replace")
    paft = re.search(r'id="_paft"[^>]*value="([^"]+)"', html).group(1)
    xsrf = re.search(r'id="_xsrf"[^>]*value="([^"]+)"', html).group(1)
    return paft, xsrf, opener


def translate(text: str, sl: str, tl: str, paft: str = "",
              cookie: str = "", xsrf: str = "", opener=None) -> tuple:
    """Returns (translation, dict_html_text, phrases_text).

    Pass opener from session() to reuse the cookie jar; or pass
    paft/xsrf scraped manually. v=2 per current web client.
    """
    text = text[:1000]
    h = ghcs(f"TranslateButton#{sl}-{tl}#General#{ghcs(text)}")
    body = ("eventName=TranslateButton&text={}&dirCode={}-{}"
            "&useAutoDetect=true&h={}&aft={}&pageIx=0&v=2".format(
                urllib.parse.quote(text), sl, tl, h, paft))
    headers = {**_UA,
               "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
               "XSRF-TOKEN": xsrf,
               "Referer": f"{HOST}/translation/{sl}-{tl}"}
    if cookie and opener is None:
        headers["Cookie"] = cookie
    req = urllib.request.Request(HOST + "/api/getTranslation",
                                 data=body.encode(), headers=headers)
    opener = opener or urllib.request
    with opener.open(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if resp.get("text"):
        return resp["text"], resp.get("dictHtml", ""), resp.get("phrasesHtml", "")
    return resp.get("error", ""), "", ""
