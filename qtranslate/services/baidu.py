"""1:1 port of Services/Baidu/Service.js (SERVICE_ID=28).

Covers the whole file: serviceHeader/Host/Link, sign(), detect
request/response, translate request/response (trans_result +
dict_result branches), serviceListenRequest, SupportedLanguages,
plus suggest() via the live /sug endpoint (reversed 2026-10-07).
v2transapi translate needs live gtk+token (JS-rendered) — errno 1022
without them; detect + suggest are LIVE-OK.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from qtranslate import common

from qtranslate.common import (
    NL,
    UNKNOWN_LANGUAGE,
    Capability,
    ServiceHeader,
    code_from_language,
    encode_get_param,
    format_q,
    is_language,
    language_from_code,
    limit_source,
    parse_json_lenient,
    post_header,
    prepare_source,
    read_response_text,
    split_headers,
    Options,
)

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


def service_header() -> ServiceHeader:
    return ServiceHeader(
        28, "Baidu",
        "Baidu Translate is a free online translation service." + NL
        + service_host() + NL + "© 2018 Baidu",
        Capability.TRANSLATE | Capability.DETECT_LANGUAGE | Capability.LISTEN)


def service_host(capability: int = Capability.TRANSLATE) -> str:
    if capability == Capability.LISTEN:
        return "https://tts.baidu.com"
    return "https://fanyi.baidu.com"


def service_link(text="", sl=-1, tl=-1) -> str:
    g = service_host()
    if text:
        d = code_from_language(sl, SUPPORTED_LANGS) \
            if is_language(sl, SUPPORTED_LANGS) else "auto"
        e = code_from_language(tl, SUPPORTED_LANGS) \
            if is_language(tl, SUPPORTED_LANGS) else "auto"
        g += format_q("/#{0}/{1}/{2}", d, e, encode_get_param(text))
    return g


def _mix(value: int, ops: str) -> int:
    """Port of inner function a(b,d) used by sign()."""
    for e in range(0, len(ops) - 2, 3):
        digit = ops[e + 2]
        shift = (ord(digit) - 87) if "a" <= digit else int(digit)
        shifted = (value >> shift) if ops[e + 1] == "+" \
            else (value << shift) & 0xFFFFFFFF
        value = ((value + shifted) & 0xFFFFFFFF) \
            if ops[e] == "+" else (value ^ shifted)
    return value & 0xFFFFFFFF


def sign(text: str, gtk: str = "0.0") -> str:
    """Port of sign(b,d): Baidu request signature from page GTK seed."""
    if len(text) > 30:
        text = text[:10] + text[len(text) // 2 - 5:len(text) // 2 + 5] \
            + text[-10:]
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
            if (ch & 64512) == 55296 and i + 1 < len(text) \
                    and (ord(text[i + 1]) & 64512) == 56320:
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


def suggest(text: str) -> list:
    """Autocomplete via POST /sug {kw} — verified live 2026-10-07.

    Reversed from headless traffic capture (per-keystroke POSTs while
    typing in the Baidu input box). Returns [{k, v}] entries. No auth.
    """
    body = "kw=" + urllib.parse.quote((text or "")[:100], safe="")
    req = urllib.request.Request(
        HOST + "/sug", data=body.encode("utf-8"),
        headers={"Content-Type":
                 "application/x-www-form-urlencoded; charset=utf-8",
                 "Accept": "*/*",
                 "Referer": "https://fanyi.baidu.com/",
                 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    for _try in range(2):
        try:
            with common.http_open(req) as resp:
                obj = json.loads(
                    resp.read().decode("utf-8", errors="replace"))
            data = obj.get("data", []) if isinstance(obj, dict) else []
            if data or _try == 1:
                return data
        except Exception:
            if _try == 1:
                return []
        import time as _t
        _t.sleep(1.0)
    return []


def detect(text: str, cookie: str = "") -> int:
    """Port of detect request/response. Returns a lang *index*."""
    body = "query=" + urllib.parse.quote(limit_source(text)[:100], safe="")
    headers = dict(split_headers(post_header()))
    headers["Cookie"] = cookie or Options.get("BaiduCookie", "")
    req = urllib.request.Request(HOST + "/langdetect",
                                 data=body.encode("utf-8"), headers=headers)
    with common.http_open(req) as resp:
        obj = parse_json_lenient(read_response_text(resp))
    if obj and obj.get("lan"):
        return language_from_code(obj["lan"], SUPPORTED_LANGS)
    return UNKNOWN_LANGUAGE


def detect_code(text: str, cookie: str = "") -> str:
    """Convenience: detect() resolved to a language code string."""
    return code_from_language(detect(text, cookie), SUPPORTED_LANGS)


def translate(text: str, sl="auto", tl: str = "en", gtk: str = "0.0",
              token: str = "", cookie: str = "") -> str:
    """Port of translate request/response (trans + dict_result branches).

    sl/tl accept indices or codes. gtk/token/cookie default to the
    Options.Baidu* session values (scraped from the Baidu page).
    """
    text = limit_source(prepare_source(text))
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    query = urllib.parse.quote(text, safe="").replace("%20", "+")
    gtk = gtk if gtk != "0.0" else Options.get("BaiduGtk", "0.0")
    token = token or Options.get("BaiduToken", "")
    body = ("query={}&from={}&to={}&simple_means_flag=3&sign={}&token={}"
            .format(query, sl_code, tl_code, sign(text, gtk), token))
    headers = split_headers(post_header())
    headers["Cookie"] = cookie or Options.get("BaiduCookie", "")
    req = urllib.request.Request(HOST + "/v2transapi",
                                 data=body.encode("utf-8"), headers=headers)
    with common.http_open(req) as resp:
        obj = parse_json_lenient(read_response_text(resp))
    return _translate_response(obj)


def _translate_response(obj: dict) -> str:
    b = ""
    if not obj:
        return b
    trans = (obj.get("trans_result") or {}).get("data", [])
    sl_idx = tl_idx = UNKNOWN_LANGUAGE
    if trans:
        for item in trans:
            b += NL * item.get("prefixWrap", 0)
            b += (item.get("dst") or "") + NL
        sl_idx = language_from_code(
            (obj.get("trans_result") or {}).get("from", ""), SUPPORTED_LANGS)
        tl_idx = language_from_code(
            (obj.get("trans_result") or {}).get("to", ""), SUPPORTED_LANGS)
    simple = ((obj.get("dict_result") or {}).get("simple_means") or {})
    symbols = simple.get("symbols") if isinstance(simple, dict) else None
    if symbols:
        b += NL
        for sym in symbols:
            for part in sym.get("parts", []) or []:
                if part.get("part"):
                    b += "[" + part["part"] + "] "
                b += "; ".join(part.get("means", []) or []) + NL
    else:
        content = (obj.get("dict_result") or {}).get("content")
        if content:
            b += NL
            for entry in content:
                for mean in (entry.get("mean") or []):
                    b += mean.get("pre", "") + " "
                    for h in (mean.get("cont") or {}):
                        b += h
                    b += NL
    return b


def listen_url(text: str, lang: str = "en", slow: bool = False) -> str:
    """Port of serviceListenRequest: TTS GET path (no download)."""
    code = code_from_language(lang, SUPPORTED_LANGS) \
        if isinstance(lang, int) else lang
    path = "/text2audio?lan={}&ie=UTF-8&text={}".format(
        code, urllib.parse.quote(text, safe=""))
    if slow:
        path += "&spd=1"
    return LISTEN_HOST + path
