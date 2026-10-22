"""The Languages page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase

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
    "Russian Serbian Sinhala Slovak Slovenian Spanish Swedish Tajik Tamil "
    "Tatar Telugu Thai Turkish Ukrainian Urdu Uzbek Vietnamese",
]

from .base import button, check, panel, rect
from qtranslate_style import THUMB


class LanguagesPage(OptionsBase):
    SEL = 4

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        for ci, col in enumerate(LANGUAGES):
            x = round(158 + ci * 126.5)
            for i, n in enumerate(col.split(" ")):
                check(lst, x, 39 + 14 * i, n.replace("_", " "), True, blue=True)
        rect(lst, 173, 293, 238, 2, THUMB)
        button(self, 155, 308, 481, "Check / Uncheck all")
