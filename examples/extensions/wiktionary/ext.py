"""Wiktionary -- free dictionary lookups via the official MediaWiki REST API.

Port of the .tmp ``wikimedia-reference`` plugin's WiktionaryService:
``{lang}.wiktionary.org/w/rest.php/v1/search/page`` finds the page,
``.../page/{key}/with_html`` returns its HTML, and the parser keeps the
part-of-speech sections (h3/h4) with their definition lists -- the same
12-group / 12-definition caps the Kotlin parser uses.

The lookup language is the request's source language when Wiktionary
has an edition for it, else English -- the same rule the plugin's
``editionCode`` applies. A language with no edition is a miss, not an
error.
"""

import json
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

_NAME = "wiktionary"
_UA = {"User-Agent": "QTranslate/1.0 (https://github.com/ahatem/QTranslate)",
       "Accept": "application/json"}
_MIN_INTERVAL = 0.3
_last_request = [0.0]

# editionCodes from WikimediaLanguages.kt -- the languages that have a
# {lang}.wiktionary.org site. Chinese variants both map to "zh".
_EDITIONS = {
    "af", "ar", "az", "be", "bg", "bn", "ca", "cs", "cy", "da", "de",
    "el", "en", "eo", "es", "et", "eu", "fa", "fi", "fr", "ga", "gl",
    "he", "hi", "hr", "hu", "hy", "id", "is", "it", "ja", "ka", "kk",
    "km", "ko", "la", "lo", "lt", "lv", "mk", "ml", "mn", "mr", "ms",
    "mt", "my", "ne", "nl", "no", "pl", "pt", "ro", "ru", "si", "sk",
    "sl", "sq", "sr", "sv", "sw", "ta", "te", "th", "tr", "uk", "ur",
    "uz", "vi", "yi", "zh",
}
_ZH_VARIANTS = {"zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk", "zh-sg"}

# Headings the Kotlin parser skips: metadata sections, not senses.
_IGNORED = {
    "alternative forms", "etymology", "pronunciation", "usage notes",
    "derived terms", "related terms", "descendants", "translations",
    "references", "further reading", "anagrams", "see also",
    "external links",
}
_MAX_GROUPS = 12
_MAX_DEFS = 12


def _edition(src):
    """The wiktionary.org subdomain for a source language, or None."""
    code = (src or "").strip().lower()
    if code in _ZH_VARIANTS:
        return "zh"
    base = code.split("-")[0].split("_")[0]
    return base if base in _EDITIONS else None


def _get_json(url):
    """One GET, rate-limited to the plugin's 300 ms minimum interval."""
    wait = _MIN_INTERVAL - (time.monotonic() - _last_request[0])
    if _last_request[0] and wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _search_page(lang, word):
    q = urllib.parse.urlencode({"q": word, "limit": 1})
    url = ("https://%s.wiktionary.org/w/rest.php/v1/search/page?%s"
           % (lang, q))
    data = _get_json(url)
    pages = data.get("pages") or []
    return pages[0] if pages else None


def _page_html(lang, key):
    url = ("https://%s.wiktionary.org/w/rest.php/v1/page/%s/with_html"
           % (lang, urllib.parse.quote(str(key), safe="")))
    data = _get_json(url)
    return data.get("html") or "", data.get("title") or ""


class _SenseParser(HTMLParser):
    """h3/h4 headings own the following <li> texts until the next
    heading -- the tolerant stand-in for the Kotlin Jsoup walk. Nested
    lists inside a definition are skipped wholesale (their <li> would
    otherwise be read as a new sense)."""

    _SKIP = {"style", "script", "sup", "table", "dl"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.groups = []
        self._heading = None
        self._in_li = False
        self._skip_depth = 0
        self._ol_depth = 0
        self._collect = False
        self._buf = []
        self._defs = []

    def _flush_def(self):
        if self._in_li:
            text = " ".join("".join(self._buf).split())
            if text:
                self._defs.append(text)
            self._buf = []
            self._in_li = False

    def _flush_group(self):
        self._flush_def()
        if self._heading and self._defs:
            self.groups.append((self._heading, self._defs[:_MAX_DEFS]))
        self._heading = None
        self._defs = []
        self._ol_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("h3", "h4"):
            self._flush_group()
            self._heading = ""
            self._collect = True
        elif tag in ("ul", "ol") and self._in_li:
            # a nested list inside a definition: swallow it whole
            self._skip_depth += 1
        elif tag == "ol" and self._heading is not None:
            self._ol_depth += 1
        elif tag == "li" and self._heading is not None \
                and self._ol_depth > 0 and self._skip_depth == 0:
            self._flush_def()
            self._in_li = True
            self._buf = []
        elif tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("h3", "h4"):
            if self._heading is not None:
                self._heading = " ".join(self._heading.split())
            self._collect = False
        elif tag == "li" and self._in_li and self._skip_depth == 0:
            self._flush_def()
        elif self._skip_depth and (tag in self._SKIP
                                   or tag in ("ul", "ol")):
            self._skip_depth -= 1
        elif tag == "ol" and self._ol_depth:
            self._flush_def()
            self._ol_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        if getattr(self, "_collect", False) and self._heading is not None:
            self._heading += data
        elif self._in_li:
            self._buf.append(data)


def _parse(html):
    """[(heading, [definitions])] with the Kotlin caps and skips."""
    p = _SenseParser()
    try:
        p.feed(html or "")
        p.close()
    except Exception:
        return []
    p._flush_group()
    out = []
    for heading, defs in p.groups:
        if not heading or heading.lower() in _IGNORED:
            continue
        out.append((heading, defs))
        if len(out) >= _MAX_GROUPS:
            break
    return out


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _lookup(word, src, tgt):
    """fn(word, src, tgt) -> the entry's HTML fragment.

    A miss or an unreachable edition returns "" -- the dictionary
    contract: the renderer shows its no-results literal rather than an
    error for the ordinary case.
    """
    lang = _edition(src)
    if lang is None or not (word or "").strip():
        return ""
    try:
        page = _search_page(lang, word.strip())
        if not page:
            return ""
        html, title = _page_html(lang, page.get("key") or page.get("title"))
    except Exception:
        return ""
    groups = _parse(html)
    if not groups:
        return ""
    parts = ['<div class="wiktionary-entry"><b>%s</b>' % _esc(title or word)]
    for heading, defs in groups:
        parts.append('<div class="wiktionary-pos"><b>%s</b><ul>'
                     % _esc(heading))
        for d in defs:
            parts.append("<li>%s</li>" % _esc(d))
        parts.append("</ul></div>")
    parts.append("</div>")
    return "".join(parts)


def register(api):
    api.register_dictionary(_NAME, _lookup)
