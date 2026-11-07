"""The Services page of the Options dialog.

The geometry was measured off the native capture 2136: the list panel,
the two section headings with their rules, the nine translation services
and the dictionary services, each with its icon, and the four buttons
under the list.
"""

from .base import OptionsBase, cfg_load, button, check, hline, label, \
    panel, rect
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
        # SELECTED dictionary inside DictionariesOrder; Add/Remove have
        # no backend (native's picker adds custom dictionary URLs, which
        # the port does not model), so they stay disabled rather than
        # fake a reaction.
        self._dict_sel = None
        self.btn_up = button(self, 156, 308, 25, "▲", enabled=False,
                             shadow=True)
        self.btn_down = button(self, 186, 308, 25, "▼", enabled=False,
                               shadow=True)
        self.btn_up.clicked.connect(lambda: _move_dict(self, -1))
        self.btn_down.clicked.connect(lambda: _move_dict(self, 1))
        button(self, 219, 308, 118, "Add dictionary...", enabled=False,
               shadow=True)
        b = button(self, 342, 308, 118, "Remove dictionary", enabled=False,
                   shadow=True)
        b.setStyleSheet("color:%s" % DIM)
        # The sunken frame's 1px white shadow, under the list.
        rect(self, 154, 303, 483, 1, WINDOW)

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
        # Rebuild the page in place: _show_page returns early on the
        # same name, so clear it first.
        shell._page_name = ""
        shell._goto("Services")
    except Exception:
        pass
