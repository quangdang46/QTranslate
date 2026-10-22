"""The Appearance page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase, button, check, combo, field, group, label, rect


class AppearancePage(OptionsBase):
    SEL = 5

    def build(self):
        group(self, 152, 35, 484, 56, "General")
        check(self, 160, 55, "Enable window style")
        label(self, 158, 77, "Theme:")
        combo(self, 397, 68, 233, "--- Default ---")
        group(self, 152, 98, 484, 226, "Popup window")
        for cy, t, on in [(122, "Enable auto size", 1),
                          (144, "Enable auto position", 1),
                          (167, "Activate when opened", 0),
                          (190, "Pin when dragging", 1)]:
            check(self, 160, cy, t, bool(on))
        label(self, 158, 213, "Auto-hide delay:")
        combo(self, 397, 204, 115, "5")
        label(self, 524, 213, "seconds")
        label(self, 158, 237, "Transparency (0 - 90):")
        field(self, 397, 227, 233, 20, "15")
        label(self, 158, 261, "Frame thickness:")
        combo(self, 397, 252, 233, "2")
        label(self, 158, 286, "Icons:")
        for i, g in enumerate(["▤", "∩", "⧉", "tā"]):
            b = button(self, 398 + 23 * i, 275, 22, g, 22)
            b.setStyleSheet("QPushButton{background:#c4c4c4;padding:0;}")
        label(self, 158, 313, "Background color:")
        label(self, 321, 313, "Text color:")
        label(self, 483, 313, "Frame color:")
        rect(self, 378, 305, 87, 17, "#000000")
        rect(self, 549, 305, 78, 17, "#5d6c7a")
