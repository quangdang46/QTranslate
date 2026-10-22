"""The Services page of the Options dialog.

The geometry was measured off the native capture 2136: the list panel,
the two section headings with their rules, the nine translation services
and the dictionary services, each with its icon, and the four buttons
under the list.
"""

from .base import OptionsBase, button, check, hline, label, panel, rect
from ..widgets import HEADING, HEADING_LINE, icon
from qtranslate_style import DIM, FACE, THUMB, WINDOW

# The icon each dictionary service draws. The names are the port's own
# display names (qtranslate.config.DICT_DISPLAY); the files are the ones
# recovered from the installer payload.
DICT_ICONS = {
    "Google Search": "google-search",
    "WordReference": "wordreference",
    "Babylon Dictionary": "babylon",
    "Wikipedia": "wikipedia",
    "Multitran": "multitran",
    "ImTranslator": "imtranslator",
    "Reverso": "reverso",
    "Urban Dictionary": "urban",
    "ABBYY Lingvo Live": "lingvo",
    "youdao": "youdao",
    "Oxford Learner Dictionary": "oxford",
}

# The icon each translation service draws.
SERVICE_ICONS = {
    "google": "google", "microsoft": "microsoft", "promt": "promt",
    "babylon": "babylon", "yandex": "yandex", "youdao": "youdao",
    "baidu": "baidu", "naver": "naver", "deepl": "deepl",
}

# The service key -> the icon file, for the services the port knows.
SERVICE_ICON_BY_NAME = {
    "Google": "google", "Microsoft": "microsoft", "Promt": "promt",
    "Babylon": "babylon", "Yandex": "yandex", "youdao": "youdao",
    "Baidu": "baidu", "Papago": "naver", "DeepL": "deepl",
}


class ServicesPage(OptionsBase):
    SEL = 3

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        # The list view is 464px wide and the vertical scrollbar's track
        # takes the 16px next to it; the track is the face colour, not
        # the list's white. MEASURED off the capture.
        rect(lst, 619, 32, 16, 270, FACE)
        # The list's own first row is empty, so the face shows there.
        rect(lst, 156, 32, 463, 1, FACE)
        # The section heading and the rule that runs beside it, both at
        # the heading's own mid height. The heading is Tahoma 9pt.
        label(lst, 167, 42, "Translation", color=HEADING, size=12)
        hline(lst, 42, 230, 607, HEADING_LINE)
        for i, name in enumerate(self.app.ordered_services()):
            icon(lst, 176, 54 + 18 * i, "service_icons",
                 SERVICE_ICON_BY_NAME.get(self.app.service_display(name), "google"))
            # The list's checkbox sits one pixel above the name's
            # middle: MEASURED off the capture (the indicator's box is
            # at rows 29..41 while the name's ink is at 32..42).
            check(lst, 160, 61 + 18 * i, "", True, blue=True)
            label(lst, 194, 62 + 18 * i, self.app.service_display(name))
        label(lst, 168, 228, "Dictionary", color=HEADING, size=12)
        hline(lst, 228, 226, 607, HEADING_LINE)
        for i, name in enumerate(self.app.dictionary_names()):
            icon(lst, 176, 240 + 18 * i, "dict_icons",
                 DICT_ICONS.get(name, "wikipedia"))
            check(lst, 160, 247 + 18 * i, "", True, blue=True)
            label(lst, 194, 248 + 18 * i, name)
        # The scrollbar's thumb: two pixels wide, 153 tall.
        rect(lst, 626, 51, 2, 153, THUMB)
        # The four buttons, measured off the capture: the two arrows are
        # 25px wide, the two wide ones 118.
        button(self, 156, 308, 25, "▲", enabled=False, shadow=True)
        button(self, 186, 308, 25, "▼", enabled=False, shadow=True)
        button(self, 219, 308, 118, "Add dictionary...", shadow=True)
        b = button(self, 342, 308, 118, "Remove dictionary", shadow=True)
        b.setStyleSheet("color:%s" % DIM)
        # The sunken frame's 1px white shadow, under the list.
        rect(self, 154, 303, 483, 1, WINDOW)
