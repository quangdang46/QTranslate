#!/usr/bin/env python3
"""GoogleSpellCheckerService port (plugins/google-services):
translate_a/single?client=gtx&dt=qc spell section -> corrections in
the shared bing_spell/system_spell shape."""
import io
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate import common  # noqa: E402
from qtranslate.services import google_spell as GS  # noqa: E402


def _resp(payload):
    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return R(json.dumps(payload).encode())


def main():
    print("== request shape ==")
    seen = {}

    def capture(req, opener=None):
        seen["url"] = req.full_url
        return _resp({
            "sentences": [{"trans": "x"}],
            "src": "en",
            "spell": {"spell_res": "the quick brown fox",
                      "spell_html_res": "the quick brown <b><i>fox</i></b>"},
        })

    orig = common.http_open
    common.http_open = capture
    try:
        res = GS.check("teh quik brown foxx", "en")
    finally:
        common.http_open = orig
    q = urllib.parse.parse_qs(urllib.parse.urlparse(seen["url"]).query)
    ck("endpoint", seen["url"].startswith(GS.ENDPOINT))
    ck("client gtx", q.get("client") == ["gtx"])
    ck("dj=1", q.get("dj") == ["1"])
    ck("dt=qc", q.get("dt") == ["qc"])
    ck("dummy target zu", q.get("tl") == ["zu"])
    ck("sl en", q.get("sl") == ["en"])

    print("== corrections ==")
    ck("correctedText", res["correctedText"] == "the quick brown fox",
       res["correctedText"])
    ck("three corrections", len(res["corrections"]) == 3,
       str(len(res["corrections"])))
    c0 = res["corrections"][0]
    ck("first correction", c0["original"] == "teh"
       and c0["startIndex"] == 0 and c0["endIndex"] == 3
       and c0["suggestions"] == ["the"] and c0["type"] == "SPELLING",
       str(c0))
    c2 = res["corrections"][2]
    ck("third correction", c2["original"] == "foxx"
       and c2["startIndex"] == 15 and c2["endIndex"] == 19, str(c2))

    print("== no-mark gate ==")
    def capture_nomark(req, opener=None):
        return _resp({
            "sentences": [{"trans": "x"}], "src": "en",
            "spell": {"spell_res": "same text",
                      "spell_html_res": "same text"}})
    common.http_open = capture_nomark
    try:
        res = GS.check("same text", "en")
    finally:
        common.http_open = orig
    ck("no marks -> no corrections",
       res["correctedText"] == "same text" and res["corrections"] == [],
       str(res))

    print("== no spell section ==")
    def capture_nospell(req, opener=None):
        return _resp({"sentences": [{"trans": "x"}], "src": "en"})
    common.http_open = capture_nospell
    try:
        res = GS.check("hello world", "en")
    finally:
        common.http_open = orig
    ck("no spell -> input back",
       res["correctedText"] == "hello world" and res["corrections"] == [],
       str(res))

    print("== unrecognised payload ==")
    def capture_empty(req, opener=None):
        return _resp({"sentences": [], "src": ""})
    common.http_open = capture_empty
    try:
        res = GS.check("teh", "en")
    finally:
        common.http_open = orig
    ck("empty payload -> None", res is None, str(res))

    print("== sentence splitting + offsets ==")
    def capture_two(req, opener=None):
        q = urllib.parse.parse_qs(
            urllib.parse.urlparse(req.full_url).query)
        sent = q["q"][0]
        if sent.startswith("Sec"):
            return _resp({"sentences": [{"trans": "x"}], "src": "en",
                          "spell": {"spell_res": "Second sentance!",
                                    "spell_html_res":
                                    "Second <b><i>sentance</i></b>!"}})
        return _resp({"sentences": [{"trans": "x"}], "src": "en",
                      "spell": {"spell_res": "First line.",
                                "spell_html_res":
                                "<b><i>First</i></b> line."}})
    common.http_open = capture_two
    try:
        res = GS.check("Frist line. Secnd sentance!", "en")
    finally:
        common.http_open = orig
    ck("two sentences joined",
       res["correctedText"] == "First line. Second sentance!",
       res["correctedText"])
    offs = [(c["original"], c["startIndex"], c["endIndex"])
            for c in res["corrections"]]
    ck("offsets span sentences",
       offs == [("Frist", 0, 5), ("Secnd", 12, 17)], str(offs))

    print("== edge cases ==")
    ck("blank -> passthrough",
       GS.check("   ", "en") == {"correctedText": "   ",
                                "corrections": []})

    print("== repeated words ==")
    def capture_rep(req, opener=None):
        return _resp({"sentences": [{"trans": "x"}], "src": "en",
                      "spell": {"spell_res": "the cat the dog",
                                "spell_html_res":
                                "the cat the <b><i>dog</i></b>"}})
    # "teh cat teh dog" -> corrected "the cat the dog": word index 2
    # differs (teh->the) and must map to the SECOND teh, not the first.
    common.http_open = capture_rep
    try:
        res = GS.check("teh cat teh dog", "en")
    finally:
        common.http_open = orig
    offs = [(c["original"], c["startIndex"]) for c in res["corrections"]]
    ck("repeated word maps second occurrence",
       offs == [("teh", 0), ("teh", 8)], str(offs))

    print()
    if FAIL:
        print("regress_google_spell: %d FAILED: %s" % (len(FAIL), FAIL))
        sys.exit(1)
    print("regress_google_spell: all checks ok")


if __name__ == "__main__":
    main()
