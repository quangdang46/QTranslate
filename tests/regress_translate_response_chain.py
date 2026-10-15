"""Regression: the translate response chains of all 9 providers.

Every one of the 9 translate providers has a recovered
``serviceTranslateResponse`` in the payload (read with brace counting,
never windowed — see ``regress_dict_response_chain.py`` for why a window
is wrong here too). This suite pins each chain's control flow against
the port.

Two real findings while writing it, both fixed 2026-10-16:

  1. **Yandex ``_useDictionary`` used the wrong split.** Native is
     ``3 >= a.split(/\\s+/).length``. ``str.split()`` collapses whitespace
     runs and drops the empty members, so ``"   a b c"`` (4 JS members,
     native rejects) looked like 3 members to the port, which accepted
     it. Fixed to ``re.split(r"\\s+", text)``.
  2. **Microsoft had two identical ``_is_short_text`` definitions** --
     the first was dead. Removed.

Google's romanization slot is pinned as a **recorded divergence**, not a
bug: native reads ``e[2]`` (and its guard is ``2 < e.length``), while the
port reads ``e[3]`` because the live shape puts the romanization there
and native's own slot is ``null``. The port deliberately keeps the value
that works, and this suite says so rather than letting the next reader
"correct" it back to native.

Headless: the JS is read from the artifact, never executed. Skips cleanly
when the artifact is absent.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present (%s)" % PAYLOAD)
    raise SystemExit(0)

TS = open(PAYLOAD, "rb").read().decode("utf-8", "replace")
HEADS = [(m.start(), int(m.group(1)))
         for m in re.finditer(r'new ServiceHeader\((\d+),', TS)]


def segment(sid):
    i = TS.find("new ServiceHeader(%d," % sid)
    if i < 0:
        return ""
    nxt = [h[0] for h in HEADS if h[0] > i]
    return TS[i:nxt[0] if nxt else len(TS)]


def body_of(sid, name):
    seg = segment(sid)
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", seg)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(seg) and depth:
        if seg[i] == "{":
            depth += 1
        elif seg[i] == "}":
            depth -= 1
        i += 1
    return seg[m.end():i - 1]


def respond(sid):
    return body_of(sid, "serviceTranslateResponse")


# --- 1. every one of the 9 providers really has a chain ------------------
TRANSLATE_IDS = [1, 5, 11, 12, 13, 28, 30, 31, 26]
for sid in TRANSLATE_IDS:
    ck("service %d has a serviceTranslateResponse" % sid,
       len(respond(sid)) > 20, "empty")

# --- 2. the shape each ResponseData carries -----------------------------
SHAPES = {
    1: "new ResponseData(b,c,h,g)",        # + romanization in slot 4
    5: "new ResponseData(b,c,d,null,a)",   # + nextRequestHandler
    11: "new ResponseData(b,c,e,null,d)",
    12: "new ResponseData(b,d,c)",         # sl/tl re-resolved from a.from/to
    13: "new ResponseData(a,c,e)",
    28: "new ResponseData(b,e,g)",
    30: "new ResponseData(k,a,l)",
    31: 'new ResponseData(d,e,c,"")',
    26: "new ResponseData(a,d,e)",
}
for sid, want in SHAPES.items():
    ck("service %d returns %s" % (sid, want), want in respond(sid),
       respond(sid)[:200])

# --- 3. Yandex: the fixed \s+ split -------------------------------------
yd = body_of(11, "_useDictionary")
ck("native Yandex splits on /\\s+/",
   "split(/\\s+/)" in yd, yd)
import qtranslate.services.yandex as Y  # noqa: E402


def _native_use_dictionary(a):
    """The recovered expression, evaluated faithfully."""
    return (bool(a) and 100 >= len(a) and not re.search(r"[\n\r]", a)
            and 3 >= len(re.split(r"\s+", a)))


for probe in ("", " ", "  a  ", "a b", "a b c", "a b c d", " a b",
              "   a b c", "\ta b", " a  b  c ", "abc", "x" * 101,
              "a\nb", "A B C"):
    got, want = Y._use_dictionary(probe), _native_use_dictionary(probe)
    ck("_use_dictionary(%r) == native (%s)" % (probe, want), got == want,
       "port=%s native=%s" % (got, want))
ck("Yandex's port does not use str.split() (the fixed bug)",
   "text.split()" not in open(os.path.join(
       ROOT, "qtranslate", "services", "yandex.py"),
       encoding="utf-8").read())

# --- 4. Microsoft: no duplicate definition, and the " " split is native's
MS = open(os.path.join(ROOT, "qtranslate", "services", "microsoft.py"),
          encoding="utf-8").read()
ck("microsoft defines _is_short_text exactly once",
   MS.count("def _is_short_text") == 1, str(MS.count("def _is_short_text")))
ms = respond(5)
ck("native Microsoft splits on a single literal space",
   'split(" ")' in ms, ms)
import qtranslate.services.microsoft as M  # noqa: E402
ck("the port keeps that same literal-space split",
   'text.split(" ")' in MS)
ck("...so both count a leading space as an empty member",
   M._is_short_text("  a  b") == (3 >= len("  a  b".split(" "))))

# --- 5. Google: the romanization slot is a RECORDED divergence ----------
g = respond(1)
ck("native Google reads the romanization from e[2]",
   re.search(r"2<e\.length&&d===f\.length-1&&\(g=e\[2\]", g) is not None,
   g[:300])
GSRC = open(os.path.join(ROOT, "qtranslate", "services",
                         "google_translate.py"), encoding="utf-8").read()
ck("the port reads e[3] and records that it is not native's slot",
   "e[3]" in GSRC and "**index 3**, not index 2" in GSRC,
   "the port's recorded divergence's justification disappeared")
ck("the port's dictionary branch guard matches native's !(3>e.length)",
   "len(e) >= 3" in GSRC and "!(3>e.length)" in g)

# --- 6. Google's request asks for the same dt set -----------------------
ck("native Google request carries dt=bd&dt=t&dt=ld&dt=rm",
   "dt=bd&dt=t&dt=ld&dt=rm" in body_of(1, "serviceTranslateRequest"))
ck("the port carries the same dt set",
   "dt=bd&dt=t&dt=ld&dt=rm" in GSRC)

# --- 7. getSourceLanguage, both slots -----------------------------------
gg = body_of(1, "getSourceLanguage")
ck("native getSourceLanguage guards on 9>a.length and reads a[8][0][0]",
   "9>a.length" in gg and "a[8]" in gg and "a[0][0]" in gg, gg)
ck("the port mirrors it",
   "len(resp) < 9" in GSRC and "resp[8]" in GSRC)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_translate_response_chain: all checks ok (%d assertions)" % n[0])
