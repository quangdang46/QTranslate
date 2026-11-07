"""Document translation -- port of core/document/*.

Formats (DocumentFormat): docx, pdf, txt, srt, vtt. PDF has two modes
upstream: TEXT_ONLY (per-page text -> .txt) and LAYOUT_AWARE (rendered
page images + overlaid vector text -> .pdf). This port implements
TEXT_ONLY only; LAYOUT_AWARE needs a PDF renderer/font pipeline that
does not exist here, so it raises honestly instead of producing a
wrong file.

translateIndexed equivalent: segments translate sequentially through
the caller's translator callable (our registry has no batch
translators), each with a 30s timeout like AppConstants.
TRANSLATION_TIMEOUT_MS, and progress callbacks (done, total, current).
"""
import os
import re
import tempfile

FORMATS = {
    "docx": "docx", "pdf": "pdf", "txt": "text",
    "srt": "srt", "vtt": "vtt",
}
PDF_MODES = ("text_only", "layout_aware")
SEGMENT_TIMEOUT = 30.0

SRT_TS = re.compile(
    r"\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}")
VTT_TS = re.compile(
    r"(?:\d{2}:)?\d{2}:\d{2}\.\d{3}\s+-->\s+(?:\d{2}:)?\d{2}:\d{2}"
    r"\.\d{3}")
MARKUP = re.compile(r"<[^>]+>|\{\\[^}]+}")


class DocumentCancelled(Exception):
    """User cancelled mid-run (upstream ViewState.CANCELLED)."""


class DocumentTranslationError(Exception):
    pass


def format_of(path) -> str | None:
    ext = os.path.splitext(str(path))[1].lstrip(".").lower()
    return FORMATS.get(ext)


def default_output(input_path, fmt, pdf_mode="text_only") -> str:
    """Upstream naming: <name>.translated.<ext>; the extension is the
    input's own for non-PDF, .txt for PDF text-only, .pdf otherwise."""
    base = os.path.splitext(os.path.abspath(str(input_path)))[0]
    if fmt == "pdf":
        ext = "txt" if pdf_mode == "text_only" else "pdf"
    else:
        ext = {"text": "txt"}.get(fmt, fmt)
    return base + ".translated." + ext


def _translate_segment(text, translator, sl, tl):
    """translateSegment: one segment through the translator callable
    with the 30s TRANSLATION_TIMEOUT_MS."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(translator, text, sl, tl)
        try:
            return fut.result(timeout=SEGMENT_TIMEOUT)
        except concurrent.futures.TimeoutError:
            raise DocumentTranslationError(
                "Translation timed out while processing the document.")


def _progress(cb, done, total, current=""):
    if cb:
        try:
            cb(done, total, current)
        except Exception:
            pass


# -- LineContent ---------------------------------------------------------

def _parse_lines(original: str):
    """LineContent.parse: normalize CRLF/CR, remember the dominant
    ending and whether the file ended with a newline."""
    ending = "\r\n" if "\r\n" in original else "\n"
    trailing = original.endswith("\n") or original.endswith("\r")
    lines = original.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if trailing and lines and lines[-1] == "":
        lines.pop()
    return lines, ending, trailing


def _render_lines(lines, ending, trailing):
    return ending.join(lines) + (ending if trailing else "")


# -- text -----------------------------------------------------------------

def _translate_text(path, out, translator, sl, tl, on_progress,
                    is_cancelled=None):
    original = open(path, encoding="utf-8", newline="").read()
    lines, ending, trailing = _parse_lines(original)
    idxs = [i for i, l in enumerate(lines) if l.strip()]
    total = len(idxs)
    _progress(on_progress, 0, total, "")
    for n, i in enumerate(idxs):
        if is_cancelled and is_cancelled():
            raise DocumentCancelled()
        src = lines[i]
        lines[i] = _translate_segment(src, translator, sl, tl)
        _progress(on_progress, n + 1, total, src[:80])
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(_render_lines(lines, ending, trailing))


# -- subtitles -------------------------------------------------------------

def _protected(text):
    """stripAndRememberMarkup: inline markup/tts tags become tokens the
    translator cannot mangle; restore() puts them back verbatim."""
    tokens = []

    def sub(m):
        tokens.append(("__QT_MARKUP_%d__" % (len(tokens)), m.group(0)))
        return tokens[-1][0]

    stripped = MARKUP.sub(sub, text)
    return stripped, tokens


def _restore(text, tokens):
    for token, markup in tokens:
        text = text.replace(token, markup)
    return text


def _translate_subtitle(path, out, ts_re, translator, sl, tl,
                        on_progress, is_cancelled=None):
    original = open(path, encoding="utf-8", newline="").read()
    lines, ending, trailing = _parse_lines(original)
    targets = []
    in_cue = False
    for i, line in enumerate(lines):
        if ts_re.search(line):
            in_cue = True
        elif not line.strip():
            in_cue = False
        elif (in_cue and not line.startswith("NOTE")
              and not line.startswith("STYLE")
              and not line.startswith("REGION")):
            targets.append(i)
    cache = {}

    def get(i):
        if i not in cache:
            cache[i] = _protected(lines[i])
        return cache[i][0]

    def set_(i, v):
        stripped, tokens = cache[i]
        lines[i] = _restore(v, tokens)

    segments = targets
    total = len(segments)
    _progress(on_progress, 0, total, "")
    for n, i in enumerate(segments):
        if is_cancelled and is_cancelled():
            raise DocumentCancelled()
        src = get(i)
        set_(i, _translate_segment(src, translator, sl, tl))
        _progress(on_progress, n + 1, total, src[:80])
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(_render_lines(lines, ending, trailing))


# -- docx -------------------------------------------------------------------

def _docx_paragraphs(doc):
    """buildList order: body paragraphs, then tables recursively;
    headers and footers after the body."""
    paras = []

    def add_block_items(container):
        # python-docx: container.iter_inner_content() yields
        # Paragraph|Table in document order (body, cells, headers).
        for item in container.iter_inner_content():
            if item.__class__.__name__ == "Paragraph":
                paras.append(item)
            else:  # Table
                for row in item.rows:
                    for cell in row.cells:
                        add_block_items(cell)

    add_block_items(doc)
    for section in doc.sections:
        for part in (section.header, section.footer,
                     section.first_page_header,
                     section.first_page_footer,
                     section.even_page_header,
                     section.even_page_footer):
            try:
                if part.is_linked_to_previous:
                    continue
                add_block_items(part)
            except Exception:
                continue
    return paras


def _p_text(p):
    return "".join(r.text for r in p.runs)


def _replace_paragraph_text(p, translated):
    """replaceParagraphText: proportional redistribution across the
    original text runs so per-run formatting survives."""
    runs = [r for r in p.runs if r.text]
    if not runs:
        return
    orig_len = max(1, sum(len(r.text) for r in runs))
    orig_off = 0
    trans_off = 0
    for idx, run in enumerate(runs):
        orig_off += len(run.text)
        if idx == len(runs) - 1:
            end = len(translated)
        else:
            end = int(len(translated) * orig_off / orig_len)
            end = max(trans_off, min(end, len(translated)))
        run.text = translated[trans_off:end]
        trans_off = end


def _translate_docx(path, out, translator, sl, tl, on_progress,
                    is_cancelled=None):
    from docx import Document
    doc = Document(path)
    paras = [p for p in _docx_paragraphs(doc) if _p_text(p).strip()]
    segments = paras
    total = len(segments)
    _progress(on_progress, 0, total, "")
    for n, p in enumerate(segments):
        if is_cancelled and is_cancelled():
            raise DocumentCancelled()
        src = _p_text(p)
        _replace_paragraph_text(
            p, _translate_segment(src, translator, sl, tl))
        _progress(on_progress, n + 1, total, src[:80])
    doc.save(out)


# -- pdf --------------------------------------------------------------------

def _pdf_pages_text(path):
    """PDFTextStripper(sortByPosition=True) per page, trimEnd each."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        try:
            pages.append((page.extract_text() or "").rstrip())
        except Exception:
            pages.append("")
    return pages, reader


def _pdf_has_images(reader) -> bool:
    for page in reader.pages:
        try:
            res = page.get("/Resources") or {}
            xo = res.get("/XObject") or {}
            for name, obj in xo.items():
                try:
                    if obj.get_object().get("/Subtype") == "/Image":
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def _require_pdf_text(pages, has_images):
    if any(p.strip() for p in pages):
        return
    msg = ("This PDF appears to contain scanned pages without "
           "selectable text. Run OCR before translating it."
           if has_images else
           "No selectable text was found in this PDF. Run OCR "
           "before translating it.")
    raise DocumentTranslationError(msg)


def _translate_pdf_text_only(path, out, translator, sl, tl,
                             on_progress, is_cancelled=None):
    pages, reader = _pdf_pages_text(path)
    _require_pdf_text(pages, _pdf_has_images(reader))
    idxs = [i for i, p in enumerate(pages) if p.strip()]
    total = len(idxs)
    _progress(on_progress, 0, total, "")
    for n, i in enumerate(idxs):
        if is_cancelled and is_cancelled():
            raise DocumentCancelled()
        src = pages[i]
        pages[i] = _translate_segment(src, translator, sl, tl)
        _progress(on_progress, n + 1, total, src[:80])
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write("\n\x0c\n".join(pages))


# -- entry point -------------------------------------------------------------

def translate_document(input_path, output_path, sl, tl,
                       translator, fmt=None, pdf_mode="text_only",
                       on_progress=None, is_cancelled=None):
    """DocumentTranslationUseCase.invoke.

    ``translator`` is a ``fn(text, sl_code, tl_code) -> str`` callable
    (the registry's ``_t_*`` shape). ``sl``/``tl`` are language codes;
    ``tl`` must not be AUTO upstream -- enforced here too.
    """
    if tl in (None, "", "auto", "AUTO"):
        raise DocumentTranslationError(
            "Target language cannot be Auto Detect.")
    if not input_path or not os.path.isfile(input_path):
        raise DocumentTranslationError(
            "Input file does not exist: %s" % input_path)
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        raise DocumentTranslationError(
            "Choose a different output file to keep the original "
            "unchanged.")
    fmt = fmt or format_of(input_path)
    if fmt is None:
        raise DocumentTranslationError(
            "Unsupported file type: .%s"
            % os.path.splitext(str(input_path))[1].lstrip("."))
    if fmt == "pdf":
        if pdf_mode == "layout_aware":
            raise DocumentTranslationError(
                "Layout-aware PDF translation is not available in "
                "this port; choose Text-only.")
        expected = "txt"
        actual = os.path.splitext(str(output_path))[1].lstrip(
            ".").lower()
        if actual != expected:
            raise DocumentTranslationError(
                "Text-only PDF translations must be saved as TXT.")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".qtranslate-", suffix=".tmp",
                               dir=out_dir)
    os.close(fd)
    try:
        kw = dict(on_progress=on_progress, is_cancelled=is_cancelled)
        if fmt == "docx":
            _translate_docx(input_path, tmp, translator, sl, tl, **kw)
        elif fmt == "pdf":
            _translate_pdf_text_only(input_path, tmp, translator, sl,
                                     tl, **kw)
        elif fmt == "text":
            _translate_text(input_path, tmp, translator, sl, tl, **kw)
        elif fmt == "srt":
            _translate_subtitle(input_path, tmp, SRT_TS, translator,
                                sl, tl, **kw)
        elif fmt == "vtt":
            _translate_subtitle(input_path, tmp, VTT_TS, translator,
                                sl, tl, **kw)
        os.replace(tmp, output_path)
        return output_path
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
