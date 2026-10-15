"""Regression: dictionary HTML-scraping primitives (group H).

Every dictionary provider scrapes HTML with ``stringFindSub`` and the
tag/link helpers, and these are the parts most likely to be subtly
wrong with no network call to reveal it. This suite pins:

  * ``_sub`` across all four include_start/include_end combinations,
    against a hand-measured truth table (marker positions computed from
    the literal, not guessed);
  * missing markers -> "" (never a partial slice, never an exception);
  * ``_remove_elements`` (paired and self-closing), ``_remove_attributes``,
    ``_remove_tags`` (unwrap, keep content);
  * ``_update_links`` absolutisation: absolute passthrough, ``//host``,
    root-relative, relative, and the scheme-prefixed no-ops
    (javascript:/mailto:/#/qtdp:).

No network, no Tk.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import dictionary as DU  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


P = "AAA_start_MIDDLE_end_ZZZ"
S, E = "_start_", "_end_"
# hand-measured: find("_start_") == 3 (ends 10), find("_end_") == 16 (ends 21)
ck("truth table base: _start_ at 3", P.find(S) == 3, str(P.find(S)))
ck("truth table base: _end_ at 16", P.find(E) == 16, str(P.find(E)))

# all four flag combinations, expectations derived from those positions
ck("incS=1 incE=1", DU._sub(P, S, True, E, True) == P[3:21],
   repr(DU._sub(P, S, True, E, True)))
ck("incS=1 incE=0", DU._sub(P, S, True, E, False) == P[3:16],
   repr(DU._sub(P, S, True, E, False)))
ck("incS=0 incE=1", DU._sub(P, S, False, E, True) == P[10:21],
   repr(DU._sub(P, S, False, E, True)))
ck("incS=0 incE=0", DU._sub(P, S, False, E, False) == P[10:16],
   repr(DU._sub(P, S, False, E, False)))

# the default CLI: content only
ck("both-marker-excluded yields just the content",
   DU._sub(P, S, False, E, False) == "MIDDLE",
   repr(DU._sub(P, S, False, E, False)))

# missing markers -> "" (never an exception, never a partial slice)
ck("missing start -> ''", DU._sub(P, "<nope>", True, E, True) == "")
ck("missing end -> ''", DU._sub(P, S, True, "<nope>", True) == "")
ck("both missing -> ''", DU._sub(P, "<a>", True, "<b>", True) == "")
ck("empty page -> ''", DU._sub("", S, True, E, True) == "")

# regex markers are accepted (hasattr .search)
rx_s, rx_e = re.compile(r"_start_"), re.compile(r"_end_")
ck("regex markers give the same result as literals",
   DU._sub(P, rx_s, False, rx_e, False) == "MIDDLE")
ck("regex include_start", DU._sub(P, rx_s, True, rx_e, False) == P[3:16])
ck("non-matching regex -> ''", DU._sub(P, re.compile(r"<zzz>"), False,
                                       rx_e, False) == "")

# --- tag helpers ---------------------------------------------------------
# NOTE: _remove_elements / _remove_tags / _remove_attributes now DELEGATE
# to the verified common.py ports. The dictionary copies had added
# inventions over native's regexes (see the Common.js evidence quoted in
# each function's docstring):
#   * _remove_elements: extra void/self-closing stripping and re.I.
#     Native's pattern REQUIRES a closing tag and is case-sensitive.
from qtranslate import common as _C  # noqa: E402

ck("_remove_elements drops a paired element",
   DU._remove_elements("<b>x</b>keep", ["b"]) == "keep")
ck("_remove_elements leaves a void element alone (native does)",
   DU._remove_elements("a<br/>b", ["br"]) == "a<br/>b",
   DU._remove_elements("a<br/>b", ["br"]))
ck("_remove_elements leaves a self-closing <img> alone (native does)",
   DU._remove_elements('<img src="a.png">text', ["img"])
   == '<img src="a.png">text',
   DU._remove_elements('<img src="a.png">text', ["img"]))
ck("_remove_elements does not remove an UNCLOSED uppercase tag",
   DU._remove_elements("<B>x</B>y", ["b"]) == "<B>x</B>y",
   DU._remove_elements("<B>x</B>y", ["b"]))
ck("_remove_elements still handles nesting",
   DU._remove_elements("<div><span>x</span></div>y", ["div"]) == "y")
ck("_remove_elements matches across newlines (native's ((.|\\n)*?))",
   DU._remove_elements("<b>\nx\n</b>keep", ["b"]) == "keep")

ck("_remove_attributes strips one attribute",
   DU._remove_attributes('<a href="u" id="1">x</a>', ["href"])
   == '<a id="1">x</a>')
ck("_remove_attributes strips several",
   DU._remove_attributes('<a href="u" id="1">x</a>', ["href", "id"])
   == "<a>x</a>")
ck("_remove_attributes strips a valueless attribute too (native's value "
   "group is optional)",
   DU._remove_attributes("<a disabled>x</a>", ["disabled"]) == "<a>x</a>",
   DU._remove_attributes("<a disabled>x</a>", ["disabled"]))
ck("_remove_attributes handles unquoted values",
   DU._remove_attributes("<a href=u>x</a>", ["href"]) == "<a>x</a>")

ck("_remove_tags unwraps and KEEPS the content",
   DU._remove_tags("<b>bold</b>", ["b"]) == "bold")
ck("_remove_tags keeps nested content",
   DU._remove_tags("<b><i>x</i></b>", ["b"]) == "<i>x</i>")
ck("_remove_tags is case-sensitive like native",
   DU._remove_tags("<B>bold</B>", ["b"]) == "<B>bold</B>",
   DU._remove_tags("<B>bold</B>", ["b"]))

# the three helpers are now the same function's behaviour
for _c in ("<b>x</b>keep", "a<br/>b", "<div><span>x</span></div>y"):
    ck("_remove_elements agrees with common for %r" % _c,
       DU._remove_elements(_c, ["b", "div", "br"])
       == _C.remove_elements(_c, ["b", "div", "br"]))
for _c in ("<b>bold</b>", "<b><i>x</i></b>"):
    ck("_remove_tags agrees with common for %r" % _c,
       DU._remove_tags(_c, ["b"]) == _C.remove_tags(_c, ["b"]))
for _c in ('<a href="u" id="1">x</a>',):
    ck("_remove_attributes agrees with common for %r" % _c,
       DU._remove_attributes(_c, ["href"])
       == _C.remove_attributes(_c, ["href"]))

ck("_remove_tags unwraps and KEEPS the content",
   DU._remove_tags("<b>bold</b>", ["b"]) == "bold")
ck("_remove_tags keeps nested content",
   DU._remove_tags("<b><i>x</i></b>", ["b"]) == "<i>x</i>")
ck("_remove_tags drops a self-closing tag",
   DU._remove_tags("a<br/>b", ["br"]) == "ab")

# --- link absolutisation -------------------------------------------------
# NOTE: dictionary._update_links now DELEGATES to common.update_html_links,
# the verified port of native updateHtmlLinks. It used to be a second,
# divergent implementation whose only behavioural difference was a plain
# relative URL (it invented base + "/" + url; native leaves it alone).
from qtranslate.common import update_html_links as _native_links  # noqa: E402

ck("absolute http URL passes through",
   'href="https://x.com/a"' in DU._update_links('href="https://x.com/a"',
                                                "https://b.com"))
ck("protocol-relative gets an https: prefix",
   DU._update_links('href="//cdn.example/a"', "https://b.com")
   == 'href="https://cdn.example/a"')
ck("root-relative gets the base host",
   DU._update_links('href="/wiki/x"', "https://b.com/root")
   == 'href="https://b.com/root/wiki/x"')
ck("a plain relative URL is left ALONE (the old copy absolutised it)",
   DU._update_links('href="img/x.png"', "https://b.com/root/")
   == 'href="img/x.png"',
   DU._update_links('href="img/x.png"', "https://b.com/root/"))
ck("javascript: is left alone",
   DU._update_links('href="javascript:void(0)"', "https://b.com")
   == 'href="javascript:void(0)"')
ck("mailto: is left alone",
   DU._update_links('href="mailto:a@b.c"', "https://b.com")
   == 'href="mailto:a@b.c"')
ck("qtdp: is left alone",
   DU._update_links('href="qtdp:x"', "https://b.com") == 'href="qtdp:x"')
ck("a fragment-only href is left alone",
   DU._update_links('href="#top"', "https://b.com") == 'href="#top"')

# the two implementations are now the same function's behaviour
for _b in ("https://b.com/root", "https://b.com/root/", "http://b.com"):
    for _c in ('href="/wiki/x"', "src='/img/a.png'",
               'href="//cdn.example/a"',
               'href="rel/p.png"', 'href="javascript:void(0)"',
               'href="qtdp:x"', 'href="#top"', 'href="https://abs.com/x"'):
        ck("dictionary agrees with the verified native port (%s, %s)"
           % (_b, _c),
           DU._update_links(_c, _b) == _native_links(_c, _b),
           "%r != %r" % (DU._update_links(_c, _b), _native_links(_c, _b)))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dictionary_html: all checks ok (%d assertions)" % n[0])
