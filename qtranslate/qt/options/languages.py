"""The Languages page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

The native's language list is a LISTVIEW with checkboxes, not a column of
checkbox widgets: the boxes are 12x13, sit ON the panel's left border and
are drawn by the OS theme. The exact sprite is recovered from the capture
(``assets/ui_icons/check_blue.png``) and the words are separate labels, so
the box and the word land on the native's pixels.

WIRED: clicking a language toggles it in ``DisabledLanguages`` (the
unchecked state dims the word, since the capture only ships the checked
sprite); "Check / Uncheck all" flips the whole list. ``build`` runs on
the shell instance, so the toggles are module functions reading state
off the shell (``_lang_disabled`` / ``_lang_labels``).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QWidget

from .base import OptionsBase, cfg_load, cfg_set, button, combo, icon, \
    label, panel, put, rect
from qtranslate_style import DIM, TEXT, THUMB

# The native's list, in the native's columns. "Swahili" is between
# "Spanish" and "Swedish" -- the list is alphabetical and the capture
# shows all eighteen of the last column.
LANGUAGES = [
    "Afrikaans Albanian Arabic Armenian Azerbaijani Basque Belarusian "
    "Bengali Bulgarian Catalan Chinese_(Simplified) "
    "Chinese_(Traditional) Croatian Czech Danish Dutch English Esperanto",
    "Estonian Filipino Finnish French Galician Georgian German Greek "
    "Haitian_Creole Hebrew Hindi Hmong Hungarian Icelandic Indonesian "
    "Irish Italian Japanese",
    "Kannada Kazakh Khmer Korean Lao Latin Latvian Lithuanian Macedonian "
    "Malay Maltese Marathi Mongolian Norwegian Persian Polish Portuguese "
    "Romanian",
    "Russian Serbian Sinhala Slovak Slovenian Spanish Swahili Swedish "
    "Tajik Tamil Tatar Telugu Thai Turkish Ukrainian Urdu Uzbek Vietnamese",
]


def _display_name(raw):
    return raw.replace("_", " ")


def _all_names():
    return [_display_name(n) for col in LANGUAGES for n in col.split(" ")]


def _persist(shell):
    from qtranslate import config as _C
    try:
        cfg = _C.load() or {}
        cfg["DisabledLanguages"] = sorted(shell._lang_disabled)
        _C.save(cfg)
    except Exception:
        pass


def _repaint(shell):
    for name, lab in (getattr(shell, "_lang_labels", {}) or {}).items():
        try:
            lab.setStyleSheet(
                "QLabel{background:transparent;color:%s;}"
                % (TEXT if name not in shell._lang_disabled else DIM))
        except Exception:
            pass


def _toggle(shell, name):
    if name in shell._lang_disabled:
        shell._lang_disabled.discard(name)
    else:
        shell._lang_disabled.add(name)
    _persist(shell)
    _repaint(shell)


def _toggle_all(shell):
    if len(shell._lang_disabled) >= len(_all_names()) // 2:
        shell._lang_disabled = set()
    else:
        shell._lang_disabled = set(_all_names())
    _persist(shell)
    _repaint(shell)


def _pinned_codes():
    try:
        cfg = cfg_load() or {}
        v = (cfg.get("General", {}) or {}).get("PinnedLanguages")
        if v is None:
            v = cfg.get("PinnedLanguages")
        if isinstance(v, str):
            v = [s for s in v.replace("|", ",").split(",") if s.strip()]
        return sorted({str(c).strip() for c in (v or []) if str(c).strip()})
    except Exception:
        return []


def _pinned_name(code):
    try:
        from qtranslate.languages import LANG_DISPLAY
        return LANG_DISPLAY.get(code, code)
    except Exception:
        return code


def _pinned_summary():
    codes = _pinned_codes()
    if not codes:
        return "all languages"
    names = [_pinned_name(c) for c in codes]
    text = ", ".join(names)
    return text if len(text) <= 60 else text[:57] + "..."


def _edit_pinned(shell):
    """The pin editor (.tmp LanguagesPanel's pinned-languages checklist):
    every language with a checkbox; the checked set is what the pickers
    narrow to. Empty = all languages."""
    from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                                   QGridLayout, QScrollArea, QVBoxLayout,
                                   QWidget)
    pinned = set(_pinned_codes())
    # Codes come from the app's own table so the dialog can never pin a
    # language the pickers do not know.
    app = getattr(shell, "app", None)
    try:
        codes = app._lang_codes() if app is not None else []
    except Exception:
        codes = []
    codes = [c for c in codes if c != "auto"] or [
        "en", "vi"]

    dlg = QDialog(shell)
    dlg.setWindowTitle("Pinned languages")
    lay = QVBoxLayout(dlg)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    body = QWidget()
    grid = QGridLayout(body)
    boxes = {}
    for i, code in enumerate(sorted(codes)):
        cb = QCheckBox("%s  (%s)" % (_pinned_name(code), code))
        cb.setChecked(code in pinned)
        grid.addWidget(cb, i // 3, i % 3)
        boxes[code] = cb
    scroll.setWidget(body)
    lay.addWidget(scroll)
    btns = QDialogButtonBox(QDialogButtonBox.Ok
                            | QDialogButtonBox.Cancel)
    lay.addWidget(btns)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    if dlg.exec() != QDialog.Accepted:
        return
    chosen = sorted(c for c, cb in boxes.items() if cb.isChecked())
    try:
        from qtranslate import config as _C
        cfg = _C.load() or {}
        cfg.setdefault("General", {})["PinnedLanguages"] = chosen
        _C.save(cfg)
    except Exception:
        return
    try:
        shell._pinned_lab.setText(
            "Pinned languages: " + _pinned_summary())
    except Exception:
        pass
    # _load_session refreshes the main window's combos in place (.tmp
    # re-renders withPinnedLanguages on every settings emission).
    try:
        if app is not None and hasattr(app, "_load_session"):
            app._load_session()
    except Exception:
        pass


def _rules():
    """General.TranslationRules as a list of {"source","target"} dicts
    in language codes -- the shape _translate._translation_rules reads."""
    try:
        cfg = cfg_load() or {}
        v = (cfg.get("General", {}) or {}).get("TranslationRules")
        if not isinstance(v, list):
            return []
        out = []
        for r in v:
            if isinstance(r, dict) and r.get("source") and r.get(
                    "target"):
                out.append({"source": str(r["source"]),
                            "target": str(r["target"])})
        return out
    except Exception:
        return []


def _read_source():
    """General.SelectionReadSource -> "source"|"translation"."""
    try:
        from qtranslate import config as _C
        v = str((_C.general_setting("SelectionReadSource", "")
                 or "")).strip().lower()
        return "source" if v == "source" else "translation"
    except Exception:
        return "translation"


def _set_read_source(combo_w):
    try:
        from qtranslate import config as _C
        cfg = _C.load() or {}
        cfg.setdefault("General", {})["SelectionReadSource"] = (
            "source" if combo_w.currentIndex() == 1 else "translation")
        _C.save(cfg)
    except Exception:
        pass


def _set_dict_auto_source(shell, mode):
    """.tmp dictAutoLookupCheck + "Look up:" radios ->
    General.DictionaryAutoSource (OFF/TRANSLATED/SOURCE)."""
    try:
        from qtranslate import config as _C
        cfg = _C.load() or {}
        cfg.setdefault("General", {})["DictionaryAutoSource"] = mode
        _C.save(cfg)
    except Exception:
        pass


def _set_dict_auto_popup(shell, on):
    """.tmp dictAutoPopupCheck -> General.DictionaryAutoPopup."""
    try:
        from qtranslate import config as _C
        cfg = _C.load() or {}
        cfg.setdefault("General", {})["DictionaryAutoPopup"] = bool(on)
        _C.save(cfg)
    except Exception:
        pass


def _rules_summary():
    rules = _rules()
    if not rules:
        return "none"
    return "%d rule%s" % (len(rules), "" if len(rules) == 1 else "s")


def _edit_rules(shell):
    """The rules editor (.tmp LanguagesPanel rules table): source and
    target combos plus an Add button; rows list "English -> Vietnamese"
    and a selected row can be removed. Same language on both sides is
    refused, duplicates refused -- upstream's two warnings."""
    from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                                   QHBoxLayout, QLabel, QListWidget,
                                   QMessageBox, QPushButton, QVBoxLayout)
    app = getattr(shell, "app", None)
    try:
        codes = [c for c in (app._lang_codes() if app is not None else [])
                 if c != "auto"] or ["en", "vi"]
    except Exception:
        codes = ["en", "vi"]
    names = {c: _pinned_name(c) for c in codes}

    dlg = QDialog(shell)
    dlg.setWindowTitle("Translation rules")
    lay = QVBoxLayout(dlg)
    lst = QListWidget()
    lay.addWidget(lst)

    def refresh():
        lst.clear()
        for r in _rules():
            lst.addItem("%s  ->  %s" % (names.get(r["source"],
                                                 r["source"]),
                                       names.get(r["target"],
                                                 r["target"])))

    refresh()
    row = QHBoxLayout()
    src_c = QComboBox()
    tgt_c = QComboBox()
    for c in codes:
        src_c.addItem(names.get(c, c), c)
        tgt_c.addItem(names.get(c, c), c)
    add_b = QPushButton("Add")
    del_b = QPushButton("Remove")
    row.addWidget(QLabel("From:"))
    row.addWidget(src_c, 1)
    row.addWidget(QLabel("To:"))
    row.addWidget(tgt_c, 1)
    row.addWidget(add_b)
    row.addWidget(del_b)
    lay.addLayout(row)
    btns = QDialogButtonBox(QDialogButtonBox.Close)
    lay.addWidget(btns)
    btns.rejected.connect(dlg.reject)

    def add_rule():
        s, t = src_c.currentData(), tgt_c.currentData()
        if s == t:
            QMessageBox.warning(dlg, "QTranslate",
                                "Source and target must differ.")
            return
        rules = _rules()
        if any(r["source"] == s for r in rules):
            QMessageBox.warning(
                dlg, "QTranslate",
                "A rule for %s already exists." % names.get(s, s))
            return
        rules.append({"source": s, "target": t})
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            cfg.setdefault("General", {})["TranslationRules"] = rules
            _C.save(cfg)
        except Exception:
            return
        refresh()

    def remove_rule():
        it = lst.currentRow()
        rules = _rules()
        if it < 0 or it >= len(rules):
            return
        del rules[it]
        try:
            from qtranslate import config as _C
            cfg = _C.load() or {}
            cfg.setdefault("General", {})["TranslationRules"] = rules
            _C.save(cfg)
        except Exception:
            return
        refresh()

    add_b.clicked.connect(add_rule)
    del_b.clicked.connect(remove_rule)
    dlg.exec()
    try:
        shell._rules_lab.setText(
            "Translation rules: " + _rules_summary())
    except Exception:
        pass


class _LangCell(QWidget):
    """One language row: click toggles enabled/disabled."""

    def __init__(self, shell, name):
        super().__init__(shell)
        self.shell = shell
        self.name = name

    def mousePressEvent(self, _e):
        _toggle(self.shell, self.name)


class LanguagesPage(OptionsBase):
    SEL = 4

    # The "Translation rules", "Read aloud" and dictionary
    # auto-lookup rows (.tmp LanguagesPanel's rules table,
    # selectionReadSource and the dictAutoLookup/dictAutoPopup
    # controls, like the pin editor) need 106px more than the
    # native capture left at the bottom.
    SIZE = (644, 512)
    CHROME = dict(OptionsBase.CHROME)
    CHROME["panel"] = (4, 29, 142, 474)
    CHROME["shadow_row"] = (3, 503, 144, 1)
    CHROME["rule"] = (508, 3, 638)
    CHROME["buttons"] = {k: (x, y + 150, w, sh)
                         for k, (x, y, w, sh)
                         in OptionsBase.CHROME["buttons"].items()}

    # MEASURED off capture 2137: the first box's top-left is at screen
    # (156, 33), the columns are 127px apart, the rows 14px, and each
    # word starts 18px after its box.
    BOX_X, BOX_Y = 156, 33
    COL_STEP, ROW_STEP = 127, 14
    TEXT_DX, TEXT_DY = 18, 6

    def build(self):
        cfg = cfg_load() or {}
        self._lang_disabled = set(cfg.get("DisabledLanguages", []) or [])
        self._lang_labels = {}
        lst = panel(self, 155, 31, 481, 272)
        for ci, col in enumerate(LANGUAGES):
            x = self.BOX_X + self.COL_STEP * ci
            for i, n in enumerate(col.split(" ")):
                name = _display_name(n)
                icon(lst, x, self.BOX_Y + self.ROW_STEP * i,
                     "ui_icons", "check_blue")
                lab = label(lst, x + self.TEXT_DX,
                            self.BOX_Y + self.TEXT_DY + self.ROW_STEP * i,
                            name,
                            color=TEXT
                            if name not in self._lang_disabled else DIM)
                # A click target over the box+word, in the panel's own
                # coordinates (the panel's _abs is its screenshot pos).
                cell = _LangCell(self, name)
                cell.setParent(lst)
                cell.setGeometry(x - lst._abs[0] - 4,
                                 self.BOX_Y + self.ROW_STEP * i
                                 - lst._abs[1] - 4, 110, 18)
                cell.show()
                self._lang_labels[name] = lab
        # The list's horizontal scrollbar: the thumb is 267px long.
        rect(lst, 173, 293, 267, 2, THUMB)
        b = button(self, 155, 308, 481, "Check / Uncheck all")
        b.clicked.connect(lambda: _toggle_all(self))
        # .tmp's pinnedLanguages (LanguagesPanel): a non-empty pin list
        # narrows every language picker to just those languages. The
        # native page has no room for a second checklist, so the pin
        # editor is a dialog behind this one row.
        self._pinned_lab = label(self, 155, 334,
                                 "Pinned languages: " + _pinned_summary())
        bp = button(self, 580, 333, 56, "Edit…")
        bp.clicked.connect(lambda: _edit_pinned(self))
        # .tmp's translationRules (LanguagesPanel rules table): a
        # source->target override applied by the main translation
        # flow. Dialog editor, same precedent as the pin editor.
        self._rules_lab = label(self, 155, 354,
                                "Translation rules: "
                                + _rules_summary())
        br = button(self, 580, 353, 56, "Edit…")
        br.clicked.connect(lambda: _edit_rules(self))
        # .tmp's selectionReadSource: which text mouse-mode
        # "Show translation and read" speaks -- the result
        # (Translation, default) or the captured selection itself
        # (Source, spoken immediately in the source language).
        label(self, 155, 376, "Read aloud:")
        rs = combo(self, 300, 374, 150, "", values=["Translation",
                                                    "Source"])
        rs.setCurrentIndex(
            1 if _read_source() == "source" else 0)
        rs.activated.connect(lambda _i: _set_read_source(rs))
        # .tmp TranslationPanel's dictionary auto-lookup group:
        # dictAutoLookupCheck -> dictionaryAutoSource OFF vs
        # TRANSLATED, the "Look up:" combo -> TRANSLATED/SOURCE, and
        # dictAutoPopupCheck -> isDictionaryAutoPopupEnabled (which
        # upstream gates the WHOLE AutoLookupCoordinator on, inline
        # gloss included).
        gen = cfg.setdefault("General", {})
        auto_src = str(gen.get("DictionaryAutoSource",
                               "TRANSLATED") or "TRANSLATED")
        self._dict_lookup = QCheckBox(
            "Automatically look up single-word translations")
        self._dict_lookup.setChecked(auto_src != "OFF")
        self._dict_lookup.toggled.connect(
            lambda on: _set_dict_auto_source(
                self, "TRANSLATED" if on else "OFF"))
        # put(), not move(): the page's numbers are SCREENSHOT coords
        # and move() would land the box 26px low, on the combo row.
        put(self, self._dict_lookup, 155, 398, 300, 16)
        self._dict_lookup.show()
        label(self, 155, 420, "Look up:")
        self._dict_look_combo = combo(self, 300, 418, 150, "",
                                      values=["Translation", "Source"])
        self._dict_look_combo.setCurrentIndex(
            1 if auto_src == "SOURCE" else 0)
        self._dict_look_combo.setEnabled(auto_src != "OFF")
        self._dict_lookup.toggled.connect(
            lambda on: self._dict_look_combo.setEnabled(bool(on)))
        self._dict_look_combo.activated.connect(
            lambda _i: _set_dict_auto_source(
                self,
                "SOURCE" if self._dict_look_combo.currentIndex() == 1
                else "TRANSLATED"))
        self._dict_popup = QCheckBox(
            "Show dictionary popup for single words")
        self._dict_popup.setChecked(
            bool(gen.get("DictionaryAutoPopup", True)))
        self._dict_popup.setEnabled(auto_src != "OFF")
        self._dict_popup.toggled.connect(
            lambda on: _set_dict_auto_popup(self, bool(on)))
        put(self, self._dict_popup, 175, 442, 320, 16)
        self._dict_popup.show()
        self._dict_lookup.toggled.connect(
            lambda on: self._dict_popup.setEnabled(bool(on)))
        # .tmp TranslationPanel's extra-output AI options
        # (StandardOptions.SUMMARY_LENGTH / REWRITE_STYLE): the values
        # the Summarize/Rewrite extra modes pass to the AI service.
        label(self, 155, 466, "Summary length:")
        sl = combo(self, 300, 464, 120, "",
                   values=["Short", "Medium", "Long"])
        _sl_ids = ["SHORT", "MEDIUM", "LONG"]
        try:
            sl.setCurrentIndex(_sl_ids.index(
                str(gen.get("SummaryLength", "MEDIUM")).upper()))
        except ValueError:
            pass
        sl.activated.connect(
            lambda i: cfg_set("General", "SummaryLength",
                              _sl_ids[i]))
        label(self, 450, 466, "Rewrite style:")
        rw = combo(self, 570, 464, 140, "",
                   values=["Formal", "Casual", "Concise", "Detailed",
                           "Simplified"])
        _rw_ids = ["FORMAL", "CASUAL", "CONCISE", "DETAILED",
                   "SIMPLIFIED"]
        try:
            rw.setCurrentIndex(_rw_ids.index(
                str(gen.get("RewriteStyle", "FORMAL")).upper()))
        except ValueError:
            pass
        rw.activated.connect(
            lambda i: cfg_set("General", "RewriteStyle",
                              _rw_ids[i]))
