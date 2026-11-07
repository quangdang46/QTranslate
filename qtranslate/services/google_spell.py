"""GoogleSpellCheckerService -- port of plugins/google-services.

GET ``translate.googleapis.com/translate_a/single`` with
``client=gtx&dj=1&dt=qc&sl=<lang>&tl=zu``: the ``zu`` target is a dummy
(Zulu) so nothing actually translates; the ``spell`` section of the
response carries ``spell_res`` (corrected text) and ``spell_html_res``
(the ``<b><i>word</i></b>`` marks around corrected words).

Differences from the Kotlin original:

* no sentence cache -- the port's spell chain (system -> bing ->
  google -> ai) already degrades quietly, and a per-check cache would
  need invalidation rules the Kotlin gets from its plugin lifecycle;
* repeated-word offsets use a running search position instead of
  ``indexOf`` from zero, which fixes the Kotlin bug where the second
  occurrence of a repeated word mapped onto the first;
* the endpoint-health circuit breaker IS shared with the translator
  (``google_translate.ENDPOINT_HEALTH``), like upstream: an open
  circuit makes this backend report unavailable so the chain moves
  on without paying the throttled host's timeout.

Returns the bing_spell/system_spell dict shape:
``{"correctedText": str, "corrections": [...]}``, or ``None`` when the
backend is unavailable so the caller falls through to the next one.
"""
import json
import re
import urllib.parse
import urllib.request

from qtranslate import common

ENDPOINT = "https://translate.googleapis.com/translate_a/single"
_SENTENCE_SPLIT = re.compile(r"(?<=[.?!])\s*")
_MARKED_WORD = re.compile(r"<b><i>(.*?)</i></b>")


def _lang_tag(lang):
    try:
        from qtranslate.services import google_translate as _GT
        return _GT._lang_code(lang or "en") or "en"
    except Exception:
        return lang or "en"


def _check_sentence(sentence, lang, opener=None):
    """One sentence -> (correctedText, corrections) or None."""
    from qtranslate.services import google_translate as _GT
    permit = _GT.ENDPOINT_HEALTH.try_acquire()
    if permit is None:
        return None
    qs = urllib.parse.urlencode({
        "client": "gtx", "dj": 1, "sl": _lang_tag(lang), "tl": "zu",
        "q": sentence, "dt": "qc"})
    req = urllib.request.Request(ENDPOINT + "?" + qs,
                                 headers={"User-Agent": "gtx"})
    try:
        with common.http_open(req, opener) as r:
            body = r.read().decode("utf-8", "replace")
        _GT.ENDPOINT_HEALTH.record_success(permit)
    except Exception:
        _GT.ENDPOINT_HEALTH.record_failure(permit)
        raise
    finally:
        _GT.ENDPOINT_HEALTH.release(permit)
    try:
        obj = json.loads(body)
    except Exception:
        obj = common.parse_json_lenient(body)
    if not isinstance(obj, dict):
        return None
    # Kotlin's "unrecognised payload" guard: an all-defaults body (a
    # throttle/error page that still parses) is a failure, not "no
    # corrections" -- returning it would cache a fake clean bill.
    spell = obj.get("spell")
    if (not obj.get("sentences") and spell is None
            and not obj.get("src")):
        return None
    corrected = ""
    html = ""
    if isinstance(spell, dict):
        corrected = spell.get("spell_res") or ""
        html = spell.get("spell_html_res") or ""
    if not spell or not corrected or not html:
        return {"correctedText": sentence, "corrections": []}

    # Kotlin only uses the <b><i> marks as a "there are corrections"
    # gate, then diffs corrected vs original word-by-word.
    if not _MARKED_WORD.search(html):
        return {"correctedText": corrected, "corrections": []}

    corrections = []
    corr_words = corrected.split(" ")
    orig_words = sentence.split(" ")
    search_from = 0
    for i, corr in enumerate(corr_words):
        orig = orig_words[i] if i < len(orig_words) else None
        if orig is None or orig == corr:
            continue
        pos = sentence.find(orig, search_from)
        if pos == -1:
            pos = sentence.find(orig)
        if pos == -1:
            continue
        search_from = pos + len(orig)
        corrections.append({
            "original": orig,
            "startIndex": pos,
            "endIndex": pos + len(orig),
            "suggestions": [corr],
            "type": "SPELLING",
        })
    return {"correctedText": corrected, "corrections": corrections}


def check(text, lang="en", opener=None):
    """Spell-check ``text``; bing_spell-shaped dict or None on failure.

    Sentences split on ``(?<=[.?!])\\s*`` exactly like the Kotlin
    ``request.text.split(...)``; offsets accumulate across sentences
    the same way (``indexOf`` from the running position).
    """
    text = text or ""
    if not text.strip():
        return {"correctedText": text, "corrections": []}
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    corrected_sentences = []
    all_corrections = []
    cursor = 0
    for sent in sentences:
        pos = text.find(sent, cursor)
        if pos == -1:
            pos = cursor
        cursor = pos + len(sent)
        try:
            res = _check_sentence(sent, lang, opener)
        except Exception:
            return None
        if res is None:
            return None
        corrected_sentences.append(res["correctedText"])
        for c in res["corrections"]:
            all_corrections.append(dict(
                c, startIndex=c["startIndex"] + pos,
                endIndex=c["endIndex"] + pos))
    return {"correctedText": " ".join(corrected_sentences).strip(),
            "corrections": all_corrections}
