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

The helpers below are MODULE-LEVEL functions, not methods of the page
class: the shell runs each page's ``build`` with the SHELL instance as
``self`` (a BasicsPage), so anything ``build`` calls must not depend on
the page class -- the other pages' builds only use OptionsBase's own
methods, and this one follows the same rule through free functions.
"""

import os
import sys

from PySide6.QtWidgets import QLabel

from qtranslate_style import DIM, FACE, TEXT

from .base import OptionsBase, button, check, hline, label, panel, rect
from ..widgets import HEADING, HEADING_LINE, put
from qtranslate.extensions import (discover_manifests, read_disabled_extensions,
                                   write_disabled_extensions)


def _open_folder():
    """The page's 'Open folder' button: the per-user extensions dir."""
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


def _disabled():
    return set(read_disabled_extensions())


def _open_settings(page, ext_id, schema):
    """The Settings button: build the dialog, exec it, save on accept."""
    dlg, editors, mgr = _build_settings_dialog(page, ext_id, schema)
    if dlg is None:
        return
    from PySide6.QtWidgets import QDialogButtonBox
    bb = dlg.findChildren(QDialogButtonBox)[0]
    bb.accepted.connect(lambda: _save_settings(dlg, editors, mgr, ext_id))
    bb.rejected.connect(dlg.reject)
    dlg.exec()


def _build_settings_dialog(page, ext_id, schema):
    """The schema renders as one editor per key (bool→checkbox,
    number→spin, else→line edit). Returns (dialog, editors, manager);
    split from ``_open_settings`` so a test can drive the fields
    without exec()ing a modal."""
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout,
                                   QLabel, QLineEdit, QSpinBox,
                                   QVBoxLayout)
    mgr = page.app.ext_manager
    dlg = QDialog(page)
    dlg.setWindowTitle("%s settings" % ext_id.rsplit(".", 1)[-1])
    lay = QVBoxLayout(dlg)
    grid = QGridLayout()
    editors = {}
    for r, (key, kind) in enumerate(sorted(schema.items())):
        grid.addWidget(QLabel(key.rsplit(".", 1)[-1]), r, 0)
        current = mgr.get_setting(ext_id, key, None)
        if kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(current))
        elif kind == "number":
            w = QSpinBox()
            w.setRange(-10 ** 6, 10 ** 6)
            if isinstance(current, (int, float)):
                w.setValue(int(current))
        else:                               # "string" and anything unknown
            w = QLineEdit()
            if current is not None:
                w.setText(str(current))
        editors[key] = (kind, w)
        grid.addWidget(w, r, 1)
    lay.addLayout(grid)
    note = QLabel("Applied the next time the extension reads it.")
    note.setStyleSheet("QLabel{color:%s;}" % DIM)
    lay.addWidget(note)
    bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
    lay.addWidget(bb)
    return dlg, editors, mgr


def _save_settings(dlg, editors, mgr, ext_id):
    """Collect the editors and write each through the schema-checked
    set_setting; a refused key is skipped, not fatal."""
    for key, (kind, w) in editors.items():
        if kind == "bool":
            value = bool(w.isChecked())
        elif kind == "number":
            value = w.value()
        else:
            value = w.text()
        try:
            mgr.set_setting(ext_id, key, value)
        except Exception:                   # noqa: BLE001 -- schema gate
            pass
    dlg.accept()


def _toggle(ext_id, on):
    """One checkbox flipped: rewrite the whole Disabled list."""
    if not ext_id:
        return
    disabled = _disabled()
    if on:
        disabled.discard(ext_id)
    else:
        disabled.add(ext_id)
    write_disabled_extensions(disabled)


def _scan(page):
    """The extension folders, as the page shows them.

    Each row: the manifest's display label (or the folder's name when
    the manifest is unreadable), its id, and the status the loader
    reported for it this session when the app has a manager -- otherwise
    just the folder.
    """
    report = {}
    ext_dir = None
    app_mgr = getattr(page.app, "ext_manager", None)
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


class ExtensionsPage(OptionsBase):
    SEL = 9

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        # The list view's scrollbar track, as Services' page draws it.
        rect(lst, 619, 32, 16, 270, FACE)
        label(lst, 167, 42, "Installed extensions", color=HEADING, size=12)
        hline(lst, 42, 320, 608, HEADING_LINE)

        rows = _scan(self)
        if not rows:
            q = QLabel("No extensions found in the per-user folder.")
            q.setStyleSheet("QLabel{color:%s;}" % DIM)
            put(lst, q, 167, 60, 440, 16)
        y = 60
        mgr = getattr(getattr(self.app, "ext_manager", None),
                      "_manifests", {}) or {}
        for row in rows:
            # A folder with no valid id cannot be "on": there is nothing
            # the loader would load even with the box ticked.
            on = row["known"] and row["id"] not in _disabled()
            c = check(lst, 167, y + 8, row["label"], on=on)
            c.setEnabled(row["known"])
            c.stateChanged.connect(
                lambda st, rid=row["id"]: _toggle(rid, bool(st)))
            q = QLabel(row["status"])
            q.setStyleSheet("QLabel{color:%s;}" % (DIM if on else TEXT))
            put(lst, q, 450, y, 100, 14)
            # An extension that declared a settings_schema gets a
            # Settings button: the schema's fields render in a small
            # dialog and Save writes them through the manager's
            # schema-checked set_setting. Full customisation without
            # hand-editing a JSON file.
            schema = (mgr.get(row["id"], {}) or {}).get("settings_schema")
            if row["known"] and isinstance(schema, dict) and schema:
                b = button(lst, 554, y - 1, 62, "Settings…")
                b.clicked.connect(
                    lambda _c=False, rid=row["id"], sch=schema:
                    _open_settings(self, rid, sch))
            y += 22
        if rows:
            hint = QLabel("Changes take effect after QTranslate restarts.")
            hint.setStyleSheet("QLabel{color:%s;}" % DIM)
            put(lst, hint, 167, y + 8, 440, 14)
        button(self, 524, 313, 110, "Open folder").clicked.connect(
            _open_folder)
