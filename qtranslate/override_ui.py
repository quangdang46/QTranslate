"""The override-conflict dialog (D18: the user picks the winner, never
auto-resolve).

``conflicts`` is ``{base_id: [ext_id, ...]}`` (see
``ExtensionManager.override_conflicts``). Returns ``{base_id: ext_id}``
for the user's choices, or ``{}`` when the dialog is cancelled.

The host calls it when user extensions claim the same provider; nothing
runs on import, so loading this module anywhere is safe.
"""
from __future__ import annotations


def pick_override_winners(parent, conflicts):
    """Open the override-conflict dialog; return the winner selection.

    ``parent`` is the calling window (owned by the view that opens the
    dialog) or None for a standalone frame -- the dialog is modal
    either way.
    """
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGroupBox,
                                   QHBoxLayout, QLabel, QPushButton,
                                   QRadioButton, QVBoxLayout)

    class _Dialog(QDialog):
        def __init__(self, dlg_parent):
            super().__init__(dlg_parent)
            self.setWindowTitle("Extension conflicts")
            self.setModal(True)
            outer = QVBoxLayout(self)
            self._choices = {}
            outer.addWidget(QLabel(
                "These extensions override the same provider. "
                "Pick the winner for each."))
            for base, exts in sorted(conflicts.items()):
                grp = QGroupBox(base)
                h = QHBoxLayout(grp)
                var = _Choice(exts[0])
                self._choices[base] = var
                for ext in exts:
                    rb = QRadioButton(ext)
                    rb.setChecked(ext == exts[0])
                    rb.toggled.connect(
                        lambda on, _c=False, v=var, e=ext: v.set(e)
                        if on else None)
                    h.addWidget(rb)
                h.addStretch(1)
                outer.addWidget(grp)

            btns = QDialogButtonBox()
            ok = QPushButton("OK")
            cancel = QPushButton("Cancel")
            btns.addButton(ok, QDialogButtonBox.AcceptRole)
            btns.addButton(cancel, QDialogButtonBox.RejectRole)
            ok.clicked.connect(self.accept)
            cancel.clicked.connect(self.reject)
            outer.addWidget(btns)

        def result_choice(self):
            return {b: v.get() for b, v in self._choices.items()}

    dlg = _Dialog(parent)
    if dlg.exec() == QDialog.Accepted:
        return dlg.result_choice()
    return {}


class _Choice:
    """One conflict row's selection (the tk `StringVar`'s role)."""

    def __init__(self, initial):
        self._v = initial

    def set(self, value):
        self._v = value

    def get(self):
        return self._v
