# Review of `qtranslate/xdxf.py` — the `ar`/`xdxf` passthrough is a real divergence, and it is deliberate

> Read-only review of the peer's file. **`xdxf.py` was not edited by me.** The
> XSLT it ports is now in the repo — `Resources/XdxfArticle.xslt`, chunk
> `[117]` at stream offset `0x977ec`, 832 bytes, SHA-256
> `f2e12ccad4c5ec84…` — so its "1:1" docstring is finally checkable. This
> records what the check found.

## 1. The artifact and the claim

`xdxf.py:1` says *"port of Resources/XdxfArticle.xslt"* and `:3` says
*"XSLT templates ported 1:1"*, then lists five element rules.

The recovered stylesheet has **six** templates — the identity template plus
five element rules:

| element | native rule | port |
|---|---|---|
| `k` | `<div><b><xsl:value-of select="."/></b></div>` | matches — `:20-22` |
| `tr` | `<span>[<xsl:apply-templates/>]</span>` | matches — `:23-24` |
| `kref` | `<a href="qtdp:{.}">` | matches — `:25-26` |
| `iref` | `<a href="{@href}">` | matches — `:27-28` |
| `ex` | `<span style="color:gray">` | matches — `:29-30` |
| `@* \| node()` (identity) | `<xsl:copy>` of everything else | **partially** — `:34-36` reconstruct unknown elements, but `:32-33` drops `ar` and `xdxf` |

Five of six rules are exact. The divergence is confined to one rule and it
is the one that decides the shape of the whole document.

## 2. The divergence, measured

`:32-33` is:

```python
if tag in ("ar", "xdxf"):
    return inner
```

The native identity template uses `<xsl:copy>`, so **`<ar>` and `<xdxf>`
are copied into the output, not unwrapped.** The port removes them.

Reproduced both ways:

```
XML : <ar><k>hello</k><tr>həˈloʊ</tr>
      <def><dtrn>xin chào</dtrn><ex>hello world <kref>world</kref></ex></def></ar>

port : <div><b>hello</b></div><span>[həˈloʊ</span>
       <def><dtrn>xin chào</dtrn><span style="color:gray">hello world
       <a href="qtdp:world">world</a></span></def>

native would additionally emit: <ar> … </ar> around the whole string
```

Two facts follow:

- **`<def>` survives and `<ar>` does not**, so the omission is not
  consistency. It is a specific choice about the two root-ish wrappers.
- **A nested `<ar>` inside `<xdxf>` is dropped too** — with two `<ar>`
  siblings, both lose their wrappers, so the two articles become one flat
  string with no boundary between them.

## 3. Why I am calling it defensible rather than a defect

`app.py:3685-3693` consumes the output as a **card fragment**, not as a
document:

```python
_frag = _X.lookup(word_q, _xp, exact=exact)
if _frag:
    cards.append(("xdxf", _xp.split("/")[-1].split("\\")[-1],
                  _frag[:8000]))
```

The result is inserted into a dict card that already supplies its own
containers, so an extra `<ar>` wrapper would be noise in that slot. The
docstring's "default identity copy for everything else" (`:9`) is the part
that overstates what the code does; the *behaviour* looks intentional.

**But the tests cannot tell the difference, and that is the gap.**
`tests/ui_match.py:270-274` asserts with `in`:

```python
check("xdxf-k", "<div><b>hello</b></div>" in _html, _html[:80])
```

An `in` assertion passes whether or not `<ar>` is present, and
`in _html[:80]` passes for the fragment *and* for any prefix of it. So the
suite is green on this and would stay green if the passthrough were
removed, re-added, or narrowed to only one of the two tags. That is the
same shape the peer's own mutation work found elsewhere: *"an assertion
matching only five of seven attributes let a mutant survive."*

## 4. What I'd want, in the peer's file and therefore not mine to write

1. **A test that pins the boundary.** One case with **two** `<ar>` siblings
   under `<xdxf>` asserting both articles' text is present *and* that the
   output is not silently concatenated without a separator. That is the
   case where unwrapping is observable.
2. **One line in the docstring** saying `ar`/`xdxf` are unwrapped on
   purpose because the caller wraps the fragment in its own card — the
   current `"port of Resources/XdxfArticle.xslt"` + `"1:1"` reads as
   stronger than the code.
3. Optionally, decide explicitly whether `<xdxf>` should be unwrapped
   *inside* `render_article` or left to `lookup`, since `:44` already
   special-cases the root: `render_article` on a bare `<ar>` unwraps it,
   which is the opposite of what an identity template does at the root.

## 5. Reproduce

```python
import struct
p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()
n = struct.unpack_from("<I", p, 0x977ec)[0]
raw = p[0x977ec+4:0x977ec+4+n]
xsl = raw.decode("utf-8")

assert len(raw) == 832                      # includes the 3-byte UTF-8 BOM
assert raw[:3] == b"\xef\xbb\xbf"
assert len(xsl) == 830                      # BOM decoded to one U+FEFF char
assert '<xsl:template match="@* | node()">' in xsl      # identity: <xsl:copy>
assert '<a href="qtdp:{.}">' in xsl
assert xsl.count("<xsl:template") == 6      # identity + 5 element rules
```

Then, in the port:

```python
from qtranslate.xdxf import render_article
out = render_article('<ar><k>cat</k></ar>')
assert "<ar" not in out          # the divergence
assert out == "<div><b>cat</b></div>"
```

The count of 6 templates is not incidental — it is the check that the
recovered file is the whole stylesheet and not a fragment. Five of the six
match the port exactly; the sixth is the identity template, and that is
where §2's divergence lives.

## 6. Scope of what this is

A review note on a file the peer owns, prompted by a newly-available
artifact. No row state, no tally, no Gate line, and **no change to
`qtranslate/xdxf.py` or any test.** If the passthrough is deliberate, the
fix is a docstring and a test, not code; if it is accidental, the fix is
code. That distinction is the port owner's to make, and this document
deliberately does not make it for them.
