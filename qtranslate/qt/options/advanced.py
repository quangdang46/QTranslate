"""The Advanced page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

WIRED: the combos and checks read/write the ``Advanced`` section of
Options.json; the OCR API key field writes ``Advanced.OcrApiKey``.
"""

from .base import OptionsBase, cfg_section, cfg_set, check, combo, \
    field, group, label


class AdvancedPage(OptionsBase):
    SEL = 7

    def build(self):
        adv = cfg_section("Advanced")
        group(self, 152, 35, 484, 180, "Advanced")
        for cy, t, key, values in [
                (55, "Default browser:", "DefaultBrowserId",
                 ["Internet Explorer", "Default browser", "Firefox",
                  "Chrome", "Edge"]),
                (79, "Copy action:", "CopyAction",
                 ["Ctrl + C", "Ctrl + Insert", "Shift + Insert"]),
                (103, "Keyboard layout indicator:",
                 "KeyboardLayoutIndicator", ["None", "Show"]),
                (128, "Preferred domain:", "PreferredDomain",
                 ["com", "org", "net", "ru"])]:
            label(self, 158, cy, t)
            cur = str(adv.get(key, values[0]))
            cb = combo(self, 455, cy - 10, 175,
                       cur if cur in values else values[0],
                       values=values)
            cb.currentTextChanged.connect(
                lambda v, k=key: cfg_set("Advanced", k, v))
        check(self, 159, 153, "Enable GUI translation",
              bool(adv.get("EnableGuiTranslation", False))
              ).toggled.connect(
            lambda v: cfg_set("Advanced", "EnableGuiTranslation",
                              bool(v)))
        check(self, 159, 176,
              "Enable listening to the same text at a slower speed",
              bool(adv.get("EnableSlowerListening", False))
              ).toggled.connect(
            lambda v: cfg_set("Advanced", "EnableSlowerListening",
                              bool(v)))
        check(self, 159, 199, "Remove line breaks",
              bool(adv.get("RemoveLineBreaks", False))
              ).toggled.connect(
            lambda v: cfg_set("Advanced", "RemoveLineBreaks", bool(v)))
        group(self, 152, 224, 484, 61, "Mouse mode")
        check(self, 159, 244,
              "Enable mouse mode only when Ctrl is pressed",
              bool(adv.get("EnableMouseModeOnCtrl", False))
              ).toggled.connect(
            lambda v: cfg_set("Advanced", "EnableMouseModeOnCtrl",
                              bool(v)))
        check(self, 159, 269,
              "Click on system tray icon switches mouse mode",
              bool(adv.get("SwitchMouseModeOnTrayClick", True))
              ).toggled.connect(
            lambda v: cfg_set("Advanced", "SwitchMouseModeOnTrayClick",
                              bool(v)))
        group(self, 152, 295, 484, 55, "API keys")
        label(self, 158, 313, "OCR API key:")
        f_key = field(self, 387, 304, 243, 22,
                      str(adv.get("OcrApiKey", "")))
        f_key.editingFinished.connect(
            lambda: cfg_set("Advanced", "OcrApiKey", f_key.text()))
        from .base import LINK
        label(self, 158, 338, "Register here for free OCR API key",
              color=LINK, underline=True)
