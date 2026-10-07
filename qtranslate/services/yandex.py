"""Yandex service port.

Reversed from: C:/Program Files (x86)/QTranslate/Services/Yandex/Service.js
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

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
    r"(\n+)", r"([.!?;\u0964](?:\s+|$))", r"([\-\u2012-\u2015](?:\s+|$))",
    r"([,:](?:\s+|$))", r"([\u3002\uff01\uff1f\uff1b\u2026])",
    r"([\uff0c\uff1a])", r"(\s+)",
]


def _truncate_text(text: str) -> str:
    """Port of YandexModel._truncateText: max-600-char chunk at a boundary."""
    if not text or len(text) <= 600:
        return text
    head = text[:600]
    for pattern in _TRUNC_PATTERNS:
        match = re.search(pattern, head)
        if match:
            keep = head[: match.start()]
            for group in match.groups():
                if group is not None:
                    keep += ""
            # split with capture then drop tail, mirroring stringSplit().slice(0,-1)
            bits = re.split("(" + pattern + ")", head)
            if len(bits) > 1:
                return "".join(bits[:-1])
            return keep
    return head


def make_chunks(text: str) -> list[str]:
    """Port of YandexModel._makeChunks."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")[:10000]
    chunks: list[str] = []
    while text:
        piece = _truncate_text(text)
        if not piece:
            break
        chunks.append(piece)
        text = text[len(piece):]
    return chunks


def detect(text: str, app_id: str = "") -> str:
    """Port of serviceDetectLanguageRequest/Response: GET /api/v1/tr.json/detect."""
    query = urllib.parse.quote(text[:256], safe="")
    path = "/api/v1/tr.json/detect?sid={}&srv=tr-text&text={}".format(app_id, query)
    req = urllib.request.Request(
        HOST + path, headers={"Accept": "*/*", "Referer": "https://translate.yandex.com"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    if obj.get("code") == 200:
        return obj.get("lang", "")
    return ""


def translate(text: str, sl: str = "", tl: str = "en", app_id: str = "") -> str:
    """Port of serviceTranslateRequest/Response: POST /api/v1/tr.json/translate."""
    chunks = make_chunks(text)
    out_lines: list[str] = []
    for chunk in chunks:
        path = (
            "/api/v1/tr.json/translate?id={}-0-0&srv=tr-text&lang={}-{}"
            "&reason=auto&format=text&yu=2210680511641235828"
        ).format(app_id, sl, tl)
        body = "text=" + urllib.parse.quote(chunk, safe="")
        req = urllib.request.Request(
            HOST + path,
            data=body.encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "Accept": "*/*",
                "Referer": "https://translate.yandex.com",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
        if obj.get("code") == 200:
            out_lines.append("\n".join(obj.get("text", [])))
    return "\n".join(out_lines)


def listen_url(text: str, lang: str = "en", slow: bool = False) -> str:
    """Port of serviceListenRequest: TTS GET path (no download)."""
    code = lang
    mapping = {
        "en": "en_GB", "sv": "sv_SE", "da": "da_DK", "cs": "cs_CZ",
        "ca": "ca_ES", "ar": "ar_AE",
    }
    code = mapping.get(code, code + "_" + code.upper())
    path = "/tts?format=mp3&quality=hi&platform=web&application=translate&lang={}&text={}".format(
        code, urllib.parse.quote(text, safe="")
    )
    if slow:
        path += "&speed=0.7"
    return LISTEN_HOST + path
