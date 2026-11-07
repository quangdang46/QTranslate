"""Bing Spell Checker -- the .tmp ``bing-services`` plugin's
BingSpellCheckerService port.

Reference: plugins/bing-services/.../BingSpellCheckerService.kt. POSTs
to ``bing.com/tspellcheckv3`` with the same scraped auth the translator
uses (``session.bing_session``: IG + abuse-prevention token/key + the
shared cookie jar carrying MUID), form fields ``text``/``fromLang``/
``token``/``key`` and query ``isVertical=1&IG=&IID=&SFX=2``. The
response is ``{"correctedText": "..."}`` -- Bing returns only the
corrected string, so corrections are derived by diffing original vs
corrected word lists, exactly like Kotlin's ``generateCorrections``
(CHANGE and DELETE deltas become Correction records with the original
span located by ``text.indexOf(phrase)``).

Text is partitioned into <=1000-char chunks on whitespace like
``partitionText``; corrected chunks are joined back with single
spaces.

Spell-check language set is the Kotlin ``spellCheckLanguageCodes``
(20 entries), mapped through ``toProviderCode`` (no->nb,
pt-BR->pt, zh-CN->zh-Hans, zh-TW->zh-Hant, sr->sr-Cyrl).
"""
from __future__ import annotations

import difflib
import json
import urllib.parse
import urllib.request

from qtranslate import common
from qtranslate import session as _S

SPELLCHECK_URL = "https://www.bing.com/tspellcheckv3"
MAX_CHUNK_LENGTH = 1000

# Kotlin spellCheckLanguageCodes, in app-level codes.
SPELL_LANGS = {
    "da", "en", "nl", "fi", "fr", "fr-CA", "de", "it", "ja", "ko",
    "no", "pl", "pt", "pt-PT", "ru", "es", "sv", "tr",
    "zh-TW", "zh-CN",
}

_UA = {"User-Agent": "QTranslate/6.10 (bing spell)"}


def _to_provider(code):
    """BingLanguageMapper.toProviderCode for the spell-check path."""
    code = (code or "").strip()
    if code in ("", "auto", "auto-detect"):
        return "auto-detect"
    return {"no": "nb", "pt-BR": "pt", "pt-PT": "pt-PT",
            "zh-CN": "zh-Hans", "zh-TW": "zh-Hant",
            "sr": "sr-Cyrl"}.get(code, code)


def partition_text(text):
    """Kotlin partitionText: whitespace words packed into <=1000-char
    chunks joined by single spaces."""
    chunks = [""]
    for word in (text or "").split():
        if not chunks[-1]:
            chunks[-1] = word
        elif len(chunks[-1] + " " + word) > MAX_CHUNK_LENGTH:
            chunks.append(word)
        else:
            chunks[-1] += " " + word
    return [c for c in chunks if c.strip()]


def _post_chunk(text, lang, auth, opener=None):
    form = {
        "text": text,
        "fromLang": lang,
        "token": auth["token"],
        "key": auth["key"],
    }
    qs = urllib.parse.urlencode({
        "isVertical": 1, "IG": auth["IG"],
        "IID": auth.get("iid", "translator.5023"), "SFX": 2})
    body = urllib.parse.urlencode(form).encode()
    headers = {**_UA,
               "Content-Type":
                   "application/x-www-form-urlencoded; charset=utf-8",
               "Origin": "https://www.bing.com",
               "Referer": "https://www.bing.com/translator"}
    # Kotlin sends cookies={"MUID": auth.muid} -- the page-embedded
    # MUID alone, not the session cookie jar (verified live: the jar
    # answers {"correctedText":""}).
    muid = auth.get("muid") or ""
    if muid:
        headers["Cookie"] = "MUID=" + muid
    elif auth.get("cookie"):
        headers["Cookie"] = auth["cookie"]
    req = urllib.request.Request(
        SPELLCHECK_URL + "?" + qs, data=body, headers=headers)
    with common.http_open(req, opener) as r:
        obj = json.loads(r.read().decode("utf-8", errors="replace"))
    return (obj.get("correctedText") or "").strip() or text


def generate_corrections(original, corrected):
    """Kotlin generateCorrections: word-level diff -> Correction dicts.

    CHANGE deltas carry the corrected text as a one-item suggestion;
    DELETE deltas carry an empty suggestion list. INSERT deltas have
    no original span and are skipped. Positions come from
    ``str.indexOf`` on the joined phrase.
    """
    corrections = []
    orig_words = original.split(" ")
    corr_words = corrected.split(" ")
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, orig_words, corr_words).get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            continue                     # no original span to map
        orig_text = " ".join(orig_words[i1:i2])
        pos = original.find(orig_text)
        if pos == -1:
            continue
        corr_text = " ".join(corr_words[j1:j2]) if tag == "replace" else ""
        corrections.append({
            "original": orig_text,
            "startIndex": pos,
            "endIndex": pos + len(orig_text),
            "suggestions": [corr_text] if corr_text else [],
            "type": "SPELLING",
        })
    return corrections


def check(text, lang="en", opener=None, session=None):
    """Spell-check ``text``; returns {"correctedText", "corrections"}.

    ``session`` may inject a bing_session() dict (tests); ``opener`` is
    forwarded to common.http_open like the other service modules.
    Blank text returns the input untouched, per Kotlin's early Ok.
    """
    text = text or ""
    if not text.strip():
        return {"correctedText": text, "corrections": []}
    auth = session if session is not None else _S.bing_session()
    net = opener if opener is not None else auth.get("opener")
    prov = _to_provider(lang)
    corrected_chunks = [_post_chunk(chunk, prov, auth, net)
                        for chunk in partition_text(text)]
    corrected = " ".join(corrected_chunks).strip()
    return {"correctedText": corrected,
            "corrections": generate_corrections(text, corrected)}
