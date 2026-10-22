"""The Hotkeys page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

Its capture (2126) is a 663x388 shot, a different size from the other
pages'. When this page is shown the shell resizes to it, and the rows
are shifted two screenshot pixels so they land where the capture says
they do. Its list is a LISTVIEW with two scrollbars, and the tracks
are the face colour over the white list -- the port draws the same, as
flat rectangles, because the measure is the pixels.
"""

from .base import OptionsBase
from ..widgets import check, label, panel, rect

from qtranslate_style import FACE, THUMB


class HotkeysPage(OptionsBase):
    """The Hotkeys page."""

    ORIGIN, SIZE = (1, 24), (650, 362)
    SEL = 1

    # The chrome of THIS page, measured off capture 2126: the window is
    # 6px wider, its sidebar sits 6px further right and 2px higher, its
    # list view has no empty first row, and its three buttons are 6px
    # further right and 2px higher (and cast no shadow).
    CHROME = {
        "panel": (10, 27, 142, 323),
        "row": (13, 29, 140),
        "face_row": None,
        "shadow_row": None,
        "rule": (356, 9, 645),
        "buttons": {
            "OK": (409, 361, 73, False),
            "Cancel": (490, 361, 73, False),
            "Apply": (571, 361, 73, False),
        },
    }

    def build(self):
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
