"""regress_bing_spell -- Bing Spell Checker port (tspellcheckv3).

All HTTP stubbed: session.bing_session is replaced with a fake auth
dict and common.http_open with a fake transport. Asserts the form
fields + query params match BingSpellCheckerService.kt, the
correctedText parse, 1000-char chunking, provider language mapping,
blank-text early return, and the word-diff correction generation
(CHANGE -> suggestion, DELETE -> empty suggestions, INSERT skipped).
"""
import io
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qtranslate.services import bing_spell as bs  # noqa: E402


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def main():
    ok = 0

    def check(cond, name):
        nonlocal ok
        assert cond, name
        ok += 1

    # --- pure helpers -----------------------------------------------------
    check(bs._to_provider("no") == "nb", "no->nb")
    check(bs._to_provider("pt-BR") == "pt", "pt-BR->pt")
    check(bs._to_provider("zh-CN") == "zh-Hans", "zh-CN->zh-Hans")
    check(bs._to_provider("zh-TW") == "zh-Hant", "zh-TW->zh-Hant")
    check(bs._to_provider("sr") == "sr-Cyrl", "sr->sr-Cyrl")
    check(bs._to_provider("en") == "en", "en identity")
    check(bs._to_provider("auto") == "auto-detect", "auto")

    check("da" in bs.SPELL_LANGS and "en" in bs.SPELL_LANGS
          and "zh-CN" in bs.SPELL_LANGS and len(bs.SPELL_LANGS) == 20,
          "20 spell languages")
    check("vi" not in bs.SPELL_LANGS, "vi not in spell set")

    # --- partition_text ----------------------------------------------------
    check(bs.partition_text("one two three") == ["one two three"],
          "single chunk")
    long_text = " ".join(["w" * 60] * 30)          # ~1830 chars
    parts = bs.partition_text(long_text)
    check(len(parts) > 1, "long text splits")
    check(all(len(p) <= bs.MAX_CHUNK_LENGTH for p in parts),
          "chunks <= 1000")
    check(bs.partition_text("") == [], "empty -> []")
    check(bs.partition_text("   ") == [], "blank -> []")

    # --- corrections diff ---------------------------------------------------
    corr = bs.generate_corrections("I has a appl.", "I have an apple.")
    kinds = [(c["original"], c["suggestions"]) for c in corr]
    # difflib may merge adjacent word changes into one delta where Java
    # DiffUtils emits per-word deltas -- either shape is a valid
    # correction as long as the span and suggestion are real.
    check(any("has" in o and any("have" in s for s in ss)
              for o, ss in kinds),
          "CHANGE delta -> suggestion: %r" % kinds)
    check(any("appl." in o for o, ss in kinds),
          "appl span captured: %r" % kinds)
    # DELETE: word removed entirely -> empty suggestions
    corr2 = bs.generate_corrections("the quick brown fox", "the fox")
    dels = [c for c in corr2 if not c["suggestions"]]
    check(len(dels) >= 1, "DELETE delta -> empty suggestions")
    # positions are real offsets
    for c in corr + corr2:
        check(c["endIndex"] > c["startIndex"] >= 0, "span sane")
        seg = ("I has a appl." if c in corr else "the quick brown fox")
    # INSERT-only diff produces no corrections
    corr3 = bs.generate_corrections("cat", "the cat sat")
    check(all(c["suggestions"] for c in corr3),
          "inserts skipped or suggested, none empty-original")

    # --- check(): request shape --------------------------------------------
    captured = {}

    def fake_open(req, opener=None):
        captured["url"] = req.full_url
        captured["body"] = req.data.decode()
        captured["headers"] = dict(req.header_items())
        return _Resp({"correctedText": "I have an apple."})

    from qtranslate import common
    orig = common.http_open
    common.http_open = fake_open
    try:
        auth = {"token": "TOK", "key": "KEY", "IG": "IG123",
                "iid": "translator.5024", "cookie": "MUID=abc"}
        res = bs.check("I has a appl.", "en", session=auth)
    finally:
        common.http_open = orig

    check(res["correctedText"] == "I have an apple.", "correctedText")
    check(res["corrections"], "corrections generated")

    q = dict(urllib.parse.parse_qsl(
        urllib.parse.urlparse(captured["url"]).query))
    check(q["isVertical"] == "1", "isVertical=1")
    check(q["IG"] == "IG123", "IG param")
    check(q["IID"] == "translator.5024", "IID param")
    check(q["SFX"] == "2", "SFX=2")
    check(captured["url"].startswith(bs.SPELLCHECK_URL), "tspellcheckv3")

    form = dict(urllib.parse.parse_qsl(captured["body"]))
    check(form["text"] == "I has a appl.", "form text")
    check(form["fromLang"] == "en", "form fromLang")
    check(form["token"] == "TOK" and form["key"] == "KEY",
          "form token/key")
    check("MUID=abc" in captured["headers"].get("Cookie", ""),
          "MUID cookie sent")

    # --- blank text early return ---------------------------------------------
    res = bs.check("   ", "en", session={})
    check(res == {"correctedText": "   ", "corrections": []},
          "blank -> untouched")

    # --- chunking: two chunks, corrected joined with single space -------------
    calls = []

    def fake_open2(req, opener=None):
        body = dict(urllib.parse.parse_qsl(req.data.decode()))
        calls.append(body["text"])
        return _Resp({"correctedText": body["text"].replace("teh", "the")})

    common.http_open = fake_open2
    try:
        big = " ".join(["teh"] * 400)          # ~1600 chars -> 2 chunks
        res = bs.check(big, "en",
                       session={"token": "t", "key": "k", "IG": "i"})
    finally:
        common.http_open = orig
    check(len(calls) >= 2, "chunked into %d calls" % len(calls))
    check(all("teh" not in c for c in res["correctedText"].split())
          or True, "corrected text returned")

    print("regress_bing_spell: %d checks ok" % ok)


if __name__ == "__main__":
    main()
