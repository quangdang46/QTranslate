"""1:1 port of Services/youdao/Service.js (SERVICE_ID=26).

Covers the whole file: serviceHeader/Host/Link, makeSign
(Utils.md5("fanyideskweb"+text+salt+key)), translate pair (with the
b.type "xx2yy" lang resolution), dictionary pair (results-contents
slice + full style block + updateHtmlLinks), buildUri,
SupportedLanguages.

Current-web EXTENSION (reversed 2026-10-07, LIVE-OK, clearly marked):
translate_web() via dict.youdao.com/jsonapi_s (no sign needed).
The legacy /translate_o returns errorCode 50 (needs mysticTime).
"""
from __future__ import annotations

import hashlib
import json
import random
import time
import urllib.parse
import urllib.request

from qtranslate.common import (
    NL,
    NL2,
    Capability,
    ServiceHeader,
    code_from_language,
    encode_get_param,
    format_q,
    is_language,
    language_from_code,
    limit_source,
    parse_json_lenient,
    get_header,
    prepare_source,
    read_response_text,
    remove_attributes,
    string_find_sub,
    update_html_links,
)

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


def service_header() -> ServiceHeader:
    return ServiceHeader(
        26, "youdao",
        "有道翻译提供即时免费的中、英、日、韩、法、俄、西班牙文全文翻译、"
        "网页翻译服务。" + NL2 + "https://fanyi.youdao.com/" + NL2 +
        "© 2022 网易公司 京ICP备0802688号",
        Capability.TRANSLATE | Capability.DICTIONARY)


def service_host(capability: int = Capability.TRANSLATE) -> str:
    if capability == Capability.TRANSLATE:
        return "fanyi.youdao.com"
    return "dict.youdao.com"


def service_link(is_dict: bool = False) -> str:
    return "https://" + ("dict.youdao.com" if is_dict else "fanyi.youdao.com")


def make_sign(text: str, salt: str) -> str:
    """Port of Utils.md5("fanyideskweb" + text + salt + key)."""
    raw = "fanyideskweb" + text + salt + _SIGN_KEY
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def translate(text: str, sl="AUTO", tl: str = "en",
              opener=None) -> tuple:
    """Port of translate pair. Returns (text, src_index, tl_index).

    sl/tl accept indices or codes. b.type "xx2yy" resolves both langs.
    Legacy /translate_o returns errorCode 50 (needs mysticTime) — the
    working path is translate_web() below (EXTENSION).
    """
    text = limit_source(prepare_source(text))
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    salt = str(int(time.time() * 1000) + int(random.random() * 10))
    sign = make_sign(text, salt)
    body = format_q(
        "i={0}&from={1}&to={2}&smartresult=dict&client={3}&salt={4}"
        "&sign={5}&doctype=json&version=2.1&keyfrom=fanyi.web",
        urllib.parse.quote(text, safe=""), sl_code, tl_code,
        "fanyideskweb", salt, sign)
    headers = dict(_split(get_header()))
    headers["Referer"] = service_link()
    headers["Cookie"] = "OUTFOX_SEARCH_USER_ID=1@100.1.1.1;"
    req = urllib.request.Request(
        HOST + "/translate_o?smartresult=dict&smartresult=rule",
        data=body.encode("utf-8"), headers=headers)
    open_ = opener.open if opener else urllib.request.urlopen
    with open_(req, timeout=20) as resp:
        obj = parse_json_lenient(read_response_text(resp))
    return _translate_response(obj)


def _split(header_block: str) -> dict:
    from qtranslate.common import split_headers
    return split_headers(header_block)


def _translate_response(obj: dict) -> tuple:
    from qtranslate.common import UNKNOWN_LANGUAGE
    out = ""
    sl_idx = tl_idx = UNKNOWN_LANGUAGE
    if not obj:
        return out, sl_idx, tl_idx
    for block in obj.get("translateResult", []) or []:
        for item in block:
            out += item.get("tgt", "") or ""
        out += NL
    for entry in (obj.get("smartResult") or {}).get("entries", []) or []:
        out += str(entry) + NL
    if obj.get("type"):
        t = obj["type"]
        c = t.find("2")
        if c > -1:
            sl_idx = language_from_code(t[:c], SUPPORTED_LANGS)
            tl_idx = language_from_code(t[c + 1:], SUPPORTED_LANGS)
    return out, sl_idx, tl_idx


_STYLE_BLOCK = (
    "<div><style>p.via,span.via{color: #959595}.trans-wrapper h3{font-size:130%;"
    "border-bottom:2px solid #ddd}.clearfix:after{content:\".\";display:block;"
    "height:0;visibility:hidden;clear:both}.clearfix{zoom:1}.img-list{float:right}"
    ".img-list img{height:80px;padding:2px;border:1px solid #e5e5e5}"
    ".keyword{margin-right:1px;vertical-align:bottom;margin-right:15px}"
    ".baav{margin-top:3px}.pronounce{margin-right:30px;color:#666;"
    "display:inline-block;line-height:26px}.pronounce .phonetic{margin-left:.2em}"
    ".phonetic,.field,.origin,.complexfont{font-weight:normal;color:#666;"
    "margin:0 .1em}.gray{color:#a0a0a0}"
    ".collinsMajorTrans{background:#eff5f8;padding:5px 5px 5px 25px;width:525px}"
    ".additional{color:#959595}.trans-container .ol li{list-style-type:decimal;"
    "list-style-position:inside;margin:0 0 .7em 0}"
    ".trans-container p,.trans-container li {line-height: 24px}</style><div>"
)


def build_uri(text: str) -> str:
    """Port of buildUri(a,b,d)."""
    return format_q("/w/{0}/", encode_get_param(text))


def dictionary_url(text: str) -> str:
    return DICT_HOST + build_uri(text)


_UA_DICT = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def dictionary(text: str, sl="AUTO", tl: str = "en",
               opener=None) -> tuple:
    """Port of dictionary pair. Returns (html, sl, tl, link).

    Same slice + style block + attribute strip + link update as the
    native serviceDictionaryResponse.
    """
    path = build_uri(text)
    req = urllib.request.Request(DICT_HOST + path, headers=_UA_DICT)
    open_ = opener.open if opener else urllib.request.urlopen
    with open_(req, timeout=20) as r:
        page = read_response_text(r)
    frag = string_find_sub(
        page, '<div id="results-contents" class="results-content">', False,
        '<div id="ads"', False)
    frag = remove_attributes(
        _STYLE_BLOCK + frag,
        ["id", "name", "onmouseover", "onmouseout", "onmousedown"])
    host = service_host(Capability.DICTIONARY)
    link = "https://" + host + build_uri(text)
    frag = update_html_links(frag, host)
    return frag, sl, tl, link


# ------------------------------------------------- EXTENSION: current web API
# (reversed 2026-10-07 from translation-website 1.0.7 bundle; LIVE-OK)

def translate_web(text: str, sl: str = "en", tl: str = "zh-CHS",
                  opener=None) -> str:
    """Live translate via dict.youdao.com/jsonapi_s — verified 2026-10-07.

    Reversed from the translation-website 1.0.7 bundle
    (VUE_APP_JSON_API_URL + VUE_APP_JSON_API_SIGN_SECRET_KEY). The
    endpoint answers with NO sign at all for plain q/from/to/client —
    web_trans.web-translation[].trans[].value holds the result.
    """
    body = urllib.parse.urlencode(
        {"q": text[:5000], "from": sl, "to": tl,
         "client": "fanyideskweb"}).encode()
    req = urllib.request.Request(
        DICT_HOST + "/jsonapi_s?doctype=json&jsonversion=4",
        data=body,
        headers={**_UA_DICT,
                 "Content-Type": "application/x-www-form-urlencoded",
                 "Referer": "https://fanyi.youdao.com/"})
    open_ = opener.open if opener else urllib.request.urlopen
    with open_(req, timeout=20) as r:
        obj = json.loads(read_response_text(r))
    out = []
    for block in (obj.get("web_trans") or {}).get("web-translation", []) or []:
        for tr in block.get("trans", []) or []:
            if tr.get("value"):
                out.append(tr["value"])
    return "\n".join(out)
