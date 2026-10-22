"""The Hotkeys page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

This page is its own shell: the native's capture (2126) is a 663x388
shot, a different size from the other pages', so the page does not use
the shared one. Its list is a LISTVIEW with two scrollbars, and the
tracks are the face colour over the white list -- the port draws the
same, as flat rectangles, because the measure is the pixels.
"""

from .base import SIDEBAR
from ..widgets import Base, button, check, hline, label, panel, put, rect
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from qtranslate_style import ACCENT, DIM, FACE, TEXT, THUMB, WINDOW


class HotkeysPage(Base):
    """The Hotkeys page. Its capture is 663x388, a different size from
    the other pages, so it does not use the shared shell."""

    ORIGIN, SIZE = (1, 24), (650, 362)
    SEL = 1

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Options")
        panel(self, 10, 27, 142, 323)
        for i, name in enumerate(SIDEBAR):
            sel = i == self.SEL
            q = QLabel(name)
            q.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # No left padding: the text has to start one pixel inside the
            # row, the way native's does (MEASURED off the capture).
            q.setStyleSheet("QLabel{background:%s;color:%s;}"
                            % (ACCENT if sel else "transparent",
                               "#ffffff" if sel else TEXT))
            put(self, q, 13, 29 + 13 * i, 140, 13)
        check(self, 159, 41, "Enable hotkeys", True)
        # The list: 481 wide, 267 tall, with the vertical scrollbar's
        # track down the right and the horizontal one's along the
        # bottom. MEASURED off capture 2126.
        t = panel(self, 159, 60, 481, 267)
        rect(t, 623, 61, 16, 252, FACE)         # the vertical track
        rect(t, 161, 312, 462, 14, FACE)        # the horizontal track
        rect(t, 630, 77, 2, 164, THUMB)         # the vertical thumb
        rect(t, 177, 317, 412, 2, THUMB)        # the horizontal thumb
        label(t, 166, 71, "Action")
        label(t, 484, 71, "Hotkey")
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
                label(t, 484, 92 + 17 * i, k)
        # The rule above the buttons: an etched line, a dark one and a
        # white one under it. MEASURED off the capture.
        hline(self, 356, 9, 645)
        hline(self, 357, 9, 644, WINDOW)
        button(self, 409, 361, 73, "OK")
        button(self, 490, 361, 73, "Cancel")
        # Apply is drawn like the others but its label is grey: the
        # native greys the label, not the whole button.
        ap = button(self, 571, 361, 73, "Apply")
        ap.setStyleSheet("color:%s" % DIM)
