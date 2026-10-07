"""1:1 port of Services/Google Translate/Service.js (SERVICE_ID=1).

Covers the whole file: serviceHeader/Host/Link, tk(), detect
request/response, translate request/response (incl. the `dt=bd`
dictionary branch), getSourceLanguage, listen request,
SupportedLanguages. Live behavior (gtx + dict-chrome-ex fallback)
verified 2026-10-07.
"""
import json
import sys
import urllib.parse
import urllib.request

from qtranslate.common import (
    MAX_URI_LEN,
    NL2,
    Capability,
    HttpMethod,
    ServiceHeader,
    code_from_language,
    encode_uri_param,
    get_header,
    is_language,
    language_from_code,
    limit_source,
    parse_json_lenient,
    add_option,
    Options,
)

SERVICE_ID = 1
SERVICE_NAME = "Google"

SUPPORTED_LANGS = [
    -1, "auto", "af", "az", "sq", "ar", "hy", "eu", "be", "bg", "ca",
    "zh-CN", "zh-TW", "hr", "cs", "da", "nl", "en", "et", "fi", "tl",
    "fr", "gl", "de", "el", "ht", "iw", "hi", "hu", "is", "id", "it",
    "ga", "ja", "ka", "ko", "lv", "lt", "mk", "ms", "mt", "no", "fa",
    "pl", "pt", "ro", "ru", "sr", "sk", "sl", "es", "sw", "sv", "th",
    "tr", "uk", "ur", "vi", "cy", "yi", "eo", "hmn", "la", "lo", "kk",
    "uz", "si", "tg", "te", "km", "mn", "kn", "ta", "mr", "bn", "tt",
]

HOST = "https://translate.google.com"


def service_header() -> ServiceHeader:
    return ServiceHeader(
        1, "Google",
        "Google's free online language translation service instantly "
        "translates text and web pages." + NL2 + service_host() + NL2 +
        "© 2020 Google",
        Capability.TRANSLATE | Capability.DETECT_LANGUAGE | Capability.LISTEN)


def service_host() -> str:
    return ("https://translate.google."
            + (Options.get("PreferredDomain")
               or Options.get("GoogleDomain") or "com"))


def service_link(text="", sl="auto", tl="en") -> str:
    from qtranslate.common import encode_get_param, format_q
    h = service_host() + "/"
    if text:
        if isinstance(sl, int):
            sl = code_from_language(sl, SUPPORTED_LANGS)
        elif not is_language(language_from_code(sl, SUPPORTED_LANGS),
                             SUPPORTED_LANGS):
            sl = "auto"
        if isinstance(tl, int):
            tl = code_from_language(tl, SUPPORTED_LANGS)
        h += format_q("#{0}/{1}/{2}", sl, tl, encode_get_param(text))
    return h


def _lang_code(idx_or_code) -> str:
    if isinstance(idx_or_code, int):
        return code_from_language(idx_or_code, SUPPORTED_LANGS)
    return idx_or_code


def _b(a: int, b: str) -> int:
    for d in range(0, len(b) - 2, 3):
        c = b[d + 2]
        c = (ord(c) - 87) if "a" <= c else int(c)
        c = (a >> c) if b[d + 1] == "+" else (a << c) & 0xFFFFFFFF
        a = (a + c) & 0xFFFFFFFF if b[d] == "+" else a ^ c
    return a


def tk(text: str, tkk: str = "0.0") -> str:
    """Port of tk(a) in Service.js. tkk = Options.GoogleTkk (seed from page)."""
    parts = tkk.split(".")
    h = int(parts[0]) if parts[0] else 0
    g = []
    e = 0
    while e < len(text):
        f = ord(text[e])
        if f < 128:
            g.append(f)
        elif f < 2048:
            g.append((f >> 6) | 192)
        else:
            if 55296 == (f & 64512) and e + 1 < len(text) and 56320 == (ord(text[e + 1]) & 64512):
                f = 65536 + ((f & 1023) << 10) + (ord(text[e + 1]) & 1023)
                e += 1
                g.append((f >> 18) | 240)
                g.append(((f >> 12) & 63) | 128)
            else:
                g.append((f >> 12) | 224)
            g.append(((f >> 6) & 63) | 128)
        g.append((f & 63) | 128)
        e += 1
    a = h
    for d in g:
        a += d
        a = _b(a, "+-a^+6")
    a = _b(a, "+-3^+b+-f")
    a ^= int(parts[1]) if len(parts) > 1 and parts[1] else 0
    if a < 0:
        a = (a & 2147483647) + 2147483648
    a %= 1_000_000
    return f"{a}.{a ^ h}"


def _parse(resp) -> str:
    out = ""
    if resp and resp[0]:
        for seg in resp[0]:
            if seg and len(seg):
                out += seg[0] or ""
    return out


def get_source_language(resp) -> int:
    """Port of getSourceLanguage(a)."""
    from qtranslate.common import UNKNOWN_LANGUAGE
    if not resp or len(resp) < 9:
        return UNKNOWN_LANGUAGE
    a = resp[8]
    if a and len(a):
        return language_from_code(a[0][0], SUPPORTED_LANGS)
    return UNKNOWN_LANGUAGE


def detect(text: str):
    """Port of serviceDetectLanguageRequest/Response. Returns lang index."""
    from qtranslate.common import UNKNOWN_LANGUAGE
    text = limit_source(text)
    token = tk(text, Options.get("GoogleTkk", "0.0"))
    q = encode_uri_param(text)
    get = len(q) <= MAX_URI_LEN
    path = ("/translate_a/single?client=gtx&sl=auto&dt=ld&ie=UTF-8&oe=UTF-8"
            f"&tk={token}" + ("" if not get else f"&q={q}"))
    data = None if get else ("q=" + q).encode()
    req = urllib.request.Request(service_host() + path, data=data,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        obj = parse_json_lenient(r.read().decode("utf-8"))
    return get_source_language(obj)


def _translate_response(obj, sl, tl):
    """Port of serviceTranslateResponse (translation + dt=bd dict branch)."""
    from qtranslate.common import UNKNOWN_LANGUAGE
    b = ""
    g = ""
    if obj:
        f = obj[0] if len(obj) > 0 else None
        if f:
            for d, e in enumerate(f):
                if e and len(e):
                    b += e[0] or ""
                    if len(e) > 2 and d == len(f) - 1:
                        g = e[2] or ""
        if len(obj) > 1 and obj[1]:
            for e in obj[1]:
                if e and len(e) >= 3:
                    b += NL2 + e[0] + ":"
                    for k in e[2]:
                        if len(k) > 1:
                            b += "\n    " + k[0]
                            if k[1] and len(k[1]):
                                b += " (" + ", ".join(k[1]) + ")"
        if isinstance(sl, int) and not is_language(sl, SUPPORTED_LANGS):
            sl = get_source_language(obj)
    return b, sl, tl, g


def translate(text: str, sl: str = "auto", tl: str = "en", tkk: str = "0.0") -> str:
    """Port of serviceTranslateRequest + serviceTranslateResponse.

    Primary: original client=gtx + tk token. Fallback: dict-chrome-ex
    (no token needed) when Google rate-limits gtx (HTTP 429).
    """
    import urllib.error
    if tkk == "0.0":
        tkk = Options.get("GoogleTkk", "0.0")
    text = limit_source(text)
    token = tk(text, tkk)
    q = encode_uri_param(text)
    get = len(q) <= MAX_URI_LEN
    hl = Options.get("LanguageCode", "en")
    path = ("/translate_a/single?client=gtx&sl={}&tl={}&hl={}"
            "&dt=bd&dt=t&dt=ld&dt=rm&ie=UTF-8&oe=UTF-8&tk={}").format(
                sl, tl, hl, token)
    if get:
        path += "&q=" + q
        data = None
    else:
        data = ("q=" + q).encode()
    req = urllib.request.Request(
        service_host() + path, data=data,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                 "Accept": "*/*", "Accept-Language": "en-US;q=0.8,en;q=0.6"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            obj = parse_json_lenient(r.read().decode("utf-8"))
            b, _, _, _ = _translate_response(obj, sl, tl)
            return b
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
    fb = ("/translate_a/single?client=dict-chrome-ex&sl={}&tl={}&dt=t&q={}"
          .format(sl, tl, q))
    req = urllib.request.Request(
        service_host() + fb, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return _parse(parse_json_lenient(r.read().decode("utf-8")))


def listen_url(text: str, lang: str = "en", slow: bool = False) -> str:
    """Port of serviceListenRequest (returns the mp3 URL, no fetch)."""
    from qtranslate.common import encode_get_param
    url = ("/translate_tts?ie=UTF-8&q={0}&tl={1}&client=gtx&tk={2}".format(
        encode_get_param(text), _lang_code(lang), tk(text)))
    if slow:
        url += "&ttsspeed=0.24"
    return service_host() + url


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello world"
    tl = sys.argv[2] if len(sys.argv) > 2 else "vi"
    print("tk:", tk(text))
    print("translation:", translate(text, "auto", tl))
