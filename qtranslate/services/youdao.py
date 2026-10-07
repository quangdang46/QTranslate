"""Youdao service port.

Reversed from: C:/Program Files (x86)/QTranslate/Services/youdao/Service.js
"""
from __future__ import annotations

import hashlib
import json
import random
import time
import urllib.parse
import urllib.request

SERVICE_ID = 26
SERVICE_NAME = "youdao"
HOST = "https://fanyi.youdao.com"
DICT_HOST = "https://dict.youdao.com"

SUPPORTED_LANGS = [
    -1, "AUTO", -1, -1, -1, "ar", -1, -1, -1, -1, -1, "zh-CHS", "zh-CHS",
    -1, -1, -1, -1, "en", -1, -1, -1, "fr", -1, "de", -1, -1, -1, -1,
    -1, -1, "id", "it", -1, "ja", -1, "ko", -1, -1, -1, -1, -1, -1, -1,
    -1, "pt", -1, "ru", -1, -1, -1, "es", -1, -1, -1, -1, -1, -1, "vi",
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1,
]

_SIGN_KEY = "Y2FYu%TNSbMCxc3t2u^XT"


def make_sign(text: str, salt: str) -> str:
    """Port of Utils.md5("fanyideskweb" + text + salt + key)."""
    raw = "fanyideskweb" + text + salt + _SIGN_KEY
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def translate(text: str, sl: str = "AUTO", tl: str = "en",
              opener=None) -> str:
    """Port of serviceTranslateRequest/Response: POST /translate_o.

    Pass a shared-jar opener (qtranslate.session._jar_opener after GETting
    the landing page) so the live OUTFOX_SEARCH_USER_ID cookie is used
    instead of the hardcoded placeholder — mirrors the engine cookie jar.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")[:5000]
    salt = str(int(time.time() * 1000) + int(random.random() * 10))
    sign = make_sign(text, salt)
    body = (
        "i={}&from={}&to={}&smartresult=dict&client={}&salt={}&sign={}"
        "&doctype=json&version=2.1&keyfrom=fanyi.web"
    ).format(
        urllib.parse.quote(text, safe=""), sl, tl, "fanyideskweb", salt, sign
    )
    req = urllib.request.Request(
        HOST + "/translate_o?smartresult=dict&smartresult=rule",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Accept": "*/*",
            "Referer": "https://fanyi.youdao.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        },
    )
    if opener is None:
        req.add_header("Cookie", "OUTFOX_SEARCH_USER_ID=1@100.1.1.1;")
        with urllib.request.urlopen(req, timeout=20) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
    else:
        with opener.open(req, timeout=20) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
    out = ""
    for block in obj.get("translateResult", []) or []:
        for item in block:
            out += item.get("tgt", "") or ""
        out += "\r\n"
    for entry in (obj.get("smartResult") or {}).get("entries", []) or []:
        out += str(entry) + "\r\n"
    return out


def dictionary_url(text: str) -> str:
    """Port of buildUri(a,b,d): dictionary page path on dict host."""
    return DICT_HOST + "/w/{}/".format(urllib.parse.quote(text, safe=""))
