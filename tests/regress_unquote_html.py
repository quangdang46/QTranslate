"""Regression: ``unquoteHtml`` -- the five entities and their semicolons.

Recovered `Common.js` (NSIS chunk at `0x13af4`):

    a=a.replace(/&amp[;]?/g,"&"); a=a.replace(/&lt[;]?/g,"<");
    a=a.replace(/&gt[;]?/g,">");  a=a.replace(/&quot[;]?/g,'"');
    return a=a.replace(/&#[0]?39[;]/g,"'")

Four patterns take an OPTIONAL semicolon; the ``&#39`` one takes a
MANDATORY one. The port had made all five optional, so a bare ``&#39``
turned into an apostrophe that native leaves alone. Pinned here, along
with the negative cases -- only these five entities are ever unquoted.
No network, no Tk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.common import unquote_html  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# --- the four optional-semicolon entities -------------------------------
for entity, out in (("&amp", "&"), ("&lt", "<"), ("&gt", ">"),
                    ("&quot", '"')):
    ck("%s; -> %r" % (entity, out), unquote_html(entity + ";") == out,
       unquote_html(entity + ";"))
    ck("%s (no semicolon) -> %r" % (entity, out),
       unquote_html(entity) == out, unquote_html(entity))

# --- &#39 : semicolon MANDATORY ------------------------------------------
ck("&#39; -> apostrophe", unquote_html("&#39;") == "'")
ck("&#039; -> apostrophe", unquote_html("&#039;") == "'")
ck("bare &#39 is LEFT ALONE (native's [;] is mandatory)",
   unquote_html("&#39") == "&#39", unquote_html("&#39"))
ck("bare &#039 is LEFT ALONE too", unquote_html("&#039") == "&#039",
   unquote_html("&#039"))

# --- everything else is untouched ----------------------------------------
# NB: &amp; has no trailing boundary in native's pattern, so it also
# matches the PREFIX of a longer token ('&ampx' -> '&x'). That is native
# behaviour, not a port bug -- pinned below.
for other in ("&nbsp;", "&copy;", "&hellip;", "&#38;", "&#x27;",
              "&AMP;", "&#39 ;"):
    ck("%r is NOT unquoted (only the five exist natively)" % other,
       unquote_html(other) == other, unquote_html(other))
ck("'&ampx' -> '&x' (native's pattern has no trailing boundary)",
   unquote_html("&ampx") == "&x", unquote_html("&ampx"))

# --- mixed text ----------------------------------------------------------
ck("mixed entities all convert",
   unquote_html("AT&amp;T &lt;b&gt; say&quot;hi&quot;&#39;")
   == 'AT&T <b> say"hi"\'',
   unquote_html("AT&amp;T &lt;b&gt; say&quot;hi&quot;&#39;"))
ck("a bare &#39 survives inside a converted string",
   unquote_html("a&amp;b&#39c") == "a&b&#39c",
   unquote_html("a&amp;b&#39c"))

# --- falsy / empty -------------------------------------------------------
ck("empty -> ''", unquote_html("") == "")
ck("None -> ''", unquote_html(None) == "")
ck("plain text passes through", unquote_html("hello world")
   == "hello world")

# --- the port must not broaden the set ----------------------------------
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "common.py"),
    encoding="utf-8").read()
_fn = src.split("def unquote_html")[1].split("\ndef ")[0]
_body = _fn.split('"""', 2)[2] if _fn.count('"""') >= 2 else _fn
ck("no &nbsp; rule was added", "nbsp" not in _body)
ck("the mandatory semicolon on &#39 is present", "&#[0]?39[;]" in _body)
ck("the native source is quoted in the docstring", "&amp[;]?" in _fn)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_unquote_html: all checks ok (%d assertions)" % n[0])
