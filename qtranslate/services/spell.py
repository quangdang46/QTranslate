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
withdrawn. Open question, honestly recorded: whether native GETs with
``?text=`` (as the port does) or POSTs a form body — the decompile shows
the Content-Type header but its body register was not traced, so the port
keeps the GET form and only adopts the verbatim headers.)

- GoogleSuggest (autocomplete): GET
  google.com/complete/search?client=firefox&q=<text>  (JSONP-ish JSON)
- SpellYandexProvider (spell check): GET
  speller.yandex.net/services/spellservice.json/checkText?text=<text>
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
    """
    url = ("https://speller.yandex.net/services/spellservice.json/checkText?text="
           + urllib.parse.quote(text) + "&lang=" + lang)
    req = urllib.request.Request(url, headers=_SPELL_HEADERS)
    with common.http_open(req, opener) as r:
        return json.loads(r.read().decode("utf-8"))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    print("suggest:", google_suggest("hello worl")[:3])
    print("spell:", yandex_spell("helo world"))
