"""1:1 port of Services/Babylon/Service.js (SERVICE_ID=13).

Covers the whole file: serviceHeader/Host/Link, SupportedLanguages,
serviceTranslateRequest (GET /translate/babylon.php JSONP) and
serviceTranslateResponse (JSONP paren-strip -> [..] wrap -> [1] branch
-> stripHtml(translatedText), '*' -> NL).

Live status 2026-10-08: endpoint SSL dead (CERTIFICATE_VERIFY_FAILED
on translation.babylon-software.com — server-side, same wall as the
Babylon dictionary lookups). Port is faithful; calls surface the
native "No data returned" error string via do_translate().
"""
import urllib.parse
import urllib.request
from qtranslate import common

from qtranslate.common import (
    NL,
    Capability,
    ServiceHeader,
    code_from_language,
    encode_get_param,
    is_language,
    language_from_code,
    limit_source,
    parse_json_lenient,
    strip_html,
    Options,
)

SERVICE_ID = 13
SERVICE_NAME = "Babylon"

SUPPORTED_LANGS = [
    -1, -1, -1, -1, -1, 15, -1, -1, -1, -1, 99, 10, 9, -1, 31, 43, 4, 0,
    -1, -1, -1, 1, -1, 6, 11, -1, 14, 60, 30, -1, -1, 2, -1, 8, -1, 12,
    -1, -1, -1, -1, -1, 46, 51, 29, 5, 47, 7, -1, -1, -1, 3, -1, 48, 16,
    13, 49, 39, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1,
]

HOST = "https://translation.babylon-software.com"


def service_header() -> ServiceHeader:
    return ServiceHeader(
        13, "Babylon",
        "Search for literally millions of terms in Babylon’s "
        "database of over 1,600 dictionaries and glossaries from the "
        "most varied fields of information. All in more than 75 "
        "languages." + "\r\n\r\n" + service_host() + "\r\n\r\n"
        "© 2014-2017 Babylon Software Ltd",
        Capability.TRANSLATE)


def service_host(a=None, b=None, c=None) -> str:
    return "https://translation.babylon-software.com"


def service_link(a="", b=None, c=None) -> str:
    return service_host()


def _translate_response(body: str, sl, tl):
    """Port of serviceTranslateResponse(a,b,c,e): JSONP -> [..] -> [1].

    b (raw body) -> strip callback parens -> wrap in [..] -> parseJSON
    -> if len > 2 take [1] -> stripHtml(translatedText), '*' -> NL.
    Returns (text, sl, tl) like the ResponseData(a,c,e) triple.
    """
    a = body
    if a:
        b = a.index("(") if "(" in a else -1
        if b != -1:
            d = a.rfind(")")
            if d != -1:
                a = "[" + a[b + 1:d] + "]"
        obj = parse_json_lenient(a)
        if obj and len(obj) > 2:
            obj = obj[1]
            if obj:
                a = strip_html(obj.get("translatedText", ""))
                a = a.replace("*", NL)
    return a, sl, tl


def _resolve_code(code):
    """Native's ``codeFromLanguage`` for an ISO code.

    Native's framework hands a service a language **index** and the service
    indexes its own ``SupportedLanguages`` with it. This port's call sites
    hand over the ISO **code** instead, so the code has to become the app's
    language id first -- the framework's own ``languageFromCode`` step over
    the shared language list -- and only then can the provider's table be
    indexed.

    For Babylon this is not cosmetic: its table holds **numbers** (0 is
    English, 7 is Russian), so the port used to ask Babylon for
    ``langpair=en|ru`` where native asks for ``langpair=0|7``.

    ``"auto"`` is left alone: native's framework detects the source itself
    for a provider whose table cannot express AUTO (``usesAutoDetectCode``
    is false for Babylon -- its slot 1 is ``-1``), so the index never
    reaches the service, and passing the marker through keeps the port's
    own detect step in charge.
    """
    if code in ("auto", "", None) or isinstance(code, int):
        return code
    from qtranslate.services.google_translate import SUPPORTED_LANGS as _APP
    idx = language_from_code(code, _APP)
    if not idx:
        return code              # not a language the app knows at all
    return code_from_language(idx, SUPPORTED_LANGS)


def translate(text: str, sl="auto", tl="en") -> str:
    """Port of serviceTranslateRequest + serviceTranslateResponse.

    GET /translate/babylon.php?v=1.0&q={0}&langpair={1}%7C{2}
    &callback=callbackFn&context=babylon
    """
    text = limit_source(text)
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else _resolve_code(sl)
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else _resolve_code(tl)
    path = ("/translate/babylon.php?v=1.0&q={0}&langpair={1}%7C{2}"
            "&callback=callbackFn&context=babylon").format(
                encode_get_param(text), sl_code, tl_code)
    req = urllib.request.Request(
        service_host() + path,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                 "Accept": "*/*",
                 "Referer": "https://translation.babylon-software.com/"})
    with common.http_open(req) as r:
        body = r.read().decode("utf-8", errors="replace")
    out, _, _ = _translate_response(body, sl, tl)
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(repr(translate("hello", "en", "fr")[:200]))
