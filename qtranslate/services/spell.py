"""Spell-check / suggest providers — reversed from QTranslate.exe strings.

- GoogleSuggest (common::GoogleSuggest): GET
  google.com/complete/search?client=firefox&q=<text>  (JSONP-ish JSON)
- SpellYandexProvider (common::SpellYandexProvider): GET
  speller.yandex.net/services/spellservice.json/checkText?text=<text>
"""
import json
import urllib.parse
import urllib.request
from qtranslate import common

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def google_suggest(text: str, lang: str = "en") -> list:
    """Port of GoogleSuggest: autocomplete suggestions."""
    url = ("https://www.google.com/complete/search?client=firefox&q="
           + urllib.parse.quote(text) + "&hl=" + lang)
    req = urllib.request.Request(url, headers=_UA)
    with common.http_open(req) as r:
        obj = json.loads(r.read().decode("utf-8"))
    return obj[1] if len(obj) > 1 else []


def yandex_spell(text: str, lang: str = "en") -> list:
    """Port of SpellYandexProvider: spelling corrections.

    Returns list of {word, suggestions[]} dicts.
    """
    url = ("https://speller.yandex.net/services/spellservice.json/checkText?text="
           + urllib.parse.quote(text) + "&lang=" + lang)
    req = urllib.request.Request(url, headers=_UA)
    with common.http_open(req) as r:
        return json.loads(r.read().decode("utf-8"))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    print("suggest:", google_suggest("hello worl")[:3])
    print("spell:", yandex_spell("helo world"))
