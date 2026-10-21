"""The example UI-contribution extension.

The app publishes UI slots derived from the native UI surface rather
than invented ones (`qtranslate/ui_slots.py`): the MENU slots are the
native ``Menus[].Id`` values a locale pack declares, and the PANEL slots
are the three ``Show*Pane`` toggles the Options page reads.

A contribution is anything the host can call. The example contributes
one menu entry to the system-tray menu -- the slot the native calls
``5`` -- and a panel to the main window's top pane.

Copy this folder into the per-user extensions directory and restart
QTranslate.
"""

# The menu slot's native id is 5 (`ui_slots.MENU_SLOT_IDS`).
TRAY_MENU_SLOT = "tray"
# The main window's top pane (the source pane's area).
TOP_PANEL_SLOT = "top"


def tray_entry():
    """The callable the host invokes for the menu entry.

    A real extension would do its work here; the example answers, so
    the contribution is observable without a network.
    """
    return "Hello from the example extension."


def top_panel():
    """The callable the host invokes to fill the top panel."""
    return "Hello from the example extension."


def register(api):
    """Called once at startup with the SDK's API object."""
    api.register_ui("menu", TRAY_MENU_SLOT, tray_entry)
    api.register_ui("panel", TOP_PANEL_SLOT, top_panel)
