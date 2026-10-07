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


def trim_string(s: str | None) -> str:
    """Port of trimString(a)."""
    return re.sub(r"(^\s+)|(\s+$)", "", s) if s else ""


def starts_with(s: str, prefix: str) -> bool:
    return s[:len(prefix)] == prefix


def ends_with(s: str, suffix: str) -> bool:
    return suffix in s[len(s) - len(suffix):]


def remove_if_starts_with(s: str, prefix: str) -> str:
    return s[len(prefix):] if starts_with(s, prefix) else s


def unquote_html(s: str | None) -> str:
    """Port of unquoteHtml(a)."""
    if not s:
        return ""
    s = re.sub(r"&amp[;]?", "&", s)
    s = re.sub(r"&lt[;]?", "<", s)
    s = re.sub(r"&gt[;]?", ">", s)
    s = re.sub(r"&quot[;]?", '"', s)
    return re.sub(r"&#[0]?39[;]?", "'", s)


def remove_empty_lines(s: str | None) -> str:
    """Port of removeEmptyLines(a)."""
    if not s:
        return ""
    s = s.replace("\r", "")
    lines = [" " if re.match(r"^\s*$", ln) else ln for ln in s.split("\n")]
    return "\n".join(lines)


def reg_exp_remove(s: str, tags: list, fmt: str) -> str:
    """Port of regExpRemove(a,b,c): format(c, tags.join('|')) as regex."""
    if not s or not tags:
        return s
    return re.sub(fmt.format("|".join(tags)), "", s, flags=re.S)


def remove_attributes(s: str, attrs: list) -> str:
    """Port of removeAttributes(a,b)."""
    return reg_exp_remove(
        s, attrs,
        r" ({0})(?:\s*=\s*(?:(?:\"((?:\\.|[^\"])*)\")|(?:'((?:\\.|[^'])*)')|([^>\s]+)))?")


def remove_tags(s: str, tags: list) -> str:
    """Port of removeTags(a,b)."""
    return reg_exp_remove(s, tags, r"</?({0})[^>]*>")


def remove_elements(s: str, tags: list) -> str:
    """Port of removeElements(a,b)."""
    return reg_exp_remove(s, tags, r"<\s*({0})[^>]*>((.|\n)*?)<\s*/\s*({0})>")


def update_html_links(html: str | None, base: str) -> str:
    """Port of updateHtmlLinks(a,b): absolutize href/src against base."""
    if not html:
        return ""
    scheme = "https://" if starts_with(base, "https") else "http://"
    base = remove_if_starts_with(base, scheme)
    if not ends_with(base, "/"):
        base += "/"
    html = re.sub(r'href="//', f'href="{scheme}', html, flags=re.I)
    html = re.sub(r'href="/', f'href="{scheme}{base}', html, flags=re.I)
    html = re.sub(r'src="//', f'src="{scheme}', html, flags=re.I)
    html = re.sub(r'src="/', f'src="{scheme}{base}', html, flags=re.I)
    html = re.sub(r"href='//", f"href='{scheme}", html, flags=re.I)
    html = re.sub(r"href='/", f"href='{scheme}{base}", html, flags=re.I)
    html = re.sub(r"src='//", f"src='{scheme}", html, flags=re.I)
    return re.sub(r"src='/", f"src='{scheme}{base}", html, flags=re.I)


def is_language(idx: int, langs: list) -> bool:
    """Port of isLanguage(a): 1 < a < len(SupportedLanguages)."""
    return 1 < idx < len(langs)


def code_from_language(idx: int, langs: list):
    """Port of codeFromLanguage(a)."""
    if idx == 1 or is_language(idx, langs):
        return langs[idx]
    return -1


def language_from_code(code: str, langs: list) -> int:
    """Port of languageFromCode(a). ENGLISH_LANGUAGE == 17 fast path."""
    try:
        if langs[17] == code:
            return 17
    except IndexError:
        pass
    for i in range(1, len(langs)):
        if langs[i] == code:
            return i
    return 0
