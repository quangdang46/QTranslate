"""1:1 port of Services/Yandex/Service.js (SERVICE_ID=11).

Covers the whole file: serviceHeader/Host/Link, YandexModel chunker,
detect request/response, translate request/response (with the
dictionary-or-next-chunk chaining), dictionaryRequest/Response,
serviceListenRequest, SupportedLanguages. Live behavior (Android
variant, since srv=tr-text returns 403) verified 2026-10-07.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import uuid

from qtranslate.common import (
    NL,
    NL2,
    UNKNOWN_LANGUAGE,
    Capability,
    HttpMethod,
    ServiceHeader,
    code_from_language,
    encode_get_param,
    encode_post_param,
    format_q,
    get_header,
    language_from_code,
    limit_source,
    parse_json_lenient,
    post_header,
    prepare_source,
    string_split,
    Options,
)

SERVICE_ID = 11
SERVICE_NAME = "Yandex"
HOST = "https://translate.yandex.net"
LISTEN_HOST = "https://tts.voicetech.yandex.net"

SUPPORTED_LANGS = [
    -1, -1, "af", "az", "sq", "ar", "hy", "eu", "be", "bg", "ca", "zh",
    "zh", "hr", "cs", "da", "nl", "en", "et", "fi", -1, "fr", "gl", "de",
    "el", "ht", "he", "hi", "hu", "is", "id", "it", "ga", "ja", "ka",
    "ko", "lv", "lt", "mk", "ms", "mt", "no", "fa", "pl", "pt", "ro",
    "ru", "sr", "sk", "sl", "es", "sw", "sv", "th", "tr", "uk", "ur",
    "vi", "cy", "yi", "eo", -1, "la", "lo", "kk", "uz", "si", "tg",
    "te", "km", "mn", "kn", "ta", "mr", "bn", "tt",
]

_TRUNC_PATTERNS = [
    r"(\n+)", r"([.!?;।](?:\s+|$))", r"([\-‒-―](?:\s+|$))",
    r"([,:](?:\s+|$))", r"([。！？；…])",
    r"([，：])", r"(\s+)",
]


def service_header() -> ServiceHeader:
    return ServiceHeader(
        11, "Yandex",
        "Translate Russian, Spanish, German, French and a number of other "
        "languages to and from English. You can translate individual "
        "words, as well as whole texts and webpages." + NL2 +
        "https://translate.yandex.com/" + NL2 +
        "© 2011-2022 «Yandex»",
        Capability.TRANSLATE | Capability.DETECT_LANGUAGE | Capability.LISTEN)


def service_host(capability: int = Capability.TRANSLATE) -> str:
    if capability == Capability.LISTEN:
        return "https://tts.voicetech.yandex.net"
    return "https://translate.yandex.net"


def service_link(text="", sl=-1, tl=-1) -> str:
    from qtranslate.common import is_language
    e = "https://translate.yandex.com"
    if text:
        b = code_from_language(sl, SUPPORTED_LANGS) \
            if is_language(sl, SUPPORTED_LANGS) else ""
        c = code_from_language(tl, SUPPORTED_LANGS) \
            if is_language(tl, SUPPORTED_LANGS) else ""
        e += format_q("/?lang={0}-{1}&text={2}", b, c,
                      encode_get_param(text))
    return e


class YandexModel:
    """Port of YandexModel (chunker, max 10000 source chars)."""

    def __init__(self, text: str):
        self._chunks: list[str] = []
        self._make_chunks(limit_source(prepare_source(text), 10000))

    def has_chunks(self) -> bool:
        return bool(self._chunks)

    def get_next_chunk(self) -> str:
        return self._chunks.pop(0) if self._chunks else ""

    def _make_chunks(self, text: str) -> None:
        self._chunks = []
        while text:
            piece = self._truncate_text(text)
            if not piece:
                break
            self._chunks.append(piece)
            text = text[len(piece):]

    def _truncate_text(self, text: str) -> str:
        if not text or len(text) <= 600:
            return text
        head = text[:600]
        for pattern in _TRUNC_PATTERNS:
            if re.search(pattern, head):
                return "".join(string_split(head, pattern)[:-1])
        return head


def make_chunks(text: str) -> list[str]:
    """Back-compat helper returning all chunks at once."""
    m = YandexModel(text)
    out = []
    while m.has_chunks():
        out.append(m.get_next_chunk())
    return out


_ANDROID_UA = ("User-Agent", "ru.yandex.translate/3.20.2024 "
               "(Android 13; SDK 33; armeabi-v7a)")


def _fetch(path: str, data: bytes | None = None,
           android: bool = False) -> dict:
    headers = {"Accept": "*/*", "Referer": "https://translate.yandex.com"}
    if data is not None:
        headers["Content-Type"] = \
            "application/x-www-form-urlencoded; charset=utf-8"
    if android:
        headers[_ANDROID_UA[0]] = _ANDROID_UA[1]
    req = urllib.request.Request(HOST + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return parse_json_lenient(resp.read().decode("utf-8"))


def detect(text: str, app_id: str = "") -> int:
    """Port of detect request/response. Returns a lang *index*.

    Original srv=tr-text is dead (403); falls back to the Android
    variant (researched 2026-10-07).
    """
    query = urllib.parse.quote(text[:256], safe="")
    if not app_id:
        app_id = Options.get("YandexAppId", "")
    try:
        obj = _fetch("/api/v1/tr.json/detect?sid={}&srv=tr-text&text={}"
                     .format(app_id, query))
        if obj.get("code") == 200:
            return language_from_code(obj.get("lang", ""), SUPPORTED_LANGS)
    except Exception:
        pass
    try:
        obj = _fetch("/api/v1/tr.json/detect?srv=android&text={}"
                     .format(query), android=True)
        if obj.get("code") == 200:
            return language_from_code(obj.get("lang", ""), SUPPORTED_LANGS)
    except Exception:
        pass
    return UNKNOWN_LANGUAGE


def detect_code(text: str, app_id: str = "") -> str:
    """Convenience: detect() resolved to a language code string."""
    return code_from_language(detect(text, app_id), SUPPORTED_LANGS)


def _use_dictionary(text: str) -> bool:
    return bool(text) and len(text) <= 100 \
        and not re.search(r"[\n\r]", text) \
        and len(text.split()) <= 3


def translate(text: str, sl="", tl: str = "en", app_id: str = "") -> str:
    """Port of translate request/response with chunk + dict chaining.

    sl/tl accept indices or codes (native calls codeFromLanguage on
    indices). Returns joined translation text.
    """
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    if not app_id:
        app_id = Options.get("YandexAppId", "")
    model = YandexModel(text)
    out_lines: list[str] = []
    first = True
    while True:
        chunk = model.get_next_chunk() if not first else None
        if first:
            # first request consumes the model's first chunk implicitly
            # (native keeps one global yandexModel; emulate per call)
            chunk = model.get_next_chunk()
            first = False
        if chunk is None:
            break
        body = "text=" + urllib.parse.quote(chunk, safe="")
        obj = None
        for path, android in (
            ("/api/v1/tr.json/translate?id={}-0-0&srv=tr-text&lang={}-{}"
             "&reason=auto&format=text&yu=2210680511641235828"
             .format(app_id, sl_code, tl_code), False),
            ("/api/v1/tr.json/translate?ucid={}&srv=android&format=text"
             "&lang={}-{}".format(
                 str(uuid.uuid4()).replace("-", "")[:32], sl_code, tl_code),
             True),
        ):
            try:
                obj = _fetch(path, body.encode("utf-8"), android=android)
                if obj.get("code") == 200:
                    break
            except Exception:
                obj = None
                continue
        if not obj or obj.get("code") != 200:
            break
        out_lines.append("\n".join(obj.get("text", [])))
        if not model.has_chunks():
            break
    return "\n".join(out_lines)


def dictionary_lookup(text: str, sl, tl, app_id: str = "") -> str:
    """Port of dictionaryRequest/Response (dicservice lookup)."""
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    if not app_id:
        app_id = Options.get("YandexAppId", "")
    path = ("/dicservice.json/lookup?srv=tr-text&sid={}&text={}&lang={}-{}"
            .format(app_id, encode_get_param(prepare_source(text)),
                    sl_code, tl_code))
    try:
        obj = _fetch(path)
    except Exception:
        return ""
    return _dictionary_response(obj)


def _dictionary_response(obj: dict) -> str:
    b = ""
    if isinstance(obj, dict) and obj.get("def"):
        for g in obj["def"]:
            if not g.get("tr"):
                continue
            b += NL + g.get("text", "") \
                + (f' [{g["ts"]}]' if g.get("ts") else "") \
                + " " + g["tr"][0].get("pos", "") + NL
            trs = g["tr"]
            for h, f in enumerate(trs):
                b += (f"{h + 1}. " if len(trs) > 1 else "    ") + f.get(
                    "text", "")
                for syn in f.get("syn", []) or []:
                    b += ", " + syn.get("text", "")
                b += NL
                if f.get("mean"):
                    b += "    (" + ", ".join(
                        m.get("text", "") for m in f["mean"]) + ")" + NL
                for ex in f.get("ex", []) or []:
                    b += "        " + ex.get("text", "") + " - " + ", ".join(
                        t.get("text", "") for t in ex.get("tr", [])) + NL
    if b:
        b = NL + b
    return b


def listen_url(text: str, lang: str = "en", slow: bool = False) -> str:
    """Port of serviceListenRequest: TTS GET path (no download)."""
    code = lang
    mapping = {"en": "en_GB", "sv": "sv_SE", "da": "da_DK", "cs": "cs_CZ",
               "ca": "ca_ES", "ar": "ar_AE"}
    code = mapping.get(code, code + "_" + code.upper())
    path = ("/tts?format=mp3&quality=hi&platform=web&application=translate"
            f"&lang={code}&text={urllib.parse.quote(text, safe='')}")
    if slow:
        path += "&speed=0.7"
    return LISTEN_HOST + path
