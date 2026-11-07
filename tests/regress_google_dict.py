#!/usr/bin/env python3
"""GoogleDictionaryService port (plugins/google-services):
translate_a/single?dt=bd,ex,md -> HTML fragment for DICT_EXT."""
import io
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate import common  # noqa: E402
from qtranslate.services import google_dict as GD  # noqa: E402


def _resp(payload):
    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return R(json.dumps(payload).encode())


DICT_PAYLOAD = {
    "sentences": [{"trans": "x"}],
    "src": "en",
    "dict": [{
        "pos": "noun",
        "base_form": "serendipity",
        "terms": ["serendipity", "chance", "luck"],
        "entry": [
            {"word": "stroke of luck",
             "reverse_translation": ["món hời"]},
            {"word": "happy accident",
             "reverse_translation": ["tai nạn may mắn"]},
        ],
    }],
    "definitions": [{
        "pos": "noun",
        "entry": [{"gloss": "happy coincidence",
                   "example": "a serendipitous meeting",
                   "definition_id": "d1"}],
    }],
    "examples": {"example": [{"text": "a serendipitous meeting",
                              "definition_id": "d1"}]},
}


def main():
    print("== request shape ==")
    seen = {}

    def capture(req, opener=None):
        seen["url"] = req.full_url
        return _resp(DICT_PAYLOAD)

    orig = common.http_open
    common.http_open = capture
    try:
        frag = GD.lookup("serendipity", "en", "vi")
    finally:
        common.http_open = orig
    q = urllib.parse.parse_qs(urllib.parse.urlparse(seen["url"]).query)
    q_multi = urllib.parse.parse_qs(
        urllib.parse.urlparse(seen["url"]).query, keep_blank_values=True)
    ck("endpoint", seen["url"].startswith(GD.ENDPOINT))
    ck("client gtx", q.get("client") == ["gtx"])
    ck("dt features sent",
       sorted(q_multi.get("dt", [])) == ["bd", "ex", "md"],
       str(q_multi.get("dt")))
    ck("sl=tl=lang", q.get("sl") == ["en"] and q.get("tl") == ["en"])

    print("== fragment ==")
    ck("non-empty", bool(frag))
    ck("word + pos", "<b>serendipity</b>" in frag and "(noun)" in frag,
       frag[:120])
    ck("term def + example",
       "stroke of luck" in frag and "món hời" in frag, frag[:200])
    ck("pos-matched gloss",
       "happy coincidence" in frag and "a serendipitous meeting" in frag)
    ck("synonyms", "Synonyms:" in frag and "chance" in frag
       and "serendipity" not in frag.split("Synonyms:")[1],
       frag)

    print("== definitions-only fallback ==")
    payload = {"sentences": [{"trans": "x"}], "src": "en",
               "definitions": [{"pos": "verb", "base_form": "run",
                                "entry": [{"gloss": "to move fast",
                                           "example": "dogs run"}]}]}
    common.http_open = lambda req, opener=None: _resp(payload)
    try:
        frag = GD.lookup("run", "en", "vi")
    finally:
        common.http_open = orig
    ck("fallback renders", "<b>run</b>" in frag and "(verb)" in frag
       and "to move fast" in frag, frag[:150])

    print("== empty / failure ==")
    common.http_open = lambda req, opener=None: _resp(
        {"sentences": [{"trans": "x"}], "src": "en"})
    try:
        frag = GD.lookup("zzzznotaword", "en", "vi")
    finally:
        common.http_open = orig
    ck("no entries -> empty", frag == "")

    def boom(req, opener=None):
        raise OSError("net down")
    common.http_open = boom
    try:
        frag = GD.lookup("word", "en", "vi")
    finally:
        common.http_open = orig
    ck("http failure -> empty", frag == "")

    ck("blank word -> empty", GD.lookup("  ", "en", "vi") == "")

    print()
    if FAIL:
        print("regress_google_dict: %d FAILED: %s" % (len(FAIL), FAIL))
        sys.exit(1)
    print("regress_google_dict: all checks ok")


if __name__ == "__main__":
    main()
