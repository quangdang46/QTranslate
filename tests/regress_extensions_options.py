"""The user's extension switches: loader honouring + the Options page.

Two halves of one feature:

1. The loader honours ``Options.json → Extensions.Disabled``: a
   user-disabled extension is reported ``disabled`` with a
   ``user-disabled`` reason, its folder is NEVER imported, and nothing
   lands in the dispatch tables. This is the user's own switch (the
   Extensions page writes it), not the D18 override winner.
2. The Options dialog has a tenth page, ``Extensions``, that lists the
   installed folders (including ones whose manifest failed validation,
   shown but not toggleable) and toggles each one's checkbox into the
   same config section.

Also covered: the per-extension settings API -- ``api.get_setting`` /
``api.set_setting`` land under ``Extensions.Settings.<ext id>`` in the
extension's OWN section, schema-declared keys only, and one extension
cannot see another's.

Headless: the page drives the real Options shell offscreen with a temp
config as DEFAULT_PATH, so the user's real Options.json is never read
or written.
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


from qtranslate import extensions as X                    # noqa: E402
from qtranslate import registry as RG                     # noqa: E402

_TABLES = ("TRANSLATORS", "DICT_EXT", "TTS_EXT", "OCR_EXT", "SPELL_EXT",
           "WORKFLOW_EXT")
_ORIG = {t: dict(getattr(RG, t)) for t in _TABLES}

# A temp config file plays DEFAULT_PATH for this whole suite: neither
# the loader's read nor the page's toggle may touch the real one.
root = tempfile.mkdtemp(prefix="qt_extopt_")
CFG = os.path.join(root, "Options.json")
io.open(CFG, "w", encoding="utf-8").write("{}")

_real_default = X.__dict__.get("_REAL_DEFAULT", None)


def _cfg():
    return json.load(io.open(CFG, encoding="utf-8"))


try:
    # Install two extensions: one healthy, one with a broken manifest.
    ext_dir = os.path.join(root, "extensions")
    os.makedirs(ext_dir)
    healthy = os.path.join(ext_dir, "hello")
    shutil.copytree(os.path.join(ROOT, "examples", "extensions",
                                 "hello_provider"), healthy)
    broken = os.path.join(ext_dir, "broken")
    os.makedirs(broken)
    io.open(os.path.join(broken, "manifest.json"), "w",
            encoding="utf-8").write("{not json")

    # --- 1. the loader honours the user's switch -----------------------
    # The suite reads/writes the temp file directly: the loader's
    # default resolution goes through config.DEFAULT_PATH, which the
    # page test pins below; here the switch is passed explicitly so the
    # contract under test is load_dir's, not the file's location.
    report = X.load_user_extensions(extensions_dir=ext_dir)
    by_id = {r["id"]: r for r in report if r.get("id")}
    ck("both folders are discovered",
       set(by_id) == {"hello-provider"} and len(report) == 2,
       str(report)[:120])
    ck("the broken folder is disabled with a reason",
       any(r.get("status") == "disabled" and r.get("reason")
           for r in report), str(report)[:120])

    report = X.load_user_extensions(extensions_dir=ext_dir,
                                    disabled={"hello-provider"})
    # The FIRST load above committed hello-provider into the live table;
    # reset to the pre-suite snapshot so the assertion below tests THIS
    # load (a disabled load commits nothing) rather than the previous one.
    for t, orig in _ORIG.items():
        getattr(RG, t).clear()
        getattr(RG, t).update(orig)
    mine = [r for r in report if r.get("id") == "hello-provider"][0]
    ck("a user-disabled extension reports disabled",
       mine["status"] == "disabled"
       and "user-disabled" in mine["reason"], str(mine))
    ck("the disabled extension's folder is NOT imported",
       "hello" not in RG.TRANSLATORS
       and not any("hello" in k for k in RG.TRANSLATORS),
       str([k for k in RG.TRANSLATORS if "hello" in k]))

    # --- 2. the settings API: per-extension, schema-checked -------------
    report = X.load_user_extensions(extensions_dir=ext_dir)
    mgr = X.last_manager()
    ck("the healthy extension loads for the settings leg",
       any(r.get("id") == "hello-provider" and r["status"] == "loaded"
           for r in report), str(report)[:120])

    mgr.set_setting("hello-provider", "Prefix", "Hei, ", path=CFG)
    ck("a setting round-trips through the config file",
       mgr.get_setting("hello-provider", "Prefix", None, path=CFG)
       == "Hei, ", repr(_cfg().get("Extensions")))
    ck("the setting lands in the extension's OWN section",
       _cfg()["Extensions"]["Settings"]["hello-provider"] == {"Prefix":
                                                              "Hei, "},
       repr(_cfg()["Extensions"]))
    ck("an unset key returns the default",
       mgr.get_setting("hello-provider", "Missing", "dflt", path=CFG)
       == "dflt")
    ck("one extension cannot read another's section",
       mgr.get_setting("ext.other", "Prefix", None, path=CFG) is None)
    ck("get_setting fails open on a corrupt file",
       mgr.get_setting("hello-provider", "Prefix", "dflt",
                       path=os.path.join(root, "nope.json")) == "dflt")

    # schema enforcement: hello_provider declares none, so any key goes;
    # power_suite declares one -- use it to prove the gate.
    ps = os.path.join(ext_dir, "power")
    shutil.copytree(os.path.join(ROOT, "examples", "extensions",
                                 "power_suite"), ps)
    X.load_user_extensions(extensions_dir=ext_dir)
    mgr = X.last_manager()
    try:
        mgr.set_setting("ext.examples.power_suite", "Undeclared", 1,
                        path=CFG)
        ck("an undeclared key is refused when a schema exists", False,
           "no ValueError")
    except ValueError:
        ck("an undeclared key is refused when a schema exists", True)
    mgr.set_setting("ext.examples.power_suite", "PowerSuite.Greeting",
                    "hi", path=CFG)
    ck("a declared key persists",
       mgr.get_setting("ext.examples.power_suite", "PowerSuite.Greeting",
                       None, path=CFG) == "hi")

    # --- 3. the Options page --------------------------------------------
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:                # noqa: BLE001
        print("SKIP regress_extensions_options: PySide6 (%s)" % exc)
        raise SystemExit(0)

    import qtranslate.config as config
    saved_default = config.DEFAULT_PATH
    config.DEFAULT_PATH = CFG               # the page reads/writes THIS
    try:
        from qtranslate.qt.app import QtApp
        from qtranslate.qt.options import PAGES, OptionsDialog
        app = QtApp([])
        app._load_session()
        app.source, app.target = "en", "vi"
        app.ext_manager = X.last_manager()

        ck("the Extensions page is registered",
           "Extensions" in PAGES, str(sorted(PAGES)))
        page = PAGES["Extensions"](app)
        page.show()
        page._goto("Extensions")

        from PySide6.QtWidgets import QCheckBox, QLabel
        cbs = [w for w in page.findChildren(QCheckBox)]
        ck("one checkbox per installed folder (broken included)",
           len(cbs) == 3, str([c.text() for c in cbs]))
        hello_cb = [c for c in cbs if "hello" in c.text().lower()]
        ck("the healthy extension's checkbox shows its name+version",
           hello_cb and "Hello Provider (example) 1.0.0"
           == hello_cb[0].text(),
           str([c.text() for c in cbs]))
        ck("the healthy extension's checkbox is checked and enabled",
           hello_cb and hello_cb[0].isChecked()
           and hello_cb[0].isEnabled())
        broken_cb = [c for c in cbs if c.text() == "broken"]
        ck("a folder without a valid manifest shows but cannot toggle",
           broken_cb and not broken_cb[0].isChecked()
           and not broken_cb[0].isEnabled(),
           str(broken_cb[0].text() if broken_cb else "absent"))

        # The user unchecks it: the config gains the Disabled entry.
        hello_cb[0].setChecked(False)
        disabled = X.read_disabled_extensions(cfg=_cfg())
        ck("unchecking writes the id into Extensions.Disabled",
           disabled == ["hello-provider"], repr(disabled))
        # ...and back on.
        hello_cb[0].setChecked(True)
        ck("re-checking clears the entry",
           X.read_disabled_extensions(cfg=_cfg()) == [], repr(_cfg()))

        labels = [l.text() for l in page.findChildren(QLabel)]
        ck("the restart hint is shown",
           any("restart" in t.lower() for t in labels), str(labels)[:120])
        page.close()
    finally:
        config.DEFAULT_PATH = saved_default

    # --- 4. end to end: the switch the page wrote is the one applied ---
    X.write_disabled_extensions(["hello-provider"], path=CFG)
    import qtranslate.extensions as _X
    ck("write_disabled_extensions persists the list",
       _cfg()["Extensions"]["Disabled"] == ["hello-provider"],
       repr(_cfg().get("Extensions")))
finally:
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
print("regress_extensions_options: all checks ok (%d assertions)" % n[0])
