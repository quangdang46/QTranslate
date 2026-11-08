#!/usr/bin/env python3
"""Layout-aware PDF translation (qtranslate/pdf_layout.py,
docs/PDF_LAYOUT.md strategy A): positioned extraction, block grouping,
text fitting, raster background + vector overlay, honest errors.

Fixtures are generated with reportlab -- no binary PDFs in the repo.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


def _make_pdf(path, pages_lines):
    """pages_lines: list of pages; each page is [(text, x, y, size,
    fontname), ...] in reportlab coords (origin bottom-left)."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    c = canvas.Canvas(path, pagesize=letter)
    for lines in pages_lines:
        for text, x, y, size, font in lines:
            c.setFont(font, size)
            c.drawString(x, y, text)
        c.showPage()
    c.save()


def tr(text, sl, tl):
    return "VI:" + text


def main():
    tmp = tempfile.mkdtemp()

    print("== extraction + grouping ==")
    from qtranslate import pdf_layout as PL
    src = os.path.join(tmp, "in.pdf")
    _make_pdf(src, [[
        ("Hello world this is a test paragraph.", 72, 720, 12,
         "Helvetica"),
        ("Second line of the same paragraph here.", 72, 704, 12,
         "Helvetica"),
        ("A Bold Heading", 72, 660, 14, "Helvetica-Bold"),
        ("Body text under the heading, more words to wrap around "
         "nicely for testing purposes indeed.", 72, 640, 12,
         "Helvetica"),
    ]])
    blocks, sizes, rotations = PL.extract_blocks(src)
    ck("one page", len(blocks) == 1, str(len(blocks)))
    ck("page size letter", sizes[0] == (612.0, 792.0), str(sizes))
    ck("rotation 0", rotations == [0], str(rotations))
    pblocks = [b for b in blocks[0] if b.text.strip()]
    ck("paragraph lines merged", any(
        "same paragraph" in b.text for b in pblocks),
       str([b.text for b in pblocks]))
    ck("heading is its own block", any(
        b.text == "A Bold Heading" and b.bold for b in pblocks),
       str([(b.text, b.bold) for b in pblocks]))
    ck("block carries size", all(b.size > 0 for b in pblocks))

    print("== fitting ==")
    b = pblocks[0]
    fit = PL.fit_block("a much longer translated text that will "
                       "definitely need wrapping inside the block",
                       b, b.x1 - b.x0, b.bottom - b.top)
    ck("fit returns size+lines", fit is not None and len(fit) == 2)
    if fit:
        size, lines = fit
        ck("fit size within floor",
           size >= b.size * PL._FLOOR * 0.95, str(size))
        ck("fit lines non-empty", all(ln.strip() for ln in lines))
    tiny = PL.PdfBlock(0, 0, 0, 10, 12, "x" * 500, 12)
    ck("impossible fit still returns clipped",
       PL.fit_block("word " * 200, tiny, 10, 12) is not None)

    print("== end-to-end layout_aware ==")
    from qtranslate import document as D
    out = os.path.join(tmp, "out.pdf")
    prog = []
    D.translate_document(src, out, "en", "vi", tr,
                         pdf_mode="layout_aware",
                         on_progress=lambda d, t, c: prog.append(
                             (d, t)))
    ck("output pdf exists", os.path.isfile(out))
    from pypdf import PdfReader
    r = PdfReader(out)
    ck("one page out", len(r.pages) == 1, str(len(r.pages)))
    txt = r.pages[0].extract_text() or ""
    ck("translated text is vector-selectable",
       "VI:" in txt, txt[:120])
    ck("progress completed", prog and prog[-1][0] == prog[-1][1],
       str(prog))

    print("== multi-page + blank-page skip ==")
    src2 = os.path.join(tmp, "two.pdf")
    _make_pdf(src2, [
        [("Page one text here.", 72, 720, 12, "Helvetica")],
        [],
        [("Page three text here.", 72, 720, 12, "Helvetica")],
    ])
    out2 = os.path.join(tmp, "two_out.pdf")
    seen = []
    D.translate_document(src2, out2, "en", "vi",
                         lambda t, s, l: seen.append(t) or tr(t, s, l),
                         pdf_mode="layout_aware")
    ck("all pages rendered", len(PdfReader(out2).pages) == 3)
    ck("blank page skipped", not any("Page two" in t for t in seen))

    print("== CJK font fallback ==")
    cjk_probe = "你好世界"
    cjk_font = PL._cjk_font_for(cjk_probe)
    base_font = PL._font("regular")
    ck("document font cannot encode CJK",
       not PL._covers(base_font, cjk_probe) or cjk_font is None)
    if cjk_font:
        ck("cjk face covers the probe", PL._covers(cjk_font, cjk_probe))
        picked = PL._font_for_text("regular", False, False, cjk_probe)
        ck("font_for_text swaps to the cjk face",
           picked == cjk_font, "%s vs %s" % (picked, cjk_font))
        out_c = os.path.join(tmp, "cjk_out.pdf")
        D.translate_document(src, out_c, "en", "vi",
                             lambda t, s, l: "你好世界",
                             pdf_mode="layout_aware")
        txt_c = PdfReader(out_c).pages[0].extract_text() or ""
        ck("cjk translation stays selectable",
           "你好" in txt_c, txt_c[:120])
    else:
        print("  .. no CJK-capable face on this system; "
              "end-to-end leg skipped")

    print("== multi-column grouping ==")
    colsrc = os.path.join(tmp, "cols.pdf")
    cl = [("Full Width Heading Across Both Columns", 60, 752, 14,
           "Helvetica-Bold")]
    for i in range(4):
        y = 720 - i * 14
        cl.append(("Left column line number %d with several words." % i,
                   60, y, 11, "Helvetica"))
        cl.append(("Right column line number %d with several words." % i,
                   340, y, 11, "Helvetica"))
    _make_pdf(colsrc, [cl])
    cblocks, _, _ = PL.extract_blocks(colsrc)
    texts = [b.text for b in cblocks[0]]
    ck("columns not interleaved", any(
        "Left column line number 0" in t and "Right column" not in t
        for t in texts), str(texts))
    ck("right column own block", any(
        t.startswith("Right column line number 0") for t in texts),
       str(texts))
    ck("heading own block", any(
        t == "Full Width Heading Across Both Columns" for t in texts))
    ck("column lines merged", any(
        "line number 3" in t and "line number 0" in t
        for t in texts), str(texts))

    print("== rotated pages ==")
    # quarter-turn pages are un-rotated into the natural frame, the
    # raster is un-rotated to match, and /Rotate rides onto the output
    from pypdf import PdfReader as PR, PdfWriter as PW
    for deg in (90, 180, 270):
        rot = os.path.join(tmp, "rot%d.pdf" % deg)
        rr = PR(src)
        ww = PW()
        pg = rr.pages[0]
        pg.rotate(deg)
        ww.add_page(pg)
        with open(rot, "wb") as f:
            ww.write(f)
        rblocks, rsizes, rrots = PL.extract_blocks(rot)
        ck("rot%d natural size" % deg, rsizes == [(612.0, 792.0)],
           str(rsizes))
        ck("rot%d rotation kept" % deg, rrots == [deg], str(rrots))
        ck("rot%d text recovered" % deg, any(
            "Hello world this is a test paragraph" in b.text
            for b in rblocks[0]),
           str([b.text for b in rblocks[0]]))
        ck("rot%d bbox natural" % deg, any(
            abs(b.x0 - 72) < 2 and abs(b.top - 62.5) < 3
            for b in rblocks[0]),
           str([(round(b.x0, 1), round(b.top, 1))
                for b in rblocks[0]]))
        out_rot = os.path.join(tmp, "rot%d_out.pdf" % deg)
        D.translate_document(rot, out_rot, "en", "vi", tr,
                             pdf_mode="layout_aware")
        rp = PdfReader(out_rot).pages[0]
        ck("rot%d /Rotate stamped" % deg,
           int(rp.get("/Rotate") or 0) == deg,
           str(rp.get("/Rotate")))
        ck("rot%d page box natural" % deg,
           abs(float(rp.mediabox.width) - 612) < 1
           and abs(float(rp.mediabox.height) - 792) < 1,
           str(rp.mediabox))
        ck("rot%d translated selectable" % deg,
           "VI:" in (rp.extract_text() or ""))
    # rotated + multi-column: the word-column merge must not glue the
    # two columns into one natural line
    rr = PR(colsrc)
    ww = PW()
    pg = rr.pages[0]
    pg.rotate(90)
    ww.add_page(pg)
    colrot = os.path.join(tmp, "cols_rot.pdf")
    with open(colrot, "wb") as f:
        ww.write(f)
    rcol_blocks, _, _ = PL.extract_blocks(colrot)
    rtexts = [b.text for b in rcol_blocks[0]]
    ck("rotated columns not interleaved", any(
        "Left column line number 0" in t and "Right column" not in t
        for t in rtexts), str(rtexts))
    ck("rotated right column own block", any(
        t.startswith("Right column line number 0") for t in rtexts),
       str(rtexts))
    # an arbitrary angle still refuses honestly before spending calls
    # (pypdf's rotate() only takes multiples of 90 -- set /Rotate raw)
    from pypdf.generic import NameObject, NumberObject
    rot45 = os.path.join(tmp, "rot45.pdf")
    rr = PR(src)
    ww = PW()
    pg = rr.pages[0]
    pg[NameObject("/Rotate")] = NumberObject(45)
    ww.add_page(pg)
    with open(rot45, "wb") as f:
        ww.write(f)
    try:
        D.translate_document(rot45, os.path.join(tmp, "rot45_out.pdf"),
                             "en", "vi", tr, pdf_mode="layout_aware")
        ck("odd-angle page refused", False)
    except D.DocumentTranslationError as e:
        ck("odd-angle page refused",
           "rotated" in str(e).lower() or "support" in str(e).lower(),
           str(e))

    print("== honest errors ==")
    # empty pdf -> no selectable text
    from pypdf import PdfWriter
    blank = os.path.join(tmp, "blank.pdf")
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    with open(blank, "wb") as f:
        w.write(f)
    try:
        D.translate_document(blank, os.path.join(tmp, "b_out.pdf"),
                             "en", "vi", tr, pdf_mode="layout_aware")
        ck("blank pdf refused", False)
    except D.DocumentTranslationError as e:
        ck("blank pdf refused", "No selectable text" in str(e), str(e))
    # cancelled mid-run
    state = {"n": 0}
    try:
        D.translate_document(
            src, os.path.join(tmp, "c_out.pdf"), "en", "vi",
            lambda t, s, l: state.__setitem__("n", state["n"] + 1)
            or t,
            pdf_mode="layout_aware",
            is_cancelled=lambda: state["n"] >= 1)
        ck("cancel raises", False)
    except D.DocumentCancelled:
        ck("cancel raises", True)
    ck("cancel leaves no output",
       not os.path.exists(os.path.join(tmp, "c_out.pdf")))

    print()
    if FAIL:
        print("regress_pdf_layout: %d FAILED: %s" % (len(FAIL), FAIL))
        sys.exit(1)
    print("regress_pdf_layout: all checks ok")


if __name__ == "__main__":
    main()
