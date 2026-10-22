"""The Languages page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

The native's language list is a LISTVIEW with checkboxes, not a column of
checkbox widgets: the boxes are 12x13, sit ON the panel's left border and
are drawn by the OS theme. The exact sprite is recovered from the capture
(``assets/ui_icons/check_blue.png``) and the words are separate labels, so
the box and the word land on the native's pixels.
"""

from .base import OptionsBase
from .base import button, icon, label, panel, rect
from qtranslate_style import THUMB

# The native's list, in the native's columns. "Swahili" is between
# "Spanish" and "Swedish" -- the list is alphabetical and the capture
# shows all eighteen of the last column.
LANGUAGES = [
    "Afrikaans Albanian Arabic Armenian Azerbaijani Basque Belarusian "
    "Bengali Bulgarian Catalan Chinese_(Simplified) "
    "Chinese_(Traditional) Croatian Czech Danish Dutch English Esperanto",
    "Estonian Filipino Finnish French Galician Georgian German Greek "
    "Haitian_Creole Hebrew Hindi Hmong Hungarian Icelandic Indonesian "
    "Irish Italian Japanese",
    "Kannada Kazakh Khmer Korean Lao Latin Latvian Lithuanian Macedonian "
    "Malay Maltese Marathi Mongolian Norwegian Persian Polish Portuguese "
    "Romanian",
    "Russian Serbian Sinhala Slovak Slovenian Spanish Swahili Swedish "
    "Tajik Tamil Tatar Telugu Thai Turkish Ukrainian Urdu Uzbek Vietnamese",
]


class LanguagesPage(OptionsBase):
    SEL = 4

    # MEASURED off capture 2137: the first box's top-left is at screen
    # (156, 33), the columns are 127px apart, the rows 14px, and each
    # word starts 18px after its box.
    BOX_X, BOX_Y = 156, 33
    COL_STEP, ROW_STEP = 127, 14
    TEXT_DX, TEXT_DY = 18, 6

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        for ci, col in enumerate(LANGUAGES):
            x = self.BOX_X + self.COL_STEP * ci
            for i, n in enumerate(col.split(" ")):
                icon(lst, x, self.BOX_Y + self.ROW_STEP * i,
                     "ui_icons", "check_blue")
                label(lst, x + self.TEXT_DX,
                      self.BOX_Y + self.TEXT_DY + self.ROW_STEP * i,
                      n.replace("_", " "))
        # The list's horizontal scrollbar: the thumb is 267px long.
        rect(lst, 173, 293, 267, 2, THUMB)
        button(self, 155, 308, 481, "Check / Uncheck all")
