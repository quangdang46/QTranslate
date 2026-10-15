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


# encodeURIComponent's unreserved set is NOT urllib's default safe set:
# JS leaves  ! ' ( ) *  unencoded while quote(safe="") percent-encodes
# all four (plus the star). Measured over every printable ASCII char.
_URI_UNRESERVED = "-_.!~*'()"


def encode_uri_param(value: str | None) -> str:
    """Port of ``encodeUriParam(a)`` -- i.e. ``encodeURIComponent``.

    Recovered `Common.js` (NSIS chunk at `0x13af4`)::

        function encodeUriParam(a){return a?encodeURIComponent(a):""}

    The port used ``quote(value, safe="")``, which percent-encodes
    ``! ' ( ) *`` -- five characters ``encodeURIComponent`` leaves alone.
    Every request parameter in the port goes through here, and a provider
    that validates a signature computed over the encoded form sees a
    different string than the one the web client sends.
    """
    if not value:
        return ""
    return urllib.parse.quote(str(value), safe=_URI_UNRESERVED)


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
    """Port of ``parseJSON(a)`` -- which is NOT ``JSON.parse``.

    The recovered `Common.js` (NSIS chunk at `0x13af4`) is::

        function parseJSON(a){return(new Function("return "+a))()}

    i.e. native **evaluates** the text as a JavaScript expression. So
    native happily accepts shapes strict JSON rejects: single-quoted
    keys and strings, unquoted keys, trailing commas, hex/octal
    literals, and surrounding whitespace or a trailing semicolon.

    This function used to be a bare ``json.loads`` while calling itself
    "lenient", so all six of those shapes raised ``JSONDecodeError``
    here and were parsed correctly by the real app. Every provider's
    response goes through one of the 28 ``parse_json_lenient`` call
    sites, so a provider emitting single quotes looked "broken" to the
    port and fine to native.

    The leniency is implemented by normalising the text, then parsing
    with ``json.loads`` -- **never** ``eval``/``exec``. A JS-literal
    shape is accepted; executable code is not. Anything still unparseable
    raises ``ValueError`` exactly as before, so callers' existing error
    handling is unchanged.
    """
    if text is None:
        raise ValueError("parse_json_lenient: no text")
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", "replace")
    if not isinstance(text, str):
        raise TypeError("parse_json_lenient: expected text")

    body = text.strip()
    if not body:
        raise ValueError("parse_json_lenient: empty text")

    try:
        # strict first: the common case costs nothing extra
        return json.loads(body)
    except ValueError:
        pass

    return json.loads(_json_expression(body))


def _json_expression(expr: str) -> str:
    """Normalise a JS object/array literal into strict JSON text.

    Handles, in order, the shapes ``new Function("return "+expr)()``
    accepts and ``json.loads`` does not: surrounding parentheses, a
    trailing semicolon, single-quoted strings (with escaped quotes),
    unquoted keys, trailing commas, and JS hex literals. Deliberately
    conservative -- anything it does not recognise is returned
    unchanged, and the caller's ``json.loads`` then raises.
    """
    s = expr.strip()
    # ( {...} );  ->  {...}  -- semicolon first, then wrapping parens
    if s.endswith(";"):
        s = s[:-1].strip()
    while s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    if not s:
        return s

    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in ("'", '"'):
            # consume one string literal, re-emitting it double-quoted
            quote = c
            i += 1
            buf = []
            while i < n:
                ch = s[i]
                if ch == "\\" and i + 1 < n:
                    nxt = s[i + 1]
                    if quote == "'" and nxt == quote and i + 2 < n \
                            and s[i + 2] == quote:
                        # \'' (or the JS '' doubling) inside a
                        # single-quoted string is one apostrophe
                        buf.append(quote)
                        i += 3
                        continue
                    if nxt == quote:
                        # an escaped copy of our own delimiter is a
                        # literal character -- keep it, unescaped inside
                        # the double-quoted output
                        buf.append(nxt)
                        i += 2
                        continue
                    buf.append(ch + nxt)
                    i += 2
                    continue
                if ch == quote:
                    i += 1
                    break
                if ch == '"' and quote == "'":
                    # apostrophes-from-double-quotes stay escaped
                    buf.append('\\"')
                    i += 1
                    continue
                buf.append(ch)
                i += 1
            out.append('"' + "".join(buf) + '"')
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        out.append(c)
        i += 1
    s = "".join(out)

    # unquoted object keys:  {a:1}  ->  {"a":1}
    s = re.sub(r'([{,]\s*)([A-Za-z_$][\w$]*)(\s*:)',
               r'\1"\2"\3', s)
    # trailing commas before } or ]
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    # JS hex literals inside values
    s = re.sub(r':\s*(0[xX][0-9a-fA-F]+)(\s*[,}\]])',
               lambda m: ':%d%s' % (int(m.group(1), 16), m.group(2)), s)
    return s


def read_response_text(resp) -> str:
    """Read a urllib response, transparently gunzipping (native sends
    `Accept-Encoding: gzip,deflate` in getHeader/postHeader)."""
    raw = resp.read()
    if resp.headers.get("Content-Encoding", "") == "gzip" \
            or raw[:2] == b"\x1f\x8b":
        import gzip
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def http_open(req, opener=None):
    """Open a request honoring Options.json Internet.Timeout + Proxy.

    Thin wrapper over session._net_open so every service port funnels
    through the native curl behavior (FUN_0045BCED/FUN_0045BF7D).
    """
    from qtranslate import session as _S
    return _S._net_open(req, opener)


def split_headers(header_block: str) -> dict:
    """Split a Common.js header block ("K: V\\r\\n...") into a dict."""
    out = {}
    for line in header_block.split("\r\n"):
        if ": " in line:
            k, v = line.split(": ", 1)
            out[k] = v
    return out


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
    """Port of ``unquoteHtml(a)`` -- exactly five entities, one mandatory.

    Recovered `Common.js` (NSIS chunk at `0x13af4`)::

        function unquoteHtml(a){if(!a)return"";
          a=a.replace(/&amp[;]?/g,"&");a=a.replace(/&lt[;]?/g,"<");
          a=a.replace(/&gt[;]?/g,">");a=a.replace(/&quot[;]?/g,'"');
          return a=a.replace(/&#[0]?39[;]/g,"'")}

    Four patterns have an OPTIONAL semicolon (``[;]?``) but the last one
    -- ``&#39`` -- has a **mandatory** one (``[;]``). The port had made
    that optional too, so a bare ``&#39`` became an apostrophe here while
    native leaves it. Exactly these five entities and nothing else: a
    ``&nbsp;`` or any other named entity is NOT unquoted.
    """
    if not s:
        return ""
    s = re.sub(r"&amp[;]?", "&", s)
    s = re.sub(r"&lt[;]?", "<", s)
    s = re.sub(r"&gt[;]?", ">", s)
    s = re.sub(r"&quot[;]?", '"', s)
    return re.sub(r"&#[0]?39[;]", "'", s)


def remove_empty_lines(s: str | None) -> str:
    """Port of removeEmptyLines(a) — exact 1:1."""
    if not s:
        return ""
    s = re.sub(r"\r", "", s, flags=re.I)
    lines = s.split("\n")
    lines = [ln if re.search(r"[\S]", ln) else "" for ln in lines]
    s = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    s = re.sub(r"\n", NL, s, flags=re.I)
    return trim_string(s)


def string_find(hay: str, needle) -> dict | None:
    """Port of stringFind(a,b): str -> indexOf, regex -> match.

    Returns {index, length} or None (JS returns undefined).
    """
    if not needle:
        return None
    if isinstance(needle, str):
        idx = hay.find(needle)
        if idx > -1:
            return {"index": idx, "length": len(needle)}
        return None
    m = re.search(needle, hay)
    if m:
        return {"index": m.start(), "length": len(m.group(0))}
    return None


def string_split(s: str, pattern) -> list:
    """Port of stringSplit(a,b).

    The IE_SPLIT_ISSUE workaround (manual capture-group splice) is
    exactly what Python's re.split() does natively, so this is 1:1.
    """
    return re.split(pattern, s)


def uses_auto_detect_code(langs: list) -> bool:
    """Port of usesAutoDetectCode()."""
    try:
        return langs[AUTO_DETECT_LANGUAGE] != UNKNOWN_LANGUAGE_CODE
    except IndexError:
        return False


def js_number(seg) -> int:
    """Port of ``Number(x)||0`` -- the seed coercion two providers share.

    Native's request-signing code seeds from a page-scraped numeric string
    and coerces each ``.``-segment with ``Number(...)||0``:
    ``Service.js``'s Google ``tk`` (``Number(c[0])||0``,
    ``a^=Number(c[1])||0``) and Baidu ``sign`` (``Number(g[i])||0``).

    The semantics that matter:

    * an **empty** segment is ``0`` (``Number("")===0``);
    * a **non-numeric** segment is ``NaN``, which is falsy, so it also
      becomes ``0`` -- native does not reject it;
    * ``Number`` accepts floats and leading/trailing whitespace, truncating
      a float toward zero;
    * ``"Infinity"``/``"-Infinity"`` are **truthy**, so they are NOT
      rewritten to 0 -- they stay infinity. The bitwise mixing downstream
      then turns them into ``0`` (JS ``ToInt32(Infinity) === 0``), which
      is what the callers need.

    Python's ``int()`` raises on all of those, so a scraped TKK/GTK of
    ``"abc.def"`` used to blow up the whole request where native quietly
    signed with a ``0`` seed. Both bugs fixed 2026-10-16.
    """
    if isinstance(seg, bool):
        return int(seg)
    if isinstance(seg, int):
        return seg
    if isinstance(seg, float):
        return int(seg)
    if seg is None:
        return 0
    seg = str(seg).strip()
    if not seg:
        return 0
    try:
        return int(seg, 10)
    except ValueError:
        pass
    try:
        val = float(seg)          # "1e3", "3.9"
    except ValueError:
        return 0
    if val != val or val in (float("inf"), float("-inf")):
        # NaN is falsy -> 0. Infinity is technically TRUTHY, but JS's
        # ToInt32 (what the `^`/`>>>` mixers do) maps every infinite
        # value to 0 anyway, so the *effective* seed is 0 and saying 0
        # here is both true of the arithmetic and non-raising.
        return 0
    return int(val)


# Global Options store: `var Options={}; function addOption(a,b){Options[a]=b}`
Options: dict = {}


def add_option(name: str, value) -> None:
    """Port of addOption(a,b) — native UtilsDispatch writes here."""
    Options[name] = value


def get_header() -> str:
    """Port of getHeader()."""
    lang = Options.get("LanguageCode", "")
    acc_lang = format_q("Accept-Language: {0};q=0.8,en-US;q=0.6,en;q=0.4",
                        lang)
    return ("Accept: */*" + NL + acc_lang + NL
            + "Accept-Encoding: gzip,deflate" + NL + "Accept-Charset: utf-8")


def post_header(as_json: bool = False) -> str:
    """Port of postHeader(a)."""
    ctype = ("application/json" if as_json
             else "application/x-www-form-urlencoded")
    return get_header() + NL + "Content-Type: " + ctype + "; charset=utf-8"


def reg_exp_remove(s: str, tags: list, fmt: str) -> str:
    """Port of ``regExpRemove(a,b,c)``.

    Recovered `Common.js` (NSIS chunk at `0x13af4`)::

        function regExpRemove(a,b,c){if(!b)return a;b=format(c,b.join("|"));
                                     return a.replace(new RegExp(b,"g"),"")}

    Native semantics, reproduced here:

    * the guard is ``if(!b)`` -- the **tag list**. An empty input string
      still runs the regex (and comes back ``""``); an empty tag list
      returns the input untouched;
    * the pattern is compiled with ``"g"`` only -- **no ``i`` flag**, so
      matching is case-SENSITIVE. ``re.S`` stands in for the native
      patterns' own ``(.|\\n)`` (which ``removeElements`` spells out) and
      nothing more;
    * every occurrence is replaced, not just the first.

    The extra ``not s`` in the guard below is a no-op in practice: native
    would run the regex over an empty string and get ``""`` back, which
    is what returning early yields too. It is kept so the function is
    total for ``None``.
    """
    if not s or not tags:
        return s
    return re.sub(fmt.format("|".join(tags)), "", s, flags=re.S)


def remove_attributes(s: str, attrs: list) -> str:
    r"""Port of removeAttributes(a,b).

    Recovered `Common.js`::

        function removeAttributes(a,b){return regExpRemove(a,b,
          " ({0})(?:\\s*=\\s*(?:(?:\"((?:\\.|[^\"])*)\")|(?:'((?:\\.|[^'])*)')|([^>\\s]+)))?")}

    In the **regex** the JS builds, ``\\.`` means an escaped dot -- i.e. the
    alternation is ``(?:\.|[^"])*``: a literal DOT or any non-quote. The
    port once wrote this as a Python raw string containing ``\\.``, which
    the regex engine reads as *backslash + any char* -- so it would match
    a ``\"`` sequence inside a quoted value that native's ``[^"]`` cannot.
    Verified divergence (fixed 2026-10-16) on ``<a href="a\"b">t</a>``:
    native yields ``<ab">t</a>``, the double-backslash port yielded
    ``<a>t</a>``, eating the attribute and the rest of the tag.
    """
    return reg_exp_remove(
        s, attrs,
        r" ({0})(?:\s*=\s*(?:(?:\"((?:\.|[^\"])*)\")|(?:'((?:\.|[^'])*)')|([^>\s]+)))?")


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
