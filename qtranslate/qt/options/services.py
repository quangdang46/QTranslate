"""The Services page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase, button, check, hline, label, panel, rect
from qtranslate_style import DIM, THUMB


class ServicesPage(OptionsBase):
    SEL = 3

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        label(lst, 168, 41, "Translation", color="#005eb8")
        hline(lst, 43, 232, 608, "#b5c9e0")
        services = self.app.ordered_services()
        for i, name in enumerate(services):
            check(lst, 160, 63 + 18 * i, "", True, blue=True)
            label(lst, 193, 63 + 18 * i, self.app.service_display(name))
        label(lst, 168, 229, "Dictionary", color="#005eb8")
        hline(lst, 231, 232, 608, "#b5c9e0")
        for i, name in enumerate(self.app.dictionary_names()):
            check(lst, 160, 249 + 18 * i, "", True, blue=True)
            label(lst, 193, 249 + 18 * i, name)
        rect(lst, 626, 48, 2, 157, THUMB)
        button(self, 157, 309, 24, "▲", enabled=False)
        button(self, 187, 309, 24, "▼", enabled=False)
        button(self, 219, 309, 117, "Add dictionary…")
        b = button(self, 342, 309, 118, "Remove dictionary")
        b.setStyleSheet("color:%s" % DIM)
