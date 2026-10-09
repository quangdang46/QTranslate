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
from qtranslate import common

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
    with common.http_open(req) as r:
        obj = parse_json_lenient(r.read().decode("utf-8"))
    return get_source_language(obj)


def _translate_response(obj, sl, tl):
    """Port of serviceTranslateResponse (translation + dt=bd dict branch).

    Returns `(translation, sl, tl, romanization)`. The 4th value is the
    `dt=rm` romanization — J7's phonetics source — which `translate()`
    requests and this parser has read since the first 1:1 port, but which
    the caller discarded until now.

    The slot is **index 3**, not index 2. Live shape for
    `client=gtx&sl=zh-CN&tl=en&dt=t&dt=rm` on `你好` (fetched 2026-10-10):

    ```json
    [[["Hello","你好",null,null,10],
      [null,null,null,"Nǐ hǎo"]]]
    ```

    Index 2 is `null` on the romanization segment; index 3 carries the
    string. Verified against the live endpoint for zh/ko/ja/ru and by
    isolating the `dt` values: `dt=rm` alone yields exactly one segment
    `[null,null,null,"Nǐ hǎo"]`, `dt=t` alone yields none.
    """
    from qtranslate.common import UNKNOWN_LANGUAGE
    b = ""
    g = ""
    if obj:
        f = obj[0] if len(obj) > 0 else None
        if f:
            for d, e in enumerate(f):
                if e and len(e):
                    b += e[0] or ""
                    # native reads the romanization slot off the LAST segment
                    if d == len(f) - 1 and len(e) > 3:
                        g = e[3] or ""
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


_TKK_CACHE = ("", 0.0)  # (tkk, fetched_at) — native caches hourly
_TKK_START = "_ctkk='"   # native DAT_0051d57c (FUN_0040FB54 primary)
_TKK_START_ALT = "TKK='"  # native DAT_0051d5c4 (fallback marker)
_TKK_END = "';"          # native DAT_0051d58c (shared end marker)
_TKK_URL = "/translate_a/element.js"  # native literal (FUN_0040fec9 path)


def _tkk_slice(js: str) -> str:
    """Slice the tkk between native markers.

    FUN_0040FB54 builds a CString from 8 bytes at DAT_0051d57c (the wide
    chars `_ctkk='`), then at DAT_0051d5c4 (`TKK='`) — sharing the end marker
    `';` at DAT_0051d58c. It calls FUN_0040fec9 with each marker pair, and
    retries with the alternate start marker when the primary slice comes back
    empty (the `*(int *)(DAT_00549774 + -0xc) == 0` guard in the decompile).
    """
    for start in (_TKK_START, _TKK_START_ALT):
        begin = js.find(start)
        if begin < 0:
            continue
        begin += len(start)
        end = js.find(_TKK_END, begin)
        if end < 0:
            continue
        token = js[begin:end]
        if token:
            return token
    return ""


def refresh_tkk(force: bool = False) -> str:
    """Port of FUN_0040FB54 → FUN_0040FEC9 (GoogleTkk seed pipeline).

    GET https://translate.google.<domain>/translate_a/element.js, slice the TKK
    between the native marker pair, cache hourly (native keys its cache on the
    calendar hour, `DAT_0054977c != local_20.wHour`). Returns the "a.b"-style
    token, or "0.0" on failure (native defaults to 0.0 until the fetch works).
    """
    import time
    global _TKK_CACHE
    now = time.time()
    if not force and _TKK_CACHE[0] and now - _TKK_CACHE[1] < 3600:
        return _TKK_CACHE[0]
    url = service_host() + _TKK_URL
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"})
        with common.http_open(req) as r:
            js = r.read().decode("utf-8", "replace")
    except Exception:
        return _TKK_CACHE[0] or "0.0"
    tkk = _tkk_slice(js) or "0.0"
    _TKK_CACHE = (tkk, now)
    try:
        Options["GoogleTkk"] = tkk
    except Exception:
        pass
    return tkk


# ------------------------------------------------------------------ J7
# dt=rm romanization from the last translate() call — the phonetics field
# for `qtranslate/phonetics.py` (J7, FUN_0042ED3F's `entry[5]`).
#
# It lives here, as module state, only because the `_t_*` adapter contract
# is a bare `str`. Native carries it in the result struct at index 5; our
# `ResponseData` (common.py) has no such field, which is Phase 5 work
# (ARCHITECTURE.md §3.1 — TranslationRequest/Result value object).
# A list so the setter needs no `global` and tests can reset it.
_ROMANIZATION = [""]


def set_romanization(value: str | None) -> None:
    """Record the `dt=rm` romanization for the render path."""
    _ROMANIZATION[0] = value or ""


def get_romanization() -> str:
    """The last romanization seen ("" when none, or after a reset)."""
    return _ROMANIZATION[0]


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
        with common.http_open(req) as r:
            obj = parse_json_lenient(r.read().decode("utf-8"))
            b, _, _, g = _translate_response(obj, sl, tl)
            # J7's phonetics source. The request has always asked for
            # `dt=rm`, and this line has always parsed it — the value was
            # then discarded. Kept as module state because the `_t_*`
            # contract is a bare string; a `phonetics` field on
            # `ResponseData` is Phase 5 (ARCHITECTURE.md §3.1).
            set_romanization(g)
            return b
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
    fb = ("/translate_a/single?client=dict-chrome-ex&sl={}&tl={}&dt=t&q={}"
          .format(sl, tl, q))
    req = urllib.request.Request(
        service_host() + fb, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    # The dict-chrome-ex fallback sends no `dt=rm`, so it yields no
    # romanization. Clear the slot: leaving the previous call's value here
    # would append a stale romanization to this result.
    set_romanization("")
    with common.http_open(req) as r:
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
