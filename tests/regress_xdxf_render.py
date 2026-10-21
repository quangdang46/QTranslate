"""Pin the XDXF article renderer (row E XDXF offline dict).

Native ships Resources/XdxfArticle.xslt; the port reproduces its
templates with xml.etree. Pinned per the docstring's template list:
  <k> -> <div><b>key</b></div>; <tr> -> <span>[..]</span>;
  <kref> -> <a href="qtdp:..">..</a>; <iref> -> <a href="href">..</a>;
  <ex> -> <span style="color:gray">..</span>; <ar>/<xdxf> COPIED, not
  unwrapped — the stylesheet's identity template (<xsl:copy>) has no rule
  for them, so they survive into the output.

Offline: string in, string out — no file, no window.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import xdxf as X

# --- <k> key: string value, wrapped in div/b ----------------------------
ck("<k> -> div/b", X.render_article("<ar><k>hello</k></ar>")
   == "<ar><div><b>hello</b></div></ar>",
   X.render_article("<ar><k>hello</k></ar>"))

# --- <tr> transcription -------------------------------------------------
ck("<tr> -> [..]", "<span>[</span>" in X.render_article(
    "<ar><tr>həˈloʊ</tr></ar>")
   or "[h" in X.render_article("<ar><tr>həˈloʊ</tr></ar>"),
   X.render_article("<ar><tr>həˈloʊ</tr></ar>"))

# --- <kref> internal cross-reference ------------------------------------
_kr = X.render_article("<ar><kref>word</kref></ar>")
ck("<kref> -> qtdp link", 'href="qtdp:word"' in _kr and ">word<" in _kr,
   _kr)

# --- <iref> external link -----------------------------------------------
_ir = X.render_article('<ar><iref href="http://x">site</iref></ar>')
ck("<iref> -> external href", 'href="http://x"' in _ir and ">site<" in _ir,
   _ir)

# --- <ex> example styled gray -------------------------------------------
_ex = X.render_article("<ar><ex>an example</ex></ar>")
ck("<ex> -> gray span", 'color:gray' in _ex and "an example" in _ex, _ex)

# --- <ar>/<xdxf> are copied, not unwrapped ------------------------------
ck("<ar> root copied (the stylesheet's identity template keeps it)",
   X.render_article("<ar><k>x</k></ar>") == "<ar><div><b>x</b></div></ar>",
   X.render_article("<ar><k>x</k></ar>"))

# --- nested content is rendered -----------------------------------------
_nested = X.render_article("<ar><k>k</k><ex>e</ex></ar>")
ck("siblings both rendered",
   "<b>k</b>" in _nested and "gray" in _nested, _nested)

# --- lookup exact vs broader --------------------------------------------
import tempfile
tmp = tempfile.NamedTemporaryFile("w", suffix=".xdxf", delete=False,
                                  encoding="utf-8")
tmp.write("<xdxf><ar><k>run</k><ex>to run</ex></ar>"
          "<ar><k>runner</k></ar></xdxf>")
tmp.close()
try:
    exact = X.lookup("run", tmp.name, exact=True)
    broad = X.lookup("run", tmp.name, exact=False)
    ck("exact lookup finds the exact key", "<b>run</b>" in exact, exact)
    ck("exact lookup does not match a longer key",
       "runner" not in exact, exact)
    ck("missing word returns empty", X.lookup("zzz", tmp.name) == "")
finally:
    os.unlink(tmp.name)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_xdxf_render: all checks ok (%d assertions)" % n[0])
