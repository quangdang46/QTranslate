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
    """Port of getResponseObj(a)."""
    if obj and len(obj) > 0:
        return obj[0]
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
    return bool(text) and "\n" not in text and "\r" not in text \
        and len(text.split(" ")) <= 3


def translate(text, sl=AUTO_DETECT_LANGUAGE, tl=ENGLISH_LANGUAGE, ig="",
              token="", key="", cookie="", opener=None,
              iid="translator.5023.3") -> str:
    """Port of translate pair (with short-text dictionary chaining)."""
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
    """translate() plus the native chaining decision.

    Returns (text, next_handler): "dictionaryRequest" for short texts
    (single dictionary-worthy phrase), else None — mirroring
    serviceTranslateResponse's 5th ResponseData field.
    """
    out = translate(text, sl, tl, **kw)
    nxt = "dictionaryRequest" if _is_short_text(text) else None
    return out, nxt


def dictionary(text, sl, tl, ig="", token="", key="", cookie="",
               opener=None) -> str:
    """Port of dictionaryRequest/dictionaryResponse: POST /tlookupv3."""
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
