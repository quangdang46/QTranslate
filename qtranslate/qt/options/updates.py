"""The Updates page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

WIRED: the checkbox writes ``Update.CheckForUpdates``; "Check now"
runs a real update check against the project's GitHub Releases feed
(``qtranslate.update_check``, ported from the upstream Kotlin
``Updater.kt``) on a worker thread and reports the result —
up-to-date, a new version with its release notes, or the error — in a
message box. The UI thread never blocks on the network.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from qtranslate import update_check

from .base import OptionsBase, cfg_section, cfg_set, check, panel, \
    button


class _UpdateBridge(QObject):
    """Marshals the worker thread's check result onto the UI thread.

    Emitting ``result`` from the daemon thread lands in the slot as a
    queued call because this object was created on the UI thread —
    the same pattern ``QtApp.invoke`` uses for background work.
    """

    result = Signal(dict)


class UpdatesPage(OptionsBase):
    SEL = 8

    def build(self):
        upd = cfg_section("Update")
        check(self, 161, 44, "Automatically check for updates",
              bool(upd.get("CheckForUpdates", True))
              ).toggled.connect(
            lambda v: cfg_set("Update", "CheckForUpdates", bool(v)))
        panel(self, 153, 63, 481, 230)
        if not hasattr(self, "_update_bridge"):
            self._update_bridge = _UpdateBridge()
            # cls.build(self) runs with the SHELL as self, so the
            # result slot must be a closure -- a bound UpdatesPage
            # method does not exist on the shell's class.
            self._update_bridge.result.connect(
                lambda res: _show_result(self, res))
        b = button(self, 524, 300, 110, "Check now")
        self._check_btn = b
        b.clicked.connect(lambda _checked=False: _check_now(self))


def _check_now(shell):
    btn = getattr(shell, "_check_btn", None)
    if btn is not None:
        btn.setEnabled(False)
        btn.setText("Checking…")
    bridge = shell._update_bridge

    def work():
        # Never raises: check_for_update maps every failure to an
        # "error" result the UI can show.
        bridge.result.emit(update_check.check_for_update())

    threading.Thread(target=work, daemon=True,
                     name="qtranslate-update-check").start()


def _show_result(shell, res):
    btn = getattr(shell, "_check_btn", None)
    if btn is not None:
        btn.setEnabled(True)
        btn.setText("Check now")
    # The dialog itself lives in update_check so the tray's manual
    # check and the startup auto-check show the same thing; `shell`
    # keeps the old parenting (the Options dialog).
    update_check.show_update_result(shell, res)
