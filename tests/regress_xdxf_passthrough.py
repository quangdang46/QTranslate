"""Pin the XDXF article renderer's `<ar>`/`<xdxf>` passthrough.

`Resources/XdxfArticle.xslt` (recovered from the installer payload: chunk
117 at stream offset 0x977ec, 832 bytes, sha256 f2e12cca...) carries six
templates -- an identity template plus one each for `<k>`, `<tr>`, `<kref>`,
`<iref>` and `<ex>`.  The identity template is

    <xsl:template match="@* | node()">
      <xsl:copy>
        <xsl:apply-templates select="@* | node()"/>
      </xsl:copy>
    </xsl:template>

so `<ar>` and `<xdxf>` -- which have no rule of their own -- are COPIED into
the output, wrappers and all.  This port used to unwrap them, which made
the rendered article differ from the stylesheet and let a nested `<ar>`
lose its boundary.

The expected strings below are the stylesheet's own output: they were taken
by running the recovered stylesheet over the same input with a conforming
XSLT 1.0 processor (libxslt), not by reading the port's source.

Every assertion calls the real functions and compares the real return
value; nothing here greps the implementation.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import xdxf as X  # noqa: E402

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


# --- the wrappers SURVIVE ------------------------------------------------
# Exactly equal, not `in`: a renderer that dropped the wrapper, or that
# emitted it twice, fails both of these.
ck("<ar> is copied into the output, not unwrapped",
   X.render_article("<ar><k>cat</k></ar>")
   == "<ar><div><b>cat</b></div></ar>",
   repr(X.render_article("<ar><k>cat</k></ar>")))

ck("<xdxf> is copied into the output, not unwrapped",
   X.render_article("<xdxf><ar><k>cat</k></ar></xdxf>")
   == "<xdxf><ar><div><b>cat</b></div></ar></xdxf>",
   repr(X.render_article("<xdxf><ar><k>cat</k></ar></xdxf>")))

# --- the two-<ar> BOUNDARY ----------------------------------------------
# An <ar> nested inside another <ar> must keep its own boundary: the inner
# one opens and closes inside the outer one, and neither is merged away.
_nested = X.render_article("<ar><k>outer</k><ar><k>inner</k></ar></ar>")
ck("a nested <ar> keeps its own boundary",
   _nested
   == "<ar><div><b>outer</b></div><ar><div><b>inner</b></div></ar></ar>",
   repr(_nested))
ck("...the nested <ar> is not flattened into its parent",
   _nested.count("<ar>") == 2 and _nested.count("</ar>") == 2, repr(_nested))
ck("...the outer <ar> is not closed before the inner one opens",
   _nested.index("<ar>") < _nested.index("<ar>", 5)
   < _nested.index("</ar>") < _nested.rindex("</ar>"),
   repr(_nested))

# Two SIBLING <ar> elements stay two articles.
_siblings = X.render_article("<xdxf><ar><k>a</k></ar><ar><k>b</k></ar></xdxf>")
ck("two sibling <ar> elements stay separate",
   _siblings
   == "<xdxf><ar><div><b>a</b></div></ar><ar><div><b>b</b></div></ar></xdxf>",
   repr(_siblings))

# --- lookup() must not split a nested <ar> at the wrong place -------------
# The old `<ar>(.*?)</ar>` scan stopped at the FIRST `</ar>`, so the half it
# cut out no longer parsed and lookup() raised.  It must return the whole
# outer article, inner <ar> and all.
_tmp = tempfile.NamedTemporaryFile("w", suffix=".xdxf", delete=False,
                                   encoding="utf-8")
_tmp.write("<xdxf><ar><k>outer</k><ar><k>inner</k></ar></ar></xdxf>")
_tmp.close()
try:
    try:
        _found = X.lookup("inner", _tmp.name)
        _raised = ""
    except Exception as e:  # noqa: BLE001
        _found = ""
        _raised = "%s: %s" % (type(e).__name__, e)
    ck("lookup() on a nested <ar> does not raise", not _raised, _raised)
    ck("...and returns the whole outer article",
       _found
       == "<ar><div><b>outer</b></div><ar><div><b>inner</b></div></ar></ar>",
       repr(_found))
    ck("...with both articles' text present",
       "<b>outer</b>" in _found and "<b>inner</b>" in _found, repr(_found))
finally:
    os.unlink(_tmp.name)

# Two sibling articles in one file: lookup returns the matching one only,
# never both concatenated.
_tmp = tempfile.NamedTemporaryFile("w", suffix=".xdxf", delete=False,
                                   encoding="utf-8")
_tmp.write("<xdxf><ar><k>alpha</k></ar><ar><k>beta</k></ar></xdxf>")
_tmp.close()
try:
    _a = X.lookup("alpha", _tmp.name)
    _b = X.lookup("beta", _tmp.name)
    ck("lookup returns only the matching sibling",
       "<b>alpha</b>" in _a and "<b>beta</b>" not in _a, repr(_a))
    ck("...and the other sibling is not concatenated in",
       "<b>beta</b>" in _b and "<b>alpha</b>" not in _b, repr(_b))
    ck("...and the returned article keeps its <ar> wrapper",
       _a.startswith("<ar>") and _a.endswith("</ar>"), repr(_a))
    ck("a word that is in no article returns empty",
       X.lookup("gamma", _tmp.name) == "")
finally:
    os.unlink(_tmp.name)

# --- the identity template copies what it has no rule for ---------------
ck("an unknown element is copied with its attributes",
   X.render_article('<ar><zz a="1" b="2">t</zz></ar>')
   == '<ar><zz a="1" b="2">t</zz></ar>',
   repr(X.render_article('<ar><zz a="1" b="2">t</zz></ar>')))
ck("an empty element is written <tag></tag>, not <tag/>",
   X.render_article("<ar><def></def></ar>") == "<ar><def></def></ar>",
   repr(X.render_article("<ar><def></def></ar>")))
ck("a comment inside the article is copied",
   X.render_article("<ar><!--note--><k>x</k></ar>")
   == "<ar><!--note--><div><b>x</b></div></ar>",
   repr(X.render_article("<ar><!--note--><k>x</k></ar>")))
ck("a processing instruction inside the article is copied",
   X.render_article("<ar><?pi go?><k>x</k></ar>")
   == "<ar><?pi go><div><b>x</b></div></ar>",
   repr(X.render_article("<ar><?pi go?><k>x</k></ar>")))

# --- xsl:value-of is the element's STRING VALUE, not its direct text ----
# <xsl:value-of select="."/> is the text of the whole subtree, so the
# child's MARKUP never reaches the key or the href.
ck("<k> renders its subtree's text",
   X.render_article("<ar><k>a<i>b</i></k></ar>")
   == "<ar><div><b>ab</b></div></ar>",
   repr(X.render_article("<ar><k>a<i>b</i></k></ar>")))
ck("<kref> takes the subtree's text, not its markup, as the target",
   X.render_article("<ar><kref>a<i>b</i></kref></ar>")
   == '<ar><a href="qtdp:ab">ab</a></ar>',
   repr(X.render_article("<ar><kref>a<i>b</i></kref></ar>")))
ck("<iref> takes the subtree's text as its label",
   X.render_article('<ar><iref href="https://x.t">p<i>q</i></iref></ar>')
   == '<ar><a href="https://x.t">pq</a></ar>',
   repr(X.render_article(
       '<ar><iref href="https://x.t">p<i>q</i></iref></ar>')))

# --- the HTML output method escapes --------------------------------------
ck("& is escaped in text",
   X.render_article("<ar><def>a &amp; b</def></ar>")
   == "<ar><def>a &amp; b</def></ar>",
   repr(X.render_article("<ar><def>a &amp; b</def></ar>")))
ck("< is escaped in text",
   X.render_article("<ar><def>a &lt; b</def></ar>")
   == "<ar><def>a &lt; b</def></ar>",
   repr(X.render_article("<ar><def>a &lt; b</def></ar>")))
ck('" is escaped in an attribute value',
   X.render_article('<ar><zz t="a &quot; b">x</zz></ar>')
   == '<ar><zz t="a &quot; b">x</zz></ar>',
   repr(X.render_article('<ar><zz t="a &quot; b">x</zz></ar>')))

# --- the five element templates still render as the stylesheet says -----
ck("<tr> renders inside [ ]",
   X.render_article("<ar><tr>hi</tr></ar>")
   == "<ar><span>[hi]</span></ar>",
   repr(X.render_article("<ar><tr>hi</tr></ar>")))
ck("<ex> renders as a gray span",
   X.render_article("<ar><ex>an example</ex></ar>")
   == '<ar><span style="color:gray">an example</span></ar>',
   repr(X.render_article("<ar><ex>an example</ex></ar>")))

if fails:
    print("FAIL %d/%d" % (len(fails), n[0]))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_xdxf_passthrough: all checks ok (%d assertions)" % n[0])
