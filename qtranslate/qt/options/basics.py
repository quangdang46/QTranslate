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

    # The "Translation" + "Window" groups (auto-copy mode, upstream
    # TranslationPanel; close-button behavior, upstream LayoutPanel)
    # plus the "Toolbars"/"Service selector" groups (.tmp LayoutPanel's
    # toolbarVisibility checkboxes and serviceSelectorAppearance combo)
    # need 246px more than the native capture left at the bottom; the
    # page and its chrome grow by the same delta (AdvancedPage sets
    # the precedent).
    SIZE = (644, 608)
    CHROME = dict(OptionsBase.CHROME)
    CHROME["panel"] = (4, 29, 142, 570)
    CHROME["shadow_row"] = (3, 599, 144, 1)
    CHROME["rule"] = (604, 3, 638)
    CHROME["buttons"] = {k: (x, y + 246, w, sh)
                         for k, (x, y, w, sh)
                         in OptionsBase.CHROME["buttons"].items()}

    def build(self):
        general = cfg_section("General")
        # AutoDetection goes through the merged read: a partial
        # Options.json must still show the native defaults (57/17/57),
        # not fall back to index 0 -- the -1 sentinel, not a language.
        try:
            from qtranslate import config as _config
            autodetect = _config.auto_detection()
        except Exception:
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
            lambda v: (cfg_set("General", "FontName", v),
                       notify_app(self.app)))

        label(self, 158, 121, "Text size:")
        sizes = [str(s) for s in (8, 9, 10, 11, 12, 14)]
        cur_size = str(general.get("TextSize", 9))
        c_size = combo(self, 455, 111, 175,
                       cur_size if cur_size in sizes else "9",
                       values=sizes)
        c_size.currentTextChanged.connect(
            lambda v: (cfg_set("General", "TextSize",
                               int(v) if v.isdigit() else 9),
                       notify_app(self.app)))

        group(self, 152, 148, 484, 48, "Auto-detect languages")
        # The two auto-detect slots are INDICES into the shared
        # SupportedLanguages table exactly as native numbers it:
        # index 0 is the -1 sentinel, so "vi" is 57 and "en" is 17
        # (config.py's AutoDetection defaults, RE_COVERAGE_CHECKLIST
        # row M21). Indexing a string-only filtered copy shifted every
        # stored value by one -- the old code wrote 56 for "vi".
        from qtranslate.services.google_translate import SUPPORTED_LANGS
        from qtranslate.languages import LANG_DISPLAY

        raw = list(SUPPORTED_LANGS)
        # (raw index, display name) for every selectable language; the
        # display names are unique, so the name->index map is exact and
        # a lookup miss can no longer write a silent 0.
        pairs = [(i, LANG_DISPLAY.get(c, c))
                 for i, c in enumerate(raw) if isinstance(c, str)]
        names = [n for _i, n in pairs]
        idx_of = {n: i for i, n in pairs}
        name_of = {i: n for i, n in pairs}

        def _name_of(idx):
            try:
                return name_of.get(int(idx), "")
            except Exception:
                return ""

        for cy, key, idx_key in ((170, "First language", "LanguageFirst"),
                                 (183, "Second language",
                                  "LanguageSecond")):
            label(self, 158, cy, key + ":")
            cur = _name_of(autodetect.get(idx_key, 0)) or names[0]
            cb = combo(self, 455, cy - 10, 175, cur, values=names)
            cb.currentTextChanged.connect(
                lambda v, k=idx_key: cfg_set(
                    "AutoDetection", k, idx_of.get(v, 0)))

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

        # OCR settings that had readers but no writer: SaveImagePath is
        # honoured by the OCR pick window and window (empty = temp dir);
        # OcrLanguage is the Google-language index (17 = en) the OCR
        # window's own picker also edits.
        from .base import field
        ocr = cfg_section("Ocr")
        group(self, 152, 292, 484, 62, "OCR")
        label(self, 158, 314, "Save images to:")
        f_dir = field(self, 387, 305, 238, 20,
                      str(ocr.get("SaveImagePath", "")))
        f_dir.setPlaceholderText("(temporary folder)")
        f_dir.editingFinished.connect(
            lambda: cfg_set("Ocr", "SaveImagePath", f_dir.text().strip()))
        label(self, 158, 340, "OCR language:")
        from qtranslate.services.google_translate import SUPPORTED_LANGS \
            as _GL
        _ocr_langs = [(i, c) for i, c in enumerate(_GL)
                      if isinstance(c, str) and c != "auto"]
        _names = [c for _, c in _ocr_langs]
        try:
            _cur_i = int(ocr.get("OcrLanguage", 17))
        except Exception:
            _cur_i = 17
        _cur = _GL[_cur_i] if 0 <= _cur_i < len(_GL) else "en"
        c_lang = combo(self, 387, 331, 238,
                       _cur if _cur in _names else "en", values=_names)
        c_lang.currentTextChanged.connect(
            lambda v: cfg_set(
                "Ocr", "OcrLanguage",
                next((i for i, c in _ocr_langs if c == v), 17)))

        # .tmp TranslationPanel autoCopyTranslation: OFF /
        # QUICK_TRANSLATE_ONLY / ALL. Stored under General so the
        # merged read picks it up like every other port-owned key.
        group(self, 152, 366, 484, 40, "Translation")
        label(self, 158, 388, "Auto-copy translation:")
        _modes = [("off", "Off"),
                  ("quick", "Quick translations only"),
                  ("all", "All translations")]
        c_copy = combo(self, 387, 379, 238,
                       dict(_modes).get(
                           str(general.get("AutoCopyTranslation",
                                           "off")).lower(), "Off"),
                       values=[v for _k, v in _modes])
        c_copy.currentTextChanged.connect(
            lambda v: cfg_set(
                "General", "AutoCopyTranslation",
                next((k for k, vv in _modes if vv == v), "off")))

        # .tmp LayoutPanel closeButtonBehavior: ASK (default upstream)
        # / MINIMIZE_TO_TRAY / EXIT. Stored as General.CloseAction;
        # absent, closeEvent derives it from the native
        # MinimizeToTrayOnClose flag so existing configs keep working.
        group(self, 152, 410, 484, 32, "Window")
        label(self, 158, 430, "Close button:")
        _close_modes = [("ask", "Ask to minimize or exit"),
                        ("minimize", "Minimize to tray"),
                        ("exit", "Exit")]
        try:
            _cur_close = str(general.get("CloseAction", "")
                             or "").lower()
        except Exception:
            _cur_close = ""
        if _cur_close not in ("ask", "minimize", "exit"):
            _cur_close = ("minimize" if general.get(
                "MinimizeToTrayOnClose", False) else "exit")
        c_close = combo(self, 387, 421, 238,
                        dict(_close_modes).get(_cur_close,
                                               "Exit"),
                        values=[v for _k, v in _close_modes])
        c_close.currentTextChanged.connect(
            lambda v: cfg_set(
                "General", "CloseAction",
                next((k for k, vv in _close_modes if vv == v),
                     "exit")))

        # .tmp LayoutPanel "Toolbars & panels" + "Service selector":
        # toolbarVisibility.isHistoryBarVisible/isLanguageBarVisible/
        # isStatusBarVisible/isServicesPanelVisible and
        # serviceSelectorAppearance. The pane toggles keep their native
        # Show*Pane names; the history/language/status bars and the
        # selector's icon/text mix are General.* keys with .tmp's own
        # semantics (the dictionary panel has no port counterpart -- a
        # recorded divergence).
        group(self, 152, 452, 484, 92, "Toolbars")
        for cy, key, dflt, label_text in (
                (472, "ShowHistoryBar", True, "Show history bar"),
                (492, "ShowLanguageBar", True, "Show language bar"),
                (512, "ShowStatusBar", True, "Show status bar"),
                (532, "ShowServicesPane", True, "Show services pane")):
            check(self, 160, cy, label_text,
                  bool(general.get(key, dflt))).toggled.connect(
                lambda v, k=key: (cfg_set("General", k, bool(v)),
                                  notify_app(self.app)))

        group(self, 152, 554, 484, 44, "Service selector")
        label(self, 158, 576, "Button appearance:")
        _app_modes = [("ICONS_ONLY", "Icons only"),
                      ("ICONS_AND_TEXT", "Icons and text"),
                      ("TEXT_ONLY", "Text only")]
        _cur_app = str(general.get("ServiceSelectorAppearance",
                                   "ICONS_AND_TEXT") or "")
        if _cur_app not in ("ICONS_ONLY", "ICONS_AND_TEXT", "TEXT_ONLY"):
            _cur_app = "ICONS_AND_TEXT"
        c_app = combo(self, 387, 566, 238,
                      dict(_app_modes).get(_cur_app, "Icons and text"),
                      values=[v for _k, v in _app_modes])
        c_app.currentTextChanged.connect(
            lambda v: (cfg_set(
                "General", "ServiceSelectorAppearance",
                next((k for k, vv in _app_modes if vv == v),
                     "ICONS_AND_TEXT")),
                notify_app(self.app)))
