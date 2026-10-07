"""Baidu service port.

Reversed from: C:/Program Files (x86)/QTranslate/Services/Baidu/Service.js
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

SERVICE_ID = 28
SERVICE_NAME = "Baidu"
HOST = "https://fanyi.baidu.com"
LISTEN_HOST = "https://tts.baidu.com"

SUPPORTED_LANGS = [
    -1, -1, -1, -1, -1, "ara", -1, -1, -1, "bul", -1, "zh", "cht", -1,
    "cs", "dan", "nl", "en", "est", "fin", -1, "fra", -1, "de", "el",
    -1, -1, -1, "hu", -1, -1, "it", -1, "jp", -1, "kor", -1, -1, -1,
    -1, -1, -1, -1, "pl", "pt", "rom", "ru", -1, -1, "slo", "spa", -1,
    "swe", "th", -1, -1, -1, "vie", -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1, -1,
]


def _mix(value: int, ops: str) -> int:
    """Port of inner function a(b,d) used by sign()."""
    for e in range(0, len(ops) - 2, 3):
        digit = ops[e + 2]
        shift = (ord(digit) - 87) if "a" <= digit else int(digit)
        shifted = (value >> shift) if ops[e + 1] == "+" else (value << shift) & 0xFFFFFFFF
        value = ((value + shifted) & 0xFFFFFFFF) if ops[e] == "+" else (value ^ shifted)
    return value & 0xFFFFFFFF


def sign(text: str, gtk: str = "0.0") -> str:
    """Port of sign(b,d): Baidu request signature from page GTK seed."""
    if len(text) > 30:
        text = text[:10] + text[len(text) // 2 - 5:len(text) // 2 + 5] + text[-10:]
    parts = gtk.split(".")
    e = int(parts[0]) if parts[0] else 0
    g = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    codepoints: list[int] = []
    i = 0
    while i < len(text):
        ch = ord(text[i])
        if ch < 128:
            codepoints.append(ch)
        elif ch < 2048:
            codepoints.append((ch >> 6) | 192)
        else:
            if (ch & 64512) == 55296 and i + 1 < len(text) and (ord(text[i + 1]) & 64512) == 56320:
                ch = 65536 + ((ch & 1023) << 10) + (ord(text[i + 1]) & 1023)
                i += 1
                codepoints.append((ch >> 18) | 240)
                codepoints.append(((ch >> 12) & 63) | 128)
            else:
                codepoints.append((ch >> 12) | 224)
            codepoints.append(((ch >> 6) & 63) | 128)
        codepoints.append((ch & 63) | 128)
        i += 1
    c = e
    for cp in codepoints:
        c = _mix(c + cp, "+-a^+6")
    c = _mix(c, "+-3^+b+-f")
    c ^= g
    if c < 0:
        c = (c & 2147483647) + 2147483648
    c %= 1000000
    return "{}.{}".format(c, c ^ e)


def detect(text: str, cookie: str = "") -> str:
    """Port of serviceDetectLanguageRequest/Response: POST /langdetect."""
    body = "query=" + urllib.parse.quote((text or "")[:100], safe="")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Accept": "*/*",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(
        HOST + "/langdetect", data=body.encode("utf-8"), headers=headers
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    return obj.get("lan", "") if isinstance(obj, dict) else ""


def translate(
    text: str,
    sl: str = "auto",
    tl: str = "en",
    gtk: str = "0.0",
    token: str = "",
    cookie: str = "",
) -> str:
    """Port of serviceTranslateRequest/Response: POST /v2transapi."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")[:5000]
    query = urllib.parse.quote(text, safe="").replace("%20", "+")
    body = "query={}&from={}&to={}&simple_means_flag=3&sign={}&token={}".format(
        query, sl, tl, sign(text, gtk), token
    )
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Accept": "*/*",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(
        HOST + "/v2transapi", data=body.encode("utf-8"), headers=headers
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    out = ""
    trans = (obj.get("trans_result") or {}).get("data", []) if obj else []
    for item in trans:
        out += "\r\n" * item.get("prefixWrap", 0)
        out += (item.get("dst") or "") + "\r\n"
    return out


def listen_url(text: str, lang: str = "en", slow: bool = False) -> str:
    """Port of serviceListenRequest: TTS GET path (no download)."""
    path = "/text2audio?lan={}&ie=UTF-8&text={}".format(
        lang, urllib.parse.quote(text, safe="")
    )
    if slow:
        path += "&spd=1"
    return LISTEN_HOST + path
