"""D18 pin: override winner persistence + saved-winner veto.

Covers the headless core of the override UI slice:

- ``read_saved_overrides`` / ``write_saved_overrides`` round-trip the winner
  selection through Options.json (dict path + file path).
- A saved winner pre-empts discovery-order conflict resolution: an extension
  claiming the same provider — by the same id or an alias — is disabled with
  a "saved winner" reason.
- ``load_user_extensions`` applies the saved winners at startup and clears a
  saved winner whose extension is no longer installed (built-in stays).
- ``override_conflicts`` merges alias-equivalent claims into one row.

The tkinter dialog itself is only structurally pinned (it opens no window on
import). Offline, no network, no window.
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import registry as RG
from qtranslate.extensions import (
    ExtensionManager, load_user_extensions, read_saved_overrides,
    write_saved_overrides)
import qtranslate.config as _C

_TABLE = RG.TRANSLATORS
_ORIGINAL = dict(RG.TRANSLATORS)


def restore():
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIGINAL)
    RG.reset_router()


def write_ext(root, folder, ext_id, source, replaces=None):
    folder_path = os.path.join(root, folder)
    os.makedirs(folder_path)
    man = {"id": ext_id, "name": ext_id, "version": "0.1.0",
           "sdk_version": "1.0", "entrypoint": "__init__:register",
           "capabilities": ["provider"]}
    if replaces:
        man["replaces"] = replaces
    with io.open(os.path.join(folder_path, "manifest.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(man))
    with io.open(os.path.join(folder_path, "__init__.py"), "w",
                 encoding="utf-8") as fh:
        fh.write(source)
    return folder_path


def replaces_src(provider, text, target):
    return ("def register(api):\n"
            "    api.register_provider(%r,\n"
            "                          lambda t, s, g: %r + t,\n"
            "                          replaces=%r)\n"
            % (provider, text, target))


# --- persistence: dict path (no file I/O) --------------------------------
ck("read returns the saved selection",
   read_saved_overrides(
       cfg={"ExtensionOverrides": {"microsoft": "ext.ms"}})
   == {"microsoft": "ext.ms"})
ck("read fails open on a non-dict section",
   read_saved_overrides(cfg={"ExtensionOverrides": 5}) == {})
ck("read fails open on no section",
   read_saved_overrides(cfg={}) == {})
ck("write merges into a config dict",
   write_saved_overrides({"google": "ext.g"},
                         cfg={"A": 1})["ExtensionOverrides"] == {"google": "ext.g"})
ck("write drops non-string/empty entries",
   write_saved_overrides({"": "x", "ok": 5, "g": "e"},
                         cfg={})["ExtensionOverrides"] == {"g": "e"})

# --- persistence: file path (config.load/save monkeypatched) -------------
_real_load, _real_save = _C.load, _C.save
_file = {"cur": {"ExtensionOverrides": {"microsoft": "ext.ms"}}}


def _load(path=None):
    return json.loads(json.dumps(_file["cur"]))


def _save(cfg, path=None):
    _file["cur"] = cfg


try:
    _C.load, _C.save = _load, _save
    ck("read from file", read_saved_overrides() == {"microsoft": "ext.ms"})
    write_saved_overrides({"google": "ext.g"})
    ck("write to file", _file["cur"]["ExtensionOverrides"] == {"google": "ext.g"})
    ck("read after write", read_saved_overrides() == {"google": "ext.g"})
finally:
    _C.load, _C.save = _real_load, _real_save

# --- saved-winner veto ---------------------------------------------------
_m = ExtensionManager()


def _fn(t, s, g):
    return "X"


_m.register("ext.bing", _fn, replaces="bing")
ck("veto: an alias-equivalent different winner",
   _m._saved_veto("ext.bing", ["bing"],
                 {"microsoft": "ext.ms"}) is not None)
ck("veto: the saved winner itself is not vetoed",
   _m._saved_veto("ext.ms", ["microsoft"],
                 {"microsoft": "ext.ms"}) is None)
ck("veto: no saved selection -> no veto",
   _m._saved_veto("ext.x", ["yandex"], {}) is None)

# --- load_dir with a saved winner ----------------------------------------
root = tempfile.mkdtemp(prefix="qt_ovrp_")
try:
    d = os.path.join(root, "exts")
    os.makedirs(d)
    write_ext(d, "a_ms", "ext.ms", replaces_src("ext.ms", "MS:", "microsoft"),
              replaces=["microsoft"])
    write_ext(d, "b_bing", "ext.bing", replaces_src("ext.bing", "B:", "bing"),
              replaces=["bing"])

    rep = ExtensionManager().load_dir(d)
    ck("alias conflict disables both without a saved winner",
       all(r["status"] == "disabled" for r in rep), str(rep))

    rep2 = ExtensionManager().load_dir(d, saved={"microsoft": "ext.ms"})
    by_id = {r["id"]: r for r in rep2}
    ck("the saved winner loads",
       by_id["ext.ms"]["status"] == "loaded", str(by_id["ext.ms"]))
    ck("the other claimant is vetoed with a reason",
       by_id["ext.bing"]["status"] == "disabled"
       and "saved winner" in by_id["ext.bing"]["reason"],
       str(by_id["ext.bing"]))

    m2 = ExtensionManager()
    m2.load_dir(d)
    ck("override_conflicts merges alias-equivalent claims",
       m2.override_conflicts() == {"microsoft": ["ext.ms", "ext.bing"]},
       str(m2.override_conflicts()))
finally:
    shutil.rmtree(root, ignore_errors=True)

# --- load_user_extensions applies saved winners + clears stale -----------
_file2 = {"cur": {"ExtensionOverrides": {"microsoft": "ext.ms"}}}


def _load2(path=None):
    return json.loads(json.dumps(_file2["cur"]))


def _save2(cfg, path=None):
    _file2["cur"] = cfg


try:
    _C.load, _C.save = _load2, _save2
    root2 = tempfile.mkdtemp(prefix="qt_ovru_")
    try:
        d2 = os.path.join(root2, "exts")
        os.makedirs(d2)
        write_ext(d2, "a_ms", "ext.ms",
                  replaces_src("ext.ms", "MS:", "microsoft"),
                  replaces=["microsoft"])
        write_ext(d2, "b_bing", "ext.bing",
                  replaces_src("ext.bing", "B:", "bing"),
                  replaces=["bing"])
        rep = load_user_extensions(extensions_dir=d2)
        by_id = {r["id"]: r for r in rep}
        ck("load_user_extensions applies the saved winner",
           by_id["ext.ms"]["status"] == "loaded"
           and by_id["ext.bing"]["status"] == "disabled", str(rep))
        ck("a valid saved winner is kept",
           read_saved_overrides() == {"microsoft": "ext.ms"},
           str(read_saved_overrides()))

        _file2["cur"] = {"ExtensionOverrides": {"microsoft": "ext.gone"}}
        load_user_extensions(extensions_dir=d2)
        ck("a stale saved winner is cleared (built-in stays)",
           read_saved_overrides() == {}, str(read_saved_overrides()))
    finally:
        shutil.rmtree(root2, ignore_errors=True)
finally:
    _C.load, _C.save = _real_load, _real_save

# --- structural: the dialog + the App method -----------------------------
_ov = io.open("qtranslate/override_ui.py", encoding="utf-8").read()
ck("override_ui opens no window at import (no top-level tk.Tk call)",
   re.search(r"^tk\.Tk\(", _ov, re.M) is None)
ck("override_ui defines pick_override_winners",
   "def pick_override_winners" in _ov)
_app_src = io.open("qtranslate/app.py", encoding="utf-8").read()
ck("App.show_override_conflicts is wired",
   re.search(r"def show_override_conflicts\(self\)", _app_src) is not None)

restore()
print("regress_override_persistence: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    try:
        print("FAIL:", f)
    except UnicodeEncodeError:
        print("FAIL:", f.encode("ascii", "replace").decode("ascii"))
sys.exit(1 if fails else 0)
