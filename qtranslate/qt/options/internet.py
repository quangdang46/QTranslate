"""The Internet page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase, combo, field, group, label


class InternetPage(OptionsBase):
    SEL = 2

    def build(self):
        group(self, 152, 35, 484, 45, "Connection")
        label(self, 158, 58, "Timeout, sec:")
        combo(self, 455, 49, 175, "10")
        group(self, 152, 91, 484, 100, "Proxy")
        combo(self, 157, 104, 470, "Use system proxy settings")
        combo(self, 162, 133, 78, "HTTP", enabled=False)
        field(self, 248, 133, 277, 20, enabled=False)
        field(self, 532, 133, 95, 20, "0", enabled=False)
        field(self, 248, 159, 186, 20, enabled=False)
        field(self, 441, 159, 186, 20, enabled=False)
