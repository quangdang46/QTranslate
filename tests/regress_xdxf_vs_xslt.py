"""Regression: the port's XDXF rendering matches the recovered XSLT.

`Resources/XdxfArticle.xslt` is in the payload (chunk 0 of the theme walk,
at `0x977ec`) and it is the authority for how a dictionary article becomes
HTML. The port reimplements it in Python because the app cannot run XSLT,
so a divergence is silent: the port still renders *something*.

This compares the port against the XSLT template-by-template for the five
element types the stylesheet actually handles, and pins the two rules that
are easiest to get wrong:

* ``<k>`` renders only its **direct text** (``xsl:value-of`` ignores
  children), so ``<k>a<b>c</b></k>`` loses the ``<b>c</b>``.
* ``<kref>`` emits ``href="qtdp:{text}"`` -- the ``qtdp:`` scheme is the
  port's own cross-reference marker, matching the stylesheet's literal.

The XSLT's own identity template is NOT compared: it copies unknown nodes
verbatim, and the port's approximation for those is documented and pinned
by `regress_xdxf_render.py`.

Headless: the XSLT is READ from the payload, never executed.
"""
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import xdxf  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(REPO, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present (%s)" % PAYLOAD)
    raise SystemExit(0)

raw = io.open(PAYLOAD, "rb").read().decode("utf-8", "replace")
# The stylesheet is a chunk of its own, not a named file inside the
# Service.js stream -- it is found by its own root element. Its line
# endings are CRLF (a UTF-8 BOM precedes `<?xml`), so comparisons are made
# against the text as stored rather than a normalised copy.
i = raw.find("<xsl:stylesheet")
ck("the payload carries the XSLT stylesheet", i >= 0)
if i < 0:
    raise SystemExit(1)
XSL = raw[i:raw.find("</xsl:stylesheet", i) + len("</xsl:stylesheet")]


def template_for(el):
    """The body of ``<xsl:template match="<el>">…</xsl:template>``."""
    m = re.search(r'<xsl:template\s+match="' + el + r'">(.*?)'
                  r'</xsl:template>', XSL, re.S)
    return m.group(1) if m else None


# --- the five element templates really are in the file ----------------
for el in ("k", "tr", "kref", "iref", "ex"):
    ck("the XSLT has a template for <%s>" % el, template_for(el) is not None,
       "no <xsl:template match=\"%s\">" % el)

# --- each template's literal, one by one (CRLF as stored) -------------
ck("<k> renders its direct text in a bold div",
   template_for("k")
   == '\r\n    <div><b><xsl:value-of select="."/></b></div>\r\n  ',
   repr(template_for("k")))
ck("<tr> renders inside [ ]",
   template_for("tr")
   == '\r\n    <span>[<xsl:apply-templates/>]</span>\r\n  ',
   repr(template_for("tr")))
ck("<kref> uses the qtdp: scheme",
   template_for("kref")
   == '\r\n    <a href="qtdp:{.}"><xsl:value-of select="."/></a>\r\n  ',
   repr(template_for("kref")))
ck("<iref> takes its href from the attribute",
   template_for("iref")
   == '\r\n    <a href="{@href}"><xsl:value-of select="."/></a>\r\n  ',
   repr(template_for("iref")))
ck("<ex> is a gray span",
   template_for("ex")
   == '\r\n    <span style="color:gray">'
   '<xsl:apply-templates/></span>\r\n  ',
   repr(template_for("ex")))

# --- and the port reproduces each one ---------------------------------
ARTICLE = ('<ar><k>hello</k><tr>həˈloʊ</tr><def><dtrn>xin chào</dtrn>'
           '<ex>hello <kref>world</kref></ex></def></ar>')
out = xdxf.render_article(ARTICLE)
ck("<k> -> <div><b>text</b></div>",
   "<div><b>hello</b></div>" in out, out)
ck("<tr> -> <span>[text]</span>",
   "<span>[həˈloʊ]</span>" in out, out)
ck("<kref> -> <a href=\"qtdp:text\">text</a>",
   '<a href="qtdp:world">world</a>' in out, out)
ck("<ex> -> <span style=\"color:gray\">…</span>",
   '<span style="color:gray">hello <a href="qtdp:world">world</a></span>'
   in out, out)

ck("<iref> -> <a href=\"<@href>\">text</a>",
   '<a href="https://x.t">ext</a>'
   in xdxf.render_article('<ar><iref href="https://x.t">ext</iref></ar>'),
   "iref not rendered from its href attribute")

# --- the value-of rule: <k> drops its children ------------------------
ck("<k> renders ONLY its direct text (xsl:value-of ignores children)",
   xdxf.render_article("<ar><k>a<i>b</i></k></ar>")
   == "<div><b>a</b></div>",
   repr(xdxf.render_article("<ar><k>a<i>b</i></k></ar>")))
ck("...while <ex> DOES recurse (it uses apply-templates)",
   "<i>b</i>" in xdxf.render_article("<ar><ex>a<i>b</i></ex></ar>"),
   repr(xdxf.render_article("<ar><ex>a<i>b</i></ex></ar>")))

# --- the identity template's presence, for the record ------------------
ck("the XSLT also carries an identity template",
   '<xsl:template match="@* | node()">' in XSL)
ck("...whose <k>/<tr>/<kref>/<iref>/<ex> matches are more specific and "
   "therefore win", all(
       XSL.find('<xsl:template match="%s">' % e)
       > XSL.find('<xsl:template match="@* | node()">')
       for e in ("k", "tr", "kref", "iref", "ex")))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_xdxf_vs_xslt: all checks ok (%d assertions)" % n[0])
