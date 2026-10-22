"""The Advanced page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase, LINK, check, combo, field, group, label


class AdvancedPage(OptionsBase):
    SEL = 7

    def build(self):
        group(self, 152, 35, 484, 180, "Advanced")
        for cy, t, v in [(55, "Default browser:", "Internet Explorer"),
                         (79, "Copy action:", "Ctrl + C"),
                         (103, "Keyboard layout indicator:", "None"),
                         (128, "Preferred domain:", "com")]:
            label(self, 158, cy, t)
            combo(self, 455, cy - 10, 175, v)
        check(self, 159, 153, "Enable GUI translation")
        check(self, 159, 176, "Enable listening to the same text at a slower speed", True)
        check(self, 159, 199, "Remove line breaks")
        group(self, 152, 224, 484, 61, "Mouse mode")
        check(self, 159, 244, "Enable mouse mode only when Ctrl is pressed")
        check(self, 159, 269, "Click on system tray icon switches mouse mode", True)
        group(self, 152, 295, 484, 55, "API keys")
        label(self, 158, 313, "OCR API key:")
        field(self, 387, 304, 243, 22)
        label(self, 158, 338, "Register here for free OCR API key",
              color=LINK, underline=True)
