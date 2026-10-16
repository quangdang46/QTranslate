"""Regression: the dict-card format string and the zero-result message.

`DICT_CARD_UNRECORDED_DIVERGENCES_2026-10-10.md` §4 recorded two things as
open. Both have since been resolved by the port, and one claim went stale
without anyone noticing:

* *"`No results found for '%s'.` absent from the port"* — **it is not
  absent.** `dict_render.NO_RESULTS` carries the literal verbatim and the
  zero-result path uses it. The claim was true when written and stopped
  being true as the port was finished, which is the same staleness shape as
  the endpoint sweep's dictionary-host conclusion.
* *"empty result set renders a blank pane"* — no longer: the card counter
  that gates `showNavigation()` is the same one that gates the zero-result
  branch, so an empty set renders native's message.

The rest of that section is still correct and is pinned here too, because
it is measured from the image rather than asserted: the 298-char pool slice
and its exact nine-specifier sequence, plus `ondblclick` /
`onselectstart` / `<input type=button>` / `READ MORE`.

Headless; the image is read, never executed. Skips if absent.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import dict_render  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append("%s -- %s" % (name, detail) if detail else name)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "docs", "review", "artifacts", "QTranslate.6.10.0.exe")

if os.path.exists(EXE):
    blob = open(EXE, "rb").read()
    pool = "".join(
        chr(struct.unpack_from("<H", blob, 0x11d8f0 + i * 2)[0])
        for i in range(400)
        if struct.unpack_from("<H", blob, 0x11d8f0 + i * 2)[0] != 0)
    card = pool[:pool.index("</div></div>") + 12]

    # --- the measured facts from the section, re-measured ---------------
    ck("the pool slice is 298 chars", len(card) == 298, str(len(card)))
    ck("its nine specifiers, in native's order",
       re.findall(r"%u|%s", card)
       == ["%u", "%u", "%u", "%s", "%s", "%u", "%u", "%u", "%s"],
       repr(re.findall(r"%u|%s", card)))
    for lit in ("ondblclick", "onselectstart", 'type="button"', "READ MORE"):
        ck("the card carries %r" % lit, lit in card, "not in the pool slice")
    ck("the header has two %s and the card fills both slots",
       card.count("<div id=\"qt-h%u\" class=\"qt-header\"") == 1
       and re.findall(r"%s", card)[:2] == ["%s", "%s"],
       repr(re.findall(r"%s", card)))

    # --- the claim that went STALE: it IS in the port -------------------
    ck("'No results found for' IS in the recovered pool",
       "No results found for '%s'." in pool,
       "the native literal is not where the note says it is")
    ck("...and it is in the PORT too (the note's claim is stale)",
       dict_render.NO_RESULTS == "No results found for '%s'.",
       repr(dict_render.NO_RESULTS))
    ck("...and the zero-result path actually uses it",
       "NO_RESULTS % " in open(dict_render.__file__,
                              encoding="utf-8").read(),
       "NO_RESULTS is defined but never used")

    # --- and the renderer fills the two header slots now ---------------
    src = open(os.path.join(ROOT, "qtranslate", "dict_render.py"),
               encoding="utf-8").read()
    for lit in ("ondblclick", "onselectstart", 'type="button"', "READ MORE"):
        ck("the port's template/renders %r" % lit, lit in src,
           "no longer in dict_render.py -- a regression")

# --- an empty result set renders the message, not a blank pane ----------
page = dict_render.render_cards([], "word")
ck("an empty result set renders native's message, not a blank pane",
   "No results found for 'word'" in page, page[:200])
ck("...and the message is escaped (the query is user input)",
   dict_render.render_cards([], "<b>&")
   .find("No results found for") > -1
   and "<b>&" not in dict_render.render_cards([], "<b>&")
   .split("No results found")[1][:40],
   repr(dict_render.render_cards([], "<b>&").split("No results found")[1][:40]))

# --- a non-empty set renders cards, and no NO_RESULTS -------------------
one = dict_render.render_cards([(1, "Google", "<p>x</p>")], "word")
ck("a non-empty set renders cards", "qt-card" in one, one[:200])
ck("...and does NOT emit the zero-result message",
   "No results found" not in one, "")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail[:15]:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_card_native: all checks ok (%d assertions%s)"
      % (n[0], ", image measured" if os.path.exists(EXE)
         else ", image absent"))
