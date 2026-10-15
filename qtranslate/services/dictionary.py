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
from qtranslate import common

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _get(url):
    req = urllib.request.Request(url, headers=_UA)
    with common.http_open(req) as r:
        return r.read().decode("utf-8", "replace")


def _post(url, body):
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers=dict(_UA, **{"Content-Type": "application/x-www-form-urlencoded"}),
    )
    with common.http_open(req) as r:
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
    """removeElements(a,b) via the verified port (was a divergent copy).

    The recovered `Common.js` (NSIS chunk at `0x149b3`) is explicit::

        function removeElements(a,b){return regExpRemove(a,b,
          "<\\\\s*({0})[^>]*>((.|\\n)*?)<\\\\s*/\\\\s*({0})>")}

    and ``regExpRemove`` compiles it as ``new RegExp(b,"g")`` -- **no
    ``i`` flag**, and a closing tag is REQUIRED. The copy that lived here
    added two inventions on top:

      * a second pattern removing self-closing/void elements
        (``<br/>``, ``<img src=...>``) -- native leaves those, so a
        provider asking for ``img`` removal (dictionary.py:530,
        ``["script","img"]``) silently stripped what native keeps;
      * case-insensitive matching.

    Both are now gone: the call delegates to ``common.remove_elements``,
    which is the byte-faithful transcription.
    """
    from qtranslate.common import remove_elements
    return remove_elements(page, tags)


def _remove_attributes(page, attrs):
    """removeAttributes(a,b) via the verified port (was a divergent copy).

    Recovered `Common.js` (NSIS chunk at `0x149b3`) is::

        function removeAttributes(a,b){return regExpRemove(a,b,
          " ({0})(?:\\s*=\\s*(?:..."
          "|(?:'((?:\\\\.|[^'])*)')|([^>\\s]+)))?")

    -- the pattern starts with a literal **space** and its whole value
    group is OPTIONAL, so both ``name="…"`` and a bare valueless
    ``name`` are removed. The local copy used ``\\s+`` instead of that
    single space and added ``re.I``. Delegates to
    ``common.remove_attributes``.
    """
    from qtranslate.common import remove_attributes
    return remove_attributes(page, attrs)


def _remove_tags(page, tags):
    """removeTags(a,b) via the verified port (was a divergent copy).

    Recovered `Common.js` (NSIS chunk at `0x149b3`)::

        function removeTags(a,b){return regExpRemove(a,b,"</?({0})[^>]*>")}

    compiled with ``new RegExp(b,"g")`` and **no ``i`` flag**, and the
    pattern is ``</?({0})[^>]*>`` -- one alternation, not the ``\\b``-
    anchored form the local copy used. The copy here also matched
    case-insensitively and anchored on ``\\b``, so ``<B>bold</B>`` was
    unwrapped where native keeps it. Delegates to ``common.remove_tags``.
    """
    from qtranslate.common import remove_tags
    return remove_tags(page, tags)


def _update_links(page, base):
    """Absolutize href/src against ``base`` — via the verified native port.

    This used to be a **second, divergent implementation** of the same
    native `Common.js` `updateHtmlLinks(a,b)` that
    ``common.update_html_links`` already ports (measured, and the one
    `services/youdao.py` calls). The two agreed on every case EXCEPT a
    plain relative URL, where this copy invented ``base + "/" + url``
    while the verified port leaves the value alone (its patterns only
    match `//` and `/` prefixes). Native is the authority, so the extra
    behaviour was an invention and is now gone: the call delegates.

    Measured agreement table (base ``https://dict.example.com/dir``):
    ``/wiki/x``, ``//cdn/a``, `javascript:`, `mailto:`, `qtdp:`, ``#top``
    and absolute URLs were already identical; ``rel/p.png`` was not
    (old: absolutised; native: untouched).
    """
    from qtranslate.common import update_html_links
    return update_html_links(page, base)


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


BABYLON_ID = 13
BABYLON_NAME = "Babylon"
BABYLON_DICT_ID = 20
BABYLON_DICT_NAME = "Babylon Dictionary"


def babylon_host() -> str:
    """Port of Babylon serviceHost()."""
    return "https://translation.babylon-software.com"


def babylon_dict_host() -> str:
    """Port of Babylon Dictionary serviceHost()."""
    return "https://dictionary.babylon-software.com"


def babylon_link() -> str:
    """Port of Babylon serviceLink(): the host itself."""
    return babylon_host()


def babylon_dict_link(sl, tl) -> str:
    """The ResponseData link field: ``host/{target}/{source}/``.

    Native: ``format("{0}/{1}/{2}/", serviceHost(), codeFromLanguage(c),
    codeFromLanguage(d))`` where ``ResponseData(text, source, target, …)`` --
    so the order is **target then source**, and the word does not appear in the
    link at all. An earlier version returned ``host/word/``, which borrows the
    shape of the *other* Babylon's link and matches no line of the JS.
    """
    src, tgt = _codes(BABYLON_DICT_LANGS, sl, tl)
    return "{0}/{1}/{2}/".format(babylon_dict_host(), tgt, src)


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
    """Port of Babylon Dictionary pair (POST /ajax.php/, now TLS-dead).

    Faithful to native: BISApi body -> strip onload attrs -> absolutize
    links. The ResponseData link field is
    host/{sl}/{tl}/ — see babylon_dict_link().

    The body's ``sourceLanguage``/``targetLanguage`` are
    ``codeFromLanguage(b)``/``codeFromLanguage(c)`` in the JS -- resolved
    through this service's own table, so the request carries Babylonian
    Dictionary's language names, not the raw language indices.
    """
    src, tgt = _codes(BABYLON_DICT_LANGS, sl, tl)
    body = "term={0}&sourceLanguage={1}&targetLanguage={2}&action=BISApi".format(
        urllib.parse.quote_plus(str(word)), src, tgt)
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


LINGVO_ID = 25
LINGVO_NAME = "ABBYY Lingvo Live"
LINGVO_STYLE = ("._QT6_ALLs *{font-size:100%}._QT6_ALLs table{border:1px "
                "solid #f0f0f2;border-collapse:collapse;margin-top:8px}"
                "._QT6_ALLs table td,._QT6_ALLs table th{border:1px solid "
                "#f0f0f2;text-align:center;padding:8px}"
                "._QT6_ALLs h3{margin-top:8px;text-transform:uppercase}")


def lingvo_host() -> str:
    """Port of serviceHost(): always https://www.lingvolive.com."""
    return "https://www.lingvolive.com"


def lingvo_build_uri(word, sl, tl, ui_lang=None) -> str:
    """Port of buildUri(): ``/{ui}/translate/{src}-{tgt}/{word}``.

    ui defaults to langToUiLang(Options.LanguageCode) like the native
    (ru->ru-ru, es->es-mx, pt-BR->pt-br, else en-us). The source and target
    are language **indices** resolved through ``LINGVO_LANGS`` by native's
    ``codeFromLanguage``, so the URL carries the codes (``en-ru``), never the
    indices (``17-46``).
    """
    from qtranslate.common import Options
    ui_lang = ui_lang or _lingvo_ui_lang(Options.get("LanguageCode", "en"))
    src, tgt = _codes(LINGVO_LANGS, sl, tl)
    return "/{0}/translate/{1}-{2}/{3}".format(ui_lang, src, tgt, _q(word))


def lingvo_link(word, sl, tl, ui_lang=None) -> str:
    """The ResponseData link field: host + buildUri."""
    return lingvo_host() + lingvo_build_uri(word, sl, tl, ui_lang)


def lingvo_lookup(word, sl, tl, ui_lang=None):
    """Port of serviceDictionaryRequest/Response (named-div slice)."""
    url = LINGVO_HOST + lingvo_build_uri(word, sl, tl, ui_lang)
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
    frag = _update_links(
        '<div class="_QT6_ALLs"><style>' + LINGVO_STYLE + "</style><div><div>"
        + frag, LINGVO_HOST)
    return frag


# ------------------------------------------------------------------ Reverso
# Services/Reverso/Service.js (SERVICE_ID=22, DICTIONARY only)

REVERSO_ID = 22
REVERSO_NAME = "Reverso"
REVERSO_HOST = "http://dictionary.reverso.net"


def reverso_host(dictionary: bool = True) -> str:
    """Port of serviceHost(): dict host vs plain host."""
    return ("http://dictionary.reverso.net" if dictionary
            else "http://reverso.net")


def reverso_link() -> str:
    """Port of serviceLink(): always the dictionary host."""
    return reverso_host(True)


def reverso_build_uri(word, sl, tl) -> str:
    """Port of buildUri(): ``/{source}-{target}/{word}``.

    Native: ``format("/{0}-{1}/{2}", codeFromLanguage(a), codeFromLanguage(c),
    encodeGetParam(b))`` -- the arguments are language **indices** and the
    table turns them into Reverso's own names (``english``, ``russian`` …), so
    the URL carries a name, not an index. ``_codes`` does that resolution;
    passing an already-resolved code through unchanged keeps both entry points
    working.
    """
    src, tgt = _codes(REVERSO_LANGS, sl, tl)
    return "/{0}-{1}/{2}".format(src, tgt, _q(word))
REVERSO_LANGS = [None, None, None, None, None, "arabic", None, None, None,
                 None, None, "chinese", "chinese", None, None, None, "dutch",
                 "english", None, None, None, "french", None, "german",
                 None, None, "hebrew", None, None, None, None, "italian",
                 None, "japanese", None, None, None, None, None, None, None,
                 None, None, None, "portuguese", "romanian", "russian",
                 None, None, None, "spanish", None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None, None]


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
    with common.http_open(req) as r:
        obj = _json.loads(r.read().decode("utf-8", errors="replace"))
    return " ".join(obj.get("translation", []) or [])


def reverso_lookup(word, sl, tl):
    try:
        url = reverso_host(True) + reverso_build_uri(word, sl, tl)
        page = _get(url)
    except Exception:
        page = ""
    frag = _sub(page, '<div id="TableHTMLResult">', False,
                "<!--Center section end", False) if page else ""
    if not frag:
        # Legacy HTML walled (403) — fall back to the live context API
        # translation + context examples as the dictionary fragment.
        try:
            tr = reverso_translate(word, sl, tl)
            if tr:
                frag = f"<div><b>{word}</b> — {tr}</div>"
        except Exception:
            pass
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
# Services/WordReference/Service.js (SERVICE_ID=19, DICTIONARY only)

WORDREF_ID = 19
WORDREF_NAME = "WordReference"
WORDREF_HOST = "https://www.wordreference.com"
WORDREF_STYLE = (".rh_me,span.phrase,span.hw{font-weight: bold}"
                 ".rh_ex,.FrEx,.ToEx{display:block;color:gray}"
                 ".rh_lab,span.in{font-style:italic}"
                 ".rh_cat,.rh_lab{float:right}"
                 ".small1,.wrcopyright{font-size:x-small}"
                 ".subjarea{font-variant:small-caps}.tooltip{display:none}")
WORDREF_LANGS = [None, "", None, None, None, "ar", None, None, None, None,
                 None, "zh", "zh", None, "cz", None, None, "en", None, None,
                 None, "fr", None, "de", "gr", None, None, None, None, None,
                 None, "it", None, "ja", None, "ko", None, None, None, None,
                 None, None, None, "pl", "pt", "ro", "ru", None, None, None,
                 "es", None, None, None, "tr", None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None, None,
                 None, None, None, None, None, None]


def wordreference_host() -> str:
    """Port of serviceHost(): always https://www.wordreference.com."""
    return "https://www.wordreference.com"


def wordreference_link() -> str:
    """Port of serviceLink(): the host itself."""
    return wordreference_host()


def wordreference_build_uri(word, sl, tl) -> str:
    """Port of buildUri(): ``/{source}{target}/{word}``.

    Native concatenates the two **codes** with no separator:
    ``format("/{0}{1}/{2}", codeFromLanguage(a), codeFromLanguage(c), …)``, so
    en→ru is ``/enru/``. Interpolating the raw indices instead would build
    ``/1746/``, which is not a URL the native client ever requests.
    """
    src, tgt = _codes(WORDREF_LANGS, sl, tl)
    return "/{0}{1}/{2}".format(src, tgt, _q(word))


def wordreference_lookup(word, sl, tl, headless_fallback=True):
    """Port of serviceDictionaryRequest/Response (article slice).

    Faithful to native: articleWRD/article slice -> remove style ->
    strip id/name/onclick -> style wrap -> absolutize links. The
    ResponseData link is host + buildUri — see wordreference_link().
    Anubis-wall fallback via headless Chromium (EXTENSION, verified).
    """
    url = WORDREF_HOST + wordreference_build_uri(word, sl, tl)
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
    frag = ("<div><style>" + WORDREF_STYLE + "</style><div>" + frag
            + "</div>")
    frag = _update_links(frag, WORDREF_HOST)
    return frag


# ---------------------------------------------------- Oxford Learner Dictionary
# Services/Oxford Learner Dictionary/Service.js (English-only: codes are 1)

OXFORD_HOST = "https://www.oxfordlearnersdictionaries.com"
OXFORD_LANGS = [1] * 76


OXFORD_ID = 29
OXFORD_NAME = "Oxford Learner Dictionary"
OXFORD_STYLE = (
    ".phonetics-font,.eph,.phon{font-family:\"Lucida Sans Unicode\",Arial}"
    ".oxford3000,.link-right,.wl-add,a.topic,.bre,.name,.nbsp,"
    ".side-panel>div,.vp-gs>div,.top-g .pos-g,.z_n+.z,.z_gr_br,"
    "#ox-enlarge+.z,.h-g+.z,.pron-gs .wrap,li.sn-g>.num,"
    "span[hide~=\"y\"],.top-container br{display:none}"
    ".serif-italic,.wx,.x,.x-g,.sans-italic,.ei,.etym_i,.geo,.pos,.reg,"
    ".subj,.wfp,.xpos,.webtop-g .pos+.pnc,.collapse .ff,"
    ".collapse[title^=\"AWL Collocations\"] .er{font-style:italic}"
    ".label-g{color:#767676}.x-gs{display:block}"
    ".x-g{display:block;margin-top:6px;position:relative;margin-left:11px}"
    ".entry-box-style,.collapse{display:block;margin:12px 0 18px 0;"
    "position:relative;overflow:hidden}"
    ".collapse{padding:12px 18px 12px 18px;border-left:3px solid #C76E06}")


def oxford_host() -> str:
    """Port of serviceHost(): always oxfordlearnersdictionaries.com."""
    return "https://www.oxfordlearnersdictionaries.com"


def oxford_link(word) -> str:
    """The ResponseData link field: search URL for the word."""
    return oxford_host() + "/search/english/?q=" + _q(word)


def oxford_lookup(word, sl=1, tl=1):
    """Port of serviceDictionaryRequest/Response (ox-wrapper slice)."""
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
    return "<div><style>" + OXFORD_STYLE + "</style>" + frag + "</div>"


# ----------------------------------------------------------------- Multitran
# Services/Multitran/Service.js (SERVICE_ID=17, DICTIONARY only;
# numeric lang codes; l1=target, l2=source)

MULTITRAN_ID = 17
MULTITRAN_NAME = "Multitran"
MULTITRAN_HOST = "https://www.multitran.com"
MULTITRAN_STYLE = ".gray{border:1px dotted gray}"
MULTITRAN_LANGS = [None, None, 31, None, None, 10, None, None, None, 15,
                   None, 97, 17, None, 16, 22, 24, 1, 26, 36, None, 4, None,
                   3, 38, None, None, None, 42, None, None, 23, 49, 28, None,
                   None, 27, 12, None, None, None, None, None, 14, 11, 13,
                   2, None, None, None, 5, None, 29, None, 32, 33, None,
                   None, None, None, 34, None, None, None, None, 45, None,
                   None, None, None, None, None, None, None, None, 9]


def multitran_host() -> str:
    """Port of serviceHost(): always https://www.multitran.com."""
    return "https://www.multitran.com"


def multitran_link(word) -> str:
    """Port of serviceLink(): host + /m.exe?s=<word>."""
    return multitran_host() + "/m.exe?s=" + _q(word)


def _multitran_code(lang):
    """Resolve a language to Multitran's numeric code.

    Native buildUri(): ``codeFromLanguage(target)`` / ``codeFromLanguage(
    source)`` index ``SupportedLanguages`` (MT array). Port accepts either an
    ISO code (what the app's call sites pass) or an already-numeric value
    (native-style), so both entry points behave identically. Unsupported
    languages (MT entry is ``None``) are returned unchanged, mirroring the
    native's lossy build rather than inventing a code.

    **ASYMMETRY, deliberately preserved: an ``int`` here means an
    ALREADY-RESOLVED MultiTran code, not a language index.** That is the
    opposite of what ``_codes`` does with an int, and the difference is real
    rather than sloppy: at a MultiTran call site ``2`` is ru, while ``46`` is
    ru as a language index. Routing this through ``_codes`` therefore turned
    ``l1=2`` into ``l1=31`` and broke ``regress_dict_args.py``. Do not unify
    the two -- the next reader will want to. See ``multitran_build_uri``.
    """
    if isinstance(lang, int) or lang in ("auto", "", None):
        return lang
    from qtranslate.services.google_translate import SUPPORTED_LANGS
    try:
        code = MULTITRAN_LANGS[SUPPORTED_LANGS.index(lang)]
    except (ValueError, IndexError):
        return lang
    return code if code is not None else lang


def _idx(lang):
    """Native language id for ``lang``, or ``None`` if it is not one.

    The native ``buildUri`` receives **indices** -- the framework turns a code
    into an id (``languageFromCode``) before any service sees it -- so a port
    called with an ISO code has to make the same conversion first. Kept as its
    own function so index→code and code→index stay legible in both directions.
    """
    if isinstance(lang, int):
        return lang
    if lang in ("auto", "", None):
        return None
    from qtranslate.services.google_translate import SUPPORTED_LANGS
    try:
        return SUPPORTED_LANGS.index(lang)
    except ValueError:
        return None


def _resolve(table, lang):
    """One leg, native-style: an **index** or an ISO code -> this service's code.

    ``codeFromLanguage`` operates on language ids, so a native caller passes an
    index (``46`` = ru) and gets that service's own value from ``table``
    (``"russian"`` for Reverso, ``2`` for Multitran). An ISO code is mapped to
    an id first -- the framework's own ``languageFromCode`` step -- so both
    spellings of the same language converge.

    An entry that is ``None``/empty is **unsupported**, and resolves to ``-1``
    exactly as native interpolates it -- it must NOT fall back to the input,
    or index ``60`` would echo ``60`` into the URL and look like a code. An
    index outside the array is ``-1`` for the same reason.

    A *code* that is not any language at all (``"vi"``, where the app's table
    has no such entry) is passed through unchanged: that is an unresolvable
    input, not an unsupported language, and keeping it visible is better than
    flattening it into the same ``-1``.
    """
    if isinstance(lang, int):
        v = common.code_from_language(lang, table)
        return -1 if v in (None, "") else v
    idx = _idx(lang)
    if idx is None:
        return lang                     # not a language the app knows at all
    v = common.code_from_language(idx, table)
    return -1 if v in (None, "") else v


def _codes(table, sl, tl):
    """(source_code, target_code) for a provider's own ``SupportedLanguages``.

    ``sl``/``tl`` are native language **indices** (what ``buildUri`` receives
    from the framework) or the ISO codes the port's own call sites pass; both
    resolve through ``_resolve`` to this service's value. An unsupported entry
    resolves to ``-1`` -- the value native interpolates -- never to a
    substitute, so an unsupported pair stays distinguishable from a
    mistranslated one.

    The framework's own behaviour here is now **measured**, and it is why this
    returns the raw entry rather than a substitute. From `Common.js` (chunk[5]
    of the NSIS stream at `0x13af4`, 6,203 bytes, sha256 `a03d677a8b3788b5...`,
    ``docs/review/COMMON_JS_RECOVERED_2026-10-11.md``)::

        var SupportedLanguages=null,UNKNOWN_LANGUAGE_CODE=-1,
            UNKNOWN_LANGUAGE=0,AUTO_DETECT_LANGUAGE=1,ENGLISH_LANGUAGE=17;
        function isLanguage(a){return a>AUTO_DETECT_LANGUAGE&&
                                    a<SupportedLanguages.length}
        function codeFromLanguage(a){return a===AUTO_DETECT_LANGUAGE||isLanguage(a)
                                    ?SupportedLanguages[a]:UNKNOWN_LANGUAGE_CODE}

    Three things follow, each a measurement rather than an inference:

    * ``codeFromLanguage`` returns the entry **unguarded** -- it tests the
      index, never the value, so an unsupported entry interpolates as ``-1``.
    * The framework contains **no refusal path at all** for it:
      ``return null`` / ``return !1`` / ``return false`` appear zero times in
      `Common.js`, and the framework never calls ``codeFromLanguage`` itself
      -- only a service's own ``buildUri`` does.
    * ``SupportedLanguages`` is ONE shared global, ``null`` in the framework
      and reassigned by each of the 19 `Service.js` files at load, so every
      provider's table is the *same* slot with different contents.

    So native does not skip or refuse an unsupported pair; it builds the URL
    with ``-1`` in it and sends it. This port reproduces that exactly, and
    ``supported()`` exists so a caller that prefers not to send can ask first.
    Adding a refusal of our own would be inventing policy the artifact does
    not have.

    One deliberate difference, and it is a port limitation rather than a claim:
    a code that is not any language at all (``"vi"`` where the app's table has
    no such entry) is passed through unchanged rather than being interpolated
    as ``-1``, so it stays visible instead of masquerading as "unsupported".
    """
    return tuple(_resolve(table, x) for x in (sl, tl))


def supported(table, sl, tl) -> bool:
    """True when both legs resolve to a code this provider supports.

    ``code_from_language``'s bounds test is not enough on its own -- it is true
    for unsupported entries too. This asks the stricter question the array
    encodes, so a caller that wants to skip (rather than issue) a request for
    an unsupported pair has one predicate instead of four ad-hoc ``is None``
    comparisons.
    """
    return all(c not in (None, -1, "") for c in _codes(table, sl, tl))


def multitran_build_uri(word, sl, tl, ui_lang=None) -> str:
    """Port of buildUri(): ``/m.exe?l1={code(target)}&l2={code(source)}&
    s={word}`` (+ ``&SHL=1`` unless UI lang is ru).

    Note l1 is the *target* and l2 the *source* (native order). Resolution is
    ``_multitran_code``'s, not ``_codes``': for Multitran an int argument is
    already a Multitran **code** (``2`` is ru), whereas native's
    ``buildUri`` inputs are language **indices** (``46`` is ru). Both spellings
    appear at Multitran call sites in this repo, and re-labeling one as the
    other would turn ``l1=2`` into ``l1=31``. See ``_multitran_code``.
    """
    from qtranslate.common import Options
    url = "/m.exe?l1={0}&l2={1}&s={2}".format(
        _multitran_code(tl), _multitran_code(sl), _q(word))
    ui = ui_lang or Options.get("LanguageCode", "en")
    if ui != "ru":
        url += "&SHL=1"
    return url


def multitran_lookup(word, sl, tl, ui_lang=None):
    """Port of serviceDictionaryRequest/Response (width=100% table slice).

    Faithful to native: table slice (inclusive) -> absolutize /m.exe
    links -> gray-style wrap. Current markup needs the anchor-tables
    fallback (first table is a header shell). The ResponseData link is
    host + buildUri — see multitran_link().
    """
    url = MULTITRAN_HOST + multitran_build_uri(word, sl, tl, ui_lang)
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
    return ("<div><style>" + MULTITRAN_STYLE + "</style>" + frag + "</div>")


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
    """The ResponseData link field: ``serviceHost(DICTIONARY) + /translation/``.

    Native: ``b = format("{0}/translation/", serviceHost(Capability.DICTIONARY))``
    in ``serviceDictionaryResponse``. ``serviceHost`` for ImTranslator returns
    ``http://imtranslator.net`` -- the ``dictionary.`` subdomain is
    ``serviceLink``'s job, not the response link's, so this returns
    ``http://imtranslator.net/translation/``.
    """
    return "{0}/translation/".format(imtranslator_host())


def imtranslator_lookup(word, sl, tl):
    """Port of serviceDictionaryRequest/Response (ASMX lookup, now 404).

    The native also returns the "http://dictionary.imtranslator.net/"
    link (serviceLink + ResponseData link field) — see
    imtranslator_link(); the fragment alone is returned here to keep
    all dictionary.py lookups string-typed.

    ``lang``/``langs`` carry ``codeFromLanguage(source)``/
    ``codeFromLanguage(target)``, resolved through this service's own table, so
    the query spells ImTranslator's language names rather than raw indices.
    """
    src, tgt = _codes(IMTRANS_LANGS, sl, tl)
    url = (IMTRANS_HOST + "/translation/dictionary/DicService.asmx/lookup"
           "?text={0}&dicID=&lang={1}%2F{2}&langs={1}%2F{2}&flags=DEFAULT"
           ).format(_q(word), src, tgt)
    page = _get(url)
    frag = _sub(page, '<translation status="ok" format="html">', False,
                "</translation>", False)
    return _html.unescape(frag)


# ----------------------------------------------------------- Urban Dictionary
# Services/Urban Dictionary/Service.js (all codes are 1: language-agnostic)

URBAN_HOST = "https://www.urbandictionary.com"
URBAN_LANGS = [1] * 76


URBAN_ID = 24
URBAN_NAME = "Urban Dictionary"
URBAN_STYLE = (".justify-between,.mug-ad,.ad-panel{display:none}"
               ".italic{font-style:italic}.font-bold{font-weight:700}"
               ".p-5{padding:1em}.px-3{padding-left:.75em;padding-right:.75em}")


def urban_host() -> str:
    """Port of serviceHost(): always https://www.urbandictionary.com."""
    return "https://www.urbandictionary.com"


def urban_link(word) -> str:
    """The ResponseData link field: ``host/<word>``.

    Native: ``format("{0}/{1}", serviceHost(DICTIONARY), encodeGetParam(b))``
    inside ``serviceDictionaryResponse`` -- so the link is the host plus the
    bare word, with **no** ``/define.php?term=`` path. That path belongs to the
    *request*; reusing it here made the link a duplicate of the request URL
    instead of the page the entry lives on, which is what ``serviceLink``
    returns too.
    """
    return "{0}/{1}".format(urban_host(), _q(word))


URBAN_API_HOST = "https://api.urbandictionary.com"


def urban_api(word):
    """Definitions via api.urbandictionary.com/v0/define — verified live
    2026-10-07 (the /define.php HTML shell is now JS-rendered with empty
    sections; same entries served as JSON here). Returns the raw list."""
    import json as _json
    req = urllib.request.Request(
        URBAN_API_HOST + "/v0/define?term=" + _q(word), headers=_UA)
    with common.http_open(req) as r:
        return _json.loads(r.read().decode("utf-8")).get("list", [])


def urban_lookup(word, sl=1, tl=1):
    """Port of serviceDictionaryRequest/Response.

    Faithful to native: section slice (inclusive) -> remove
    script/svg/iframe/button -> strip style attrs -> absolutize links ->
    wrap in <div><style>...</style><div>. The per-word link is
    urban_link(word) (ResponseData link field). Falls back to the live
    v0 JSON API when the HTML shell has no rendered entries (current
    site renders client-side).
    """
    url = URBAN_HOST + "/define.php?term=" + _q(word)
    page = _get(url)
    frag = _sub(page, re.compile(r"<section "), True,
                re.compile(r"</section>"), True)
    if frag:
        frag = _remove_elements(frag, ["script", "svg", "iframe", "button"])
        frag = _remove_attributes(frag, ["style"])
        frag = _update_links(frag, URBAN_HOST)
        if "udh-ritems" not in frag or re.search(r"\w{20,}", frag):
            return "<div><style>" + URBAN_STYLE + "</style><div>" + frag
    try:
        items = urban_api(word)[:5]
    except Exception:
        return ""
    parts = []
    for it in items:
        parts.append("<p><b>{}</b><br>{}<br><i>{}</i></p>".format(
            _html.escape(it.get("word", "")),
            _html.escape(it.get("definition", ""))[:800],
            _html.escape(it.get("example", ""))[:400]))
    if not parts:
        return ""
    return ("<div><style>" + URBAN_STYLE + "</style><div>"
            + "".join(parts))


# ----------------------------------------------------------------- Wikipedia
# Services/Wikipedia/Service.js (SERVICE_ID=14, DICTIONARY only)

WIKI_ID = 14
WIKI_NAME = "Wikipedia"
WIKI_LANGS = [None, "", "af", "az", "sq", "ar", "hy", "eu", "be", "bg",
              "ca", "zh", "zh", "hr", "cs", "da", "nl", "en", "et", "fi",
              None, "fr", "gl", "de", "el", "ht", "he", "hi", "hu", "is",
              "id", "it", "ga", "ja", "ka", "ko", "lv", "lt", "mk", "ms",
              "mt", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk", "sl",
              "es", "sw", "sv", "th", "tr", "uk", "ur", "vi", "cy", "yi",
              "eo", "hmn", "la", "lo", "kk", "uz", "si", "tg", "te", "km",
              "mn", "kn", "ta", "mr", "bn", "tt"]


def _wiki_host(lang_code):
    """Port of serviceHost(): ``https://{lang}.m.wikipedia.org``.

    Native::

        a = codeFromLanguage(DICTIONARY ? c : b);          // the index
        a == UNKNOWN_LANGUAGE_CODE && (a = SupportedLanguages[ENGLISH_LANGUAGE]);
        return format("https://{0}.m.wikipedia.org", a);

    So the language is **resolved through this service's own table** and the
    fallback is that array's ``ENGLISH_LANGUAGE`` entry -- not a literal
    ``"en"``, which would only coincide while the entry stays ``en``. An index
    reaching this function as a bare int therefore resolves (``17`` -> ``en``)
    rather than being interpolated, which would build ``17.m.wikipedia.org``.
    """
    if isinstance(lang_code, int):
        code = _codes(WIKI_LANGS, lang_code, lang_code)[0]
    else:
        code = lang_code
    if code in ("", -1, None):
        code = WIKI_LANGS[17]
    return "https://{0}.m.wikipedia.org".format(code)


def wikipedia_host_for(sl, tl):
    """Host for a dictionary lookup always uses the *target* lang."""
    return _wiki_host(_codes(WIKI_LANGS, sl, tl)[1])


def wikipedia_link() -> str:
    """Port of serviceLink(): always ``https://www.wikipedia.org/``.

    That constant is ``serviceLink``'s, and it is *not* the link the
    ``ResponseData`` carries -- the response's link is the article URL, which is
    ``wikipedia_article_url()``. Two different fields; an earlier version of
    this module conflated them.
    """
    return "https://www.wikipedia.org/"


def wikipedia_lookup(word, sl, tl):
    """Port of serviceDictionaryRequest/Response (bodyContent slice).

    The native also returns article_url = host + /wiki/<word> (the
    ResponseData link field) — see wikipedia_article_url(); the
    fragment alone is returned here to keep all dictionary.py lookups
    string-typed. Vector-skin fallback (catlinks) kept for current
    site markup.
    """
    host = wikipedia_host_for(sl, tl)
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


def wikipedia_article_url(word, sl, tl) -> str:
    """The ResponseData link field: host + /wiki/<word>."""
    host = wikipedia_host_for(sl, tl)
    return host + "/wiki/" + _q(word)


# ------------------------------------------------------------- Google Search
# Services/Google Search/Service.js (SERVICE_ID=10, DICTIONARY only)

GSEARCH_ID = 10
GSEARCH_NAME = "Google Search"
GSEARCH_HOST = "https://www.google.com"
GSEARCH_STYLE = (".main>div{padding-bottom:1em}"
                 ".main>div:first-child,img,button{display:none}")


def gsearch_host() -> str:
    """Port of serviceHost(): always https://www.google.com."""
    return "https://www.google.com"


def gsearch_link(word) -> str:
    """Port of serviceLink(): host + /?q=<word>."""
    return gsearch_host() + "/?q=" + _q(word)


def gsearch_build_uri(word, tl) -> str:
    """Port of buildUri(): ``/search?q=<word>&ie=UTF-8&hl=<target code>``.

    Native resolves ``tl`` through this service's own ``SupportedLanguages``
    (``codeFromLanguage``), so the index 46 becomes ``hl=ru``. Index 1 maps to
    ``""`` natively -- the auto-detect slot -- and interpolating that leaves
    ``hl=`` empty, which is what the native client sends.
    """
    return "/search?q={0}&ie=UTF-8&hl={1}".format(
        _q(word), common.code_from_language(tl, GSEARCH_LANGS)
        if isinstance(tl, int) else tl)
GSEARCH_LANGS = [None, "", "af", "az", "sq", "ar", "hy", "eu", "be", "bg",
                 "ca", "zh-CN", "zh-TW", "hr", "cs", "da", "nl", "en", "et",
                 "fi", "tl", "fr", "gl", "de", "el", "ht", "iw", "hi", "hu",
                 "is", "id", "it", "ga", "ja", "ka", "ko", "lv", "lt", "mk",
                 "ms", "mt", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk",
                 "sl", "es", "sw", "sv", "th", "tr", "uk", "ur", "vi", "cy",
                 "yi", "eo", "hmn", "la", "lo", "kz", "uz", "si", "tg", "te",
                 "km", "mn", "kn", "ta", "mr", "bn", "tt"]


def google_search_lookup(word, sl, tl):
    """Port of serviceDictionaryRequest/Response (main-div slice).

    Faithful to native: main slice -> remove style/script/svg ->
    strip id/name/style/class -> remove h3-h6 -> absolutize links ->
    .main style wrap. The ResponseData link is host + buildUri.
    (Current Google markup is JS-rendered; slice returns "" — port
    kept faithful, not hidden.)
    """
    url = GSEARCH_HOST + gsearch_build_uri(word, tl)
    page = _get(url)
    frag = _sub(page, '<div id="main">', False, "<footer>", False)
    if not frag:
        return ""
    frag = _remove_elements(frag, ["style", "script", "svg"])
    frag = _remove_attributes(frag, ["id", "name", "style", "class"])
    frag = _remove_tags(frag, ["h[3-6]"])
    frag = _update_links(frag, GSEARCH_HOST)
    return ('<style>' + GSEARCH_STYLE + '</style><div class="main">'
            + frag + "</div>")


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
