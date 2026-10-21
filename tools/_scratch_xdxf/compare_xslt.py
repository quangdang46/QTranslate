"""Compare the port's render_article against the recovered XSLT, case by case.

The reference is the real stylesheet executed by libxslt (`/usr/bin/xsltproc`),
applied to the same XML the port is given.  This enumerates every divergence
between `qtranslate/xdxf.py` and `Resources/XdxfArticle.xslt`.

Run:  python3.11 -I tools/_scratch_xdxf/compare_xslt.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from qtranslate import xdxf  # noqa: E402

XSLT = os.path.join(ROOT, "tools", "_scratch_xdxf", "XdxfArticle.xslt")

CASES = {
    "k plain": "<ar><k>cat</k></ar>",
    "k with element child": "<ar><k>a<i>b</i></k></ar>",
    "k with tail text": "<ar><k>a<i>b</i>tail</k></ar>",
    "tr": "<ar><tr>həˈloʊ</tr></ar>",
    "kref": "<ar><kref>word</kref></ar>",
    "kref with child": "<ar><kref>a<i>b</i></kref></ar>",
    "iref": '<ar><iref href="https://x.t">ext</iref></ar>',
    "iref with child": '<ar><iref href="https://x.t">p<i>q</i></iref></ar>',
    "ex": "<ar><ex>hello world <kref>world</kref></ex></ar>",
    "unknown element": "<ar><def><dtrn>xin chào</dtrn></def></ar>",
    "unknown with attrs": '<ar><zz a="1" b="2">t</zz></ar>',
    "empty element": "<ar><def></def></ar>",
    "ampersand": "<ar><def>a &amp; b</def></ar>",
    "nested ar": "<ar><k>outer</k><ar><k>inner</k></ar></ar>",
    "xdxf root": "<xdxf><ar><k>cat</k></ar></xdxf>",
    "two ar siblings": "<xdxf><ar><k>a</k></ar><ar><k>b</k></ar></xdxf>",
    "text + element": "<ar>lead<k>cat</k>tail</ar>",
    "whitespace": "<ar>\n  <k>cat</k>\n</ar>",
}


def reference(xml_text: str) -> str:
    """Run the real stylesheet over xml_text; return its output."""
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False,
                                     encoding="utf-8") as f:
        f.write(xml_text)
        path = f.name
    try:
        p = subprocess.run(["xsltproc", XSLT, path], capture_output=True,
                           text=True)
        if p.returncode != 0:
            return "!! xsltproc failed: " + p.stderr.strip()
        return p.stdout
    finally:
        os.unlink(path)


def normalise(s: str) -> str:
    """Strip the two newlines libxslt's HTML serialiser adds on its own.

    1. a newline after the top-level element;
    2. a newline after a block-level end tag (``</div>``) when the next
       sibling is an element.

    Both are serialiser formatting, not stylesheet semantics, so the port
    does not reproduce them (see the module docstring).  The same
    normalisation is applied to both sides, so the comparison stays fair.
    """
    s = s.replace("</div>\n", "</div>")
    if s.endswith("\n"):
        s = s[:-1]
    return s


def main() -> int:
    same = 0
    diff = 0
    for name, xml_text in CASES.items():
        want = reference(xml_text)
        try:
            got = xdxf.render_article(xml_text)
        except Exception as e:  # noqa: BLE001
            got = "!! raised %s: %s" % (type(e).__name__, e)
        if normalise(want) == normalise(got):
            same += 1
            print("SAME  %-24s %r" % (name, got))
        else:
            diff += 1
            print("DIFF  %-24s" % name)
            print("        xslt : %r" % want)
            print("        port : %r" % got)
    print("\n%d same, %d different, %d total" % (same, diff, same + diff))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
