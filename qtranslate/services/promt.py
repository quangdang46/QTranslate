"""Port of C:/Program Files (x86)/QTranslate/Services/Promt/Service.js (SERVICE_ID=12).

Live status 2026-10-07: 400 without paft+XSRF. Shared-jar gets Antiforgery
cookies but paft is JS-rendered (absent from static HTML) — headless
browser required for the full flow. ghcs() hash verified working.
"""

PROMT.One /api/getTranslation. Signing: ghcs() Java-style hash over
"TranslateButton#{sl}-{tl}#General#{ghcs(text)}" then ghcs() again.
Session values (PromtPaft, PromtCookie, PromtXsrf) are scraped from the
service page and passed as args.
"""
import json
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


def translate(text: str, sl: str, tl: str, paft: str = "",
              cookie: str = "", xsrf: str = "") -> tuple:
    """Returns (translation, dict_html_text, phrases_text)."""
    text = text[:1000]
    h = ghcs(f"TranslateButton#{sl}-{tl}#General#{ghcs(text)}")
    body = ("eventName=TranslateButton&text={}&dirCode={}-{}"
            "&useAutoDetect=true&h={}&aft={}&pageIx=0&v=1".format(
                urllib.parse.quote(text), sl, tl, h, paft))
    req = urllib.request.Request(
        HOST + "/api/getTranslation", data=body.encode(),
        headers={"User-Agent": "Mozilla/5.0",
                 "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                 "Cookie": cookie, "XSRF-TOKEN": xsrf})
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if resp.get("text"):
        return resp["text"], resp.get("dictHtml", ""), resp.get("phrasesHtml", "")
    return resp.get("error", ""), "", ""
