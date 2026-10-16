"""Spell-check / suggest providers.

Native classes are evidence-backed (RTTI): ``common::GoogleSuggest``,
``common::SpellYandexProvider``, ``common::SpellProvider``,
``controls::ISuggestionsProvider``, ``windows::DictionarySuggestionsProvider``.

Request shape for the Yandex path is byte-backed, not guessed: decompiling
``FUN_0042c968`` (the builder referencing the verbatim string
``/services/spellservice.json/checkText`` at ``0x51f380``; evidence in
``docs/review/SPELL_SERVICE_STRINGS_2026-10-14.md``) shows the host
``speller.yandex.net`` is ALSO a verbatim string, and the request carries
the header block::

    Accept-Encoding: gzip,deflate
    Accept-Charset: utf-8
    Content-Type: application/x-www-form-urlencoded

(An older note here claimed the host/path were "not present verbatim ...
assembled at runtime" — the decompile disproves that, so it is
withdrawn. An open question recorded here -- GET with ``?text=`` or POST a
form body -- was **closed 2026-10-16** by reading `.rdata` directly: the
literal ``text=`` sits immediately before the form-urlencoded header and
the path has no ``?``, so native POSTs. See ``yandex_spell`` below; the
request is pinned by ``tests/regress_spell_request.py``.)

- GoogleSuggest (autocomplete): GET
  google.com/complete/search?client=firefox&q=<text>  (JSONP-ish JSON)
- SpellYandexProvider (spell check): POST (form body)
  speller.yandex.net/services/spellservice.json/checkText   body: text=<text>&lang=<lang>
"""
import json
import urllib.parse
import urllib.request
from qtranslate import common

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Verbatim header block from FUN_0042c968's decompile (see module docstring).
# The port used to send only a User-Agent.
_SPELL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Encoding": "gzip,deflate",
    "Accept-Charset": "utf-8",
    "Content-Type": "application/x-www-form-urlencoded",
}


def google_suggest(text: str, lang: str = "en") -> list:
    """Port of GoogleSuggest: autocomplete suggestions."""
    url = ("https://www.google.com/complete/search?client=firefox&q="
           + urllib.parse.quote(text) + "&hl=" + lang)
    req = urllib.request.Request(url, headers=_UA)
    with common.http_open(req) as r:
        obj = json.loads(r.read().decode("utf-8"))
    return obj[1] if len(obj) > 1 else []


def yandex_spell(text: str, lang: str = "en", opener=None) -> list:
    """Port of SpellYandexProvider: spelling corrections.

    Returns list of {word, suggestions[]} dicts. ``opener`` is accepted
    (and forwarded to ``http_open``) so callers can share a cookie jar
    and tests can stub the transport; every other service module already
    took this parameter, so its absence here was an inconsistency.

    **POST, not GET** — an open question this module recorded for two
    days, resolved 2026-10-16 by reading the string table rather than the
    decompile. The image's `.rdata` holds, in this order::

        \r  \t  \r\n  text=
        Accept-Encoding: gzip,deflate\r\n
        Accept-Charset: utf-8\r\n
        Content-Type: application/x-www-form-urlencoded\r\n
        /services/spellservice.json/checkText
        speller.yandex.net
        pos  len  s

    Three things settle it: the literal ``text=`` sits immediately before
    (and apart from) a **form-urlencoded** Content-Type; the path carries
    **no ``?``**; and the body register the decompile could not reach is
    therefore answered by the shape of its own neighbouring strings --
    ``text=`` + a urlencoded header + a query-less path is a form body.
    The port GETs no more. ``_SPELL_HEADERS`` already carried native's
    verbatim block, so only the request itself was wrong.
    """
    url = ("https://speller.yandex.net/services/spellservice.json/checkText")
    body = ("text=" + urllib.parse.quote_plus(text)
            + "&lang=" + urllib.parse.quote(lang)).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=_SPELL_HEADERS)
    with common.http_open(req, opener) as r:
        return json.loads(r.read().decode("utf-8"))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    print("suggest:", google_suggest("hello worl")[:3])
    print("spell:", yandex_spell("helo world"))
