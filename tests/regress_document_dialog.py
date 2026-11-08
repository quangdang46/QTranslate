"""Regression: the document translation dialog's own state machine
(``qtranslate/qt/document_dialog.py``).

``tests/regress_document.py`` pins ``qtranslate/document.py`` (the
worker); this suite pins the DIALOG around it:

  1. input/output pickers prefill through ``open_with`` and the PDF
     mode row appears only for .pdf inputs;
  2. the suggested output name follows the mode
     (``<name>.translated.txt`` text-only, ``.pdf`` layout-aware);
  3. a finished run flips the primary button to "Open", an error or a
     cancel restores "Translate" and reports through ``app.notify``;
  4. ``translation_context_changed`` resets a completed run to READY;
  5. ``_open_output`` goes through QDesktopServices (cross-platform --
     the old macOS-only ``open`` Popen did nothing on Windows);
  6. ``_start`` refuses to run without input+output, and the worker
     path delivers ``_finished`` back on the GUI thread.

Offscreen; ``DOC.translate_document`` is stubbed so no provider or
file I/O beyond temp fixtures happens.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import config as _CFG                    # noqa: E402
_CFG.DEFAULT_PATH = os.path.join(tempfile.mkdtemp(prefix="qt-docdlg-"),
                                 "Options.json")

try:
    from PySide6.QtWidgets import QApplication
    qapp = QApplication.instance() or QApplication([])
    from qtranslate.qt.document_dialog import DocumentTranslationDialog
    from qtranslate import document as DOC
except Exception as exc:                                # noqa: BLE001
    print("SKIP regress_document_dialog: Qt/document imports failed "
          "(%s)" % exc)
    raise SystemExit(0)


class _FakeApp:
    """The app surface the dialog reads: service/source/target, the
    ordered-services list, the GUI-thread hop and the notify bus."""

    def __init__(self):
        self.win = None
        self.service = "google"
        self.source = "en"
        self.target = "vi"
        self.notices = []

    def ordered_services(self):
        return ["google"]

    def _on_ui(self, fn):
        fn()                      # tests run on the GUI thread anyway

    def notify(self, *a, **kw):
        self.notices.append((a, kw))


app = _FakeApp()
dlg = DocumentTranslationDialog(app)

ck("window title", dlg.windowTitle() == "Translate document",
   dlg.windowTitle())
ck("pdf mode row starts hidden", not dlg.pdf_row.isVisible())
ck("primary disabled before input",
   not dlg.primary.isEnabled() and dlg.primary.text() == "Translate")
ck("out browse disabled before input", not dlg.out_btn.isEnabled())

# -- open_with / suggestions ---------------------------------------------
tmp = tempfile.mkdtemp(prefix="qt-docdlg-files-")
pdf_in = os.path.join(tmp, "report.pdf")
txt_in = os.path.join(tmp, "notes.txt")
open(pdf_in, "wb").write(b"%PDF-1.4 fake")
open(txt_in, "w", encoding="utf-8").write("hello")

dlg.open_with(txt_in)
ck("txt input hides the pdf row", not dlg.pdf_row.isVisible())
ck("txt output suggestion", dlg._output.endswith(".translated.txt"),
   dlg._output)
ck("primary enabled after input", dlg.primary.isEnabled())

dlg.open_with(pdf_in)
ck("pdf input shows the pdf row", dlg.pdf_row.isVisible())
# default combo index is Text-only -> .txt output
dlg.pdf_mode.setCurrentIndex(1)
dlg._suggest_output()
ck("pdf text-only suggests .txt", dlg._output.endswith(".translated.txt"),
   dlg._output)
dlg.pdf_mode.setCurrentIndex(0)
dlg._suggest_output()
ck("pdf layout-aware suggests .pdf", dlg._output.endswith(".translated.pdf"),
   dlg._output)

# -- _finished state machine ----------------------------------------------
dlg._finished(None, None)
ck("None/None finish is an honest failure, not a crash",
   dlg.status.text().startswith("Failed:"), dlg.status.text())

dlg._finished("/tmp/out.pdf", None)
ck("success flips primary to Open", dlg.primary.text() == "Open")
ck("success records output", dlg._done_output == "/tmp/out.pdf")
ck("success status", "Completed" in dlg.status.text(), dlg.status.text())
ck("success notifies", any("Completed" in str(a) for a, _ in app.notices))

dlg.translation_context_changed()
ck("context change resets to Ready",
   dlg.primary.text() == "Translate" and dlg._done_output is None
   and dlg.status.text() == "Ready.", dlg.status.text())

app.notices.clear()
dlg._finished(None, RuntimeError("boom"))
ck("error restores Translate", dlg.primary.text() == "Translate")
ck("error status", dlg.status.text().startswith("Failed:"),
   dlg.status.text())
ck("error notifies error",
   any(kw.get("code") == "document.failed" for _, kw in app.notices),
   str(app.notices))

dlg._finished(None, "cancelled")
ck("cancel status", dlg.status.text() == "Cancelled.",
   dlg.status.text())

# -- _open_output -----------------------------------------------------------
opened = []
try:
    from PySide6.QtGui import QDesktopServices
    _orig_open = QDesktopServices.openUrl
    QDesktopServices.openUrl = staticmethod(lambda url: opened.append(
        url.toLocalFile()) or True)
except Exception:
    _orig_open = None
try:
    dlg._done_output = pdf_in
    dlg._open_output()
finally:
    if _orig_open is not None:
        QDesktopServices.openUrl = staticmethod(_orig_open)
ck("open goes through QDesktopServices",
   [os.path.normpath(p) for p in opened] == [os.path.normpath(pdf_in)],
   str(opened))

# -- _start guards ----------------------------------------------------------
dlg2 = DocumentTranslationDialog(_FakeApp())
dlg2._start()
ck("_start without input does not run", not dlg2._running)

# -- worker path (stubbed translate_document) -------------------------------
calls = []
_orig_tdoc = DOC.translate_document
try:
    DOC.translate_document = lambda *a, **kw: (
        calls.append((a, kw)) or a[1])
    dlg.open_with(txt_in)
    dlg._output = os.path.join(tmp, "out.txt")
    dlg.out_field.setText(dlg._output)
    dlg._output = dlg._output
    dlg._start()
    import time
    for _ in range(100):
        if not dlg._running:
            break
        time.sleep(0.02)
        qapp.processEvents()
    qapp.processEvents()
finally:
    DOC.translate_document = _orig_tdoc
ck("worker ran translate_document", len(calls) == 1, str(calls))
if calls:
    ck("worker passed output path", calls[0][0][1] == dlg._output,
       str(calls[0][0][1]))
    ck("finished flipped to Open", dlg.primary.text() == "Open",
       dlg.primary.text())

if fail:
    print("FAIL %d" % len(fail))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_document_dialog: all checks ok (%d assertions)" % n[0])
