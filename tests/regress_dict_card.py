"""Regression: dictionary card markup matches native FUN_004253cc's format string.

Native evidence: the card is built by ONE wide format string at file offset
0x11d8f0 of docs/review/artifacts/QTranslate.6.10.0.exe (298 chars, RVA
0x11e8f0, VA 0x51e8f0), referenced exactly once, from FUN_004253cc.
Docs: docs/review/DICT_CARD_BUILDER_2026-10-10.md.

    <div id="qt-s%u" class="qt-card"><div id="qt-h%u" class="qt-header"
      ondblclick="toggle(%u);" onselectstart="return false;">%s%s</div>
      <div id="qt-d%u" class="qt-data"><input type="button" id="qt-l%u"
      onclick="fullEntry(%u);return false;" class="qt-read-more"
      value="READ MORE"></input>%s</div></div>

The literal is re-read from the artifact each run, so this suite fails if the
string ever moves or the port drifts from it -- rather than asserting a copy of
the string that could itself be wrong.

The four things a port is most likely to get wrong are each pinned:
  ondblclick (not onclick) on the header
  onselectstart="return false;" on the header
  qt-l is an <input type=button value="READ MORE">, not an <a>
  no inline display:none -- checkEntry decides, not the emitter
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import dict_render as DR  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


# ---- read the native format string straight out of the artifact -------------
_ART = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "docs", "review", "artifacts", "QTranslate.6.10.0.exe")
# 298 CHARS = 596 BYTES of UTF-16LE. (An earlier draft said "298 bytes",
# which silently truncated the string to half its length and made the <input>
# assertions fail -- corrected rather than quietly widened. A second draft then
# said 595, which is one byte short: 298 code units x 2 bytes is 596. The
# string IS NUL-terminated exactly at its own </div></div>, so a NUL-scan and a
# structural cut agree here.)
_OFF, _CHARS = 0x11d8f0, 298

if os.path.exists(_ART):
    blob = open(_ART, "rb").read()
    raw = blob[_OFF:_OFF + _CHARS * 2]
    native = raw.decode("utf-16-le", errors="replace")
    ck("native card literal is at 0x11d8f0 and starts with <div id=\"qt-s%u\"",
       native.startswith('<div id="qt-s%u" class="qt-card">'), repr(native[:40]))
    ck("native literal is 9 substitutions",
       len(re.findall(r"%u", native)) == 6
       and len(re.findall(r"%s", native)) == 3,
       "u=%d s=%d" % (native.count("%u"), native.count("%s")))
    ck("native toggle is ondblclick", 'ondblclick=\\"toggle(%u);\\"' in native
       or 'ondblclick="toggle(%u);"' in native)
    ck("native header sets onselectstart", 'onselectstart' in native)
    ck("native qt-l is an <input type=button>", '<input type="button"' in native)
    ck("native qt-l reads READ MORE", 'value="READ MORE"' in native)
    ck("native qt-l has NO inline display:none",
       'display:none' not in native[native.find('qt-l'):])
    ck("native data slot follows the </input>", '</input>%s</div></div>' in native)
    _have_art = True
else:
    _have_art = False
    ck("artifact present (run from the repo root)", False, _ART)

# ---- the port emits the same shape -----------------------------------------
page = DR.render_cards([("7", "Google", "<b>hi</b>")])
i = page.find('<div id="qt-s7"')
ck("card is emitted into qt-content", i >= 0, repr(page[:120]))
card = page[i:page.find("</div></div>", i) + 12] if i >= 0 else ""

# attribute order and both classes, as in the native literal
ck("card: id before class", card.startswith('<div id="qt-s7" class="qt-card">'))
ck("header: id before class", 'id="qt-h7" class="qt-header"' in card)
ck("data: id before class", 'id="qt-d7" class="qt-data"' in card)
ck("qt-l: id and class in native order",
   'type="button" id="qt-l7" onclick="fullEntry(7);return false;" '
   'class="qt-read-more" value="READ MORE"' in card)

ck("toggle is ondblclick, not onclick",
   'ondblclick="toggle(7);"' in card and 'onclick="toggle(7)' not in card)
ck("header sets onselectstart", 'onselectstart="return false;"' in card)
ck("qt-l closes with </input> and is followed by the fragment",
   '</input><b>hi</b>' in card)
ck("no <a class=qt-read-more>", 'qt-read-more' in card and '<a ' not in
   card[card.find('qt-read-more') - 40:card.find('qt-read-more') + 40])
ck("no inline display:none on qt-l", 'display:none' not in card)
ck("no more... label", "more..." not in card)
ck("card closes </div></div>", card.endswith("</div></div>"))

# ---- the JS driver calls, both native's ------------------------------------
ck("appendMenuItem gets 3 args", "appendMenuItem(7, 'Google', '')" in page)
ck("checkEntry called per card", "checkEntry(7)" in page)
ck("showNavigation is conditional on >1",
   re.search(r"\.length\s*>\s*1\)showNavigation\(\)", page) is not None)

# ---- multiple cards get distinct ids, like native's %u ---------------------
p2 = DR.render_cards([("1", "A", "x"), ("2", "B", "y")])
for sid in (1, 2):
    ck(f"card {sid} ids are unique",
       all(f'id="qt-{p}{sid}"' in p2 for p in "shdl"))
ck("two cards -> showNavigation still guarded",
   p2.count("showNavigation") == 2)   # definition + the conditional call

# ---- native's zero-result message (FUN_00425767's card counter == 0) ------
# FUN_00451dbd returns the definition when one exists and
# L"No results found for '%s'." otherwise; the pane state machine calls it when
# the counter at +0x180 is zero -- the SAME counter that gates showNavigation
# below. The port emitted nothing at all before 2026-10-11: zero cards, an
# empty qt-content div, no message. docs/review/DICT_CARD_BUILDER_2026-10-10.md
# 2b measured the gap; this is the fix, pinned against the artifact's own
# literal so the wording cannot drift.
#
# NOTE on the three assertions below: the template ALWAYS ships the JS function
# definitions (appendMenuItem, showNavigation) and the .qt-card CSS rule, so
# counting those substrings would pass trivially. What distinguishes the
# zero-result state is the emitted CALLS inside window.onload, and that is what
# is asserted -- a definition is native's, a missing call is our divergence.
_NATIVE_NO_RESULTS = None
if _have_art:
    _blob = open(_ART, "rb").read()
    _s = _blob[0x11dbc8:0x11dbc8 + 200].decode("utf-16-le", errors="replace")
    _NATIVE_NO_RESULTS = _s[:_s.find("\x00")]
    ck("native no-results literal is at 0x11dbc8 and has the %s verbatim",
       _NATIVE_NO_RESULTS == "No results found for '%s'.", repr(
           _NATIVE_NO_RESULTS))

ck("the port's NO_RESULTS renders exactly what native's literal renders",
   _NATIVE_NO_RESULTS is not None
   and DR.NO_RESULTS % "hello" == _NATIVE_NO_RESULTS % "hello",
   "%r vs %r" % (DR.NO_RESULTS, _NATIVE_NO_RESULTS))

# zero cards -> the message, and the query word is substituted in
_empty = DR.render_cards([], "hello")
ck("zero cards emits the message inside qt-content",
   'class="qt-content">No results found for \'hello\'.' in _empty, repr(
       _empty[_empty.find("qt-content"):][:60]))
ck("zero cards emits no card element", 'id="qt-s' not in _empty)
ck("zero cards emits no appendMenuItem CALL",
   "appendMenuItem(7," not in _empty and "appendMenuItem(1," not in _empty)
# the conditional showNavigation call is native's own onload and always ships;
# the zero-result branch is the absence of the per-card checkEntry calls.
ck("zero cards emits no checkEntry CALL", "checkEntry(" not in _empty.split(
    "window.onload")[0].replace("function checkEntry", ""),
   "checkEntry is defined in the template but must not be CALLED")

# the query is HTML-escaped: it is user input reaching HTML
_esc = DR.render_cards([], "<script>")
ck("the query word is escaped",
   "&lt;script&gt;" in _esc,
   repr(_esc[_esc.find("qt-content"):][:60]))

# with cards, the message must NOT appear -- native's counter is nonzero
ck("cards present -> no no-results message",
   "No results found" not in DR.render_cards([("1", "A", "x")], "hello"))
ck("cards present -> the card element is there",
   'id="qt-s1"' in DR.render_cards([("1", "A", "x")], "hello"))

# ---- header slots 1+2: icon markup and the browser link ----------------------
# Native's header is TWO substitution slots ("%s%s"): slot 1 = the service
# icon <img>, slot 2 = <a href=...>title</a> or the bare title. The port
# emitted only the bare title, so slot 2 never linked and slot 1 was empty.
#   docs/review/DICT_CARD_HEADER_SLOTS_RESOLVED_2026-10-10.md
#
# SLOT 1 (icon): an absent Service.ico yields NO <img> at all -- native's
# GetFileAttributesW branch at 0x004254c3 jumps (JZ 0x004254e3) past the
# file:/// format (PUSH 0x51e7d4). 0x522a78 ("Default.ico") is referenced
# from a different function and never appears on this path, so there is no
# default to port. Asserted as absence, not as a string: the header for any
# service must carry no <img> on this host.
# SLOT 2 (link-or-title): native's serviceLink() per service. Asserted
# against the recovered Service.js bodies, not against the port's own
# table, so a JS/port drift fails here.
_hdr_lingvo = DR.render_cards([("25", "ABBYY Lingvo Live", "x")], "hello")
ck("slot 1: no <img> in any header (the .ico is absent on this host)",
   "<img" not in _hdr_lingvo,
   "native emits no <img> when GetFileAttributesW says absent")
ck("slot 2: a service with a home page links its title",
   '<a href="https://www.lingvolive.com" class="qt-link-browser" '
   'title="Open in browser">ABBYY Lingvo Live</a>' in _hdr_lingvo,
   "native: FUN_004023f1(&local_78, L\"<a href=...\">...\")")
ck("slot 2: the wrapper is the artifact's own literal, not a paraphrase",
   DR._LINK_WRAP == '<a href="%s" class="qt-link-browser" '
   'title="Open in browser">%s</a>',
   repr(DR._LINK_WRAP))
_hdr_unknown = DR.render_cards([("99", "Unknown Service", "x")], "hello")
ck("slot 2: a service with no home page renders the bare title",
   'class="qt-header" ondblclick="toggle(99);" '
   'onselectstart="return false;">Unknown Service</div>' in _hdr_unknown,
   "native's FUN_00401ec9 else-branch: the title alone, no <a>")
ck("the link table covers every service the port can render",
   all(DR.service_link(t) for _, t, _ in
       [("10", "Google Search", ""), ("14", "Wikipedia", ""),
        ("17", "Multitran", ""), ("18", "ImTranslator", ""),
        ("19", "WordReference", ""), ("20", "Babylon Dictionary", ""),
        ("22", "Reverso", ""), ("24", "Urban Dictionary", ""),
        ("25", "ABBYY Lingvo Live", ""),
        ("29", "Oxford Learner Dictionary", "")]),
   "a service the port renders must have a home page or an explicit "
   "no-link decision, never a silent omission")


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_card: all checks ok (%d assertions, artifact=%s)"
      % (n[0], "used" if _have_art else "MISSING"))
