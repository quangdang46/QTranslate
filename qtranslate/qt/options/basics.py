"""The Basics page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase, check, combo, group, label


class BasicsPage(OptionsBase):
    """The first page. The native capture of it was never taken, so this
    page is built from the settings the port supports, not from a
    measured picture."""

    SEL = 0

    def build(self):
        # The strings are the pack's own (dialog 10 of Locales/English/
        # lang.json), even though the layout has no native capture to
        # measure positions from -- see docs/roadmap/BLOCKERS.md B4.
        group(self, 152, 35, 484, 130, "General")
        check(self, 160, 55, "Start with Windows", True)
        label(self, 158, 77, "Interface language:")
        combo(self, 455, 68, 175, "English")
        label(self, 158, 99, "Font name:")
        combo(self, 455, 89, 175, "Segoe UI")
        label(self, 158, 121, "Text size:")
        combo(self, 455, 111, 175, "9")
        group(self, 152, 148, 484, 48, "Auto-detect languages")
        label(self, 158, 170, "First language:")
        combo(self, 455, 160, 175, "Vietnamese")
        label(self, 158, 183, "Second language:")
        combo(self, 455, 173, 175, "English")
        group(self, 152, 208, 484, 70, "History")
        check(self, 160, 228, "Enable history", True)
        check(self, 160, 250, "Clear history on exit", True)
        check(self, 160, 263, "Expand items")
