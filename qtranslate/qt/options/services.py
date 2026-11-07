"""The Services page of the Options dialog.

The geometry was measured off the native capture 2136: the list panel,
the two section headings with their rules, the nine translation services
and the dictionary services, each with its icon, and the four buttons
under the list.
"""

from .base import OptionsBase, cfg_load, button, check, combo, hline, \
    label, panel, rect
from ..widgets import HEADING, HEADING_LINE, icon
from qtranslate_style import DIM, FACE, THUMB, WINDOW


def _top(key, default):
    cfg = cfg_load() or {}
    return cfg.get(key, default)


def _set_top(key, value):
    from qtranslate import config as _C
    try:
        cfg = _C.load() or {}
        cfg[key] = value
        _C.save(cfg)
    except Exception:
        pass

# The icon each dictionary service draws. The names are the port's own
# display names (qtranslate.config.DICT_DISPLAY); the files are the ones
# recovered from the installer payload.
DICT_ICONS = {
    "Google Search": "google-search",
    "WordReference": "wordreference",
    "Babylon Dictionary": "babylon",
    "Wikipedia": "wikipedia",
    "Multitran": "multitran",
    "ImTranslator": "imtranslator",
    "Reverso": "reverso",
    "Urban Dictionary": "urban",
    "ABBYY Lingvo Live": "lingvo",
    "youdao": "youdao",
    "Oxford Learner Dictionary": "oxford",
}

# The icon each translation service draws.
SERVICE_ICONS = {
    "google": "google", "microsoft": "microsoft", "promt": "promt",
    "babylon": "babylon", "yandex": "yandex", "youdao": "youdao",
    "baidu": "baidu", "naver": "naver", "deepl": "deepl",
}

# The service key -> the icon file, for the services the port knows.
SERVICE_ICON_BY_NAME = {
    "Google": "google", "Microsoft": "microsoft", "Promt": "promt",
    "Babylon": "babylon", "Yandex": "yandex", "youdao": "youdao",
    "Baidu": "baidu", "Papago": "naver", "DeepL": "deepl",
}


class ServicesPage(OptionsBase):
    SEL = 3
    # Grew for the port-owned "Service presets" and "Preferred
    # services" groups below the measured list (same precedent as
    # Basics/Languages/Advanced).
    SIZE = (644, 486)
    CHROME = dict(OptionsBase.CHROME)
    CHROME["panel"] = (4, 29, 142, 448)
    CHROME["shadow_row"] = (3, 477, 144, 1)
    CHROME["rule"] = (482, 3, 638)
    CHROME["buttons"] = {k: (x, y + 124, w, sh)
                         for k, (x, y, w, sh)
                         in OptionsBase.CHROME["buttons"].items()}

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        # The list view is 464px wide and the vertical scrollbar's track
        # takes the 16px next to it; the track is the face colour, not
        # the list's white. MEASURED off the capture.
        rect(lst, 619, 32, 16, 270, FACE)
        # The list's own first row is empty, so the face shows there.
        rect(lst, 156, 32, 463, 1, FACE)
        # The section heading and the rule that runs beside it, both at
        # the heading's own mid height. The heading is Tahoma 9pt.
        label(lst, 167, 42, "Translation", color=HEADING, size=12)
        hline(lst, 42, 230, 608, HEADING_LINE)
        disabled_svcs = set(_top("DisabledServices", []))
        disabled_dicts = set(_top("DisabledDictionaries", []))
        from qtranslate import config as _C
        # The FULL order, including disabled services: the list must
        # show a disabled service's row so its box can turn it back on
        # (app.ordered_services() filters them out).
        svc_ids = list(_top("ServicesOrder", _C.DEFAULT_SERVICES_ORDER))
        for i, sid in enumerate(svc_ids):
            # sid is the numeric service id -- service_display() wants
            # the service KEY. Passing the id through printed "1","5",
            # "12"... down the whole list (the Services-page audit).
            key = _C.SERVICE_NAMES.get(sid, "")
            name = (_C.SERVICE_DISPLAY.get(sid)
                    or str(self.app.service_display(key)))
            icon(lst, 176, 54 + 18 * i, "service_icons",
                 SERVICE_ICON_BY_NAME.get(name, "google"))
            # The list's checkbox sits one pixel above the name's
            # middle: MEASURED off the capture (the indicator's box is
            # at rows 29..41 while the name's ink is at 32..42).
            on = sid not in disabled_svcs
            cb = check(lst, 160, 61 + 18 * i, "", on, blue=True)
            cb.toggled.connect(
                lambda v, s=sid: _toggle_service(s, v))
            label(lst, 194, 62 + 18 * i, name)
        label(lst, 168, 228, "Dictionary", color=HEADING, size=12)
        hline(lst, 228, 226, 608, HEADING_LINE)
        from qtranslate import config as _C
        dict_ids = list(_top("DictionariesOrder",
                             _C.DEFAULT_DICTIONARIES_ORDER))
        for i, did in enumerate(dict_ids):
            name = str(_C.DICT_DISPLAY.get(did, did))
            icon(lst, 176, 240 + 18 * i, "dict_icons",
                 DICT_ICONS.get(name, "wikipedia"))
            on = did not in disabled_dicts
            cb = check(lst, 160, 247 + 18 * i, "", on, blue=True)
            cb.toggled.connect(
                lambda v, did=did: _toggle_dict(did, v))
            lab = label(lst, 194, 248 + 18 * i, name)
            # Clicking the row selects the dictionary the arrows move.
            lab.mousePressEvent = (
                lambda _e, d=did, w=lab: _select_dict(self, d, w))
        # The scrollbar's thumb: two pixels wide, 153 tall.
        rect(lst, 626, 51, 2, 153, THUMB)
        # The four buttons, measured off the capture: the two arrows are
        # 25px wide, the two wide ones 118. The arrows reorder the
        # SELECTED dictionary inside DictionariesOrder. Add registers an
        # XDXF file in OfflineDictionaries -- the backend
        # qtranslate.dictionary_search already queries -- and Remove
        # drops the selected row from DictionariesOrder, the same write
        # the dictionary window's strip menu makes. Both stay disabled
        # until a row is selected (Remove) or are always live (Add).
        self._dict_sel = None
        self.btn_up = button(self, 156, 308, 25, "▲", enabled=False,
                             shadow=True)
        self.btn_down = button(self, 186, 308, 25, "▼", enabled=False,
                               shadow=True)
        self.btn_up.clicked.connect(lambda: _move_dict(self, -1))
        self.btn_down.clicked.connect(lambda: _move_dict(self, 1))
        self.btn_add = button(self, 219, 308, 118, "Add dictionary...",
                              enabled=True, shadow=True)
        self.btn_add.setToolTip(
            "Add an XDXF dictionary file (.xdxf/.xdx); offline "
            "dictionaries are searched before the online ones")
        self.btn_add.clicked.connect(lambda: _add_dict(self))
        self.btn_remove = button(self, 342, 308, 118, "Remove dictionary",
                                 enabled=False, shadow=True)
        self.btn_remove.setToolTip(
            "Remove the selected dictionary from the list")
        self.btn_remove.clicked.connect(lambda: _remove_dict(self))
        self.btn_remove.setStyleSheet("color:%s" % DIM)
        # The sunken frame's 1px white shadow, under the list.
        rect(self, 154, 303, 483, 1, WINDOW)

        # ---- Service presets (.tmp ServicesPanel preset row) --------
        # Port-owned: a named bundle of {translator, comparison set}.
        # Picking one applies it to the running app immediately.
        label(self, 167, 322, "Service presets", color=HEADING, size=12)
        hline(self, 322, 470, 608, HEADING_LINE)
        self._preset_names = _preset_names()
        self._preset_combo = combo(
            self, 167, 340, 230, "", values=self._preset_names or [""])
        self._preset_combo.setEnabled(bool(self._preset_names))
        self._preset_combo.activated.connect(
            lambda _i: _apply_preset(self))
        self.btn_pnew = button(self, 405, 339, 70, "New", shadow=True)
        self.btn_pnew.clicked.connect(lambda: _preset_new(self))
        self.btn_ren = button(self, 480, 339, 70, "Rename", shadow=True)
        self.btn_ren.clicked.connect(lambda: _preset_rename(self))
        self.btn_pdel = button(self, 555, 339, 70, "Delete", shadow=True)
        self.btn_pdel.clicked.connect(lambda: _preset_delete(self))
        hint = label(
            self, 167, 368,
            "A preset saves the translator and comparison services; "
            "choosing one switches the app to it.", color=DIM)
        hint.setWordWrap(True)
        _refresh_presets(self)

        # ---- Preferred services (.tmp per-role service selection) --
        # The port resolves TTS/spell/OCR through fallback chains, so a
        # role "selection" is a preferred-first backend; "Auto" keeps
        # the default order. Writes General.PreferredServices.
        label(self, 167, 404, "Preferred services", color=HEADING,
              size=12)
        hline(self, 404, 500, 608, HEADING_LINE)
        prefs = _preferred()
        for row, (role, text, values) in enumerate(_PREF_ROWS):
            y = 422 + 22 * row
            label(self, 167, y + 2, text)
            cb = combo(self, 265, y, 190, "", values=values)
            # Stored value is a backend key; the display rows are
            # index-aligned with _PREF_VALUES (0 == "Auto" both ways).
            vals = _PREF_VALUES.get(role) or []
            cur = prefs.get(role) or ""
            if cur in vals:
                cb.setCurrentIndex(vals.index(cur))
            cb.activated.connect(
                lambda _i, r=role, c=cb: _set_preferred(self, r, c))

    # ------------------------------------------------------------- wiring
    # NB: build() runs on the SHELL instance, so page behaviour lives in
    # module functions, never self._methods (see options/extensions.py).


def _toggle_service(sid, on):
    ids = set(_top("DisabledServices", []))
    if on:
        ids.discard(sid)
    else:
        ids.add(sid)
    _set_top("DisabledServices", sorted(ids))


def _toggle_dict(did, on):
    ids = set(_top("DisabledDictionaries", []))
    if on:
        ids.discard(did)
    else:
        ids.add(did)
    _set_top("DisabledDictionaries", sorted(ids))


def _select_dict(shell, did, row):
    """Select a dictionary row: the arrows then move THAT entry, and the
    row is highlighted so the target of the move is visible."""
    try:
        old = getattr(shell, "_dict_sel_row", None)
        if old is not None:
            old.setStyleSheet("")
        shell._dict_sel = did
        shell._dict_sel_row = row
        row.setStyleSheet("background:#cce4ff;")
        shell.btn_up.setEnabled(True)
        shell.btn_down.setEnabled(True)
        if getattr(shell, "btn_remove", None) is not None:
            shell.btn_remove.setEnabled(True)
    except Exception:
        pass


def _move_dict(shell, delta):
    """Move the selected dictionary one slot inside DictionariesOrder
    and rebuild the page so the list shows the new order."""
    from qtranslate import config as _C
    try:
        did = getattr(shell, "_dict_sel", None)
        if did is None:
            return
        ids = list(_top("DictionariesOrder",
                        _C.DEFAULT_DICTIONARIES_ORDER))
        if did not in ids:
            return
        i = ids.index(did)
        j = i + delta
        if not (0 <= j < len(ids)):
            return
        ids[i], ids[j] = ids[j], ids[i]
        _set_top("DictionariesOrder", ids)
        _rebuild(shell)
    except Exception:
        pass


def _rebuild(shell):
    """Rebuild the page in place: _show_page returns early on the same
    name, so clear it first."""
    shell._page_name = ""
    shell._goto("Services")


def _add_dict(shell):
    """"Add dictionary...": pick an XDXF file and register it.

    The backend already exists -- ``qtranslate.dictionary_search``
    prepends every path in ``OfflineDictionaries`` to the lookup
    (``qtranslate/xdxf.py`` renders the articles) -- only the UI was
    missing. The file joins the END of the offline list, so the most
    recently added dictionary is searched last among the offline ones.
    """
    try:
        from PySide6.QtWidgets import QFileDialog
        path, _flt = QFileDialog.getOpenFileName(
            shell, "Add dictionary", "",
            "XDXF dictionaries (*.xdxf *.xdx);;All files (*)")
    except Exception:
        return
    if not path:
        return
    try:
        from qtranslate import config as _C
        cfg = _C.load() or {}
        offline = list(cfg.get("OfflineDictionaries") or [])
        if path not in offline:
            offline.append(path)
            cfg["OfflineDictionaries"] = offline
            _C.save(cfg)
    except Exception:
        return


def _remove_dict(shell):
    """"Remove dictionary": drop the selected row from
    ``DictionariesOrder`` -- the same write the dictionary window's
    strip menu makes (``qt/dictionary.py::_remove_dictionary``)."""
    try:
        did = getattr(shell, "_dict_sel", None)
        if did is None:
            return
        from qtranslate import config as _C
        cfg = _C.load() or {}
        order = cfg.get("DictionariesOrder")
        if order is None:
            order = list(_C.DEFAULT_DICTIONARIES_ORDER)
        ids = [i for i in order if i != did]
        if len(ids) == len(order):
            return
        cfg["DictionariesOrder"] = ids
        _C.save(cfg)
    except Exception:
        return
    _rebuild(shell)


# ------------------------------------------------------- service presets
# .tmp ServicesPanel: preset combo + New/Rename/Delete + hint. A preset
# bundles the translator and the comparison set; applying it calls
# QtApp.apply_preset which also marks General.ActivePresetId.

def _cfg():
    from qtranslate import config as _C
    return _C.load() or {}


def _save(cfg):
    from qtranslate import config as _C
    _C.save(cfg)


def _preset_names():
    from qtranslate import presets as _P
    try:
        return [p["name"] for p in _P.presets(_cfg())]
    except Exception:
        return []


def _preset_by_name(name):
    from qtranslate import presets as _P
    for p in _P.presets(_cfg()):
        if p["name"] == name:
            return p
    return None


def _current_selection(shell):
    """What "New" snapshots: the app's live translator + the checked
    comparison set (falling back to the stored config)."""
    app = getattr(shell, "app", None)
    translator = getattr(app, "service", "") if app else ""
    comparison = []
    try:
        from qtranslate import presets as _P
        snap = _P.snapshot(_cfg())
        comparison = snap["comparison"]
        if not translator:
            translator = snap["translator"]
    except Exception:
        pass
    return translator, comparison


def _apply_preset(shell):
    name = shell._preset_combo.currentText()
    p = _preset_by_name(name)
    app = getattr(shell, "app", None)
    if p is None:
        return
    if app is not None and hasattr(app, "apply_preset"):
        app.apply_preset(p)
    else:
        # Options opened without a live app: still persist the choice.
        from qtranslate import presets as _P
        cfg = _cfg()
        _P.apply(cfg, p)
        _save(cfg)


def _preset_new(shell):
    from PySide6.QtWidgets import QInputDialog
    name, ok = QInputDialog.getText(
        shell, "New preset", "Preset name:")
    if not ok or not str(name).strip():
        return
    from qtranslate import presets as _P
    translator, comparison = _current_selection(shell)
    cfg = _cfg()
    _P.create(cfg, name, translator, comparison)
    _save(cfg)
    _refresh_presets(shell)


def _preset_rename(shell):
    name = shell._preset_combo.currentText()
    p = _preset_by_name(name)
    if p is None:
        return
    from PySide6.QtWidgets import QInputDialog
    new, ok = QInputDialog.getText(
        shell, "Rename preset", "Preset name:", text=name)
    if not ok or not str(new).strip():
        return
    from qtranslate import presets as _P
    cfg = _cfg()
    _P.rename(cfg, p["id"], new)
    _save(cfg)
    _refresh_presets(shell)


def _preset_delete(shell):
    name = shell._preset_combo.currentText()
    p = _preset_by_name(name)
    if p is None:
        return
    from PySide6.QtWidgets import QMessageBox
    if QMessageBox.question(
            shell, "Delete preset",
            "Delete preset '%s'?" % p["name"]) != \
            QMessageBox.StandardButton.Yes:
        return
    from qtranslate import presets as _P
    cfg = _cfg()
    _P.delete(cfg, p["id"])
    _save(cfg)
    _refresh_presets(shell)


# (role, row label, combo values -- index 0 is always "Auto")
_PREF_ROWS = (
    ("tts", "Text to speech",
     ["Auto", "Google", "Bing", "System voice"]),
    ("spell", "Spell checker",
     ["Auto", "System", "Bing", "Google", "AI"]),
    ("ocr", "Text recognition",
     ["Auto", "Vision (macOS)", "Tesseract", "OCR.space",
      "Google Vision", "AI"]),
)

_PREF_VALUES = {
    "tts": ["", "google", "bing", "system"],
    "spell": ["", "system", "bing", "google", "ai"],
    "ocr": ["", "vision", "tesseract", "ocrspace", "google-vision",
            "ai"],
}


def _preferred():
    try:
        v = (_cfg().get("General", {}) or {}).get("PreferredServices")
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _set_preferred(shell, role, combo_w):
    try:
        cfg = _cfg()
        g = cfg.setdefault("General", {})
        prefs = g.setdefault("PreferredServices", {})
        if not isinstance(prefs, dict):
            prefs = g["PreferredServices"] = {}
        vals = _PREF_VALUES.get(role) or []
        idx = combo_w.currentIndex()
        prefs[role] = vals[idx] if 0 <= idx < len(vals) else ""
        _save(cfg)
    except Exception:
        pass


def _refresh_presets(shell):
    """Refill the combo and select the active preset, if any."""
    from qtranslate import presets as _P
    try:
        combo_w = shell._preset_combo
        combo_w.blockSignals(True)
        combo_w.clear()
        cfg = _cfg()
        ps = _P.presets(cfg)
        names = [p["name"] for p in ps]
        for n in names:
            combo_w.addItem(n)
        combo_w.setEnabled(bool(names))
        active = _P.active_id(cfg)
        for p in ps:
            if p["id"] == active:
                combo_w.setCurrentIndex(names.index(p["name"]))
                break
        else:
            if names:
                combo_w.setCurrentIndex(0)
    except Exception:
        pass
    finally:
        try:
            combo_w.blockSignals(False)
        except Exception:
            pass
