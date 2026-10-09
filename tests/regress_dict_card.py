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
# 298 CHARS = 595 BYTES of UTF-16LE. (The doc's first draft said "298 bytes",
# which silently truncated the string to half its length and made the <input>
# assertions fail -- corrected rather than quietly widened.)
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


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_card: all checks ok (%d assertions, artifact=%s)"
      % (n[0], "used" if _have_art else "MISSING"))
