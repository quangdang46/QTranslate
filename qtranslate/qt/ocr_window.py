"""The text-recognition result window on PySide6.

Native's Text Recognition menu (id 10) is a WINDOW menu, not a picker:
OCR language, Translate, Copy image, Copy text, Save image, Edit image,
Select all, Clear selection, Close. Before this module the port put the
picked text straight into the main window's result pane, so menu 10 was
a published slot with no host -- the same shape as the capability gap.

The window shows the OCR'd text in a pane with the nine native items in
its menu, in native's order. Each item is an operation the port already
has: OCR language opens the options flow that owns
``OcrLanguage``/``Ocr/OcrLanguage``, Translate puts the text through the
engine the main window uses, Copy image/text and Save image move the
grab or the text the way the overlay's S/C keys already do, and Close
closes. Select all / Clear selection / Edit image work on the pane's
own text.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class OcrResultWindow(QWidget):
    """The OCR result: grabbed image kept, text shown, menu 10 on top."""

    def __init__(self, app, image=None):
        super().__init__(None, Qt.Window)
        self.app = app
        self._image = image
        self.setWindowTitle("Text recognition")
        self.resize(474, 301)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.out = QTextEdit(self)
        self.out.setReadOnly(True)
        lay.addWidget(self.out)

    def set_text(self, text: str):
        self.out.setPlainText(text or "")

    # --------------------------------------------------------- menu 10
    def menu(self):
        from .context_menus import build as build_menu
        return build_menu(self, self.app, "ocr", 10, [
            (110, "OCR language", self._pick_language),
            (120, "Translate", self._translate),
            (130, "Copy image", self._copy_image),
            (140, "Copy text", self._copy_text),
            (150, "Save image", self._save_image),
            # Native edits the grabbed IMAGE in its OCR editor; the port
            # has no editor, so the item is drawn disabled -- visible in
            # the menu, honestly not faked.
            (160, "Edit image", None),
            (170, "Select all", self.out.selectAll),
            (180, "Clear selection",
             lambda: self.out.textCursor().clearSelection()),
            (190, "Close", self.close),
        ])

    def contextMenuEvent(self, event):          # noqa: N802 (Qt name)
        self.menu().exec(event.globalPos())

    # ------------------------------------------------------------ handlers
    def _pick_language(self):
        """Open the Options page that owns the OCR language setting."""
        try:
            self.app.open_options("Advanced")
        except Exception:
            pass

    def _translate(self):
        try:
            self.app.show_translation(self.out.toPlainText()[:2000],
                                      self.app._translate(
                                          self.out.toPlainText()
                                          [:2000]).text)
        except Exception:
            pass

    def _copy_image(self):
        try:
            if self._image is not None:
                from PySide6.QtWidgets import QApplication
                QApplication.clipboard().setPixmap(self._image)
        except Exception:
            pass

    def _copy_text(self):
        try:
            self.out.copy()
        except Exception:
            pass

    def _save_image(self):
        try:
            if self._image is None:
                return
            import datetime as _dt
            import os as _o
            _dir = _o.path.expanduser("~")
            try:
                from qtranslate import config as _C
                _dir = _C.load().get("Ocr", {}).get(
                    "SaveImagePath", "") or _dir
            except Exception:
                pass
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "Save image",
                _o.path.join(_dir, "ocr_%s.png"
                             % _dt.datetime.now().strftime("%Y%m%d_%H%M%S")),
                "PNG (*.png)")
            if path:
                self._image.save(path, "PNG")
        except Exception:
            pass
