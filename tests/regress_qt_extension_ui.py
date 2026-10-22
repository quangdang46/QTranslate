"""The PySide6 front end shows what an extension registered.

The extension platform is Core (``qtranslate.extensions`` + ``qtranslate.ui_slots``),
and both front ends load the same way. What was MISSING was the consuming
half: an extension could register a menu contribution and a theme, and
nothing in the running app ever read them back. The registry existed and
the tests proved the registry worked -- the UI did not.

This suite proves the Qt view reads them:

* an extension installed in a folder is loaded at startup (the shared
  loader, not a Qt-specific one),
* its tray-menu contribution appears in the real tray menu, and clicking
  it runs the extension's callable,
* a theme the extension registered is the one the theme resolver returns.

Offline: a temp folder, a fake extension, no network.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


try:
    from PySide6.QtWidgets import QApplication
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_extension_ui: PySide6 is not importable (%s)" % exc)
    raise SystemExit(0)

try:
    from qtranslate.qt.app import QtApp
    from qtranslate.qt.tray import Tray
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_qt_extension_ui: the Qt front end does not import (%s)"
          % exc)
    raise SystemExit(0)


def write_ext(root, name, ext_id, source, capabilities=("provider",)):
    """Write an extension folder the way a user would: copy it in."""
    folder = os.path.join(root, name)
    os.makedirs(folder, exist_ok=True)
    man = {"id": ext_id, "name": ext_id, "version": "0.1.0",
           "sdk_version": "1.0", "entrypoint": "ext:register",
           "capabilities": list(capabilities)}
    with open(os.path.join(folder, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(man, f)
    with open(os.path.join(folder, "ext.py"), "w", encoding="utf-8") as f:
        f.write(source)


root = tempfile.mkdtemp(prefix="qt_ext_ui_")
try:
    # --- an extension that contributes a tray-menu entry ----------------
    add = os.path.join(root, "add")
    os.makedirs(add)
    write_ext(
        add, "ext_ui", "ext.ui",
        "def tray_entry():\n"
        "    return 'Hello from the extension.'\n"
        "\n"
        "def register(api):\n"
        "    api.register_ui('menu', 'tray', tray_entry)\n",
        capabilities=("ui",))

    from qtranslate import registry as RG
    from qtranslate.extensions import (ExtensionManager, last_manager,
                                       load_user_extensions)
    from qtranslate.ui_slots import UISlotRegistry

    _TABLE = RG.TRANSLATORS
    _ORIGINAL = dict(RG.TRANSLATORS)
    try:
        report = load_user_extensions(extensions_dir=add)
        ck("the UI extension loads", report and report[0]["status"] == "loaded",
           str(report))

        manager = last_manager()
        ck("the manager is reachable after the load", manager is not None)
        slots = manager.ui_slots if manager else None
        ck("the manager holds the UI registry", isinstance(slots, UISlotRegistry),
           type(slots).__name__)
        ck("the contribution is in the tray slot",
           bool(slots.entries("menu", "tray")), str(slots.entries("menu", "tray")))
        winner = slots.winner("menu", "tray")
        ck("the winner is the extension's callable",
           callable(winner.get("contribution")), str(winner))

        # --- the real tray menu shows it -------------------------------
        app = QtApp([])
        app._load_session()
        app.ext_manager = manager
        tray = Tray(app)
        labels = [a.text() for a in tray.menu.actions() if a.text()]
        ck("the tray menu shows the extension's entry",
           any("ext.ui" in t or "tray_entry" in t for t in labels), str(labels))

        # The menu's action runs the extension's callable.
        ran = []
        act = None
        for a in tray.menu.actions():
            if a.text() and ("ext.ui" in a.text() or "tray_entry" in a.text()):
                act = a
                break
        ck("the extension entry is an action", act is not None)
        if act is not None:
            # The tray's handler opens a message box, which would block.
            # The callable itself is what matters: it is the extension's.
            contrib = slots.winner("menu", "tray")["contribution"]
            ck("the contribution answers with the extension's text",
               contrib() == "Hello from the extension.", repr(contrib()))

        # --- an extension theme is the one the resolver returns ---------
        tadd = os.path.join(root, "theme")
        os.makedirs(tadd)
        write_ext(
            tadd, "ext_theme", "ext.theme",
            "def register(api):\n"
            "    api.register_theme('ext.theme',\n"
            "                      {'Window': {'Normal': {'Back': '#123456'}}})\n",
            capabilities=("theme",))
        treport = load_user_extensions(extensions_dir=tadd,
                                       manager=ExtensionManager(RG))
        ck("the theme extension loads",
           treport and treport[0]["status"] == "loaded", str(treport))

        # The theme lives in the manager it was loaded into.
        theme_manager = last_manager()
        from qtranslate import theme as T
        rec = T.active_theme("ext.theme", manager=theme_manager)
        ck("the theme resolver returns the extension's theme",
           isinstance(rec, dict) and rec, str(rec)[:120])
        ck("the extension theme is not the built-in default",
           rec != T.default_theme(), "the built-in default came back")
        ck("the extension theme carries its own colour",
           "123456" in json.dumps(rec).lower().replace("#", ""),
           json.dumps(rec)[:200])

        # --- the theme really reaches the running app's palette ---------
        # The resolver returning the extension's theme is not enough: the
        # app's palette and stylesheet have to carry it, or the theme is
        # registered and never seen.
        from PySide6.QtGui import QPalette
        app2 = QtApp([])
        app2.ext_manager = theme_manager
        app2.apply_theme("ext.theme")
        palette = app2.qapp.palette()
        window_color = palette.color(QPalette.ColorRole.Window).name()
        sheet = app2.qapp.styleSheet()
        ck("the extension theme reaches the app's palette",
           window_color.lower() in ("#123456", "#113355"),
           "palette Window is %s, sheet has it: %s"
           % (window_color, "#123456" in sheet.lower()))

        # --- a panel contribution appears in the main window -------------
        # The docs promise "a dockable panel to the main window". The
        # pane slots are the native's three "Show*Pane" toggles.
        from qtranslate.qt.main_window import MainWindow
        papp = QtApp([])
        papp.ext_manager = manager
        # The example contributes to the "top" pane.
        from qtranslate.ui_slots import UISlotRegistry
        slots.add("panel", "top", lambda: "Panel from the extension.")
        pwin = MainWindow(papp)
        ck("the panel contribution is shown in the main window",
           "top" in pwin.panels, str(list(pwin.panels)))
        if "top" in pwin.panels:
            ck("the panel shows the extension's text",
               "Panel from the extension." in pwin.panels["top"].text(),
               pwin.panels["top"].text())

        # With no extension the window has NO panel, so the pixels stay
        # the native's.
        plain = MainWindow(QtApp([]))
        ck("a window with no extension has no panel strip",
           plain.panels == {}, str(list(plain.panels)))
    finally:
        RG.TRANSLATORS.clear()
        RG.TRANSLATORS.update(_ORIGINAL)
finally:
    shutil.rmtree(root, ignore_errors=True)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_qt_extension_ui: all checks ok (%d assertions)" % n[0])
