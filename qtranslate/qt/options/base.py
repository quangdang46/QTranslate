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

# The nine native pages in native's order, then the port's OWN page:
# Extensions is not a native page (native has no extension system), so
# it trails the captured order instead of sitting inside it.
SIDEBAR = ["Basics", "Hotkeys", "Internet", "Services", "Languages",
           "Appearance", "Exceptions", "Advanced", "Updates", "Extensions"]


class OptionsBase(Base):
    """The Options shell: the page list on the left, the page's body on
    the right, and the three buttons at the bottom.

    The shell is a SINGLE window: clicking a page in the list rebuilds
    the body in place rather than opening a new window. Each page module
    still owns its own ``build`` (its own numbers, its own file); the
    shell calls it with ``self`` after pointing the instance's ORIGIN
    and SIZE at the page's own.

    The shell's own chrome -- the sidebar panel, its rows, the rule and
    the three buttons -- is described by ``CHROME``, because the
    Hotkeys page's capture is a different size and its chrome sits at
    different coordinates. Everything is rebuilt on each swap, so a page
    with a different chrome gets it.
    """

    ORIGIN, SIZE = (1, 26), (644, 362)
    SEL = 0

    # The shell's chrome, in the page's own coordinates.
    #   panel      -- the bordered area the page list sits in
    #   row        -- x, y, width of one page-list row (the pitch is 13)
    #   face_row   -- the list view's empty first row (face colour)
    #   shadow_row -- the sunken frame's 1px white shadow
    #   rule       -- the etched line above the buttons: y, x0, x1
    #   buttons    -- each button's x, y, width, and whether it casts the
    #                 1px light shadow under itself
    CHROME = {
        "panel": (4, 29, 142, 324),
        "row": (7, 31, 139),
        "face_row": (5, 30, 140, 1),
        "shadow_row": (3, 353, 144, 1),
        "rule": (358, 3, 638),
        "buttons": {
            "OK": (403, 363, 73, True),
            "Cancel": (484, 363, 73, True),
            "Apply": (565, 363, 73, True),
        },
    }

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._page_name = SIDEBAR[self.SEL]
        self._rows = []
        self.setWindowTitle("Options")
        self._show_page(self._page_name, first=True)

    # ---------------------------------------------------------------- shell
    def _build_chrome(self):
        """The sidebar, the rule and the three buttons, in this page's
        own coordinates."""
        ch = self.CHROME
        panel(self, *ch["panel"])
        face_row = ch.get("face_row")
        if face_row:
            rect(self, *face_row, FACE)
        shadow_row = ch.get("shadow_row")
        if shadow_row:
            rect(self, *shadow_row, WINDOW)
        self._rows = []
        rx, ry, rw = ch["row"]
        for i, name in enumerate(SIDEBAR):
            q = QLabel(name)
            q.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # No left padding: the text has to start one pixel inside the
            # row, the way native's does (MEASURED off the capture).
            put(self, q, rx, ry + 13 * i, rw, 13)
            q.mousePressEvent = (lambda _e, n=name: self._goto(n))
            self._rows.append(q)
        ry, x0, x1 = ch["rule"]
        hline(self, ry, x0, x1)
        hline(self, ry + 1, x0, x1 - 1, WINDOW)
        for text, (bx, by, bw, shadow) in ch["buttons"].items():
            b = button(self, bx, by, bw, text, shadow=shadow)
            if text in ("OK", "Cancel"):
                b.clicked.connect(self.close)
            else:
                # Apply is drawn like the others but its label is grey:
                # the native greys the label, not the whole button.
                b.setStyleSheet("color:%s" % DIM)

    def _paint_rows(self):
        """Repaint the sidebar highlight for the current page."""
        for q in self._rows:
            sel = q.text() == self._page_name
            q.setStyleSheet("QLabel{background:%s;color:%s;}"
                            % (ACCENT if sel else "transparent",
                               "#ffffff" if sel else TEXT))

    def _clear(self):
        """Take down every widget the previous page built.

        The widgets are hidden and unparented, NOT deleted. A Qt widget
        that is deleted while a paint event for it is still queued is an
        access violation in the painter, and the Options dialog can
        have one queued for a page that is being swapped out. Hiding
        and unparenting removes them from the paint queue without
        destroying the object, and the next event loop pass frees them.
        """
        for w in list(self.findChildren(object)):
            if w is self:
                continue
            try:
                w.hide()
                w.setParent(None)
            except Exception:
                pass

    def _show_page(self, page_name, first=False):
        """Rebuild a page's body in place, without a new window."""
        cls = PAGES.get(page_name)
        if cls is None:
            return
        if not first and page_name == self._page_name:
            return
        self._page_name = page_name
        self._clear()
        # The pages' numbers are written against each page class's own
        # ORIGIN/SIZE. Run the SAME build code with the shell as self,
        # after pointing the instance's ORIGIN/SIZE at the page's own.
        # The only page that differs is Hotkeys (ORIGIN (1,24) against
        # the shell's (1,26), SIZE 650 wide against 644): its rows are
        # shifted two screenshot pixels, and the window widens by 6.
        saved_origin, saved_size = self.ORIGIN, self.SIZE
        saved_chrome = self.CHROME
        try:
            self.ORIGIN, self.SIZE = cls.ORIGIN, cls.SIZE
            self.CHROME = cls.CHROME
            # The Languages page reads its column layout off the class
            # (BOX_X, COL_STEP, ...); same trick covers those.
            for attr in ("BOX_X", "BOX_Y", "COL_STEP", "ROW_STEP",
                         "TEXT_DX", "TEXT_DY"):
                if hasattr(cls, attr) and not hasattr(self, attr):
                    setattr(self, attr, getattr(cls, attr))
            if (self.width(), self.height()) != cls.SIZE:
                self.setFixedSize(*cls.SIZE)
            self._build_chrome()
            cls.build(self)
        finally:
            self.ORIGIN, self.SIZE = saved_origin, saved_size
            self.CHROME = saved_chrome
        self._paint_rows()

    def _goto(self, page_name):
        """Switch to another page: rebuild the body in place."""
        self._show_page(page_name)

    def build(self):
        """The page's own body. Subclasses fill it in."""


# Filled in by qtranslate.qt.options.__init__ once every page class
# exists, so a page module does not have to import its eight siblings.
PAGES: dict = {}
