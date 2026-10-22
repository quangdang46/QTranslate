"""The Hotkeys page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import SIDEBAR
from ..widgets import Base, button, check, label, panel, put, rect
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from qtranslate_style import ACCENT, TEXT, THUMB


class HotkeysPage(Base):
    """The Hotkeys page. Its capture is 663x388, a different size from
    the other pages, so it does not use the shared shell."""

    ORIGIN, SIZE = (1, 24), (661, 363)
    SEL = 1

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Options")
        panel(self, 10, 28, 142, 323)
        for i, name in enumerate(SIDEBAR):
            sel = i == self.SEL
            q = QLabel(name)
            q.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # No left padding: the text has to start one pixel inside the
            # row, the way native's does (MEASURED off the capture).
            q.setStyleSheet("QLabel{background:%s;color:%s;}"
                            % (ACCENT if sel else "transparent",
                               "#ffffff" if sel else TEXT))
            put(self, q, 11, 28 + 13 * i, 140, 13)
        check(self, 159, 41, "Enable hotkeys", True)
        t = panel(self, 159, 60, 465, 251)
        label(t, 166, 71, "Action")
        label(t, 483, 71, "Hotkey")
        rect(t, 477, 62, 1, 247, "#e5e5e5")
        rows = [("Show main window", ""),
                ("Show popup window", "Ctrl + Q"),
                ("Show dictionary window", ""),
                ("Show history window", ""),
                ("Show keyboard window", ""),
                ("Listen to selected text", ""),
                ("Copy translation to clipboard", ""),
                ("Replace selected text", "Alt + W"),
                ("Switch mouse mode", ""),
                ("Translate clipboard content", ""),
                ("Translate clipboard in main window", ""),
                ("Translate clipboard in popup window", ""),
                ("Dictionary from clipboard", "")]
        for i, (a, k) in enumerate(rows):
            label(t, 166, 92 + 17 * i, a)
            if k:
                label(t, 483, 92 + 17 * i, k)
        rect(t, 629, 75, 2, 164, THUMB)
        button(self, 408, 361, 75, "OK")
        button(self, 489, 361, 75, "Cancel")
        button(self, 570, 361, 75, "Apply", enabled=False)
