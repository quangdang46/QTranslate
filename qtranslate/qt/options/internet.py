"""The Internet page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase, combo, field, group, label


class InternetPage(OptionsBase):
    SEL = 2

    def build(self):
        group(self, 152, 35, 484, 45, "Connection")
        label(self, 158, 59, "Timeout, sec:")
        combo(self, 455, 50, 175, "10")
        group(self, 152, 91, 484, 101, "Proxy")
        combo(self, 157, 105, 470, "Use system proxy settings")
        combo(self, 162, 134, 78, "HTTP", enabled=False)
        field(self, 248, 134, 277, 20, enabled=False)
        field(self, 532, 134, 95, 20, "0", enabled=False)
        field(self, 248, 160, 186, 20, enabled=False)
        field(self, 441, 160, 186, 20, enabled=False)
