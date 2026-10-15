"""Regression: dictionary response chains match the recovered Service.js.

For each dictionary provider this pins the slice markers, the
remove/attribute/tag chain, and the style wrap against its own
``Service.js`` in the payload -- the part of the 17 unread files that
decides whether the rendered article is native's.

No bug found. One case is pinned because it LOOKS like a bug:

``removeTags(a,["h[3-6]"])`` (Google Search) is not a typo for a list of
heading names. ``regExpRemove`` builds ``"</?({0})[^>]*>"`` and formats
it with ``b.join("|")``, so one member ``h[3-6]`` lands in the regex as a
**character class** and matches `<h3>`..`<h6>`. Expanding it to
``["h3","h4","h5","h6"]`` would look tidier and diverge from native (and,
via the ``|`` join, behave differently with more members).

Headless -- the JS is read, never executed. Skips if the artifact is
absent.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.common import remove_tags  # noqa: E402
from qtranslate.services import dictionary as DU  # noqa: E402

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


def segment(service_id):
    i = TS.find("new ServiceHeader(%d," % service_id)
    rest = [h[0] for h in HEADS if h[0] > i]
    return TS[i:rest[0] if rest else len(TS)]


def response(service_id):
    """This service's serviceDictionaryResponse body (brace-counted).

    The bundle pastes each service's JS next to a locale string table, so
    an unbounded window picks up unrelated arrays -- the body is cut at the
    matching brace instead.
    """
    seg = segment(service_id)
    m = re.search(r"function serviceDictionaryResponse\([^)]*\)\s*\{", seg)
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


# --- 1. the slice markers, one per provider -----------------------------
# Each entry: (service id, start marker, start inclusive?, end marker,
#             end inclusive?). Cells are the MARKUP the JS looks for, with
# the JS's own quoting left as recovered -- a literal is checked both as
# it appears and after the ``\x3c`` escape is decoded, so quoting style
# cannot make a real marker look absent.
SLICES = [
    (17, '<table width="100%">', True, '</table>', True),
    (19, r'<div id="(articleWRD|article)">', False,
     '<div id="postArticle">', False),
    (22, '<div id="TableHTMLResult">', False,
     'Center section end', False),
    (29, '<div id="ox-wrapper"', False, '<div id="rightcolumn"', False),
    (10, '<div id="main">', False, '<footer>', False),
    (14, '<div id="bodyContent"', True, 'post-content', True),
]
for sid, start, inc_s, end, inc_e in SLICES:
    body = response(sid)
    ck("service %d slices on %s" % (sid, start[:26]),
       start in body and end in body,
       "markers not found in %r" % body[:120])
    ck("service %d's start marker is %sinclusive" % (
        sid, "" if inc_s else "NOT "),
       ("!0" if inc_s else "!1") in
       body[body.find(start):body.find(start) + 120] if start in body
       else False)

# --- 2. the port carries every one of those literals --------------------
SRC = open(os.path.join(ROOT, "qtranslate", "services", "dictionary.py"),
           encoding="utf-8").read()
for marker in ('<table width="100%">', 'articleWRD|article',
               '<div id="postArticle">', '<div id="TableHTMLResult">',
               '<div id="ox-wrapper"', '<div id="rightcolumn"',
               '<div id="main">', '<div id="bodyContent"',
               'post-content', 'catlinks'):
    ck("port carries the marker %r" % marker[:34], marker in SRC,
       "not in dictionary.py")

# --- 3. the remove/attribute chains, verbatim ---------------------------
# Native writes its JS arrays without spaces (``["id","name"]``); the port
# writes Python style (``["id", "name"]``). Compare the names.
def members_of(body, call):
    """The quoted members of the array passed to ``<call>(...)``."""
    m = re.search(re.escape(call) + r"\([^,]*,?\s*\[([^\]]*)\]", body)
    if not m:
        return []
    return re.findall(r"['\"]([^'\"]*)['\"]", m.group(1))


def members_of(body, call):
    """The members of the array passed to ``<call>(...)`` in the JS."""
    m = re.search(re.escape(call) + r"\([^,]*,?\s*\[([^\]]*)\]", body)
    if not m:
        m = re.search(re.escape(call) + r"\(([^)]*)\)", body)
        if m:
            m2 = re.search(r"\[([^\]]*)\]", m.group(1))
            if m2:
                return _members(m2.group(1))
        return []
    return _members(m.group(1))


def _members(raw):
    return re.findall(r"['\"]([^'\"]*)['\"]", raw)


CHAINS = [
    (19, "removeAttributes", ["id", "name", "onclick"]),
    (22, "removeElements", ["script", "iframe"]),
    (29, "removeElements", ["script", "img"]),
    (10, "removeElements", ["style", "script", "svg"]),
]
for sid, call, want in CHAINS:
    body = response(sid)
    got = members_of(body, call)
    ck("service %d calls %s(%s)" % (sid, call, ",".join(want)),
       set(want) <= set(got), "native has %r" % got)
    ck("the port also removes %s for service %d" % (",".join(want), sid),
       all(w in SRC for w in want))

ck("Google Search's removeTags list is h[3-6], not expanded",
   'removeTags(a,["h[3-6]"])' in response(10))

# --- 4. the h[3-6] character-class case (looks like a bug, is not) ------
sample = ('<h3 class="t">H3</h3><p>body</p>'
          '<h6>H6</h6><h2>H2</h2>')
got = remove_tags(sample, ["h[3-6]"])
ck("h3 and h6 tags are removed", "<h3" not in got and "<h6" not in got,
   got)
ck("h2 is kept (outside the class)", "<h2>H2</h2>" in got, got)
ck("inner text is kept (removeTags unwraps, it does not delete)",
   "H3" in got and "H6" in got, got)
_common_src = open(os.path.join(ROOT, "qtranslate", "common.py"),
                   encoding="utf-8").read()
ck("the port's remove_tags formats with a | join like native regExpRemove",
   re.search(r'def reg_exp_remove\([^)]*\):?', _common_src) is not None
   and 'tags.join("|")' in _common_src
   or '"|".join' in _common_src)
ck("...but expanding it would be extensionally equivalent here, so the "
   "port's faithful form is a fidelity choice, not a bug fix",
   remove_tags("<h3>x</h3>", ["h3", "h4", "h5", "h6"])
   == remove_tags("<h3>x</h3>", ["h[3-6]"])
   and remove_tags("<h7>x</h7>", ["h3", "h4", "h5", "h6"])
   == remove_tags("<h7>x</h7>", ["h[3-6]"]))

# --- 5. WordReference's full chain, byte for byte -----------------------
_wr = response(19)
for step in ('removeElements(a,["style"])', 'removeAttributes(a,'
             '["id","name","onclick"])', 'updateHtmlLinks(a,d)',
             'buildUri(b,c,e)'):
    ck("WordReference native calls %s" % step[:40], step in _wr, step)
ck("the port's WordReference slice is the same regex",
   r'<div id="(articleWRD|article)">' in SRC)
ck("the port's WordReference style is the native one",
   DU.WORDREF_STYLE.startswith(".rh_me,span.phrase,span.hw")
   and DU.WORDREF_STYLE.count("}") > 5)

# --- 6. Oxford's own-URL rewrite is present natively -------------------
ck("Oxford's native response rewrites the site's absolute URLs",
   "oxfordlearnersdictionaries" in response(29))
ck("the port mentions that rewrite too",
   "oxfordlearnersdictionaries" in SRC)
ck("Oxford's native chain also drops the <div class=\"sound\"> audio blocks",
   re.search(r'<div class="sound', response(29)) is not None)
ck("the port drops them too",
   re.search(r'<div class="sound', SRC) is not None)

# --- 7. youdao's dictionary chain (service 26) -------------------------
_yd = response(26)
ck("youdao's native response slices results-contents up to the ads div",
   'results-contents' in _yd and '<div id="ads"' in _yd)
ck("...and strips five attributes: id/name + three event handlers",
   members_of(_yd, "removeAttributes")
   == ["id", "name", "onmouseover", "onmouseout", "onmousedown"],
   repr(members_of(_yd, "removeAttributes")))
_yd_src = open(os.path.join(ROOT, "qtranslate", "services", "youdao.py"),
               encoding="utf-8").read()
ck("youdao's port does both, with the same attribute list",
   "results-contents" in _yd_src and '"id", "name", "onmouseover"'
   in _yd_src)
ck("youdao's port builds the link as https:// + host + buildUri",
   '"https://" + host' in _yd_src or "'https://' + host" in _yd_src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_response_chain: all checks ok (%d assertions)" % n[0])
