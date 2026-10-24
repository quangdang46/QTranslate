"""The Extensions page of the Options dialog.

This page is the PORT'S OWN addition, not a native page: native has nine
Options pages and no extension system, so there is no capture to measure
and the numbers below follow the sibling pages' grid (a full-width panel
like Services', the same row pitch) instead of pretending otherwise.

What it shows: every extension folder discovered under the per-user
extensions directory (D16), with its manifest's name and version, its
load status, and ONE checkbox per extension -- the user's own on/off
switch. Unchecking writes ``Extensions.Disabled`` in Options.json
(``write_disabled_extensions``) and the loader skips the folder on the
next start: no code imported, no dispatch table written. A change takes
effect after QTranslate restarts; the page says so rather than pretending
it applied live.
"""

import os
import sys

from PySide6.QtWidgets import QLabel

from qtranslate_style import DIM, FACE, TEXT

from .base import OptionsBase, button, check, hline, label, panel, rect
from ..widgets import HEADING, HEADING_LINE, put
from qtranslate.extensions import (discover_manifests, read_disabled_extensions,
                                   write_disabled_extensions)


class ExtensionsPage(OptionsBase):
    SEL = 9

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        # The list view's scrollbar track, as Services' page draws it.
        rect(lst, 619, 32, 16, 270, FACE)
        label(lst, 167, 42, "Installed extensions", color=HEADING, size=12)
        hline(lst, 42, 320, 608, HEADING_LINE)

        rows = self._scan()
        if not rows:
            q = QLabel("No extensions found in the per-user folder.")
            q.setStyleSheet("QLabel{color:%s;}" % DIM)
            put(lst, q, 167, 60, 440, 16)
        y = 60
        for row in rows:
            # A folder with no valid id cannot be "on": there is nothing
            # the loader would load even with the box ticked.
            on = row["known"] and row["id"] not in self._disabled()
            c = check(lst, 167, y + 8, row["label"], on=on)
            # A folder whose manifest failed validation has no id, so
            # there is nothing to switch -- the checkbox is disabled and
            # the status column says why.
            c.setEnabled(row["known"])
            c.stateChanged.connect(
                lambda st, rid=row["id"]: self._toggle(rid, bool(st)))
            q = QLabel(row["status"])
            q.setStyleSheet("QLabel{color:%s;}" % (DIM if on else TEXT))
            put(lst, q, 460, y, 165, 14)
            y += 20
        if rows:
            hint = QLabel("Changes take effect after QTranslate restarts.")
            hint.setStyleSheet("QLabel{color:%s;}" % DIM)
            put(lst, hint, 167, y + 8, 440, 14)
        button(self, 524, 313, 110, "Open folder").clicked.connect(
            self._open_folder)

    # ------------------------------------------------------------------
    def _scan(self):
        """The extension folders, as the page shows them.

        Each row: the manifest's display label (or the folder's name
        when the manifest is unreadable), its id, and the status the
        loader reported for it this session when the app has a manager
        -- otherwise just the folder.
        """
        report = {}
        ext_dir = None
        app_mgr = getattr(self.app, "ext_manager", None)
        if app_mgr is not None:
            ext_dir = getattr(app_mgr, "_extensions_dir", None)
            report = {os.path.basename(r.get("path") or ""): r
                      for r in getattr(app_mgr, "_last_report", [])}
        rows = []
        for path, manifest in discover_manifests(ext_dir):
            name = folder = os.path.basename(path)
            ext_id = None
            if isinstance(manifest, dict):
                ext_id = manifest.get("id")
                name = "%s %s" % (manifest.get("name", folder),
                                  manifest.get("version", ""))
            r = report.get(folder) or {}
            if r.get("status") == "loaded":
                status = "loaded"
            elif r.get("reason"):
                status = str(r["reason"])[:38]
            else:
                status = folder
            rows.append({"id": ext_id, "label": name.strip(),
                         "status": status, "known": bool(ext_id)})
        return rows

    @staticmethod
    def _disabled():
        return set(read_disabled_extensions())

    @staticmethod
    def _toggle(ext_id, on):
        """One checkbox flipped: rewrite the Disabled list."""
        if not ext_id:
            return
        disabled = set(read_disabled_extensions())
        if on:
            disabled.discard(ext_id)
        else:
            disabled.add(ext_id)
        write_disabled_extensions(disabled)

    @staticmethod
    def _open_folder():
        try:
            from qtranslate.platforms import current
            d = current().extensions_dir()
        except Exception:                   # noqa: BLE001
            return
        os.makedirs(d, exist_ok=True)
        if os.name == "nt":
            os.startfile(d)                 # noqa: S606
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin"
                              else "xdg-open", d])
