"""The Appearance page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

The four buttons of the "Icons:" row are ARTWORK, not font glyphs: the
native draws a small pictogram in each. The cells are recovered from the
capture (``assets/ui_icons/ap_icon1..4.png``) -- the button, its gradient
and the shadow the OS theme draws under it -- and a transparent button
sits over each one so the row is still clickable.
"""

from .base import OptionsBase, button, check, combo, field, group, icon, label, rect


class AppearancePage(OptionsBase):
    SEL = 5

    def build(self):
        group(self, 152, 35, 484, 58, "General")
        check(self, 159, 54, "Enable window style")
        label(self, 158, 77, "Theme:")
        combo(self, 398, 67, 232, "--- Default ---", h=19)
        group(self, 152, 100, 484, 229, "Popup window")
        for cy, t, on in [(121, "Enable auto size", 1),
                          (143, "Enable auto position", 1),
                          (166, "Activate when opened", 0),
                          (189, "Pin when dragging", 1)]:
            check(self, 159, cy, t, bool(on))
        label(self, 158, 212, "Auto-hide delay:")
        combo(self, 398, 204, 114, "5", h=19)
        label(self, 524, 212, "seconds")
        label(self, 158, 235, "Transparency (0 - 90):")
        field(self, 398, 226, 232, 22, "15")
        label(self, 158, 258, "Frame thickness:")
        combo(self, 398, 251, 232, "2", h=19)
        label(self, 158, 284, "Icons:")
        for i in range(4):
            x = 398 + 24 * i
            b = button(self, x, 274, 21, "", h=21)
            b.setObjectName("flat")
            icon(self, x, 274, "ui_icons", "ap_icon%d" % (i + 1))
        label(self, 159, 312, "Background color:")
        label(self, 321, 312, "Text color:")
        label(self, 483, 312, "Frame color:")
        rect(self, 379, 304, 86, 18, "#000000")
        rect(self, 549, 304, 78, 18, "#5d6c7a")
