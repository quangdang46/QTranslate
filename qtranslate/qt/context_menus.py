"""The native context menus, built from the locale packs.

Every menu here is native's own, identified by the ``Menus[].Id`` the
shipped locale packs carry (``qtranslate/locale.py`` reads them):

| slot | native menu | where it appears |
|---|---|---|
| `source_context` | 2 | right-click in the source pane |
| `result_context` | 3 | right-click in the result pane |
| `language` | 4 | right-click on a language combo |
| `dict_header` | 7 | the dictionary window's ':' button |
| `history_menu` | 9 | the history window's own menu |
| `ocr` | 10 | the text-recognition window |

The LABELS come from the pack (so a translated UI gets translated
menus) and the IDS come from the same pack, which is why a menu cannot
drift into a list of strings the native never had. Each id is bound to
the operation the port already performs elsewhere; an item the port
does not implement is DISABLED with that reason rather than dropped or
faked, so the menu shows the native's shape and the port's real ability.

``ui_slots.MENU_SLOT_IDS`` names these same ids, so an extension that
targets ``menu``/`source_context` lands in exactly this menu -- that is
what closes the "published names with no host" gap.
"""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


def pack_labels(menu_id: int) -> dict:
    """``{item_id: text}`` for one native menu, from the English pack."""
    try:
        from qtranslate import locale
        pack = locale.load_pack("English")
        return {k: v for k, v in locale.menu_labels(pack, menu_id)
                if isinstance(k, int)}
    except Exception:
        return {}


def _label(menu_id: int, item_id: int, default: str) -> str:
    return pack_labels(menu_id).get(item_id, default)


def build(parent, app, slot: str, menu_id: int, items, enabled=None):
    """Build one native menu and append the slot's extension entries.

    ``items`` is ``[(item_id, default_label, handler), ...]`` in native's
    order. A handler of ``None`` draws a disabled item -- used where
    native has the entry and the port has no operation behind it yet, so
    the gap is visible in the UI instead of hidden.
    """
    m = QMenu(parent)
    enabled = enabled or (lambda item_id, fn: fn is not None)
    for item_id, default, fn in items:
        act = QAction(_label(menu_id, item_id, default), parent)
        if fn is None:
            act.setEnabled(False)
        else:
            act.triggered.connect(lambda _c=False, f=fn: f())
        m.addAction(act)
    append_extensions(m, parent, app, slot)
    return m


def append_extensions(menu, parent, app, slot: str):
    """Add an extension's contributions to ``slot`` under a separator."""
    from .widgets import extension_menu_entries
    entries = extension_menu_entries(parent, app, slot)
    if not entries:
        return menu
    menu.addSeparator()
    for label, contrib in entries:
        act = QAction(label, parent)
        act.triggered.connect(
            lambda _c=False, f=contrib: app.run_ui_contribution(f))
        menu.addAction(act)
    return menu
