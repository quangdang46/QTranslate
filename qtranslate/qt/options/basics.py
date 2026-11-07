"""The Basics page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

Every control is WIRED: each one reads its value from Options.json on
build and writes it back on change (the same write-through rule the
Extensions page uses), so a setting changed here is a setting the app
actually keeps.
"""

from qtranslate.startup import startup_entry

from .base import (OptionsBase, cfg_load, cfg_section, cfg_set, check,
                   combo, group, label, notify_app)


def _locale_names():
    """The locale packs the app ships (assets/locales/<name>)."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    d = os.path.join(here, "assets", "locales")
    try:
        return sorted(n for n in os.listdir(d)
                      if os.path.isdir(os.path.join(d, n)))
    except Exception:
        return ["English"]


class BasicsPage(OptionsBase):
    """The first page. The native capture of it was never taken, so this
    page is built from the settings the port supports, not from a
    measured picture."""

    SEL = 0

    def build(self):
        general = cfg_section("General")
        appearance = cfg_section("Appearance")
        autodetect = cfg_section("AutoDetection")
        group(self, 152, 35, 484, 130, "General")
        # Start-with-Windows: native's HKCU Run entry (row G). The
        # checkbox reads the real state and writes it back on toggle,
        # the way the tkinter view did before its removal.
        present, set_present = startup_entry()
        box = check(self, 160, 55, "Start with Windows", present)
        box.toggled.connect(set_present)

        label(self, 158, 77, "Interface language:")
        locales = _locale_names()
        cur_locale = general.get("LocaleFoderName", "English")
        c_loc = combo(self, 455, 68, 175,
                      cur_locale if cur_locale in locales else locales[0],
                      values=locales)
        c_loc.currentTextChanged.connect(
            lambda v: (cfg_set("General", "LocaleFoderName", v),
                       notify_app(self.app)))

        label(self, 158, 99, "Font name:")
        fonts = ["", "Segoe UI", "Tahoma", "Arial", "Times New Roman"]
        # FontName lives in General (the writer below targets General)
        # -- reading Appearance showed a phantom default and could
        # overwrite the real key when the dialog opened.
        cur_font = general.get("FontName", "") or fonts[1]
        c_font = combo(self, 455, 89, 175,
                       cur_font if cur_font in fonts else fonts[1],
                       values=fonts)
        c_font.currentTextChanged.connect(
            lambda v: cfg_set("General", "FontName", v))

        label(self, 158, 121, "Text size:")
        sizes = [str(s) for s in (8, 9, 10, 11, 12, 14)]
        cur_size = str(general.get("TextSize", 9))
        c_size = combo(self, 455, 111, 175,
                       cur_size if cur_size in sizes else "9",
                       values=sizes)
        c_size.currentTextChanged.connect(
            lambda v: cfg_set("General", "TextSize",
                              int(v) if v.isdigit() else 9))

        group(self, 152, 148, 484, 48, "Auto-detect languages")
        # The two auto-detect slots are INDICES into the shared
        # SupportedLanguages table (native's AutoDetection section).
        from qtranslate.services.google_translate import SUPPORTED_LANGS
        table = [c for c in SUPPORTED_LANGS if isinstance(c, str)]
        from qtranslate.languages import LANG_DISPLAY

        def _name_of(idx):
            try:
                return LANG_DISPLAY.get(table[int(idx)], "")
            except Exception:
                return ""

        names = [n for n in (LANG_DISPLAY.get(c, c) for c in table) if n]
        for cy, key, idx_key in ((170, "First language", "LanguageFirst"),
                                 (183, "Second language",
                                  "LanguageSecond")):
            label(self, 158, cy, key + ":")
            cur = _name_of(autodetect.get(idx_key, 0)) or names[0]
            cb = combo(self, 455, cy - 10, 175, cur, values=names)
            cb.currentTextChanged.connect(
                lambda v, k=idx_key: cfg_set(
                    "AutoDetection", k,
                    table.index(_code_of(v))
                    if _code_of(v) in table else 0))

        group(self, 152, 208, 484, 70, "History")
        check(self, 160, 228, "Enable history",
              bool(general.get("EnableHistory", True))
              ).toggled.connect(
            lambda v: cfg_set("General", "EnableHistory", bool(v)))
        check(self, 160, 250, "Clear history on exit",
              bool(general.get("ClearHistoryOnExit", True))
              ).toggled.connect(
            lambda v: cfg_set("General", "ClearHistoryOnExit", bool(v)))
        check(self, 160, 263, "Expand items",
              bool(general.get("ExpandHistoryItems", False))
              ).toggled.connect(
            lambda v: cfg_set("General", "ExpandHistoryItems", bool(v)))


def _code_of(name):
    from qtranslate.languages import LANG_CODES
    return LANG_CODES.get(name, "")
