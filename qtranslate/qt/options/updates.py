"""The Updates page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase, button, check, panel


class UpdatesPage(OptionsBase):
    SEL = 8

    def build(self):
        check(self, 161, 44, "Automatically check for updates")
        panel(self, 153, 63, 481, 230)
        button(self, 524, 300, 110, "Check now")
