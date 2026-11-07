"""regress_extension_lifecycle -- live enable/disable for extensions.

The Options -> Extensions checkbox used to need a restart: it wrote
``Extensions.Disabled`` and the loader skipped the folder next boot.
``ExtensionManager.disable``/``enable`` now apply the switch to the
running process. This suite pins, against an isolated fake registry:

  * every surface an extension can write is attributed to its id
    (provider, replaces, theme, the five dispatch tables, listeners,
    UI slot contributions),
  * ``disable`` removes exactly those entries and rebuilds TRANSLATORS
    back to the built-in baseline,
  * ``enable`` re-runs the fail-open loader and the provider serves
    again,
  * a ``replaces`` override restores the built-in on disable,
  * unknown ids fail honestly (False / None).
"""
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate.extensions import ExtensionManager  # noqa: E402
from qtranslate import registry as real_registry  # noqa: E402


class FakeReg:
    """Isolated stand-in for qtranslate.registry: same attribute names,
    no global state."""

    def __init__(self):
        self._google = lambda *a: "google"
        self._ms = lambda *a: "ms"
        self.TRANSLATORS = {"google": self._google,
                            "microsoft": self._ms,
                            "bing": self._ms}
        self.DICT_EXT = {}
        self.TTS_EXT = {}
        self.OCR_EXT = {}
        self.SPELL_EXT = {}
        self.WORKFLOW_EXT = {}
        self.router_reset = 0

    def reset_router(self):
        self.router_reset += 1


def manifest(ext_id, caps, **overrides):
    base = {"id": ext_id, "name": ext_id + " display", "version": "0.1.0",
            "sdk_version": "1.0", "entrypoint": "__init__:register",
            "capabilities": caps}
    base.update(overrides)
    return base


def write_ext(root, name, man, source):
    folder = os.path.join(root, name)
    os.makedirs(folder)
    with io.open(os.path.join(folder, "manifest.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(man))
    with io.open(os.path.join(folder, "__init__.py"), "w",
                 encoding="utf-8") as fh:
        fh.write(source)
    return folder


def _raises_value(fn):
    try:
        fn()
        return False
    except ValueError:
        return True
    except Exception:
        return False


root = tempfile.mkdtemp(prefix="qt_lifecycle_")
try:
    SRC = (
        "def register(api):\n"
        "    api.register_provider('ext.p', lambda t, s, g: 'P')\n"
        "    api.register_theme('ext.theme', {'Common': {'x': 1}})\n"
        "    api.register_dictionary('ext.dict',\n"
        "                           lambda w, s, t: 'D')\n"
        "    api.register_ui('menu', 'tray', lambda: 'ui')\n"
        "    api.on('app.ready', lambda p: None)\n"
    )
    folder = write_ext(
        root, "ext_a",
        manifest("ext.a", ["provider", "theme", "ui", "dictionary"]),
        SRC)

    reg = FakeReg()
    m = ExtensionManager(reg)
    report = m.load_dir(root)
    ck("extension loads", report[0]["status"] == "loaded", str(report))
    m.commit(reg)

    # ---- everything is live before the toggle -------------------------
    ck("provider committed to TRANSLATORS", "ext.p" in reg.TRANSLATORS)
    ck("dict table written", "ext.dict" in reg.DICT_EXT)
    ck("theme registered", "ext.theme" in m.themes())
    ck("listener registered",
       any(e == "ext.a" for e, _f in m._listeners.get("app.ready", [])))
    ui = m.ui_slots
    ck("ui slot has owner-tagged entry",
       ui is not None and any(
           e.get("owner") == "ext.a"
           for e in ui.entries("menu", "tray")))
    ck("folder remembered for re-enable",
       m._ext_folders.get("ext.a") == folder)

    # ---- disable --------------------------------------------------------
    ck("disable known id", m.disable("ext.a") is True)
    ck("provider gone from TRANSLATORS", "ext.p" not in reg.TRANSLATORS)
    ck("dict table cleaned", "ext.dict" not in reg.DICT_EXT)
    ck("theme gone", "ext.theme" not in m.themes())
    ck("listener gone",
       not any(e == "ext.a" for e, _f in m._listeners.get("app.ready", [])))
    ck("ui contribution gone",
       not any(e.get("owner") == "ext.a"
               for e in (m.ui_slots.entries("menu", "tray")
                         if m.ui_slots else [])))
    ck("built-ins survive the rebuild",
       reg.TRANSLATORS.get("google") is reg._google
       and reg.TRANSLATORS.get("microsoft") is reg._ms
       and reg.TRANSLATORS.get("bing") is reg._ms)
    ck("router cache reset on rebuild", reg.router_reset >= 1)

    # ---- enable ----------------------------------------------------------
    out = m.enable("ext.a", saved={}, disabled=set())
    ck("enable re-loads the extension",
       out is not None and out.get("status") == "loaded", str(out))
    ck("provider back in TRANSLATORS", "ext.p" in reg.TRANSLATORS)
    ck("dict table back", "ext.dict" in reg.DICT_EXT)
    ck("listener back",
       any(e == "ext.a" for e, _f in m._listeners.get("app.ready", [])))
    ck("ui contribution back with owner",
       any(e.get("owner") == "ext.a"
           for e in m.ui_slots.entries("menu", "tray")))

    # ---- a replaces override restores the built-in ----------------------
    write_ext(
        root, "ext_b",
        manifest("ext.b", ["provider"], replaces=["google"]),
        "def register(api):\n"
        "    api.register_provider('ext.b', lambda t, s, g: 'B',\n"
        "                          replaces='google')\n")
    # reload the whole dir so ext.b registers too
    m2 = ExtensionManager(FakeReg())
    reg2 = m2._rg
    m2.load_dir(root)
    m2.commit(reg2)
    ck("override wins while enabled",
       reg2.TRANSLATORS.get("google") is not reg2._google)
    ck("ext.b disable restores built-in google",
       m2.disable("ext.b") is True
       and reg2.TRANSLATORS.get("google") is reg2._google)

    # ---- honest failures --------------------------------------------------
    ck("disable unknown id is False", m.disable("ext.nope") is False)
    ck("enable unknown id is None", m.enable("ext.nope") is None)

    # ---- install_folder (PluginsPanel install action) ---------------------
    src_root = tempfile.mkdtemp(prefix="qt_extsrc_")
    dst_root = tempfile.mkdtemp(prefix="qt_extdst_")
    try:
        src = write_ext(
            src_root, "ext_c",
            manifest("ext.c", ["provider"]),
            "def register(api):\n"
            "    api.register_provider('ext.c', lambda t, s, g: 'C')\n")
        reg3 = FakeReg()
        m3 = ExtensionManager(reg3)
        m3._extensions_dir = dst_root
        m3.load_dir(dst_root)          # sets _extensions_dir + baseline
        out = m3.install_folder(src, importer=None)
        ck("install loads the extension",
           out.get("status") == "loaded", str(out))
        ck("install copied the folder",
           os.path.isdir(os.path.join(dst_root, "ext_c"))
           and os.path.isfile(os.path.join(
               dst_root, "ext_c", "manifest.json")))
        ck("installed provider committed",
           "ext.c" in reg3.TRANSLATORS)
        ck("install is idempotent-guarded",
           _raises_value(lambda: m3.install_folder(src)))
        bad = os.path.join(src_root, "bad")
        os.makedirs(bad)
        try:
            m3.install_folder(bad)
            ck("bad manifest refused", False)
        except Exception:
            ck("bad manifest refused", True)
        ck("refused install copied nothing",
           not os.path.exists(os.path.join(dst_root, "bad")))
    finally:
        import shutil
        shutil.rmtree(src_root, ignore_errors=True)
        shutil.rmtree(dst_root, ignore_errors=True)
finally:
    import shutil
    shutil.rmtree(root, ignore_errors=True)

if fails:
    print("FAIL %d/%d" % (len(fails), n[0]))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_extension_lifecycle: all checks ok (%d assertions)" % n[0])
