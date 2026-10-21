"""XDXF offline dictionary article renderer — a port of
Resources/XdxfArticle.xslt.

The stylesheet was recovered from the QTranslate 6.10.0 installer payload
(chunk 117 at stream offset 0x977ec, 832 bytes, sha256 f2e12cca...; the
walk is docs/review/PAYLOAD_CHUNK_CENSUS_2026-10-15.md §1).  It carries six
templates — an identity template plus one each for <k>, <tr>, <kref>,
<iref> and <ex> — and this module reproduces all six with stdlib
xml.etree (no XSLT engine needed):

  <k>    -> <div><b>key</b></div>       (xsl:value-of select=".")
  <tr>   -> <span>[transcription]</span>
  <kref> -> <a href="qtdp:...">...</a>  (internal cross-reference)
  <iref> -> <a href="...">...</a>       (external link)
  <ex>   -> <span style="color:gray">...</span>
  everything else -> copied verbatim by the identity template (<xsl:copy>),
                     attributes and all.

Two consequences of the identity template, both of which this port used to
get wrong:

* ``<ar>`` and ``<xdxf>`` are COPIED, not unwrapped.  The stylesheet has no
  rule for them, so ``<xsl:copy>`` keeps them — and a nested ``<ar>`` keeps
  its own boundary instead of merging into its parent.
* ``<xsl:value-of select="."/>`` is the element's STRING VALUE (the text of
  its whole subtree), not its direct text.  ``<k>a<i>b</i></k>`` is the key
  "ab", and ``<kref>a<i>b</i></kref>`` links to ``qtdp:ab``: the child's
  markup never reaches the href.

The stylesheet also asks for ``<xsl:output method="html"/>``, so the
serialisation follows the HTML output method — &, < and > are escaped in
text, &, <, > and " in attribute values, and an empty element is written
``<tag></tag>`` rather than ``<tag/>``.

One difference is left standing on purpose: libxslt's HTML serialiser
also breaks its output with newlines around block-level elements (the
``<div>`` the ``<k>`` template produces is one).  That is a property of the
serialiser, not of the stylesheet, so the port does not reproduce it.

Three more differences, all in cases an XDXF article does not contain:

* an attribute value holding a ``"`` is written ``&quot;`` here, while
  libxslt switches the delimiter to ``'`` -- both decode to the same value;
* a processing instruction that sits OUTSIDE the root element is not
  emitted, because ElementTree keeps only the root (one inside it is);
* a namespaced element is matched on its local name, while XPath 1.0 would
  match the ``<k>``/``<tr>``/... rules only on elements in no namespace --
  and ElementTree drops the ``xmlns`` declarations that would go with them.

Pinned by tests/regress_xdxf_passthrough.py.
"""
import re
import xml.etree.ElementTree as ET


def _esc_text(s: str) -> str:
    """HTML output method escaping for a text node."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    """HTML output method escaping for a double-quoted attribute value."""
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _string_value(node) -> str:
    """The XSLT string-value of a node: the text of its whole subtree."""
    return "".join(node.itertext())


def _content(node) -> str:
    """``<xsl:apply-templates/>`` — the node's own text, then every child
    rendered with its tail."""
    out = [_esc_text(node.text or "")]
    for c in node:
        out.append(_render(c))
        out.append(_esc_text(c.tail or ""))
    return "".join(out)


def _render(node) -> str:
    """Render one node the way the stylesheet's templates do."""
    tag = node.tag
    if tag is ET.Comment:
        return "<!--%s-->" % (node.text or "")
    if tag is ET.ProcessingInstruction:
        return "<?%s>" % (node.text or "")
    if "}" in tag:
        tag = tag.split("}")[-1]
    if tag == "k":
        # <xsl:value-of select="."/> = the element's string value.
        return "<div><b>%s</b></div>" % _esc_text(_string_value(node))
    if tag == "tr":
        return "<span>[%s]</span>" % _content(node)
    if tag == "kref":
        s = _string_value(node)
        return '<a href="qtdp:%s">%s</a>' % (_esc_attr(s), _esc_text(s))
    if tag == "iref":
        s = _string_value(node)
        return '<a href="%s">%s</a>' % (_esc_attr(node.get("href", "")),
                                       _esc_text(s))
    if tag == "ex":
        return '<span style="color:gray">%s</span>' % _content(node)
    # Identity template: <xsl:copy> keeps the element and its attributes.
    attrs = "".join(' %s="%s"' % (k, _esc_attr(v))
                    for k, v in node.attrib.items())
    return "<%s%s>%s</%s>" % (tag, attrs, _content(node), tag)


def render_article(xml_text: str) -> str:
    """Apply Resources/XdxfArticle.xslt to one XDXF article.

    Returns the HTML the stylesheet produces for `xml_text`, wrappers and
    all: the identity template copies ``<ar>``/``<xdxf>``, so the rendered
    article keeps them.
    """
    xml_text = re.sub(r"<\?xml(\s[^>]*)?\?>", "", xml_text, count=1).strip()
    root = ET.fromstring(xml_text, parser=ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True, insert_pis=True)))
    return _render(root)


_AR_TAG = re.compile(r"<ar\b[^>]*>|</ar\s*>", re.IGNORECASE)


def _iter_articles(data: str):
    """Yield the text of every outermost ``<ar>...</ar>`` element in `data`.

    A non-greedy ``<ar>(.*?)</ar>`` stops at the FIRST ``</ar>``, so an
    ``<ar>`` nested inside another ``<ar>`` was cut in half and the leftover
    no longer parsed.  Counting the depth finds the outer boundary.
    """
    depth = 0
    start = None
    for m in _AR_TAG.finditer(data):
        tag = m.group(0)
        if tag.startswith("</"):
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                yield data[start:m.end()]
                start = None
        else:
            if depth == 0:
                start = m.start()
            if not tag.endswith("/>"):
                depth += 1


def lookup(word: str, xdxf_path: str, exact: bool = True) -> str:
    """Offline lookup: scan XDXF for the article whose <k> key matches.

    The article is returned as the stylesheet renders it — the ``<ar>``
    wrapper included, because the identity template copies it.

    ``exact=True`` (native default — ``DictionaryExactSearch`` on): the key
    must equal the query (``<k>word</k>`` / ``<kref>word``). ``exact=False``:
    the key need only *contain* the query — the broadened search the native
    XDXF path fans out to when the flag is off (consumer ``FUN_004151c3``,
    options ``+0x181``). Only the exact-vs-broader distinction is
    evidence-backed; the precise native index algorithm is INFERRED.
    """
    word = word.strip()
    with open(xdxf_path, encoding="utf-8", errors="replace") as f:
        data = f.read()
    pat = (r"<k>\s*%s\s*(</k>|<kref)" if exact
           else r"<k>\s*[^<]*%s[^<]*(</k>|<kref)")
    rx = re.compile(pat % re.escape(word))
    for article in _iter_articles(data):
        if rx.search(article):
            return render_article(article)
    return ""


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    demo = ("<ar><k>hello</k><tr>həˈloʊ</tr><def><dtrn>xin chào</dtrn>"
            "<ex>hello world <kref>world</kref></ex></def></ar>")
    print(render_article(demo))
