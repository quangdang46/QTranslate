"""The Options dialog (native DLG 154 and the nine page templates) on PySide6.

Every number here was MEASURED off the native captures in
``docs/review/native_screens``: 2135 (Internet), 2136 (Services), 2137
(Languages), 2138 (Appearance), 2139 (Exceptions), 2140 (Advanced), 2141
(Updates) and 2126 (Hotkeys, which is a 663x388 shot and so a different
size). The geometry is in ``qtranslate-pyside6-spec.md`` §5.

The behaviour is the port's: the same settings the tkinter front end
writes (``qtranslate.config``) are the ones this dialog shows, so the two
front ends agree on what the app is configured to do.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel

from qtranslate_style import ACCENT, DIM, FACE, TEXT, THUMB, WINDOW

from ..widgets import (Base, LINK, button, check, combo, field, group,
                       hline, icon, label, panel, put, rect, vline)

# The nine pages, in native's order. The Hotkeys page is the SECOND one
# (measured off the captures 2140/2141, not the order a reader would
# guess).
SIDEBAR = ["Basics", "Hotkeys", "Internet", "Services", "Languages",
           "Appearance", "Exceptions", "Advanced", "Updates"]

# The four columns of the Languages checklist, transcribed from the
# native capture 2137.


class OptionsBase(Base):
    """The Options shell: the page list on the left, the page's body on
    the right, and the three buttons at the bottom."""

    ORIGIN, SIZE = (1, 26), (644, 362)
    SEL = 0

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Options")
        self._shell()
        self.build()

    # ---------------------------------------------------------------- shell
    def _shell(self):
        # The page list: a bordered panel with one 13px row per page,
        # the current one filled in the accent colour. Clicking another
        # row opens that page's own window in the same spot and closes
        # this one -- each page is its own top-level window (its own
        # module, its own ORIGIN), not a panel swapped inside one shell.
        panel(self, 4, 29, 142, 324)
        # The list view's first row is empty, so the face shows there, and
        # the sunken frame casts a 1px white shadow under itself. Both
        # MEASURED off the capture.
        rect(self, 5, 30, 140, 1, FACE)
        rect(self, 3, 353, 144, 1, WINDOW)
        for i, name in enumerate(SIDEBAR):
            sel = i == self.SEL
            q = QLabel(name)
            q.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # No left padding: the text has to start one pixel inside the
            # row, the way native's does (MEASURED off the capture).
            q.setStyleSheet("QLabel{background:%s;color:%s;}"
                            % (ACCENT if sel else "transparent",
                               "#ffffff" if sel else TEXT))
            put(self, q, 7, 31 + 13 * i, 139, 13)
            if not sel:
                q.mousePressEvent = (lambda _e, n=name: self._goto(n))
        # The rule above the buttons: an etched line, a dark one and a
        # white one under it. MEASURED off the capture.
        hline(self, 358, 3, 638)
        hline(self, 359, 3, 638, WINDOW)
        button(self, 403, 363, 73, "OK").clicked.connect(self.close)
        button(self, 484, 363, 73, "Cancel").clicked.connect(self.close)
        # Apply is drawn like the others but its label is grey: the
        # native greys the label, not the whole button.
        ap = button(self, 565, 363, 73, "Apply")
        ap.setStyleSheet("color:%s" % DIM)

    def _goto(self, page_name):
        """Switch to another page: open it at this window's position,
        close this one. Each page keeps its own geometry (the Hotkeys
        page is a different size), so the pages are separate windows
        rather than one shell with a swapped-in body."""
        cls = PAGES.get(page_name)
        if cls is None:
            return
        geo = self.geometry()
        nxt = cls(self.app)
        nxt.move(geo.topLeft())
        nxt.show()
        self.app._opts = nxt
        self.close()

    def build(self):
        """The page's own body. Subclasses fill it in."""


# Filled in by qtranslate.qt.options.__init__ once every page class
# exists, so a page module does not have to import its eight siblings.
PAGES: dict = {}
