"""GoogleDictionaryService -- port of plugins/google-services.

GET ``translate.googleapis.com/translate_a/single`` with
``client=gtx&dj=1&dt=bd&dt=ex&dt=md&sl=<lang>&tl=<lang>&q=<word>``:
the dictionary data types return pos-tagged entries, glosses,
examples and synonyms in one payload.

Returns the DICT_EXT contract: an HTML fragment for the card, or ""
when nothing usable came back (the caller treats "" as no card).
"""
import html as _html
import json
import urllib.parse
import urllib.request

from qtranslate import common

ENDPOINT = "https://translate.googleapis.com/translate_a/single"
FEATURES = ("bd", "ex", "md")


def _lang_tag(lang):
    try:
        from qtranslate.services import google_translate as _GT
        return _GT._lang_code(lang or "en") or "en"
    except Exception:
        return lang or "en"


def lookup(word, lang="en", target="", opener=None):
    """fn(word, src, tgt) -> HTML fragment (DICT_EXT contract)."""
    word = (word or "").strip()
    if not word:
        return ""
    tag = _lang_tag(lang)
    params = [("client", "gtx"), ("dj", "1")]
    params += [("dt", f) for f in FEATURES]
    params += [("sl", tag), ("tl", tag), ("q", word)]
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "gtx"})
    try:
        with common.http_open(req, opener) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception:
        return ""
    try:
        obj = json.loads(body)
    except Exception:
        obj = common.parse_json_lenient(body)
    if not isinstance(obj, dict):
        return ""
    entries = _entries(obj, word)
    if not entries:
        return ""
    return _render(entries)


def _entries(obj, word):
    """Kotlin lookup(): dict-section entries first, definitions-only
    fallback when the dict section is absent."""
    out = []
    dicts = obj.get("dict") or []
    definitions = obj.get("definitions") or []
    examples_by_id = {}
    for ex in ((obj.get("examples") or {}).get("example") or []):
        if isinstance(ex, dict) and ex.get("definition_id"):
            examples_by_id[ex["definition_id"]] = ex.get("text") or ""
    if dicts:
        for d in dicts:
            if not isinstance(d, dict):
                continue
            defs = []
            pos = (d.get("pos") or "").lower()
            for term in d.get("entry") or []:
                if not isinstance(term, dict):
                    continue
                rev = term.get("reverse_translation") or []
                defs.append({
                    "text": term.get("word") or "",
                    "example": rev[0] if rev else ""})
            for df in definitions:
                if not isinstance(df, dict):
                    continue
                if not (df.get("pos") or "").lower() == pos:
                    continue
                for e in df.get("entry") or []:
                    if not isinstance(e, dict):
                        continue
                    defs.append({
                        "text": e.get("gloss") or "",
                        "example": e.get("example")
                            or examples_by_id.get(
                                e.get("definition_id"), "")})
            terms = [t for t in (d.get("terms") or [])
                     if isinstance(t, str)]
            base = d.get("base_form")
            synonyms = [t for t in dict.fromkeys(terms)
                        if t != base][:10]
            out.append({
                "word": base or word,
                "pos": d.get("pos") or "",
                "definitions": _dedup(defs)[:10],
                "synonyms": synonyms})
    elif definitions:
        for df in definitions:
            if not isinstance(df, dict):
                continue
            defs = [{"text": e.get("gloss") or "",
                     "example": e.get("example")
                         or examples_by_id.get(
                             e.get("definition_id"), "")}
                    for e in (df.get("entry") or [])
                    if isinstance(e, dict)]
            out.append({
                "word": df.get("base_form") or word,
                "pos": df.get("pos") or "",
                "definitions": defs,
                "synonyms": []})
    return [e for e in out if e["definitions"]]


def _dedup(defs):
    seen = set()
    out = []
    for d in defs:
        key = d["text"]
        if key and key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _render(entries):
    parts = []
    for e in entries[:3]:
        head = "<b>%s</b>" % _html.escape(e["word"])
        if e["pos"]:
            head += " <i>(%s)</i>" % _html.escape(e["pos"])
        lines = [head]
        for d in e["definitions"][:5]:
            text = _html.escape(d["text"])
            if d.get("example"):
                text += " <i>— %s</i>" % _html.escape(d["example"])
            lines.append("<div>%s</div>" % text)
        if e["synonyms"]:
            lines.append("<div><i>Synonyms: %s</i></div>"
                         % _html.escape(", ".join(e["synonyms"])))
        parts.append("<div>%s</div>" % "".join(lines))
    return "".join(parts)
