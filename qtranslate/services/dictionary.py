"""Python ports of QTranslate dictionary/search Service.js plugins.

Reversed from QTranslate 6.10.0 - Services/*/Service.js.
Each provider ports serviceDictionaryRequest (URI building) +
serviceDictionaryResponse (HTML slicing) using stdlib urllib/re only.

sl/tl are service language *codes* (the codeFromLanguage() values);
see each provider's SUPPORTED_LANGS list below (None = unsupported,
mirrors the -1 entries in the JS arrays, indexed by internal lang id).
"""

import html as _html
import re
import urllib.parse
import urllib.request

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _get(url):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _post(url, body):
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers=dict(_UA, **{"Content-Type": "application/x-www-form-urlencoded"}),
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _q(s):
    """encodeGetParam: percent-encode a query value."""
    return urllib.parse.quote(str(s), safe="")


def _sub(page, start, include_start, end, include_end):
    """Port of stringFindSub(text, start, incStart, end, incEnd).

    start/end may be plain strings or compiled regexes.
    Returns "" when a marker is missing.
    """
    if hasattr(start, "search"):
        m = start.search(page)
        if not m:
            return ""
        i = m.start() if include_start else m.end()
    else:
        i = page.find(start)
        if i < 0:
            return ""
        if not include_start:
            i += len(start)
    if hasattr(end, "search"):
        m = end.search(page, i)
        if not m:
            return ""
        j = m.end() if include_end else m.start()
    else:
        j = page.find(end, i)
        if j < 0:
            return ""
        if include_end:
            j += len(end)
    return page[i:j]


def _remove_elements(page, tags):
    for t in tags:
        page = re.sub(r"<%s\b[^>]*>.*?</%s\s*>" % (t, t), "", page,
                      flags=re.S | re.I)
        page = re.sub(r"<%s\b[^>]*/>" % t, "", page, flags=re.I)
    return page


def _remove_attributes(page, attrs):
    for a in attrs:
        page = re.sub(r"""\s+%s\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""" % a, "",
                      page, flags=re.I)
    return page


def _remove_tags(page, tags):
    """Port of removeTags: unwrap tags, keep inner content."""
    for t in tags:
        page = re.sub(r"</?%s\b[^>]*>" % t, "", page, flags=re.I)
    return page


def _update_links(page, base):
    """Port of updateHtmlLinks: absolutize href/src against base host."""
    base = base.rstrip("/")

    def _abs(m, attr=""):
        url = m.group(1)
        if re.match(r"(?i)(https?:|javascript:|mailto:|#|qtdp:)", url):
            return m.group(0)
        if url.startswith("//"):
            return m.group(0).replace(url, "https:" + url, 1)
        if url.startswith("/"):
            return m.group(0).replace(url, base + url, 1)
        return m.group(0).replace(url, base + "/" + url, 1)

    page = re.sub(r'''(?i)\bhref\s*=\s*["']([^"'#]+)["']''',
                  lambda m: _abs(m), page)
    page = re.sub(r'''(?i)\bsrc\s*=\s*["']([^"']+)["']''',
                  lambda m: _abs(m), page)
    return page


# ---------------------------------------------------------------- Babylon
# Services/Babylon/Service.js (translate capability; numeric lang codes)

BABYLON_HOST = "https://translation.babylon-software.com"
BABYLON_LANGS = [None, None, None, None, None, 15, None, None, None, None,
                 99, 10, 9, None, 31, 43, 4, 0, None, None, None, 1, None,
                 6, 11, None, 14, 60, 30, None, None, 2, None, 8, None,
                 12, None, None, None, None, None, 46, 51, 29, 5, 47, 7,
                 None, None, None, 3, None, 48, 16, 13, 49, 39, None, None,
                 None, None, None, None, None, None, None, None, None, None,
                 None, None, None, None, None, None, None]


def babylon_lookup(word, sl, tl):
    """GET /translate/babylon.php?...callback=callbackFn; unwrap JSONP."""
    import json
    url = (BABYLON_HOST + "/translate/babylon.php?v=1.0&q={0}&langpair={1}%7C{2}"
           "&callback=callbackFn&context=babylon").format(_q(word), sl, tl)
    body = _get(url)
    i = body.find("(")
    if i >= 0:
        j = body.rfind(")")
        if j >= 0:
            body = "[" + body[i + 1:j] + "]"
    try:
        data = json.loads(body)
        if len(data) > 2 and data[1]:
            text = re.sub(r"<[^>]+>", "", data[1].get("translatedText", ""))
            return text.replace("*", "\n")
    except ValueError:
        pass
    return body


# ------------------------------------------------------- Babylon Dictionary
# Services/Babylon Dictionary/Service.js (POST /ajax.php/)

BABYLON_DICT_HOST = "https://dictionary.babylon-software.com"
BABYLON_DICT_LANGS = [None, None, None, None, None, "arabic", None, None,
                      None, None, None, "chinese (s)", "chinese (t)", None,
                      None, None, "dutch", "english", None, None, None,
                      "french", None, "german", "greek", None, "hebrew",
                      None, None, None, None, "italian", None, "japanese",
                      None, "korean", None, None, None, None, None, None,
                      None, None, "portuguese", None, "russian", None, None,
                      None, "spanish", None, "swedish", None, "turkish",
                      None, None, None, None, None, None, None, None, None,
                      None, None, None, None, None, None, None, None, None,
                      None, None, None]


def babylon_dict_lookup(word, sl, tl):
    body = "term={0}&sourceLanguage={1}&targetLanguage={2}&action=BISApi".format(
        urllib.parse.quote_plus(str(word)), sl, tl)
    page = _post(BABYLON_DICT_HOST + "/ajax.php/", body)
    page = _remove_attributes(page, ["onload"])
    page = _update_links(page, BABYLON_DICT_HOST)
    return page


# ---------------------------------------------------------- ABBYY Lingvo Live
# Services/ABBYY Lingvo Live/Service.js

LINGVO_HOST = "https://www.lingvolive.com"
LINGVO_LANGS = [None, None, None, None, None, None, None, None, None, None,
                None, "zh", "zh", None, None, "da", "nl", "en", None, "fi",
                None, "fr", None, "de", "el", None, None, None, "hu", None,
                None, "it", None, None, None, None, None, None, None, None,
                None, "no", None, "pl", "pt", None, "ru", None, None, None,
                "es", None, None, None, "tr", "uk", None, None, None, None,
                None, None, "la", None, "kk", None, None, None, None, None,
                None, None, None, None, None, "tt"]


def _lingvo_ui_lang(code):
    return {"ru": "ru-ru", "es": "es-mx", "pt-BR": "pt-br"}.get(code, "en-us")


def lingvo_lookup(word, sl, tl, ui_lang="en-us"):
    url = LINGVO_HOST + "/{0}/translate/{1}-{2}/{3}".format(
        ui_lang, sl, tl, _q(word))
    page = _get(url)
    m = re.search(r'<div name="#(dictionary|user|quote|phrase|wordform)"', page)
    if not m:
        return ""
    frag = page[m.start():]
    j = frag.find('<div class="HLjpm"')
    if j <= 0:
        j = frag.find("<footer")
    if j > 0:
        frag = frag[:j]
    frag = _remove_attributes(frag, ["id", "name", "class", "data-reactid"])
    frag = _remove_elements(frag, ["button", "svg"])
    frag = _update_links(frag, LINGVO_HOST)
    return frag


# ------------------------------------------------------------------ Reverso
# Services/Reverso/Service.js

REVERSO_HOST = "http://dictionary.reverso.net"
REVERSO_LANGS = [None, None, None, None, None, "arabic", None, None, None,
                 None, None, "chinese", "chinese", None, None, None, "dutch",
                 "english", None, None, None, "french", None, "german",
                 None, None, "hebrew", None, None, None, None, "italian",
                 None, "japanese", None, None, None, None, None, None, None,
                 None, None, None, "portuguese", "romanian", "russian",
                 None, None, None, "spanish", None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None]


REVERSO_API_HOST = "https://api.reverso.net"
REVERSO_API_LANGS = {
    "en": "eng", "english": "eng", "fr": "fra", "french": "fra",
    "de": "ger", "german": "ger", "es": "spa", "spanish": "spa",
    "it": "ita", "italian": "ita", "ru": "rus", "russian": "rus",
    "pt": "por", "portuguese": "por", "zh": "chi", "chinese": "chi",
    "zh-CHS": "chi", "ja": "jpn", "japanese": "jpn", "ar": "ara",
    "arabic": "ara", "he": "heb", "hebrew": "heb", "nl": "dut",
    "dutch": "dut", "pl": "pol", "polish": "pol", "ro": "rum",
    "romanian": "rum", "tr": "tur", "turkish": "tur", "uk": "ukr",
    "ukrainian": "ukr", "hi": "hin", "ko": "kor", "sv": "swe",
    "da": "dan", "fi": "fin", "el": "ell", "cs": "cze", "sk": "slo",
    "hu": "hun", "th": "tha", "vi": "vie",
}


def reverso_translate(text, sl="en", tl="fr"):
    """Translate via Reverso context API — verified live 2026-10-07.

    POST api.reverso.net/translate/v1/translation, no auth. The legacy
    dictionary.reverso.net HTML path is Cloudflare-walled (403); this
    JSON API replaces it for translate. Returns the joined translation.
    """
    src = REVERSO_API_LANGS.get(sl, sl)
    dst = REVERSO_API_LANGS.get(tl, tl)
    import json as _json
    body = _json.dumps({
        "format": "text", "from": src, "to": dst, "input": text[:5000],
        "options": {"sentenceSplitter": True, "origin": "translation.web",
                    "contextResults": True, "languageDetection": True},
    }).encode()
    req = urllib.request.Request(
        REVERSO_API_HOST + "/translate/v1/translation", data=body,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                 "Content-Type": "application/json",
                 "Referer": "https://www.reverso.net/"})
    with urllib.request.urlopen(req, timeout=20) as r:
        obj = _json.loads(r.read().decode("utf-8", errors="replace"))
    return " ".join(obj.get("translation", []) or [])


def reverso_lookup(word, sl, tl):
    url = REVERSO_HOST + "/{0}-{1}/{2}".format(sl, tl, _q(word))
    page = _get(url)
    frag = _sub(page, '<div id="TableHTMLResult">', False,
                "<!--Center section end", False)
    if not frag:
        return ""
    frag = re.sub(r"font-size:\s\d+px;?", "", frag)
    frag = _remove_elements(frag, ["script", "iframe"])
    frag = _remove_attributes(
        frag, ["id", "name", "class", "href", "onclick", "onmouseover",
               "onmouseout"])
    frag = _remove_tags(frag, ["font", "img"])
    frag = _update_links(frag, REVERSO_HOST)
    return frag


# ------------------------------------------------------------ WordReference
# Services/WordReference/Service.js

WORDREF_HOST = "https://www.wordreference.com"
WORDREF_LANGS = [None, "", None, None, None, "ar", None, None, None, None,
                 None, "zh", "zh", None, "cz", None, None, "en", None, None,
                 None, "fr", None, "de", "gr", None, None, None, None, None,
                 None, "it", None, "ja", None, "ko", None, None, None, None,
                 None, None, None, "pl", "pt", "ro", "ru", None, None, None,
                 "es", None, None, None, "tr", None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None, None,
                 None, None, None, None, None, None]


def wordreference_lookup(word, sl, tl, headless_fallback=True):
    url = WORDREF_HOST + "/{0}{1}/{2}".format(sl, tl, _q(word))
    page = _get(url)
    if "not a bot" in page and headless_fallback:
        # Anubis JS-challenge wall — re-fetch via headless Chromium
        # (qtranslate/headless.py). Verified 2026-10-07.
        try:
            from qtranslate.headless import wordreference_html
            page = wordreference_html(word, sl, tl)
        except Exception:
            pass
    frag = _sub(page, re.compile(r'<div id="(articleWRD|article)">'), False,
                '<div id="postArticle">', False)
    if not frag:
        return ""
    frag = _remove_elements(frag, ["style"])
    frag = _remove_attributes(frag, ["id", "name", "onclick"])
    frag = _update_links(frag, WORDREF_HOST)
    return frag


# ---------------------------------------------------- Oxford Learner Dictionary
# Services/Oxford Learner Dictionary/Service.js (English-only: codes are 1)

OXFORD_HOST = "https://www.oxfordlearnersdictionaries.com"
OXFORD_LANGS = [1] * 76


def oxford_lookup(word, sl=1, tl=1):
    url = OXFORD_HOST + "/search/english/?q=" + _q(word)
    page = _get(url)
    frag = _sub(page, '<div id="ox-wrapper"', False,
                '<div id="rightcolumn"', False)
    if not frag:
        return ""
    frag = _update_links(frag, OXFORD_HOST)
    frag = re.sub(
        r"(https?://)?(www\.)?oxfordlearnersdictionaries\.com/"
        r"(search/english/\?q=|definition/english/)",
        "qtdp:", frag, flags=re.I)
    frag = _remove_attributes("<div " + frag, ["id", "dpsid", "dpsref", "geo"])
    frag = _remove_elements(frag, ["script", "img"])
    frag = re.sub(r'<div class="sound(.|\n)*?</div>', "", frag, flags=re.I)
    return frag


# ----------------------------------------------------------------- Multitran
# Services/Multitran/Service.js (numeric lang codes; l1=target, l2=source)

MULTITRAN_HOST = "https://www.multitran.com"
MULTITRAN_LANGS = [None, None, 31, None, None, 10, None, None, None, 15,
                   None, 97, 17, None, 16, 22, 24, 1, 26, 36, None, 4, None,
                   3, 38, None, None, None, 42, None, None, 23, 49, 28, None,
                   None, 27, 12, None, None, None, None, None, 14, 11, 13,
                   2, None, None, None, 5, None, 29, None, 32, 33, None,
                   None, None, None, 34, None, None, None, None, 45, None,
                   None, None, None, None, None, None, None, None, 9]


def multitran_lookup(word, sl, tl, ui_lang="en"):
    url = (MULTITRAN_HOST + "/m.exe?l1={0}&l2={1}&s={2}").format(tl, sl,
                                                                _q(word))
    if ui_lang != "ru":
        url += "&SHL=1"
    page = _get(url)
    # Current markup: first width=100% table is a header shell; real
    # entries live in the following width=100% tables containing
    # <a name="..."> anchors (noun/verb/...). Collect those.
    blocks = re.findall(r'<table width="100%">.*?</table>', page,
                        flags=re.S | re.I)
    entries = [b for b in blocks if "<a name=" in b]
    frag = "\n".join(entries) if entries else _sub(
        page, '<table width="100%">', True, "</table>", True)
    if not frag:
        return ""
    frag = re.sub(r'href="/m\.exe', 'href="https://www.multitran.com/m.exe',
                  frag, flags=re.I)
    return frag


# -------------------------------------------------------------- ImTranslator
# Services/ImTranslator/Service.js (SERVICE_ID=18, DICTIONARY only)

IMTRANS_HOST = "http://imtranslator.net"
IMTRANS_ID = 18
IMTRANS_NAME = "ImTranslator"
IMTRANS_LANGS = [None, "", "af", "az", "sq", "ar", "hy", "eu", "be", "bg",
                 "ca", "zh", "zt", "hr", "cs", "da", "nl", "en", "et", "fi",
                 "tl", "fr", "gl", "de", "el", "ht", "iw", "hi", "hu", "is",
                 "id", "it", "ga", "ja", "ka", "ko", "lv", "lt", "mk", "ms",
                 "mt", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk", "sl",
                 "es", "sw", "sv", "th", "tr", "uk", "ur", "vi", "cy", "yi",
                 "eo", "hmn", "la", "lo", None, None, None, None, None, None,
                 None, None, None, None, None, None]


def imtranslator_host() -> str:
    """Port of serviceHost(): always http://imtranslator.net."""
    return "http://imtranslator.net"


def imtranslator_link() -> str:
    """Port of serviceLink(): the dictionary subdomain + ResponseData link."""
    return "http://dictionary.imtranslator.net/"


def imtranslator_lookup(word, sl, tl):
    """Port of serviceDictionaryRequest/Response (ASMX lookup, now 404).

    The native also returns the "http://dictionary.imtranslator.net/"
    link (serviceLink + ResponseData link field) — see
    imtranslator_link(); the fragment alone is returned here to keep
    all dictionary.py lookups string-typed.
    """
    url = (IMTRANS_HOST + "/translation/dictionary/DicService.asmx/lookup"
           "?text={0}&dicID=&lang={1}%2F{2}&langs={1}%2F{2}&flags=DEFAULT"
           ).format(_q(word), sl, tl)
    page = _get(url)
    frag = _sub(page, '<translation status="ok" format="html">', False,
                "</translation>", False)
    return _html.unescape(frag)


# ----------------------------------------------------------- Urban Dictionary
# Services/Urban Dictionary/Service.js (all codes are 1: language-agnostic)

URBAN_HOST = "https://www.urbandictionary.com"
URBAN_LANGS = [1] * 76


def urban_lookup(word, sl=1, tl=1):
    url = URBAN_HOST + "/define.php?term=" + _q(word)
    page = _get(url)
    frag = _sub(page, re.compile(r"<section "), True,
                re.compile(r"</section>"), True)
    if not frag:
        return ""
    frag = _remove_elements(frag, ["script", "svg", "iframe", "button"])
    frag = _remove_attributes(frag, ["style"])
    frag = _update_links(frag, URBAN_HOST)
    return frag


# ----------------------------------------------------------------- Wikipedia
# Services/Wikipedia/Service.js (host is per-target-lang m.wikipedia.org)

WIKI_LANGS = [None, "", "af", "az", "sq", "ar", "hy", "eu", "be", "bg",
              "ca", "zh", "zh", "hr", "cs", "da", "nl", "en", "et", "fi",
              None, "fr", "gl", "de", "el", "ht", "he", "hi", "hu", "is",
              "id", "it", "ga", "ja", "ka", "ko", "lv", "lt", "mk", "ms",
              "mt", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk", "sl",
              "es", "sw", "sv", "th", "tr", "uk", "ur", "vi", "cy", "yi",
              "eo", "hmn", "la", "lo", "kk", "uz", "si", "tg", "te", "km",
              "mn", "kn", "ta", "mr", "bn", "tt"]


def _wiki_host(lang_code):
    code = lang_code or "en"
    return "https://{0}.m.wikipedia.org".format(code)


def wikipedia_lookup(word, sl, tl):
    host = _wiki_host(tl)
    page = _get(host + "/wiki/" + _q(word))
    frag = _sub(page, '<div id="bodyContent"', True,
                '<div class="post-content"', True)
    if not frag:
        # Fallback for current Vector skin (post-content retired):
        # slice bodyContent up to the footer block.
        frag = _sub(page, '<div id="bodyContent"', True,
                    '<div id="catlinks"', False)
    if not frag:
        return ""
    frag = _remove_attributes(frag + "></div>", ["id", "name", "class"])
    frag = _update_links(frag, host)
    return frag


# ------------------------------------------------------------- Google Search
# Services/Google Search/Service.js

GSEARCH_HOST = "https://www.google.com"
GSEARCH_LANGS = [None, "", "af", "az", "sq", "ar", "hy", "eu", "be", "bg",
                 "ca", "zh-CN", "zh-TW", "hr", "cs", "da", "nl", "en", "et",
                 "fi", "tl", "fr", "gl", "de", "el", "ht", "iw", "hi", "hu",
                 "is", "id", "it", "ga", "ja", "ka", "ko", "lv", "lt", "mk",
                 "ms", "mt", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk",
                 "sl", "es", "sw", "sv", "th", "tr", "uk", "ur", "vi", "cy",
                 "yi", "eo", "hmn", "la", "lo", "kz", "uz", "si", "tg", "te",
                 "km", "mn", "kn", "ta", "mr", "bn", "tt"]


def google_search_lookup(word, sl, tl):
    url = GSEARCH_HOST + "/search?q={0}&ie=UTF-8&hl={1}".format(_q(word), tl)
    page = _get(url)
    frag = _sub(page, '<div id="main">', False, "<footer>", False)
    if not frag:
        return ""
    frag = _remove_elements(frag, ["style", "script", "svg"])
    frag = _remove_attributes(frag, ["id", "name", "style", "class"])
    frag = _remove_tags(frag, ["h[3-6]"])
    frag = _update_links(frag, GSEARCH_HOST)
    return frag


PROVIDERS = {
    "babylon": babylon_lookup,
    "babylon_dict": babylon_dict_lookup,
    "lingvo": lingvo_lookup,
    "reverso": reverso_lookup,
    "wordreference": wordreference_lookup,
    "oxford": oxford_lookup,
    "multitran": multitran_lookup,
    "imtranslator": imtranslator_lookup,
    "urban": urban_lookup,
    "wikipedia": wikipedia_lookup,
    "google_search": google_search_lookup,
}
