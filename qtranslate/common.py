"""Port of QTranslate Common.js framework.

Reversed from: C:/Program Files (x86)/QTranslate/Services/Common.js
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field

MAX_URI_LEN = 1800
MAX_SOURCE_LEN = 5000
NL = "\r\n"
NL2 = "\r\n\r\n"

UNKNOWN_LANGUAGE_CODE = -1
UNKNOWN_LANGUAGE = 0
AUTO_DETECT_LANGUAGE = 1
ENGLISH_LANGUAGE = 17


class Capability:
    TRANSLATE = 1
    DETECT_LANGUAGE = 2
    DETECT = 2
    LISTEN = 4
    DICTIONARY = 8


class HttpMethod:
    UNDEFINED = 0
    GET = 1
    POST = 2


class CodePage:
    WINDOWS1251 = 1251
    UTF8 = 65001
    ISO8859_1 = 28591


@dataclass
class ServiceHeader:
    id: int
    name: str = ""
    info: str = ""
    capabilities: int = 0


@dataclass
class RequestData:
    method: int
    uri: str = ""
    data: str = ""
    headers: str = ""
    codepage: int = CodePage.UTF8
    response_handler: str = ""


@dataclass
class ResponseData:
    translation: str = ""
    source_language: int | None = None
    translation_language: int | None = None
    data: str = ""
    next_request_handler: str = ""


def encode_uri_param(value: str | None) -> str:
    if not value:
        return ""
    return urllib.parse.quote(str(value), safe="")


def encode_get_param(value: str | None) -> str:
    enc = encode_uri_param(value or "")
    if len(enc) > MAX_URI_LEN:
        enc = enc[:MAX_URI_LEN]
        cut = enc.rfind("%20")
        if cut > 0:
            return enc[:cut]
    return enc


def encode_post_param(value: str | None) -> str:
    return encode_uri_param(value or "")


def limit_source(text: str | None, limit: int = MAX_SOURCE_LEN) -> str:
    if not text:
        return ""
    return text[:limit] if len(text) > limit else text


def prepare_source(text: str | None) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def format_q(template: str, *args) -> str:
    out = template
    for i, arg in enumerate(args):
        out = re.sub(r"\{" + str(i) + r"\}", str(arg), out)
    return out


def parse_json_lenient(text: str):
    return json.loads(text)


def strip_html(html: str | None) -> str:
    if not html:
        return ""
    text = re.sub(r"<!--[\s\S]*?-->", "", html)
    text = re.sub(r"<(style|script)(.|\s)*?(style|script)>", "", text)
    text = re.sub(r"<br/>", NL, text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"&#x27;", "'", text, flags=re.IGNORECASE)
    text = re.sub(r" +(?= )", "", text)
    text = text.replace("\r", "")
    lines = text.split("\n")
    lines = ["" if not re.search(r"[\S]", ln) else ln for ln in lines]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n", NL, text)
    return text.strip()


def string_find_sub(
    text: str, start: str | re.Pattern, from_start: bool,
    end: str | re.Pattern, include_end: bool,
) -> str:
    """Port of stringFindSub(a,b,c,d,e) in Common.js."""
    if not text or not start or not end:
        return ""

    def _find(hay: str, needle):
        if isinstance(needle, str):
            idx = hay.find(needle)
            if idx == -1:
                return None
            return (idx, len(needle))
        m = re.search(needle, hay)
        if not m:
            return None
        return (m.start(), len(m.group(0)))

    first = _find(text, start)
    if not first:
        return ""
    rest = text[first[0]:] if from_start else text[first[0] + first[1]:]
    second = _find(rest, end)
    if not second:
        return ""
    cut = second[0] + second[1] if include_end else second[0]
    return rest[:cut]
