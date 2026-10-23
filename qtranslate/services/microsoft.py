"""1:1 port of Services/Microsoft Translator/Service.js (SERVICE_ID=5).

Covers the whole file: serviceHeader/Host/Link, serviceRequest,
getResponseObj/getSourceLanguage, detect pair, translate pair (with
the short-text dictionary chaining), dictionaryRequest/Response,
SupportedLanguages. Live behavior (shared cookie jar + dynamic IID
+ gender-debias flag) verified 2026-10-07.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from qtranslate import common

from qtranslate.common import (
    NL,
    NL2,
    UNKNOWN_LANGUAGE,
    AUTO_DETECT_LANGUAGE,
    ENGLISH_LANGUAGE,
    Capability,
    ServiceHeader,
    code_from_language,
    encode_get_param,
    encode_post_param,
    format_q,
    is_language,
    language_from_code,
    limit_source,
    parse_json_lenient,
    get_header,
    post_header,
    read_response_text,
    Options,
)

SERVICE_ID = 5
SERVICE_NAME = "Microsoft"
HOST = "https://www.bing.com"

SUPPORTED_LANGS = [
    -1, "auto-detect", "af", -1, -1, "ar", -1, -1, -1, "bg", "ca", "zh-Hans",
    "zh-Hant", "hr", "cs", "da", "nl", "en", "et", "fi", "fil", "fr", -1,
    "de", "el", "ht", "he", "hi", "hu", "is", "id", "it", -1, "ja", -1,
    "ko", "lv", "lt", -1, "ms", "mt", "no", "fa", "pl", "pt", "ro", "ru",
    "sr-Cyrl", "sk", "sl", "es", -1, "sv", "th", "tr", "uk", "ur", "vi",
    "cy", -1, -1, "mww", -1, -1, -1, -1, -1, -1, "te", -1, -1, -1, "ta",
    -1, "bn-BD", -1,
]


def service_header() -> ServiceHeader:
    return ServiceHeader(
        5, "Microsoft",
        "Microsoft Translator is a cloud service that translates between "
        "60+ languages." + NL2 + service_host() + "/translator/" + NL2 +
        "© 2021 Microsoft",
        Capability.TRANSLATE | Capability.DETECT_LANGUAGE)


def service_host() -> str:
    if Options.get("PreferredDomain") == "cn" \
            or Options.get("GoogleDomain") == "cn":
        return "https://cn.bing.com"
    return "https://www.bing.com"


def service_link(text="", sl=1, tl=17) -> str:
    d = service_host() + "/translator"
    if text:
        b = code_from_language(sl, SUPPORTED_LANGS) \
            if is_language(sl, SUPPORTED_LANGS) else "-"
        c = code_from_language(tl, SUPPORTED_LANGS) \
            if is_language(tl, SUPPORTED_LANGS) else "-"
        d += format_q("?text={0}&from={1}&to={2}", encode_get_param(text),
                      b, c)
    return d


def _post(path: str, body: str, cookie: str = "") -> list:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Accept": "*/*",
        "Origin": "https://www.bing.com",
        "Referer": "https://www.bing.com/translator",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(HOST + path, data=body.encode("utf-8"),
                                 headers=headers)
    with common.http_open(req) as resp:
        return parse_json_lenient(read_response_text(resp))


def _service_request(text, sl=AUTO_DETECT_LANGUAGE, tl=ENGLISH_LANGUAGE,
                     ig="", token="", key="", cookie="", opener=None,
                     iid="translator.5023.3", _retried=False) -> list:
    """Port of serviceRequest(a,b,c): POST /ttranslatev3.

    Fixes researched 2026-10-07 (bing hardened since 2021 JS):
    - dynamic IID scraped from page data-iid (was hardcoded translator.5023.x)
    - body gains tryFetchingGenderDebiasedTranslations=true
    - shared cookie jar (decompile insight FUN_00465A92) when opener given
    - body.statusCode 205 = token expired -> rescrape + retry once
    """
    text = limit_source(text, 1000)
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    path = "/ttranslatev3?isVertical=1&IG={}&IID={}".format(ig, iid)
    body = ("text={}&fromLang={}&to={}&token={}&key={}"
            "&tryFetchingGenderDebiasedTranslations=true").format(
        encode_post_param(text), sl_code, tl_code, token, key)
    if opener is not None:
        req = urllib.request.Request(
            HOST + path, data=body.encode("utf-8"),
            headers={"Content-Type":
                     "application/x-www-form-urlencoded; charset=utf-8",
                     "Accept": "*/*", "Origin": "https://www.bing.com",
                     "Referer": "https://www.bing.com/translator"})
        with common.http_open(req, opener) as r:
            obj = parse_json_lenient(read_response_text(r))
    else:
        obj = _post(path, body, cookie)
    if (isinstance(obj, dict) and obj.get("statusCode") == 205
            and not _retried):
        from qtranslate import session as _sess
        s = _sess.bing_session()
        return _service_request(text, sl, tl, s["IG"], s["token"], s["key"],
                                s["cookie"], opener, s.get("iid", iid),
                                _retried=True)
    return obj


def get_response_obj(obj):
    """Port of getResponseObj(a), guarded against Microsoft's error shape.

    Native's response is a LIST of entries. Microsoft also answers an
    error OBJECT (``{"statusCode": 400, "errorMessage": ...}``) when the
    endpoint rejects the request, and indexing that with ``[0]`` raised a
    ``KeyError: 0`` that read like a port defect instead of what it is: a
    refused request. The error body is returned as-is so the caller's
    ``entry.get(...)`` finds nothing and the empty translation is
    reported, rather than the browser URL leaking a traceback.
    """
    if isinstance(obj, list):
        return obj[0] if obj else None
    if isinstance(obj, dict):
        if obj.get("statusCode") and int(obj["statusCode"]) >= 400:
            return None
        return obj
    return None


def get_source_language(entry) -> int:
    """Port of getSourceLanguage(a). Returns a lang *index*."""
    try:
        if entry and entry.get("detectedLanguage"):
            return language_from_code(
                entry["detectedLanguage"]["language"], SUPPORTED_LANGS)
    except (KeyError, TypeError, IndexError):
        pass
    return UNKNOWN_LANGUAGE


def next_handler(entry) -> str | None:
    """Port of the E22 chain signal: ``nextRequestHandler``.

    Native's Service.js does NOT decide "send this to the dictionary"
    from the input text -- the ttranslatev3 response's
    ``nextRequestHandler`` field does, and ``tlookupv3`` is the block it
    names (`docs/RE_COVERAGE_CHECKLIST.md` row E22). This port used to
    GUESS that decision from the text (a word-count heuristic in
    ``_is_short_text``), which is an invention standing in for a signal
    the server actually sends.

    Returns the handler name when the response asks for one, else None.
    An unknown/absent field yields None: never guess a handler name.
    """
    try:
        raw = entry.get("nextRequestHandler") if entry else None
    except AttributeError:
        return None
    if not raw:
        return None
    name = str(raw).strip()
    return name or None


def detect(text, ig="", token="", key="", cookie="", opener=None,
           iid="translator.5023.3"):
    """Port of detect pair. Returns a lang *index*."""
    return get_source_language(
        get_response_obj(_service_request(
            text, ig=ig, token=token, key=key, cookie=cookie, opener=opener,
            iid=iid)))


def detect_code(text, **kw) -> str:
    """Convenience: detect() resolved to a language code string."""
    return code_from_language(detect(text, **kw), SUPPORTED_LANGS)


def _is_short_text(text: str) -> bool:
    r"""PORT-SIDE HEURISTIC -- not the native chain signal.

    Kept only because callers may want a local hint. The native rule is
    the response's ``nextRequestHandler`` (E22); ``translate_full`` uses
    that, and only falls back to this when the server did not answer.

    Native's own inline test, recovered 2026-10-16 from
    ``serviceTranslateResponse``::

        a = a && !/[\n\r]/.test(a) && 3 >= a.split(" ").length
            ? "dictionaryRequest"
            : null

    The split is on ``" "`` -- a single literal space -- which Python's
    ``split(" ")`` also reproduces exactly (leading spaces DO yield an
    empty leading member, unlike Yandex's ``\\s+`` and a bare
    ``str.split()``). So this helper keeps native's expression even
    though it is no longer the chain rule.
    """
    return bool(text) and "\n" not in text and "\r" not in text \
        and len(text.split(" ")) <= 3


def _seed(ig, token, key, cookie):
    """Resolve the session fields, honouring native's Options keys.

    The recovered image's Options table carries, next to Google's and
    Baidu's and Promt's, ``BingCookie`` / ``BingToken`` / ``BingKey`` /
    ``IG`` (`tests/regress_session_markers.py` reads them out of `.rdata`).
    Every other provider here already falls back to its Options seed --
    Baidu reads ``BaiduCookie``/``BaiduToken``/``BaiduGtk``, Promt reads
    ``PromtCookie``/``PromtXsrf``/``PromtPaft``, Google reads
    ``GoogleTkk`` -- so a user can persist a session across runs. Microsoft
    accepted the values only as arguments, which meant a saved session was
    silently ignored and the caller had to re-scrape every time.
    """
    return (
        ig or Options.get("IG", ""),
        token or Options.get("BingToken", ""),
        key or Options.get("BingKey", ""),
        cookie or Options.get("BingCookie", ""),
    )


def translate(text, sl=AUTO_DETECT_LANGUAGE, tl=ENGLISH_LANGUAGE, ig="",
              token="", key="", cookie="", opener=None,
              iid="translator.5023.3") -> str:
    """Port of translate pair (no chaining; see translate_full)."""
    ig, token, key, cookie = _seed(ig, token, key, cookie)
    obj = _service_request(text, sl, tl, ig, token, key, cookie, opener, iid)
    entry = get_response_obj(obj)
    out = ""
    if entry and entry.get("translations"):
        out = entry["translations"][0].get("text", "")
    sl_idx = sl if isinstance(sl, int) else UNKNOWN_LANGUAGE
    if isinstance(sl, int) and not is_language(sl, SUPPORTED_LANGS):
        sl_idx = get_source_language(entry)
    _ = sl_idx  # resolved source index, returned via tuple below if needed
    return out


def translate_full(text, sl=AUTO_DETECT_LANGUAGE, tl=ENGLISH_LANGUAGE,
                   **kw):
    """translate() plus the NATIVE chain decision.

    Returns ``(text, next)`` where ``next`` is the handler the server
    asked for (``"dictionaryRequest"`` in practice). Precedence, per E22:

      1. the response's ``nextRequestHandler`` -- the native signal;
      2. ``None`` when the server named no handler.

    The old body derived the decision from the input text via
    ``_is_short_text``; that guessed at a signal the server actually
    sends, so a long phrase the server marked for the dictionary was
    skipped and a short one it did not mark was chased. It is no longer
    used as the primary rule.
    """
    _ig, _tok, _key, _ck = _seed(kw.get("ig", ""), kw.get("token", ""),
                                 kw.get("key", ""), kw.get("cookie", ""))
    obj = _service_request(text, sl, tl, _ig, _tok, _key, _ck,
                           kw.get("opener"),
                           kw.get("iid", "translator.5023.3"))
    entry = get_response_obj(obj)
    out = ""
    if entry and entry.get("translations"):
        out = entry["translations"][0].get("text", "")
    return out, next_handler(entry)


def dictionary(text, sl, tl, ig="", token="", key="", cookie="",
               opener=None) -> str:
    """Port of dictionaryRequest/dictionaryResponse: POST /tlookupv3.

    SERVER WALL (verified 2026-10-08): tlookupv3 returns 401 for every
    IID/header combo (old .2 suffix, live data-iid, get/post headers)
    while ttranslatev3 on the same session is 200 — Bing retired the
    standalone dictionary endpoint. `translate_full()` reports the chain
    via the response's `nextRequestHandler` (E22); routing into this
    function is the caller's decision from that signal. Returns "" so
    callers fall through. Kept faithful for when/if the endpoint reopens.
    """
    if not (ig and token and key):
        try:
            from qtranslate.session import bing_session as _bs
            _s = _bs()
            ig, token, key = _s["IG"], _s["token"], _s["key"]
            cookie, opener = _s["cookie"], _s["opener"]
        except Exception:
            pass
    text = limit_source(text, 1000)
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    path = "/tlookupv3?isVertical=1&IG={}&IID=translator.5023.2".format(ig)
    body = "text={}&from={}&to={}&token={}&key={}".format(
        encode_post_param(text), sl_code, tl_code, token, key)
    if opener is not None:
        req = urllib.request.Request(
            HOST + path, data=body.encode("utf-8"),
            headers={"Content-Type":
                     "application/x-www-form-urlencoded; charset=utf-8",
                     "Accept": "*/*", "Origin": "https://www.bing.com",
                     "Referer": "https://www.bing.com/translator"})
        with common.http_open(req, opener) as r:
            obj = parse_json_lenient(read_response_text(r))
    else:
        obj = _post(path, body, cookie)
    labels = {
        "ADJ": "Adjectives", "ADV": "Adverbs", "CONJ": "Conjunctions",
        "DET": "Determiners", "MODAL": "Verbs", "NOUN": "Nouns",
        "PREP": "Prepositions", "PRON": "Pronouns", "VERB": "Verbs",
    }
    out = ""
    try:
        groups: dict[str, list[str]] = {}
        for item in obj[0]["translations"]:
            line = "    " + item["displayTarget"]
            if item.get("backTranslations"):
                line += " (" + ", ".join(
                    b["displayText"] for b in item["backTranslations"]) + ")"
            groups.setdefault(item.get("posTag", ""), []).append(line)
        for tag, lines in groups.items():
            out += labels.get(tag, tag) + ":" + NL + NL.join(lines) + NL2
    except (KeyError, IndexError, TypeError):
        pass
    return NL2 + out if out else ""
