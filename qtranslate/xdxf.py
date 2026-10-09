"""XDXF offline dictionary article renderer — port of Resources/XdxfArticle.xslt.

XSLT templates ported 1:1:
  <k>    -> <div><b>key</b></div>
  <tr>   -> <span>[transcription]</span>
  <kref> -> <a href="qtdp:..."> (internal cross-reference)
  <iref> -> <a href="..."> (external link)
  <ex>   -> <span style="color:gray"> (example)
  default identity copy for everything else.
Uses only stdlib xml.etree (no XSLT engine needed).
"""
import re
import xml.etree.ElementTree as ET


def _render(node) -> str:
    tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
    inner = (node.text or "") + "".join(
        _render(c) + (c.tail or "") for c in node)
    if tag == "k":
        # xsl:value-of select="." = direct text only (not children)
        return f"<div><b>{node.text or ''}</b></div>"
    if tag == "tr":
        return f"<span>[{inner}]</span>"
    if tag == "kref":
        return f'<a href="qtdp:{inner}">{inner}</a>'
    if tag == "iref":
        return f'<a href="{node.get("href", "")}">{inner}</a>'
    if tag == "ex":
        return f'<span style="color:gray">{inner}</span>'
    attrs = "".join(f' {k}="{v}"' for k, v in node.attrib.items())
    if tag in ("ar", "xdxf"):
        return inner
    if list(node) or inner.strip():
        return f"<{tag}{attrs}>{inner}</{tag}>"
    return f"<{tag}{attrs}/>"


def render_article(xml_text: str) -> str:
    """Render one XDXF <ar> article to HTML (mirrors the XSLT output)."""
    xml_text = re.sub(r"<\?.*?\?>", "", xml_text, count=1).strip()
    root = ET.fromstring(xml_text)
    if root.tag.endswith("}ar") or root.tag == "ar":
        return "".join((_render(c) + (c.tail or "") for c in root))
    return _render(root)


def lookup(word: str, xdxf_path: str, exact: bool = True) -> str:
    """Offline lookup: scan XDXF for the article whose <k> key matches.

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
    for m in re.finditer(r"<ar>(.*?)</ar>", data, re.S):
        body = m.group(1)
        if rx.search(body):
            return render_article("<ar>" + body + "</ar>")
    return ""


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    demo = ("<ar><k>hello</k><tr>həˈloʊ</tr><def><dtrn>xin chào</dtrn>"
            "<ex>hello world <kref>world</kref></ex></def></ar>")
    print(render_article(demo))
