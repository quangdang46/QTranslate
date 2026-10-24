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
        self._armed = False
        self.icon = QSystemTrayIcon(self._paint_icon(False), None)
        self.icon.setToolTip("QTranslate")
        self.menu = self._menu()
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)

    # ---------------------------------------------------------------- icon
    def _paint_icon(self, armed):
        """The tray icon's OWN pixels: grey when the mouse capture is
        off, ACCENT blue when on -- the operator's report (2026-10-24):
        "click the tray icon and the icon changes colour". The old tray
        carried an EMPTY QIcon, so nothing could ever change."""
        from PySide6.QtGui import QIcon, QPainter, QPixmap
        from PySide6.QtCore import Qt as _Qt
        from qtranslate_style import ACCENT
        pm = QPixmap(16, 16)
        pm.fill(_Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(_Qt.blue if armed else _Qt.gray)
        p.setPen(_Qt.NoPen)
        p.drawEllipse(1, 1, 14, 14)
        p.setPen(_Qt.white)
        fnt = p.font()
        fnt.setBold(True)
        p.setFont(fnt)
        p.drawText(pm.rect(), _Qt.AlignCenter, "Q")
        p.end()
        return QIcon(pm)

    # ---------------------------------------------------------------- menu
    def _menu(self) -> QMenu:
        app = self.app
        menu = QMenu()

        head = menu.addAction("QTranslate")
        head.setEnabled(False)
        f = head.font()
        f.setBold(True)
        head.setFont(f)

        for text, slot in (("Show main window", app.show_main_window),
                           ("Dictionary", app.open_dictionary),
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
        # The installed extensions by NAME, each with its own on/off
        # switch -- visible where the operator actually looks (the tray),
        # not only in the Options page. A toggle persists
        # Extensions.Disabled and takes effect at the next start.
        ext_sub = self._extensions_submenu(menu)
        if ext_sub is not None:
            menu.addMenu(ext_sub)
        menu.addSeparator()
        act = menu.addAction("Exit")
        act.triggered.connect(self.quit)
        return menu

    def _extensions_submenu(self, menu):
        """The installed extensions with a checkable on/off each.

        Returns None (no submenu) when nothing is installed, so the tray
        of a bare install looks exactly like it always did.
        """
        from qtranslate.extensions import (read_disabled_extensions,
                                           write_disabled_extensions)
        manager = getattr(self.app, "ext_manager", None)
        ids = sorted(getattr(manager, "_manifests", {}) or {})
        if not ids:
            return None
        sub = menu.addMenu("Extensions")
        disabled = set(read_disabled_extensions())
        for ext_id in ids:
            act = sub.addAction(ext_id)
            act.setCheckable(True)
            act.setChecked(ext_id not in disabled)
            act.setStatusTip("Takes effect after QTranslate restarts")
            act.triggered.connect(
                lambda _c=False, on=act.isChecked(), eid=ext_id:
                _toggle_extension(eid, on))
        return sub


    def _add_extension_entries(self, menu):
        """Add the entries an extension contributed to the tray menu."""
        manager = getattr(self.app, "ext_manager", None)
        if manager is None:
            return
        # An unresolved override conflict is the user's to decide (D18).
        # The entry only appears while there is one, so a normal install
        # sees the menu it always did.
        try:
            conflicted = bool(manager.override_conflicts())
        except Exception:
            conflicted = False
        if conflicted:
            act = menu.addAction("Choose the winning extensions...")
            act.triggered.connect(
                lambda _c=False: self.app.choose_override_winners())
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
        """A LEFT click toggles the mouse capture on/off (the operator's
        toggle: off = select + Ctrl+Q yourself; on = the selected mode
        applies, and the icon turns blue). A double-click shows the main
        window, the way native's does."""
        if reason == QSystemTrayIcon.Trigger:
            try:
                self.app.toggle_mouse_enabled()
            except Exception:               # noqa: BLE001
                pass
        elif reason == QSystemTrayIcon.DoubleClick:
            self.app.show_main_window()

    def quit(self):
        self.icon.hide()
        self.app.quit()

    # ---------------------------------------------------------------- state
    def show(self):
        self.icon.show()

    def hide(self):
        self.icon.hide()

    def sync_state(self, armed, hook_installed):
        """The tray's state follows native's rule (FUN_00418DA0), via
        ``tray_state.select_state``: the flag is the MOUSE-CAPTURE arm
        state and the other bit is whether the hook actually installed --
        NOT the HotKeys list (which was the port-side guess this module
        replaced). The ICON turns blue while armed (see ``_paint_icon``)
        and the tooltip carries the state off-Windows too.
        """
        self._armed = bool(armed)
        try:
            from qtranslate import tray_state as _TS
            _idx = _TS.select_state(bool(armed), bool(hook_installed))
            self._state = _TS.state_name(_idx)
        except Exception:
            self._state = "off"
        try:
            self.icon.setIcon(self._paint_icon(self._armed))
            self.icon.setToolTip(
                "QTranslate (mouse mode: %s)" % ("on" if armed else "off"))
        except Exception:
            pass

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


def _toggle_extension(ext_id, on):
    """Persist one extension's on/off switch (the tray submenu's writer)."""
    from qtranslate.extensions import (read_disabled_extensions,
                                       write_disabled_extensions)
    disabled = set(read_disabled_extensions())
    if on:
        disabled.discard(ext_id)
    else:
        disabled.add(ext_id)
    write_disabled_extensions(disabled)
