"""The events API and the Extensions page's settings editor.

The operator's push: "QTranslate full custom for the user". Two seams:

1. **Events** (``api.on``): a closed event list (``translation.done``,
   ``app.ready``); an unknown name is refused AT REGISTER TIME; a
   listener fires on the real emit point (``push_hist``, which every
   "a translation reached the UI" path funnels through) and a raising
   listener is skipped, never fatal.
2. **The settings editor**: an extension that declares a
   ``settings_schema`` gets a Settings button on the Extensions page;
   the dialog renders one field per key (bool/number/string), and Save
   writes every value through the manager's schema-checked
   ``set_setting`` -- full customisation without hand-editing JSON.

Offscreen; the studio example provides the schema; the history file and
Options.json go to temp dirs.
"""
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import engine, registry as RG             # noqa: E402
from qtranslate import extensions as _X                   # noqa: E402
from qtranslate.extensions import (last_manager,          # noqa: E402
                                   load_user_extensions)
import qtranslate.config as _config                       # noqa: E402
import qtranslate.qt.app as _appmod                       # noqa: E402

_TABLES = ("TRANSLATORS", "DICT_EXT", "TTS_EXT", "OCR_EXT", "SPELL_EXT",
           "WORKFLOW_EXT")
_ORIG = {t: dict(getattr(RG, t)) for t in _TABLES}

root = tempfile.mkdtemp(prefix="qt_evset_")
CFG = os.path.join(root, "Options.json")
io.open(CFG, "w", encoding="utf-8").write("{}")
_saved_default = _config.DEFAULT_PATH
_config.DEFAULT_PATH = CFG
_saved_hist = _appmod.HISTORY_PATH
_appmod.HISTORY_PATH = os.path.join(root, "History.json")

try:
    ext_dir = os.path.join(root, "extensions")
    os.makedirs(ext_dir)
    shutil.copytree(os.path.join(ROOT, "examples", "extensions", "studio"),
                    os.path.join(ext_dir, "studio"))
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["builtin"] = lambda t, s, g: "BUILTIN:" + t
    RG.reset_router()
    load_user_extensions(extensions_dir=ext_dir)
    mgr = last_manager()
    ck("studio loaded for the events/settings legs",
       any(r.get("id") == "ext.examples.studio" and r["status"] == "loaded"
           for r in mgr._last_report), str(mgr._last_report)[:160])

    # --- 1. the events API ----------------------------------------------
    ck("the closed event list is what the docs say",
       set(_X.KNOWN_EVENTS) == {"translation.done", "app.ready"},
       str(sorted(_X.KNOWN_EVENTS)))
    got = []
    mgr.add_listener("ext.examples.studio", "translation.done",
                     lambda p: got.append(p))
    app = None
    try:
        from qtranslate.qt.app import QtApp
        from qtranslate.qt.main_window import MainWindow
        app = QtApp([])
        app._load_session()
        app.source, app.target = "en", "vi"
        app.ext_manager = mgr
        app.win = MainWindow(app)
    except Exception as exc:                # noqa: BLE001
        ck("the offscreen app builds", False, repr(exc))
        raise SystemExit(1)

    app.push_hist("google", "hello", "xin chào")
    ck("translation.done fires with the finished payload",
       got and got[-1] == {"provider": "google", "text": "hello",
                           "result": "xin chào", "ok": True},
       str(got))

    # a raising listener is skipped, the next one still runs
    seen = []
    mgr.add_listener("ext.examples.studio", "translation.done",
                     lambda p: 1 / 0)
    mgr.add_listener("ext.examples.studio", "translation.done",
                     lambda p: seen.append(p.get("text")))
    app.push_hist("google", "second", "xin chào lần hai")
    ck("a raising listener is skipped, the next still runs",
       seen == ["second"], str(seen))

    try:
        mgr.add_listener("ext.examples.studio", "made.up.event", print)
        ck("an unknown event is refused", False, "no ValueError")
    except ValueError:
        ck("an unknown event is refused", True)
    try:
        mgr.add_listener("ext.examples.studio", "translation.done", 42)
        ck("a non-callable listener is refused", False, "no TypeError")
    except TypeError:
        ck("a non-callable listener is refused", True)

    # the studio extension's OWN listener counted the pushes (cross-module)
    panel = mgr.ui_slots.winner("panel", "top")
    text = panel["contribution"]()
    ck("studio's api.on listener counted both translations",
       "2 translations" in text, repr(text)[:120])

    # --- 2. the settings editor ------------------------------------------
    from PySide6.QtWidgets import (QCheckBox, QLineEdit, QSpinBox)
    schema = mgr._manifests["ext.examples.studio"]["settings_schema"]
    ck("studio declares three settings",
       set(schema) == {"Studio.Greeting", "Studio.Title",
                       "Studio.MaxWords"}, str(sorted(schema)))

    # the page shows a Settings button for the schema'd extension
    from qtranslate.qt.options import PAGES
    page = PAGES["Extensions"](app)
    page.show()
    page._goto("Extensions")
    app.qapp.processEvents()
    from PySide6.QtWidgets import QPushButton
    btns = [b for b in page.findChildren(QPushButton)
            if b.text() == "Settings…"]
    ck("the schema'd extension row got a Settings button",
       len(btns) == 1, str(len(btns)))

    # the dialog: fields render per kind, Save writes through the gate
    from qtranslate.qt.options.extensions import (_build_settings_dialog,
                                                  _save_settings)
    dlg, editors, mgr2 = _build_settings_dialog(
        page, "ext.examples.studio", schema)
    ck("the settings dialog built for the schema", dlg is not None)
    ck("one editor per schema key, right kinds",
       set(editors) == set(schema)
       and isinstance(editors["Studio.Greeting"][1], QLineEdit)
       and isinstance(editors["Studio.Title"][1], QLineEdit)
       and isinstance(editors["Studio.MaxWords"][1], QSpinBox),
       str({k: type(v).__name__ for k, v in editors.items()}))
    editors["Studio.Greeting"][1].setText("★")
    editors["Studio.MaxWords"][1].setValue(7)
    _save_settings(dlg, editors, mgr2, "ext.examples.studio")
    ck("Save persisted the string",
       mgr.get_setting("ext.examples.studio", "Studio.Greeting", None)
       == "★")
    ck("Save persisted the number",
       mgr.get_setting("ext.examples.studio", "Studio.MaxWords", None)
       == 7)
    ck("Save respected the schema gate (no undeclared key written)",
       "Undeclared" not in
       (json.load(io.open(CFG, encoding="utf-8"))
        .get("Extensions", {}).get("Settings", {})
        .get("ext.examples.studio", {})))

    # the change flows through the provider module (cross-module, again)
    res = engine.translate("studio.glossary", "thank you", "vi", src="en")
    ck("the edited greeting reaches the provider",
       res.ok and res.text.startswith("★"), repr(res.text)[:60])
    page.close()
    app.win.close()
finally:
    _config.DEFAULT_PATH = _saved_default
    _appmod.HISTORY_PATH = _saved_hist
    for t, orig in _ORIG.items():
        getattr(RG, t).clear()
        getattr(RG, t).update(orig)
    RG.reset_router()
    shutil.rmtree(root, ignore_errors=True)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_extension_events_settings_ui: all checks ok (%d assertions)"
      % n[0])
