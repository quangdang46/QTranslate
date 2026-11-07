#!/usr/bin/env python3
"""Document translation port (core/document/*): format detection,
TXT/SRT/VTT segment translation with markup protection, DOCX paragraph
translation, PDF text-only extraction, validation rules, progress."""
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


from qtranslate import document as D  # noqa: E402


def tr(text, sl, tl):
    return "[T:%s]" % text


def main():
    tmp = tempfile.mkdtemp()

    print("== format detection ==")
    for name, want in (("a.docx", "docx"), ("b.PDF", "pdf"),
                       ("c.txt", "text"), ("d.srt", "srt"),
                       ("e.vtt", "vtt"), ("f.bin", None),
                       ("g", None)):
        p = os.path.join(tmp, name)
        open(p, "w").write("x")
        ck("format %s -> %s" % (name, want),
           D.format_of(p) == want, str(D.format_of(p)))

    print("== txt ==")
    src = os.path.join(tmp, "in.txt")
    out = os.path.join(tmp, "out.txt")
    open(src, "w", newline="").write(
        "Hello world.\r\n\r\nSecond line.\r\n")
    prog = []
    D.translate_document(src, out, "en", "vi", tr,
                         on_progress=lambda d, t, c: prog.append(
                             (d, t)))
    got = open(out, newline="").read()
    ck("lines translated", "[T:Hello world.]" in got
       and "[T:Second line.]" in got, got)
    ck("blank line preserved", "\r\n\r\n" in got, repr(got))
    ck("crlf ending kept", got.endswith("\r\n"), repr(got[-8:]))
    ck("progress fired", prog and prog[-1][0] == prog[-1][1]
       and prog[-1][1] == 2, str(prog))

    print("== srt ==")
    src = os.path.join(tmp, "in.srt")
    out = os.path.join(tmp, "out.srt")
    open(src, "w").write(
        "1\n00:00:01,000 --> 00:00:02,000\nHello <i>world</i>\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nSecond {\\an8}cue\n")
    D.translate_document(src, out, "en", "vi", tr)
    got = open(out).read()
    ck("cue text translated",
       "[T:Hello" in got and got.split("\n")[2].startswith("[T:"),
       got)
    ck("markup restored",
       "<i>" in got and "{\\an8}" in got, got)
    ck("timestamps kept",
       "00:00:01,000 --> 00:00:02,000" in got, got)
    ck("cue numbers kept", got.startswith("1\n"), got[:10])

    print("== vtt ==")
    src = os.path.join(tmp, "in.vtt")
    out = os.path.join(tmp, "out.vtt")
    open(src, "w").write(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello vtt\n")
    D.translate_document(src, out, "en", "vi", tr)
    got = open(out).read()
    ck("vtt translated + header kept",
       "WEBVTT" in got and "[T:Hello vtt]" in got, got)

    print("== docx ==")
    src = os.path.join(tmp, "in.docx")
    out = os.path.join(tmp, "out.docx")
    from docx import Document
    d = Document()
    d.add_paragraph("Hello docx")
    d.add_paragraph("")
    d.add_paragraph("Second para")
    d.save(src)
    D.translate_document(src, out, "en", "vi", tr)
    d2 = Document(out)
    texts = [p.text for p in d2.paragraphs]
    ck("docx paragraphs translated",
       texts[0] == "[T:Hello docx]" and texts[2] == "[T:Second para]",
       str(texts))
    ck("blank paragraph kept", texts[1] == "", str(texts))

    print("== pdf text-only ==")
    # Build a minimal PDF with extractable text via reportlab-free
    # approach: pypdf blank page has no text -> require_pdf_text error.
    from pypdf import PdfWriter
    pdf = os.path.join(tmp, "in.pdf")
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    with open(pdf, "wb") as f:
        w.write(f)
    out = os.path.join(tmp, "out.pdf.txt")
    try:
        D.translate_document(pdf, out, "en", "vi", tr,
                             pdf_mode="text_only")
        ck("empty pdf raises", False, "no exception")
    except D.DocumentTranslationError as e:
        ck("empty pdf raises", "No selectable text" in str(e), str(e))

    print("== cancellation ==")
    src = os.path.join(tmp, "many.txt")
    out = os.path.join(tmp, "many.out.txt")
    open(src, "w").write("\n".join("line %d" % i
                                  for i in range(50)) + "\n")
    state = {"n": 0}

    def slow_tr(t, s, l):
        state["n"] += 1
        return t

    def cancel_after_3():
        return state["n"] >= 3

    try:
        D.translate_document(src, out, "en", "vi", slow_tr,
                             is_cancelled=cancel_after_3)
        ck("cancel raises DocumentCancelled", False)
    except D.DocumentCancelled:
        ck("cancel raises DocumentCancelled", True)
    ck("cancelled run leaves no output", not os.path.exists(out))
    ck("no temp litter",
       not [f for f in os.listdir(tmp) if f.startswith(".qtranslate-")])

    print("== validation ==")
    try:
        D.translate_document(os.path.join(tmp, "none.docx"),
                             out, "en", "vi", tr)
        ck("missing input raises", False)
    except D.DocumentTranslationError:
        ck("missing input raises", True)
    try:
        D.translate_document(src, src, "en", "vi", tr)
        ck("same in/out raises", False)
    except D.DocumentTranslationError:
        ck("same in/out raises", True)
    try:
        D.translate_document(src, out, "en", "auto", tr)
        ck("auto target raises", False)
    except D.DocumentTranslationError:
        ck("auto target raises", True)
    pdf_in = os.path.join(tmp, "in.pdf")
    try:
        D.translate_document(pdf_in, os.path.join(tmp, "bad.pdf"),
                             "en", "vi", tr)
        ck("pdf wrong output ext raises", False)
    except D.DocumentTranslationError as e:
        ck("pdf wrong output ext raises",
           "TXT" in str(e), str(e))
    try:
        D.translate_document(pdf_in, out, "en", "vi", tr,
                             pdf_mode="layout_aware")
        ck("layout-aware honest error", False)
    except D.DocumentTranslationError as e:
        ck("layout-aware honest error",
           "not available" in str(e).lower(), str(e))
    ck("unsupported ext",
       D.format_of(os.path.join(tmp, "x.exe")) is None)

    print()
    if FAIL:
        print("regress_document: %d FAILED: %s" % (len(FAIL), FAIL))
        sys.exit(1)
    print("regress_document: all checks ok")


if __name__ == "__main__":
    main()
