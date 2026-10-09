"""Regression: Google `dt=rm` romanization — J7's phonetics source.

Two things are pinned here, both measured against the live endpoint on
2026-10-10:

1. **The parse slot is index 3, not index 2.** `_translate_response` read
   `e[2]` and returned it as the romanization; the caller discarded it, so
   the bug was invisible. Live shape for
   `client=gtx&sl=zh-CN&tl=en&dt=t&dt=rm` on `你好`:

   ```json
   [[["Hello","你好",null,null,10],
     [null,null,null,"Nǐ hǎo"]]]
   ```

   `e[2]` is `null` on the romanization segment — the string is at `e[3]`.
   Isolated by `dt`: `dt=rm` alone yields exactly one segment
   `[null,null,null,"Nǐ hǎo"]`; `dt=t` alone yields none.
2. **The romanization reaches `phonetics.append_phonetics`** via the module
   accessors, i.e. J7's three gates now have a real value to gate on.

The offline cases use the exact live payloads. `--live` re-fetches them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate.services import google_translate as G  # noqa: E402
from qtranslate import phonetics as P  # noqa: E402

LIVE = "--live" in sys.argv
fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


# The exact payload the endpoint returned for 你好 (zh-CN -> en).
# Kept verbatim so the assertions test the parse, not a live fetch.
ZH_LIVE = [[
    ["Hello", "你好", None, None, 10],
    [None, None, None, "Nǐ hǎo"],
]]
JA_LIVE = [[
    ["thank you", "ありがとう ございます", None, None, 10],
    [None, None, None, "Arigatōgozaimasu"],
]]
# A response with no romanization segment at all (dt=rm absent / empty).
NO_ROM = [[["Hello", "你好", None, None, 10]]]
# A short segment that stops before index 3 — must not raise.
SHORT = [[["Hello", "你好", None]]]

b, sl, tl, g = G._translate_response(ZH_LIVE, "auto", "en")
ck("live zh payload: translation parsed", b == "Hello", repr(b))
ck("live zh payload: romanization from index 3",
   g == "Nǐ hǎo", repr(g))
ck("the return is the documented 4-tuple", (sl, tl) == ("auto", "en"))

b2, _, _, g2 = G._translate_response(JA_LIVE, "auto", "en")
ck("live ja multi-word: romanization from the last segment",
   g2 == "Arigatōgozaimasu", repr(g2))

_, _, _, g3 = G._translate_response(NO_ROM, "auto", "en")
ck("no romanization segment -> empty, not a crash", g3 == "", repr(g3))

_, _, _, g4 = G._translate_response(SHORT, "auto", "en")
ck("segment shorter than 4 slots -> empty, no IndexError", g4 == "", repr(g4))

_, _, _, g5 = G._translate_response(None, "auto", "en")
ck("None response -> empty", g5 == "")

# The old code read e[2]; prove the pin is load-bearing, not decorative.
def _old_parse(obj):
    g = ""
    f = obj[0] if obj and len(obj) > 0 else None
    if f:
        for d, e in enumerate(f):
            if e and len(e):
                if len(e) > 2 and d == len(f) - 1:
                    g = e[2] or ""
    return g

ck("the old e[2] read yields nothing on the live payload",
   _old_parse(ZH_LIVE) == "", repr(_old_parse(ZH_LIVE)))

# --- the accessors that carry it to the render path ---
G.set_romanization(None)
ck("accessor resets to empty", G.get_romanization() == "")
G.set_romanization("Nǐ hǎo")
ck("accessor stores the value", G.get_romanization() == "Nǐ hǎo")

# --- stale state must not survive into a later, different result ---
# translate() overwrites the slot on the gtx path and clears it on the
# dict-chrome-ex fallback (which sends no dt=rm). Without that clear, a
# previous call's romanization would be appended to an unrelated result.
_src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "services",
    "google_translate.py"), encoding="utf-8").read()
ck("the 429 fallback clears the slot",
   _src.count('set_romanization("")') == 1,
   "expected exactly one clearing call (the fallback)")
ck("the gtx path always overwrites the slot",
   "set_romanization(g)" in _src)

# --- the three J7 gates now have data to act on ---
out = "Hello"
ck("gate 3 off -> unchanged",
   P.append_phonetics(out, G.get_romanization(), enabled=False) == "Hello")
ck("gate 1 (<Error>) -> unchanged",
   P.append_phonetics("<Error>", G.get_romanization(), enabled=True)
   == "<Error>")
ck("all three open -> native append",
   P.append_phonetics(out, G.get_romanization(), enabled=True)
   == "Hello\r\r" + "Romanization: " + "Nǐ hǎo")
ck("empty romanization -> unchanged (gate 2)",
   P.append_phonetics(out, "", enabled=True) == "Hello")

# --- the request must still ask for dt=rm ---
_src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "services",
    "google_translate.py"), encoding="utf-8").read()
ck("translate() requests dt=rm", "dt=rm" in _src)

if LIVE:
    import json
    import urllib.parse
    import urllib.request

    def fetch(sl, tl, q):
        url = ("https://translate.google.com/translate_a/single?"
               "client=gtx&sl=%s&tl=%s&ie=UTF-8&oe=UTF-8&tk=0.0&q=%s"
               "&dt=t&dt=rm" % (sl, tl, urllib.parse.quote(q, safe="")))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    try:
        for sl, tl, q, want in [
                ("zh-CN", "en", "你好", "Nǐ hǎo"),
                ("ko", "en", "안녕하세요", "annyeonghaseyo"),
                ("ja", "en", "こんにちは", "Kon'nichiwa"),
                ("ru", "en", "Привет", "Privet")]:
            got = G._translate_response(fetch(sl, tl, q), "auto", "en")[3]
            ck("live %s romanization" % sl, got == want, repr(got))
    except Exception as e:  # a dead endpoint is not a failed assertion
        print("  (live fetch skipped: %s: %s)" % (type(e).__name__, e))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_google_romanization: all checks ok (%d assertions)" % n[0])
