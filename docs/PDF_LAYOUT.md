# PDF layout-aware translation — feasibility & design note

Status: **implemented (MVP, 2026-11-08)** in `qtranslate/pdf_layout.py`,
wired to `pdf_mode="layout_aware"` in `document.py`. Deps added to
`requirements.txt`: `pdfplumber` (positioned extraction),
`pypdfium2` (216 DPI page raster), `reportlab` (output PDF: page image
+ vector text — upstream's exact shape). Block grouping ports the
upstream heuristics (baseline gap, font-size/face delta, indentation,
bullets); fitting wraps + shrinks to the 0.68× floor and picks
contrasting ink on the sampled local background. Fonts prefer system
TTFs; when the translated text carries glyphs the document font cannot
encode (CJK etc.), `_font_for_text` swaps to the first covering face
from `_CJK_CANDIDATES` (simsun/msgothic/malgun, macOS PingFang/
Hiragino/Arial Unicode, Noto CJK/wqy/Droid on Linux), with a per-line
draw-time retry as backstop. Pages rotated by 90/180/270 degrees are
supported: pdfplumber's visual-frame line boxes are mapped back into
the page's natural frame (`_unrot_bbox`/`_segments_unrotated`, with
per-segment order correction and word-column re-joining in
`_merge_rot_lines`), the pdfium raster is PIL-rotated the same way,
and the source `/Rotate` is stamped onto the output page so it
displays identically to the input. Same-baseline char gaps wider than
a word space split merged lines (`_lines_of`), and `_column_bands`
partitions lines on low-coverage vertical gutters so two-column pages
translate per column instead of interleaving. Arbitrary angles still
refuse before any translation call; a glyph no installed face covers
still drops the line rather than corrupting output. Pinned by
`tests/regress_pdf_layout.py`.

`qtranslate/document.py` implements `pdf_mode="text_only"`
(pypdf per-page `extract_text()`, pages joined with `\n\f\n`, saved as
`.txt`). This note evaluates closing that gap.

## What upstream does (reference: `.tmp/QTranslate`)

Upstream is JVM/QTranslate; `:core` implements two `PdfTranslationMode`s:

- **TEXT_ONLY** (`PdfDocument.kt`): `PDFTextStripper(sortByPosition=true)`
  per page → translate each page string → write `.txt`. Same contract we
  already ported.
- **LAYOUT_AWARE**: a "best-effort appearance" mode, not true reflow:
  1. `PositionedTextStripper` (a `PDFTextStripper` subclass,
     `pdf/PdfExtraction.kt`) collects every text run as a `PdfTextBlock`
     with bbox `(x, top, width, height)`, `fontFamily` (SERIF/SANS_SERIF/
     MONOSPACED), `fontStyle` (bold/italic bits) and `fontSizePoints`,
     derived from `TextPosition` glyph metrics.
  2. `groupPdfBlocks` merges consecutive lines into paragraph-like blocks
     using baseline step, font-size delta, indentation and bullet rules.
  3. Each block's `sourceText` is translated; `translatedText` is stored
     back on the block.
  4. Each page is **rendered to a 216 DPI raster image**
     (`TextFreePdfRenderer`, PDFBox), then `prepareTranslatedBlocks`
     (`pdf/PdfLayout.kt`) fits the translated text into each block's pixel
     bounds: wrap via `LineBreakMeasurer`, shrink font size to a 0.68×
     floor, sample the local background colour and pick a contrasting
     text colour, draw raster fallback for non-encodable glyphs.
  5. A new PDF is written: the page image is embedded as the full-page
     background and the fitted text is overlaid as **vector text**
     (`PdfVectorFonts` embeds TTFs, `drawVectorLines` via
     `PDPageContentStream`). Original vector graphics become raster.

Contract summary: coordinates + font metadata per text block, paragraph
grouping heuristics, then rasterize-and-overlay. Output is always `.pdf`;
non-blank pages only are translated (same `translateIndexed` shape).

## Python library options

| Option | License | Maintenance | Positioned extraction | Rebuild path |
|---|---|---|---|---|
| PyMuPDF (fitz) | AGPL-3.0 / commercial dual (since 1.24) | Active, fast | `page.get_text("dict")` → blocks→lines→spans with bbox, size, font, flags; also renders pages natively | Overlay via `page.insert_text` / redaction; or full upstream-style raster+vector rebuild |
| pdfplumber / pdfminer.six | MIT / MIT | Maintained, slower | `extract_words`/chars give x0,x1,top,bottom,size,fontname — enough to rebuild upstream's block model | Extraction only; output via pypdf/ReportLab |
| pypdf (pinned 6.1.3) | BSD-3 | Active | `extract_text(extraction_mode="layout")` is text-only; visitor callbacks expose `cm`/`tm` matrices (coordinates recoverable but manual); `PageObject.redact()` can delete text | Can merge overlay PDFs (`merge_page`) and embed images; cannot draw text itself |
| ReportLab (add dep) | BSD-like | Active | n/a | Generates a text-layer PDF (TTF embed, wrap, colour) that pypdf merges as an overlay |

## Rebuild strategies

- **A. Upstream-faithful raster+overlay**: render page → fit translated
  blocks → draw text → new PDF. Needs a renderer (PyMuPDF — AGPL — or
  poppler via `pdf2image`/system binary). Simplest to reason about;
  degrades vector content to raster.
- **B. Redact-and-replace (recommended)**: keep the original page vector
  content; `redact` each source block's rect (pypdf removes covered text),
  then merge a ReportLab overlay PDF containing the fitted translated
  text. Preserves tables/graphics/fonts resolution; no rasteriser needed.
- **C. Pure reflow**: rebuild document from extracted text (like docx).
  Loses all layout — only useful as fallback for broken PDFs.

## Recommendation

**pdfplumber (extraction) + pypdf redact/merge + ReportLab (overlay)**,
i.e. strategy B. Reasons:

- All components are permissive licences (MIT/BSD) compatible with this
  MPL-2.0 project. PyMuPDF's AGPL/commercial dual licence is the
  blocker for the otherwise easiest path; revisit only if the project
  accepts AGPL or buys a licence.
- pypdf is already pinned; ReportLab and pdfplumber are pure-Python,
  installable deps (`requirements.txt` additions).
- Strategy B preserves the original page exactly — better fidelity than
  upstream's rasterisation, and it sidesteps needing a PDF renderer.

Translation-segment granularity: port `groupPdfBlocks`/`belongsToSameParagraph`
to Python (~120 lines) and translate at **block level**, matching upstream
and keeping paragraph context for the translator. Fitting: replicate
`fitText` — greedy wrap into block width, shrink font from
`fontSizePoints` to a ~0.68 floor, then fall back to letting text overflow
clipped or shrink further; pick a text colour contrasting the sampled
local background (ReportLab can sample the original page's rendered region
only via a rasteriser — instead use a heuristic: dark text on light
backgrounds; colour blocks are a known limitation).

Effort (rough): extraction+grouping port 3–4 d; ReportLab text-fitting +
overlay merge 4–5 d; TTF font bundling (cross-platform: repo has no TTF
assets; ship a small set or rely on system fonts with fallback) 1–2 d;
RTL/CJK/rotated-text handling and tests 3–5 d. **Total ≈ 2.5–4 weeks** for
an MVP supporting horizontal LTR text; rotated text and complex tables are
explicitly out of scope initially.

## Risks

- **Redaction side effects**: `redact()` removes all content overlapping
  the rect — can clip borders, images or adjacent glyphs. Mitigate with
  tight per-block rects and visual-diff tests on fixture PDFs.
- **Font coverage**: translated text may need glyphs the chosen TTF lacks
  (CJK, emoji); need font fallback chain and honest failure per block.
- **Fit overflow**: long translations in fixed bboxes degrade to tiny or
  clipped text; acceptable for "best-effort appearance" parity with
  upstream, but must not silently corrupt layout.
- **Tables/columns**: line-grouping heuristics mis-group multi-column and
  table layouts; upstream has the same weakness — parity is acceptable.
- **RTL/bidirectional text** and rotated text: upstream doesn't handle
  them well either; keep the honest-error path for pages where blocks are
  undetectable.
- **Licence creep**: avoid PyMuPDF/poppler-GPL/Ghostscript-AGPL unless
  deliberately accepted; everything above is MIT/BSD.
