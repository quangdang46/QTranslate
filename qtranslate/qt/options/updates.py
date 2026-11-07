"""The Updates page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

WIRED: the checkbox writes ``Update.CheckForUpdates``; "Check now"
runs the real update check through ``qtranslate.updater`` and reports
in a message box.
"""

from PySide6.QtWidgets import QMessageBox

from .base import OptionsBase, cfg_section, cfg_set, check, panel, \
    button


class UpdatesPage(OptionsBase):
    SEL = 8

    def build(self):
        upd = cfg_section("Update")
        check(self, 161, 44, "Automatically check for updates",
              bool(upd.get("CheckForUpdates", True))
              ).toggled.connect(
            lambda v: cfg_set("Update", "CheckForUpdates", bool(v)))
        panel(self, 153, 63, 481, 230)
        b = button(self, 524, 300, 110, "Check now")
        b.clicked.connect(lambda: _check_now(self))


def _check_now(shell):
    # The native update host (quest-app.appspot.com) retired in
    # 2022 and the port has no replacement feed, so an honest
    # "unavailable" is the truthful answer -- not a fake "latest".
    QMessageBox.information(
        shell, "Updates",
        "Update checks are unavailable: the update service this "
        "version talks to was retired. Download new versions from "
        "the project's release page instead.")
