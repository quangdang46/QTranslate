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

    # The "API keys" group carries four provider keys (OCR, Google
    # Vision, Google Translate, DeepL) -- 50px more than the native
    # capture's three-row group, so the page and its chrome grow by
    # the same delta (HotkeysPage sets the precedent for a page with
    # its own SIZE/CHROME).
    SIZE = (644, 412)
    CHROME = dict(OptionsBase.CHROME)
    CHROME["panel"] = (4, 29, 142, 374)
    CHROME["shadow_row"] = (3, 403, 144, 1)
    CHROME["rule"] = (408, 3, 638)
    CHROME["buttons"] = {k: (x, y + 50, w, sh)
                         for k, (x, y, w, sh)
                         in OptionsBase.CHROME["buttons"].items()}

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
        gen = cfg_section("General")
        group(self, 152, 295, 484, 103, "API keys")
        # .tmp plugin secrets -> Options.json General.*: the Google
        # plugin's visionApiKey/translateApiKey and the deepl-services
        # apiKey, alongside the native OCR key.
        for cy, t, sect, key in [
                (311, "OCR API key:", "Advanced", "OcrApiKey"),
                (332, "Google Vision API key:", "General",
                 "GoogleVisionApiKey"),
                (353, "Google Translate API key:", "General",
                 "GoogleTranslateApiKey"),
                (374, "DeepL API key:", "General", "DeeplApiKey")]:
            label(self, 158, cy, t)
            sec = adv if sect == "Advanced" else gen
            f = field(self, 387, cy - 9, 243, 20,
                      str(sec.get(key, "")))
            f.editingFinished.connect(
                lambda w=f, s=sect, k=key:
                cfg_set(s, k, w.text()))
