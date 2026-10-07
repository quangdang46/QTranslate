"""Microsoft Translator (Bing) service port.

Reversed from: C:/Program Files (x86)/QTranslate/Services/Microsoft Translator/Service.js
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

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


def _post(path: str, body: str, cookie: str = "") -> list:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Accept": "*/*",
        "Origin": "https://www.bing.com",
        "Referer": "https://www.bing.com/translator",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(
        HOST + path, data=body.encode("utf-8"), headers=headers
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _service_request(
    text: str,
    sl: str = "auto-detect",
    tl: str = "en",
    ig: str = "",
    token: str = "",
    key: str = "",
    cookie: str = "",
    iid: str = "translator.5023.3",
    _retried: bool = False,
) -> list:
    """Port of serviceRequest(a,b,c): POST /ttranslatev3.

    Fixes researched 2026-10-07 (bing hardened since 2021 JS):
    - dynamic IID scraped from page data-iid (was hardcoded translator.5023.x)
    - body gains tryFetchingGenderDebiasedTranslations=true
    - short lang codes required (zh-Hans not zh-Hans-longform)
    - body.statusCode 205 = token expired -> caller must rescrape + retry once
    """
    path = "/ttranslatev3?isVertical=1&IG={}&IID={}".format(ig, iid)
    body = ("text={}&fromLang={}&to={}&token={}&key={}"
            "&tryFetchingGenderDebiasedTranslations=true").format(
        urllib.parse.quote(text[:1000], safe=""),
        sl,
        tl,
        token,
        key,
    )
    obj = _post(path, body, cookie)
    if (isinstance(obj, dict) and obj.get("statusCode") == 205
            and not _retried):
        from qtranslate import session as _sess
        s = _sess.bing_session()
        return _service_request(text, sl, tl, s["IG"], s["token"], s["key"],
                                s["cookie"], s.get("iid", iid), _retried=True)
    return obj


def detect(text: str, ig: str = "", token: str = "", key: str = "", cookie: str = "", iid: str = "translator.5023.3") -> str:
    """Port of serviceDetectLanguageRequest/Response."""
    obj = _service_request(text, ig=ig, token=token, key=key, cookie=cookie, iid=iid)
    try:
        return obj[0]["detectedLanguage"]["language"]
    except (KeyError, IndexError, TypeError):
        return ""


def translate(
    text: str,
    sl: str = "auto-detect",
    tl: str = "en",
    ig: str = "",
    token: str = "",
    key: str = "",
    cookie: str = "",
    iid: str = "translator.5023.3",
) -> str:
    """Port of serviceTranslateRequest/Response: POST /ttranslatev3."""
    obj = _service_request(text, sl, tl, ig, token, key, cookie, iid)
    try:
        return obj[0]["translations"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return ""


def dictionary(
    text: str,
    sl: str,
    tl: str,
    ig: str = "",
    token: str = "",
    key: str = "",
    cookie: str = "",
) -> str:
    """Port of dictionaryRequest/dictionaryResponse: POST /tlookupv3."""
    path = "/tlookupv3?isVertical=1&IG={}&IID=translator.5023.2".format(ig)
    body = "text={}&from={}&to={}&token={}&key={}".format(
        urllib.parse.quote(text[:1000], safe=""), sl, tl, token, key
    )
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
                    b["displayText"] for b in item["backTranslations"]
                ) + ")"
            groups.setdefault(item.get("posTag", ""), []).append(line)
        for tag, lines in groups.items():
            out += (labels.get(tag, tag)) + ":\r\n" + "\r\n".join(lines) + "\r\n\r\n"
    except (KeyError, IndexError, TypeError):
        pass
    return "\r\n\r\n" + out if out else ""
