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
        """Choose the OCR language (``Ocr.OcrLanguage``).

        The setting is a Google-language INDEX -- the same table the
        main window's combos use -- so the menu lists every supported
        language by display name and writes the index back. Native's
        menu 110 opens the Options page; a direct picker is the same
        setting with one less hop.
        """
        menu = self._language_menu()
        menu.exec(self.mapToGlobal(self.rect().center()))

    def _language_menu(self):
        """The built OCR-language picker (exclusive radio group).

        Split from ``_pick_language`` so tests can inspect the menu
        without entering its modal ``exec``.
        """
        from PySide6.QtWidgets import QMenu
        from qtranslate import config as _C
        try:
            from qtranslate.services.google_translate import SUPPORTED_LANGS
            table = list(SUPPORTED_LANGS)
        except Exception:
            table = []
        from qtranslate.languages import display as _disp
        try:
            cfg = _C.load() or {}
            cur = int((cfg.get("Ocr", {}) or {}).get("OcrLanguage", 17))
        except Exception:
            cur = 17
        from PySide6.QtGui import QActionGroup
        menu = QMenu(self)
        grp = QActionGroup(menu)
        grp.setExclusive(True)
        for i, code in enumerate(table):
            if not isinstance(code, str) or code in ("auto", "-1"):
                continue
            act = menu.addAction(_disp(code))
            act.setCheckable(True)
            act.setChecked(i == cur)
            act.triggered.connect(
                lambda _c=False, idx=i: self._set_ocr_language(idx))
            grp.addAction(act)
        return menu

    def _set_ocr_language(self, index):
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            ocr = cfg.setdefault("Ocr", {})
            ocr["OcrLanguage"] = int(index)
            _C.save(cfg)
        except Exception:
            pass

    def _translate(self):
        try:
            self.app.show_translation(
                self.out.toPlainText()[:2000],
                self.app._translate(
                    self.out.toPlainText()[:2000]).text,
                origin="ocr")
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
