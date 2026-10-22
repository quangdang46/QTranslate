"""The tray icon and its menu, on PySide6.

Native's tray menu is the real taskbar right-click menu, so it is NOT
self-drawn: this is a ``QSystemTrayIcon`` with a ``QMenu``, and Qt draws
it (the spec's hard rule 6).

The order is native's, and it was read off the menu in the capture
2126 and the spec's section 9:

    QTranslate (bold heading) / Dictionary / Text recognition / History /
    Keyboard / Options / About QTranslate -- sep -- Enable global hotkeys
    (checkable) / Mouse mode (submenu) -- sep -- Exit
"""
from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

# The three mouse modes, in native's order. The names are native's own
# strings -- the English lang.json, ids 60/70/71 -- and the index is
# native's General.MouseMode (DAT_005493F8).
MOUSE_MODES = ("Show icon", "Show translation", "Show translation and read")


class Tray:
    """The tray icon, its menu, and the state the menu reflects."""

    def __init__(self, app):
        self.app = app
        self._hotkeys_on = True
        self._mouse_mode = MOUSE_MODES[0]
        self.icon = QSystemTrayIcon(QIcon(), None)
        self.icon.setToolTip("QTranslate")
        self.menu = self._menu()
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)

    # ---------------------------------------------------------------- menu
    def _menu(self) -> QMenu:
        app = self.app
        menu = QMenu()

        head = menu.addAction("QTranslate")
        head.setEnabled(False)
        f = head.font()
        f.setBold(True)
        head.setFont(f)

        for text, slot in (("Dictionary", app.open_dictionary),
                           ("Text recognition", app.open_ocr),
                           ("History", app.open_history),
                           ("Keyboard", app.open_keyboard),
                           ("Options...", app.open_options),
                           ("About QTranslate", app.show_about)):
            act = menu.addAction(text)
            act.triggered.connect(lambda _c=False, s=slot: s())

        menu.addSeparator()

        self.act_hotkeys = menu.addAction("Enable global hotkeys")
        self.act_hotkeys.setCheckable(True)
        self.act_hotkeys.setChecked(self._hotkeys_on)
        self.act_hotkeys.triggered.connect(self._toggle_hotkeys)

        sub = menu.addMenu("Mouse mode")
        self._mode_actions = {}
        for mode in MOUSE_MODES:
            act = sub.addAction(mode)
            act.setCheckable(True)
            act.setChecked(mode == self._mouse_mode)
            act.triggered.connect(
                lambda _c=False, m=mode: self._set_mouse_mode(m))
            self._mode_actions[mode] = act

        menu.addSeparator()
        # The extension UI slot: the native's tray menu is id 5 in the
        # locale packs, and an extension may contribute an entry to it
        # (``ui_slots.MENU_SLOT_IDS``). The contribution is anything the
        # host can call; its result is shown in a message box, so the
        # example extension's answer is observable without a network.
        self._add_extension_entries(menu)
        menu.addSeparator()
        act = menu.addAction("Exit")
        act.triggered.connect(self.quit)
        return menu

    def _add_extension_entries(self, menu):
        """Add the entries an extension contributed to the tray menu."""
        manager = getattr(self.app, "ext_manager", None)
        if manager is None:
            return
        slots = getattr(manager, "ui_slots", None)
        if slots is None:
            return
        try:
            entries = slots.entries("menu", "tray")
        except Exception:
            return
        for entry in entries:
            label = entry.get("label") or "Extension"
            contrib = entry.get("contribution")
            act = menu.addAction(label)
            act.triggered.connect(
                lambda _c=False, f=contrib: self._run_contribution(f))

    def _run_contribution(self, contrib):
        """Run an extension's contribution and show what it returned."""
        if not callable(contrib):
            return
        try:
            result = contrib()
        except Exception as exc:                # noqa: BLE001
            result = "Extension failed: %s" % exc
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, "QTranslate",
                                str(result) if result is not None else "")

    # -------------------------------------------------------------- actions
    def _toggle_hotkeys(self, checked):
        self._hotkeys_on = bool(checked)
        self.app.set_hotkeys_enabled(self._hotkeys_on)

    def _set_mouse_mode(self, mode):
        self.set_mouse_mode(mode)
        self.app.set_mouse_mode(mode)

    def _activated(self, reason):
        """A double-click on the tray icon shows the main window, the way
        native's does."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.app.show_main_window()

    def quit(self):
        self.icon.hide()
        self.app.quit()

    # ---------------------------------------------------------------- state
    def show(self):
        self.icon.show()

    def hide(self):
        self.icon.hide()

    def set_hotkeys(self, on):
        self._hotkeys_on = bool(on)
        self.act_hotkeys.setChecked(self._hotkeys_on)

    def set_mouse_mode(self, mode):
        """Reflect the mode in the submenu.

        It does NOT call the app back: the app calls this, so the
        checkmarks follow the mode whoever changed it (the tray, the
        hotkey, the config the last session left behind).
        """
        self._mouse_mode = mode
        for name, act in self._mode_actions.items():
            act.setChecked(name == mode)
