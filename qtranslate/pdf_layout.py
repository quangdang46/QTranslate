"""Layout-aware PDF translation — docs/PDF_LAYOUT.md strategy A.

Upstream (.tmp ``core/document``): ``PositionedTextStripper`` collects
every text run with its bbox and font metrics, ``groupPdfBlocks``
merges consecutive lines into paragraph-like blocks, each block's
source text is translated, the page is rendered to a raster, and the
translated text is fitted into each block's pixel bounds (wrap, shrink
to a floor, contrasting ink on the sampled local background) and
overlaid as vector text.

This port keeps the same contract with permissive-licence parts only:

* ``pdfplumber.extract_text_lines`` -> positioned lines (bbox, size,
  bold/italic, colour) grouped into paragraph blocks;
* ``pypdfium2`` renders each page to a raster background;
* ``reportlab`` writes the output PDF: page image + vector text,
  exactly upstream's "raster background, selectable text" shape.

Honest limits (same class as upstream's own): horizontal LTR text
only. Pages rotated by a multiple of 90 degrees are supported by
un-rotating every extracted line into the page's natural frame
(``_segments_unrotated``), un-rotating the raster the same way, and
carrying the page's ``/Rotate`` onto the output; arbitrary angles
still raise ``LayoutAwareUnavailable`` before any translation call is
spent. Blocks whose translation comes back empty keep the original
text visible (the background still shows it); blocks that cannot be
fitted are covered with the sampled background colour so no stale
glyphs show through.
"""
import os
import re
from dataclasses import dataclass

# -- block model ------------------------------------------------------------


@dataclass
class PdfLine:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    size: float
    bold: bool = False
    italic: bool = False
    mono: bool = False
    color: tuple = (0, 0, 0)


@dataclass
class PdfBlock:
    page: int                     # 0-based page index
    x0: float
    top: float
    x1: float
    bottom: float
    text: str                     # source text (lines joined by " ")
    size: float                   # dominant font size, points
    bold: bool = False
    italic: bool = False
    mono: bool = False
    color: tuple = (0, 0, 0)
    translated: str = ""


class LayoutAwareUnavailable(Exception):
    """The PDF cannot go through the layout-aware path (rotated pages,
    no extractable blocks, missing optional deps)."""


# -- extraction -------------------------------------------------------------

_BOLD_RE = re.compile(r"bold|black|heavy", re.I)
_ITALIC_RE = re.compile(r"italic|oblique", re.I)
_MONO_RE = re.compile(r"mono|courier|consol", re.I)
_BULLET_RE = re.compile(r"^\s*(?:[•·◦▪‣]|[-*–—]|\(?\d{1,2}[.)]|[a-zA-Z][.)])\s+")


def _color_of(chars):
    """First non-stroking colour, normalised to an (r, g, b) 0..1 tuple."""
    for ch in chars:
        c = ch.get("non_stroking_color")
        if c is None:
            continue
        try:
            if len(c) >= 3:
                return tuple(float(v) for v in c[:3])
            g = float(c[0])
            return (g, g, g)
        except Exception:
            continue
    return (0, 0, 0)


def _line_of(raw) -> PdfLine | None:
    """One extract_text_lines entry -> PdfLine, or None when it carries
    no horizontal ink (whitespace-only / fully vertical)."""
    chars = [c for c in (raw.get("chars") or [])
             if c.get("upright", True) and c.get("text", "").strip()]
    if not chars:
        return None
    # raw["text"] keeps the real word spacing; joining chars would
    # glue words together.
    text = (raw.get("text") or "").strip()
    if not text.strip():
        return None
    sizes = sorted(float(c.get("size") or 0) for c in chars
                   if c.get("size"))
    size = sizes[len(sizes) // 2] if sizes else 0.0
    if size <= 0:
        size = float(raw.get("bottom", 0)) - float(raw.get("top", 0))
    names = " ".join(str(c.get("fontname") or "") for c in chars)
    return PdfLine(
        text=text,
        x0=float(raw.get("x0", 0)), top=float(raw.get("top", 0)),
        x1=float(raw.get("x1", 0)), bottom=float(raw.get("bottom", 0)),
        size=size,
        bold=bool(_BOLD_RE.search(names)),
        italic=bool(_ITALIC_RE.search(names)),
        mono=bool(_MONO_RE.search(names)),
        color=_color_of(chars))


def _group_blocks(lines):
    """Merge consecutive lines into paragraph-like blocks.

    A new block starts on: a paragraph-sized vertical gap, a large font
    step (headings), an indentation jump, or after a heading/bullet
    line. Heuristics in the spirit of upstream ``groupPdfBlocks`` --
    same weakness on multi-column layouts is acceptable parity.
    """
    blocks = []
    cur = None
    cur_first = ""
    for ln in lines:
        if cur is None:
            cur = PdfBlock(0, ln.x0, ln.top, ln.x1, ln.bottom, ln.text,
                           ln.size, ln.bold, ln.italic, ln.mono, ln.color)
            cur_first = ln.text
            continue
        gap = ln.top - cur.bottom
        lead = max(cur.size, ln.size, 1.0)
        indent_jump = abs(ln.x0 - cur.x0) > 1.6 * lead
        size_jump = abs(ln.size - cur.size) > 0.35 * max(cur.size,
                                                        ln.size, 1.0)
        para_gap = gap > 1.45 * lead
        bullet = bool(_BULLET_RE.match(ln.text))
        cur_bullet = bool(_BULLET_RE.match(cur_first))
        # A change of face (bold/italic/size) closes the block --
        # headings and emphasised runs never merge into body text.
        heading = (cur.bold != ln.bold or cur.italic != ln.italic
                   or cur.mono != ln.mono or size_jump)
        same_para = (not para_gap and not indent_jump
                     and not size_jump and not bullet
                     and not cur_bullet)
        if same_para and not heading:
            cur.text += " " + ln.text
            cur.x1 = max(cur.x1, ln.x1)
            cur.bottom = max(cur.bottom, ln.bottom)
            cur.top = min(cur.top, ln.top)
            continue
        blocks.append(cur)
        cur = PdfBlock(0, ln.x0, ln.top, ln.x1, ln.bottom, ln.text,
                       ln.size, ln.bold, ln.italic, ln.mono, ln.color)
        cur_first = ln.text
    if cur is not None:
        blocks.append(cur)
    return blocks


# -- rotated pages ---------------------------------------------------------
#
# pdfplumber reports char/line boxes in the page's VISUAL frame (the
# orientation /Rotate displays), with the text direction baked into
# the char order -- which runs backwards on 180/270 pages and splits
# each visual line into a word-column on 90/270. The port instead works
# in the page's NATURAL frame (rotation 0): every segment is mapped
# back with the matching quarter-turn, segments of one natural line
# are clustered by their unrotated band and re-joined left-to-right,
# and a segment whose char order runs against +x is reversed (180/270
# pages store the glyphs right-to-left). The raster is un-rotated the
# same way and the output page keeps the source /Rotate, so the
# finished PDF displays exactly like the input.

_ROT_SUPPORTED = (0, 90, 180, 270)


def _unrot_bbox(x0, top, x1, bottom, w, h, rot):
    """A visual-frame box -> the page's natural (rotation-0) frame.

    ``w``/``h`` are the VISUAL page dims in points; the natural frame
    swaps them for quarter turns. All four cases are pure axis swaps,
    so transforming the two diagonal corners is exact.
    """
    if rot == 90:
        return top, w - x1, bottom, w - x0
    if rot == 180:
        return w - x1, h - bottom, w - x0, h - top
    if rot == 270:
        return h - bottom, x0, h - top, x1
    return x0, top, x1, bottom


def _unrot_point(x, y, w, h, rot):
    x0, top, x1, bottom = _unrot_bbox(x, y, x, y, w, h, rot)
    return (x0 + x1) / 2.0, (top + bottom) / 2.0


def _segments_unrotated(raw, w, h, rot):
    """One extract_text_lines entry -> natural-frame line segments.

    On 90/270 pages a visual 'line' is one word-column of the natural
    line, so each visual line becomes ONE segment; on 0/180 it is
    already a whole natural line. Text order is corrected per segment
    by comparing the unrotated x of its first and last char.
    """
    chars = [c for c in (raw.get("chars") or [])
             if c.get("upright", True) or rot != 0]
    chars = [c for c in chars if c.get("text", "").strip()]
    if not chars:
        return []
    text = (raw.get("text") or "").strip()
    if not text:
        return []
    sizes = sorted(float(c.get("size") or 0) for c in chars
                   if c.get("size"))
    size = sizes[len(sizes) // 2] if sizes else 0.0
    if size <= 0:
        size = (float(raw.get("bottom", 0)) - float(raw.get("top", 0)))
    names = " ".join(str(c.get("fontname") or "") for c in chars)
    x0, top, x1, bottom = _unrot_bbox(
        float(raw.get("x0", 0)), float(raw.get("top", 0)),
        float(raw.get("x1", 0)), float(raw.get("bottom", 0)), w, h, rot)
    if rot in (90, 270):
        # On quarter turns the visual 'size' is the glyph's rotated
        # height (its advance), not the font size; the natural-frame
        # font size is the visual char WIDTH instead.
        widths = sorted(float(c.get("x1", 0)) - float(c.get("x0", 0))
                        for c in chars
                        if c.get("x1") is not None and c.get("x0") is not None)
        if widths:
            size = widths[len(widths) // 2]
    seg_text = text
    if rot:
        # Char order follows the visual text direction; when that runs
        # against +x in the natural frame the stored string is the
        # mirror image (180/270 pages).
        try:
            c0, c1 = chars[0], chars[-1]
            cx0 = (float(c0.get("x0", 0)) + float(c0.get("x1", 0))) / 2
            cy0 = (float(c0.get("top", 0)) + float(c0.get("bottom", 0))) / 2
            cx1 = (float(c1.get("x0", 0)) + float(c1.get("x1", 0))) / 2
            cy1 = (float(c1.get("top", 0)) + float(c1.get("bottom", 0))) / 2
            _, ya = _unrot_point(cx0, cy0, w, h, rot)
            _, yb = _unrot_point(cx1, cy1, w, h, rot)
            xa, _ = _unrot_point(cx0, cy0, w, h, rot)
            xb, _ = _unrot_point(cx1, cy1, w, h, rot)
            if xb < xa:
                seg_text = text[::-1]
        except Exception:
            pass
    return [PdfLine(
        text=seg_text, x0=x0, top=top, x1=x1, bottom=bottom, size=size,
        bold=bool(_BOLD_RE.search(names)),
        italic=bool(_ITALIC_RE.search(names)),
        mono=bool(_MONO_RE.search(names)),
        color=_color_of(chars))]


def _merge_rot_lines(segments):
    """Cluster natural-frame segments into lines and order them.

    Segments whose unrotated bands overlap vertically belong to the
    same natural line (the word-columns of a 90/270 page); they are
    joined left-to-right. Everything is then sorted top->bottom,
    left->right like pdfplumber's own line order.
    """
    segments = sorted(segments, key=lambda l: (l.top, l.x0))
    lines = []
    cur = []
    for s in segments:
        if cur:
            top = min(g.top for g in cur)
            bottom = max(g.bottom for g in cur)
            # Same natural line: the word-columns share (nearly) the
            # same unrotated band, so their overlap is most of a line
            # height; distinct lines leave a real gap.
            overlap = min(s.bottom, bottom) - max(s.top, top)
            if overlap <= 0.4 * max(s.size, 1.0):
                lines.append(cur)
                cur = []
        cur.append(s)
    if cur:
        lines.append(cur)
    out = []
    for group in lines:
        group.sort(key=lambda l: l.x0)
        first = group[0]
        merged = PdfLine(
            text=" ".join(g.text for g in group),
            x0=min(g.x0 for g in group), top=min(g.top for g in group),
            x1=max(g.x1 for g in group), bottom=max(g.bottom for g in group),
            size=max(g.size for g in group),
            bold=any(g.bold for g in group),
            italic=any(g.italic for g in group),
            mono=all(g.mono for g in group),
            color=first.color)
        out.append(merged)
    out.sort(key=lambda l: (l.top, l.x0))
    return out


def extract_blocks(path):
    """-> (blocks, page_sizes, rotations). One list per page, plus each
    page's NATURAL-frame (width, height) in points and its /Rotate
    value. For quarter-turn pages the blocks are un-rotated into the
    natural frame; ``_render_pages`` un-rotates the raster to match and
    the writer carries /Rotate onto the output page."""
    import pdfplumber
    blocks = []
    sizes = []
    rotations = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages):
            w = float(page.width)
            h = float(page.height)
            try:
                rot = int(page.rotation or 0) % 360
            except Exception:
                rot = 0
            rotations.append(rot)
            if rot in (90, 270):
                sizes.append((h, w))
            else:
                sizes.append((w, h))
            lines = []
            try:
                raws = page.extract_text_lines() or []
                if rot in (90, 180, 270):
                    segs = []
                    for raw in raws:
                        segs.extend(_segments_unrotated(raw, w, h, rot))
                    lines = _merge_rot_lines(segs)
                else:
                    for raw in raws:
                        ln = _line_of(raw)
                        if ln is not None:
                            lines.append(ln)
            except Exception:
                lines = []
            lines.sort(key=lambda l: (l.top, l.x0))
            page_blocks = _group_blocks(lines)
            for b in page_blocks:
                b.page = pno
            blocks.append(page_blocks)
    return blocks, sizes, rotations


# -- fonts ------------------------------------------------------------------

_FONT_CANDIDATES = {
    "regular": [
        r"C:\Windows\Fonts\arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ],
    "bold": [
        r"C:\Windows\Fonts\arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ],
    "italic": [
        r"C:\Windows\Fonts\ariali.ttf",
        "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
    ],
    "mono": [
        r"C:\Windows\Fonts\cour.ttf",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    ],
}

_fonts = {}
_STD14 = {"regular": "Helvetica", "bold": "Helvetica-Bold",
          "italic": "Helvetica-Oblique", "mono": "Courier"}

# CJK-capable faces tried, in order, when the block's own font cannot
# encode the translated text (``_covers``). TTC files need a
# subfontIndex -- 0 is the default face for every candidate here.
_CJK_CANDIDATES = [
    (r"C:\Windows\Fonts\simsun.ttc", 0),
    (r"C:\Windows\Fonts\msgothic.ttc", 0),
    (r"C:\Windows\Fonts\malgun.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", 0),
]
_cjk_names = {}      # (path, subfontIndex) -> registered name or None


def _register_ttf(path, subfont_index, tag):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    name = "QTLayout_%s_%s" % (
        tag, abs(hash(os.path.abspath(path) + "|%d" % subfont_index)))
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(
            TTFont(name, path, subfontIndex=subfont_index))
        pdfmetrics.registerFontFamily(
            name, normal=name, bold=name, italic=name, boldItalic=name)
    return name


def _font(kind="regular", bold=False, italic=False):
    """A reportlab font name for canvas.setFont.

    Prefers a system TTF (unicode-capable -- needed for Vietnamese/CJK
    translations); falls back to the standard-14 families, which raise
    UnicodeEncodeError on unencodable glyphs -- callers cover the block
    in that case rather than emit a corrupt PDF.
    """
    family = "mono" if kind == "mono" else \
        "bold" if bold else "italic" if italic else "regular"
    if family in _fonts:
        return _fonts[family]
    path = next((p for p in _FONT_CANDIDATES[family]
                 if os.path.isfile(p)), None)
    if path:
        try:
            _fonts[family] = _register_ttf(path, 0, family)
            return _fonts[family]
        except Exception:
            pass
    _fonts[family] = _STD14[family]
    return _fonts[family]


def _covers(font, text):
    """True when ``font`` can encode every non-space char of ``text``.

    TTF faces expose ``charToGlyph``; a missing entry means the glyph
    does not exist (the draw would drop the line). Standard-14 fonts
    have no such table -- return True and let drawString's own
    try/except be the judge, exactly like before.
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        face = pdfmetrics.getFont(font).face
        cg = getattr(face, "charToGlyph", None)
        if cg is None:
            return True
        return all(cg.get(ord(c)) for c in text if not c.isspace())
    except Exception:
        return True


def _cjk_font_for(text):
    """First registered CJK face covering ``text``'s codepoints, or None."""
    need = {ord(c) for c in text if not c.isspace()}
    if not need:
        return None
    from reportlab.pdfbase import pdfmetrics
    for path, idx in _CJK_CANDIDATES:
        if not os.path.isfile(path):
            continue
        key = (path, idx)
        if key not in _cjk_names:
            try:
                _cjk_names[key] = _register_ttf(path, idx, "cjk")
            except Exception:
                _cjk_names[key] = None
        name = _cjk_names[key]
        if not name:
            continue
        face = pdfmetrics.getFont(name).face
        cg = getattr(face, "charToGlyph", None)
        if cg is not None and all(cg.get(c) for c in need):
            return name
    return None


def _font_for_text(kind, bold, italic, text):
    """The block's font, swapped for a CJK face when the translation
    carries glyphs the document font cannot encode (otherwise the
    overlay would silently drop those lines)."""
    font = _font(kind, bold, italic)
    if _covers(font, text):
        return font
    return _cjk_font_for(text) or font


def _string_width(text, font, size):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    try:
        return stringWidth(text, font, size)
    except Exception:
        # A font that cannot encode the text at all (std-14 + CJK)
        # would crash the fitter; treat the run as wide glyphs so the
        # block still wraps and the draw path's own fallback decides.
        return len(text) * size


# -- fitting ----------------------------------------------------------------

_FLOOR = 0.68          # upstream's minimum shrink factor
_LEADING = 1.18


def fit_block(text, block, max_width, max_height):
    """-> (size_pt, [lines]) fitted into the block's box, or None when
    even the floor size cannot place a single line.

    Greedy word wrap at the block's font size, shrink toward
    ``size * _FLOOR``, clip lines that would overflow the block's
    height (upstream's "best-effort appearance" contract).
    """
    words = text.split()
    if not words:
        return None
    size = float(block.size) or 10.0
    floor = max(size * _FLOOR, 4.0)
    font = _font_for_text("mono" if getattr(block, "mono", False)
                          else "regular",
                          bold=block.bold, italic=block.italic, text=text)
    while size >= floor:
        lines, ok = _wrap(words, font, size, max_width)
        if lines and len(lines) * size * _LEADING <= max_height + 0.5:
            return size, lines
        size *= 0.92
    # last resort at the floor: take what fits, clip the rest
    size = floor
    lines, _ok = _wrap(words, font, size, max_width)
    fit = int(max_height // (size * _LEADING))
    lines = lines[:max(fit, 1)]
    return size, lines


def _wrap(words, font, size, max_width):
    lines = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if cur and _string_width(cand, font, size) > max_width:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines, bool(lines)


# -- background colour ------------------------------------------------------


def _bg_color(img, rect):
    """Dominant colour inside ``rect`` (x0, top, x1, bottom in image
    pixels) -- the local page background the translated ink sits on."""
    x0, top, x1, bottom = [int(round(v)) for v in rect]
    x0, top = max(0, x0), max(0, top)
    x1, bottom = min(img.width, x1), min(img.height, bottom)
    if x1 <= x0 or bottom <= top:
        return (1, 1, 1)
    crop = img.crop((x0, top, x1, bottom)).convert("RGB")
    # Downscale hard then take the modal colour: cheap and stable.
    small = crop.resize((max(1, crop.width // 8),
                         max(1, crop.height // 8)))
    counts = {}
    for r, g, b in small.getdata():
        key = (r // 24, g // 24, b // 24)
        counts[key] = counts.get(key, 0) + 1
    r, g, b = max(counts.items(), key=lambda kv: kv[1])[0]
    return ((r * 24 + 12) / 255.0, (g * 24 + 12) / 255.0,
            (b * 24 + 12) / 255.0)


def _ink_for(bg):
    """Contrasting ink: dark text on light backgrounds, light on dark
    (upstream samples the local bg and picks a contrasting colour)."""
    lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    return (0.05, 0.05, 0.05) if lum > 0.55 else (0.95, 0.95, 0.95)


# -- render + overlay ---------------------------------------------------------

_RENDER_SCALE = 216.0 / 72.0     # upstream renders at 216 DPI


def _render_pages(path, count, rotations=None):
    """pypdfium2 -> one PIL image per page at _RENDER_SCALE.

    pdfium renders the VISUAL orientation; for quarter-turn pages the
    image is rotated back into the natural frame so it lines up with
    the un-rotated block coordinates. ``img.rotate(+r)`` undoes the
    clockwise ``/Rotate r`` pdfium applied (PIL angles are CCW).
    """
    import pypdfium2 as pdfium
    rotations = rotations or [0] * count
    doc = pdfium.PdfDocument(path)
    try:
        out = []
        for i in range(min(count, len(doc))):
            page = doc[i]
            try:
                img = page.render(scale=_RENDER_SCALE).to_pil() \
                    .convert("RGB")
                rot = int(rotations[i]) if i < len(rotations) else 0
                if rot:
                    img = img.rotate(rot, expand=True)
                out.append(img)
            finally:
                page.close()
        return out
    finally:
        doc.close()


def _translate_pdf_layout(path, out, translator, sl, tl,
                          on_progress, is_cancelled=None):
    """The LAYOUT_AWARE path: translate at block granularity, keep the
    page as a rendered background, overlay fitted vector text."""
    from .document import (_progress, _translate_segment,
                           DocumentTranslationError)
    try:
        import pdfplumber  # noqa: F401
        import pypdfium2  # noqa: F401
        import reportlab  # noqa: F401
        from PIL import Image  # noqa: F401  (pypdfium2 .to_pil())
    except ImportError as e:
        raise LayoutAwareUnavailable(
            "Layout-aware PDF translation needs pdfplumber, "
            "pypdfium2, reportlab and Pillow (%s)." % e)

    blocks_per_page, sizes, rotations = extract_blocks(path)
    bad = [r for r in rotations if r not in _ROT_SUPPORTED]
    if bad:
        # Arbitrary angles put pdfplumber's coords and the raster in
        # frames the quarter-turn un-rotation cannot reconcile; refuse
        # honestly rather than draw text sideways.
        raise LayoutAwareUnavailable(
            "Layout-aware translation does not support pages rotated "
            "by %s degrees; use Text-only mode." % bad[0])
    flat = [b for page in blocks_per_page for b in page
            if b.text.strip()]
    if not flat:
        raise DocumentTranslationError(
            "No selectable text was found in this PDF. Run OCR "
            "before translating it.")

    total = len(flat)
    _progress(on_progress, 0, total, "")
    for n, b in enumerate(flat):
        if is_cancelled and is_cancelled():
            from .document import DocumentCancelled
            raise DocumentCancelled()
        try:
            b.translated = _translate_segment(b.text, translator, sl, tl)
        except DocumentTranslationError:
            raise
        except Exception:
            b.translated = ""
        _progress(on_progress, n + 1, total, b.text[:80])

    images = _render_pages(path, len(sizes), rotations)
    if len(images) != len(sizes):
        raise LayoutAwareUnavailable(
            "Could not render every page for layout-aware output.")

    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    c = rl_canvas.Canvas(out)
    for pno, ((w_pt, h_pt), img) in enumerate(zip(sizes, images)):
        # reportlab's default page is A4; every page must be sized to
        # the source or the raster is stretched/clipped.
        c.setPageSize((w_pt, h_pt))
        # Blocks, raster and page box all live in the natural frame;
        # the source /Rotate rides onto the output below.
        c.drawImage(ImageReader(img), 0, 0, width=w_pt, height=h_pt,
                    preserveAspectRatio=False, mask="auto")
        s = _RENDER_SCALE
        for b in blocks_per_page[pno]:
            if not b.translated or not b.translated.strip():
                continue
            # pixel rect for background sampling
            rect = (b.x0 * s, b.top * s, b.x1 * s, b.bottom * s)
            bg = _bg_color(img, rect)
            ink = _ink_for(bg)
            bw, bh = (b.x1 - b.x0), (b.bottom - b.top)
            # cover the source glyphs with the local background
            c.setFillColorRGB(*bg)
            c.rect(b.x0, h_pt - b.bottom, bw, bh, stroke=0, fill=1)
            fit = fit_block(b.translated, b, bw, bh)
            if not fit:
                continue
            size, lines = fit
            font = _font_for_text("mono" if b.mono else "regular",
                                  bold=b.bold, italic=b.italic,
                                  text=b.translated)
            c.setFillColorRGB(*ink)
            leading = size * _LEADING
            # first baseline: block top + ascent (~0.8 em)
            y = h_pt - b.top - size * 0.82
            for ln in lines:
                try:
                    c.setFont(font, size)
                    c.drawString(b.x0, y, ln)
                except Exception:
                    # unencodable glyphs: one more chance with a CJK
                    # face before the line is dropped rather than
                    # corrupting the output
                    alt = _cjk_font_for(ln)
                    if alt and alt != font:
                        try:
                            c.setFont(alt, size)
                            c.drawString(b.x0, y, ln)
                            y -= leading
                            continue
                        except Exception:
                            pass
                y -= leading
        c.showPage()
    c.save()

    if any(rotations):
        # Everything above was drawn in the natural frame; stamp the
        # source /Rotate onto each output page so viewers display it
        # exactly like the input. pypdf's PageObject.rotate() adds to
        # any existing /Rotate (reportlab writes none).
        try:
            from pypdf import PdfReader, PdfWriter
            reader = PdfReader(out)
            writer = PdfWriter()
            for pno, page in enumerate(reader.pages):
                rot = int(rotations[pno]) if pno < len(rotations) else 0
                if rot:
                    page.rotate(rot)
                writer.add_page(page)
            tmp_out = out + ".rot"
            with open(tmp_out, "wb") as f:
                writer.write(f)
            os.replace(tmp_out, out)
        except Exception:
            # A failed rotation stamp degrades to an unrotated page --
            # ugly but readable; never lose the translated output.
            try:
                os.unlink(out + ".rot")
            except Exception:
                pass
