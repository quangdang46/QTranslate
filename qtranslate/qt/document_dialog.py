"""Document translation dialog -- port of ui/swing/document/
DocumentTranslationDialog.kt.

Input file / output file pickers, a PDF-mode row (visible only for
.pdf), a progress bar with percent, and Translate -> Open once the
run completes. Language pair and translator come from the main
window's current selection, like upstream's translationContextChanged.
"""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog,
                               QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QVBoxLayout,
                               QWidget)

from qtranslate import document as DOC


class DocumentTranslationDialog(QDialog):
    """Modal-free dialog owned by the main app (upstream keeps one
    instance and re-opens it)."""

    def __init__(self, app):
        super().__init__(app.win if hasattr(app, "win") else None)
        self.app = app
        self.setWindowTitle("Translate document")
        self.setModal(False)
        self._input = None
        self._output = None
        self._fmt = None
        self._running = False
        self._cancel = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.in_field = QLineEdit()
        self.in_field.setPlaceholderText("Choose input file…")
        self.in_field.setReadOnly(True)
        self.out_field = QLineEdit()
        self.out_field.setPlaceholderText("Choose output file…")
        self.out_field.setReadOnly(True)

        def row(title, field, btn_text, pick):
            box = QWidget()
            h = QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(QLabel(title))
            h.addWidget(field, 1)
            b = QPushButton(btn_text)
            b.clicked.connect(pick)
            h.addWidget(b)
            return box

        lay.addWidget(row("Input:", self.in_field, "Browse…",
                          self._choose_input))
        self.out_row = row("Output:", self.out_field, "Browse…",
                           self._choose_output)
        self.out_btn = self.out_row.findChild(QPushButton)
        self.out_btn.setEnabled(False)
        lay.addWidget(self.out_row)

        # PDF mode row -- only meaningful for .pdf inputs, like the
        # upstream pdfOptionsPanel.
        self.pdf_row = QWidget()
        ph = QHBoxLayout(self.pdf_row)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.addWidget(QLabel("PDF mode:"))
        self.pdf_mode = QComboBox()
        # Layout-aware needs a renderer/font pipeline this port does
        # not have; the item stays visible but disabled, matching the
        # honest-failure contract in document.translate_document.
        self.pdf_mode.addItem("Layout-aware (not available)")
        self.pdf_mode.model().item(0).setEnabled(False)
        self.pdf_mode.addItem("Text-only")
        self.pdf_mode.setCurrentIndex(1)
        ph.addWidget(self.pdf_mode, 1)
        self.pdf_row.hide()
        lay.addWidget(self.pdf_row)

        prog = QWidget()
        pv = QHBoxLayout(prog)
        pv.setContentsMargins(0, 0, 0, 0)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.pct = QLabel("0%")
        pv.addWidget(self.progress, 1)
        pv.addWidget(self.pct)
        lay.addWidget(prog)
        self.status = QLabel("Choose a document to translate.")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        self.primary = QPushButton("Translate")
        self.primary.setDefault(True)
        self.primary.setEnabled(False)
        self.primary.clicked.connect(self._primary_clicked)
        btns.addWidget(self.close_btn)
        btns.addWidget(self.primary)
        lay.addLayout(btns)

    # -- picking ---------------------------------------------------------
    def _choose_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose document",
            "", "Documents (*.docx *.pdf *.txt *.srt *.vtt);;"
                 "All files (*)")
        if path:
            self.open_with(path)

    def _choose_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Choose output file", self.out_field.text() or "",
            "All files (*)")
        if path:
            self.out_field.setText(path)
            self._output = path

    def open_with(self, path):
        """openWith(file): prefill input, suggest output, show."""
        self._input = path
        self._fmt = DOC.format_of(path)
        self.in_field.setText(path)
        self.pdf_row.setVisible(self._fmt == "pdf")
        self._suggest_output()
        self.show()
        self.raise_()
        self.activateWindow()

    def open(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _suggest_output(self):
        if not self._input:
            return
        mode = ("text_only" if self.pdf_mode.currentIndex() == 1
                else "layout_aware")
        self._output = DOC.default_output(self._input, self._fmt, mode)
        self.out_field.setText(self._output)
        self.out_btn.setEnabled(True)
        self.primary.setEnabled(True)
        self.primary.setText("Translate")
        self.status.setText("Ready.")

    def closeEvent(self, event):
        # Upstream windowClosing -> cancelOrClose: closing mid-run
        # cancels the translation instead of letting it finish.
        if self._running:
            self._cancel = True
        super().closeEvent(event)

    def _primary_clicked(self):
        if self._running:
            self._cancel = True
            return
        if getattr(self, "_done_output", None):
            self._open_output()
            return
        self._start()

    def _open_output(self):
        path = getattr(self, "_done_output", None)
        if not path:
            return
        try:
            import subprocess
            subprocess.Popen(["open", path])
        except Exception:
            pass

    # -- run ---------------------------------------------------------------
    def _start(self):
        if not self._input or not self._output:
            return
        from qtranslate import engine
        service = getattr(self.app, "service", "google") or "google"
        try:
            enabled = self.app.ordered_services()
            if enabled and service not in enabled:
                service = enabled[0]
        except Exception:
            pass
        sl = getattr(self.app, "source", "auto") or "auto"
        tl = getattr(self.app, "target", "vi") or "vi"
        translator = self._engine_translator(service)
        mode = ("text_only" if self.pdf_mode.currentIndex() == 1
                else "layout_aware")
        self._running = True
        self._cancel = False
        self._done_output = None
        self.primary.setText("Cancel")
        self.primary.setEnabled(True)
        self.close_btn.setEnabled(False)
        import threading
        threading.Thread(target=self._worker,
                         args=(translator, sl, tl, mode),
                         daemon=True).start()

    def _engine_translator(self, service):
        """fn(text, sl, tl) -> str through engine.translate so the
        provider fallback chain applies per segment."""
        from qtranslate import engine

        def call(text, sl, tl):
            res = engine.translate(service, text, tl, sl)
            return getattr(res, "text", "") or ""
        return call

    def _progress(self, done, total, current):
        pct = 100 if not total else int(done * 100 / total)
        self.progress.setValue(pct)
        self.pct.setText("%d%%" % pct)
        self.status.setText(
            "Translating %d/%d%s" % (
                done, total,
                (" — " + current) if current else ""))

    def _worker(self, translator, sl, tl, mode):
        try:
            out = DOC.translate_document(
                self._input, self._output, sl, tl, translator,
                pdf_mode=mode,
                on_progress=lambda d, t, c: self.app._on_ui(
                    lambda: self._progress(d, t, c)),
                is_cancelled=lambda: self._cancel)
            self.app._on_ui(lambda: self._finished(out, None))
        except DOC.DocumentCancelled:
            self.app._on_ui(lambda: self._finished(None, "cancelled"))
        except Exception as exc:
            self.app._on_ui(lambda err=exc: self._finished(None, err))

    def _finished(self, out, err):
        self._running = False
        self.close_btn.setEnabled(True)
        if err == "cancelled":
            self.primary.setText("Translate")
            self.status.setText("Cancelled.")
            return
        if err is not None:
            self.primary.setText("Translate")
            self.status.setText("Failed: %s" % err)
            # The dialog's status line dies with the dialog; the
            # notification bus is what still reaches the user after it
            # closes (the .tmp NotificationBus role).
            try:
                self.app.notify("error", "Document translation failed",
                                str(err), code="document.failed",
                                source="document")
            except Exception:
                pass
            return
        self._done_output = out
        self.progress.setValue(100)
        self.pct.setText("100%")
        self.primary.setText("Open")
        self.status.setText("Completed: %s" % os.path.basename(out))
        try:
            self.app.notify("info", "Document translation",
                            "Completed: %s" % os.path.basename(out),
                            code="document.completed",
                            source="document")
        except Exception:
            pass

    def translation_context_changed(self):
        """Mirror upstream: a finished/failed run resets to READY when
        the language pair changes."""
        if not self._running and getattr(self, "_done_output", None):
            self._done_output = None
            self.primary.setText("Translate")
            self.status.setText("Ready.")
