"""The override-conflict picker (decision D18).

Two extensions may claim to replace the same built-in provider (D18 says
the USER picks the winner; discovery order must never decide). The
manager reports the groups (``override_conflicts()``), and this dialog
asks which extension should win for each group, then persists the
choice through the core's own ``write_saved_overrides``.

Nothing here invents a rule: an unset group keeps the built-in (the
manager's rollout already behaves that way), and a saved winner is what
``load_user_extensions`` applies at the next start.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                               QLabel, QVBoxLayout)


class OverridePicker(QDialog):
    """One row per conflicted provider: pick the winning extension."""

    def __init__(self, groups, saved=None, parent=None):
        """``groups`` is ``{base_id: [ext_id, ...]}``, ``saved`` the
        current ``{base_id: ext_id}`` selection."""
        super().__init__(parent)
        self.setWindowTitle("Choose the winning extensions")
        saved = saved or {}
        self._boxes = {}

        layout = QVBoxLayout(self)
        intro = QLabel("Two or more extensions replace the same provider. "
                       "Pick the one QTranslate should use. A provider you "
                       "leave on \"Built-in\" keeps the app's own.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for base in sorted(groups):
            exts = list(groups[base])
            label = QLabel("%s is replaced by %d extensions:" %
                           (base, len(exts)))
            layout.addWidget(label)
            box = QComboBox()
            # Index 0 is always the built-in: choosing nothing is a real
            # choice, so the user is never forced to accept an extension.
            box.addItem("Built-in (no override)", "")
            for ext in sorted(exts):
                box.addItem(ext, ext)
            current = saved.get(base, "")
            idx = box.findData(current)
            box.setCurrentIndex(idx if idx >= 0 else 0)
            layout.addWidget(box)
            self._boxes[base] = box

        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(420)

    def selection(self) -> dict:
        """The chosen winners: ``{base_id: ext_id}``, omitting built-ins."""
        out = {}
        for base, box in self._boxes.items():
            ext = box.currentData()
            if ext:
                out[base] = ext
        return out
