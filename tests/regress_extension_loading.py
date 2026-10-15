"""Slice 7 pin: extension-directory discovery + manifest validation +
fail-open loading.

Covers the Phase-3 matrix (``TEST_STRATEGY.md`` §3): missing/short/bad
``sdk_version``, broken entrypoint, unimportable module — plus discovery,
rollback on a failed override (rule 4), and the D17 import-path mechanism.

Offline, no window, no network (temp folders only).
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


from qtranslate import platforms as P
from qtranslate.extensions import (
    SDK_VERSION, ExtensionManager, ManifestError, discover,
    read_manifest, validate)


def manifest(ext_id, **overrides):
    base = {"id": ext_id, "name": ext_id, "version": "0.1.0",
            "sdk_version": "1.0", "entrypoint": "__init__:register",
            "capabilities": ["provider"]}
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


def rejects(name, man):
    try:
        validate(man)
    except ManifestError:
        ck(name, True)
        return
    ck(name, False, "validate accepted %r" % (man,))


# --- manifest validation matrix ----------------------------------------
ck("a valid manifest validates", validate(manifest("ext.ok"))["id"] == "ext.ok")
rejects("missing sdk_version", {k: v for k, v in manifest("e").items()
                                if k != "sdk_version"})
rejects("missing id", {k: v for k, v in manifest("e").items() if k != "id"})
rejects("empty (short) sdk_version", manifest("e", sdk_version=""))
rejects("non-numeric (bad) sdk_version", manifest("e", sdk_version="abc"))
rejects("incompatible sdk major", manifest("e", sdk_version="2.0"))
rejects("non-string sdk_version", manifest("e", sdk_version=1))
ck("same-major sdk_version is compatible",
   validate(manifest("e", sdk_version="1.7"))["id"] == "e")
rejects("entrypoint without a colon", manifest("e", entrypoint="__init__"))
rejects("entrypoint with empty callable", manifest("e", entrypoint="__init__:"))
rejects("entrypoint with empty module", manifest("e", entrypoint=":register"))
rejects("capabilities empty", manifest("e", capabilities=[]))
rejects("unknown capability", manifest("e", capabilities=["telepathy"]))
rejects("replaces not a list", manifest("e", replaces="google"))
rejects("manifest not an object", ["not", "a", "dict"])

ck("SDK_VERSION is a semver-ish string",
   isinstance(SDK_VERSION, str) and SDK_VERSION.count(".") >= 1)

# --- discovery ----------------------------------------------------------
root = tempfile.mkdtemp(prefix="qt_ext_")
try:
    write_ext(root, "b_ext", manifest("ext.b"), "def register(api):\n    pass\n")
    write_ext(root, "a_ext", manifest("ext.a"), "def register(api):\n    pass\n")
    os.makedirs(os.path.join(root, "no_manifest"))
    os.makedirs(os.path.join(root, ".hidden"))
    with io.open(os.path.join(root, "loose.txt"), "w", encoding="utf-8") as fh:
        fh.write("not a folder")

    found = discover(root)
    ck("discovery finds only manifest-bearing folders",
       [os.path.basename(p) for p in found] == ["a_ext", "b_ext"], str(found))
    ck("discovery of a missing directory is empty, not an error",
       discover(os.path.join(root, "nope")) == [])
    ck("discovery of no directory argument is empty", discover("") == [])

    # --- read_manifest errors ------------------------------------------
    _err = None
    try:
        read_manifest(os.path.join(root, "no_manifest"))
    except ManifestError as exc:
        _err = str(exc)
    ck("a folder without manifest.json disables (ManifestError)",
       _err is not None and "manifest.json" in _err, repr(_err))

    bad_json = os.path.join(root, "bad_json")
    os.makedirs(bad_json)
    with io.open(os.path.join(bad_json, "manifest.json"), "w",
                 encoding="utf-8") as fh:
        fh.write("{not json")
    _err = None
    try:
        read_manifest(bad_json)
    except ManifestError as exc:
        _err = str(exc)
    ck("invalid JSON disables (ManifestError)",
       _err is not None and "JSON" in _err, repr(_err))

    # --- fail-open loading ---------------------------------------------
    load_root = tempfile.mkdtemp(prefix="qt_load_")
    try:
        gen = os.path.join(load_root, "gen")
        conflict = os.path.join(load_root, "conflict")
        half = os.path.join(load_root, "half")
        for d in (gen, conflict, half):
            os.makedirs(d)

        write_ext(
            gen, "ext_ok", manifest("ext.ok"),
            "def register(api):\n"
            "    api.register_provider('ext.ok', lambda t, s, g: 'ok')\n")
        write_ext(
            gen, "ext_import_fail", manifest("ext.import_fail"),
            "raise ImportError('missing vendored dep')\n")
        write_ext(
            gen, "ext_bad_entry",
            manifest("ext.bad_entry", entrypoint="__init__:nope"),
            "def register(api):\n    pass\n")
        write_ext(
            gen, "ext_vendor", manifest("ext.vendor"),
            "import qt_vendored_probe_xyz\n"
            "def register(api):\n"
            "    api.register_provider(\n"
            "        'ext.vendor', lambda t, s, g: qt_vendored_probe_xyz.VALUE)\n")
        with io.open(os.path.join(gen, "ext_vendor",
                                  "qt_vendored_probe_xyz.py"), "w",
                     encoding="utf-8") as fh:
            fh.write("VALUE = 'vendored'\n")

        m = ExtensionManager()
        results = m.load_dir(gen)
        by_id = {r["id"]: r for r in results if r["id"]}

        ck("every discovered folder yields an outcome",
           len(results) == 4, str([r["id"] for r in results]))
        ck("a good extension loads", by_id["ext.ok"]["status"] == "loaded",
           str(by_id["ext.ok"]))
        ck("a loaded extension's provider is registered",
           "ext.ok" in m.providers())
        ck("an unimportable module disables fail-open",
           by_id["ext.import_fail"]["status"] == "disabled"
           and "ImportError" in by_id["ext.import_fail"]["reason"],
           str(by_id["ext.import_fail"]))
        ck("a broken entrypoint callable disables fail-open",
           by_id["ext.bad_entry"]["status"] == "disabled"
           and "ImportError" in by_id["ext.bad_entry"]["reason"],
           str(by_id["ext.bad_entry"]))
        ck("a vendored dependency inside the folder is importable (D17)",
           by_id["ext.vendor"]["status"] == "loaded", str(by_id["ext.vendor"]))
        ck("the extension folder is removed from sys.path after import",
           os.path.join(gen, "ext_vendor") not in sys.path, str(sys.path[:4]))

        # --- a failed override rolls back, built-in stays (rule 4) -----
        write_ext(
            half, "ext_half", manifest("ext.half", replaces=["google"]),
            "def register(api):\n"
            "    api.register_provider('ext.half', lambda t, s, g: 'h',\n"
            "                          replaces='google')\n"
            "    raise RuntimeError('boom')\n")
        m_half = ExtensionManager()
        builtin_google = m_half.active("google")
        half_results = m_half.load_dir(half)
        ck("a failed override rolls back its partial registration",
           half_results[0]["status"] == "disabled"
           and "ext.half" not in m_half.providers(), str(half_results[0]))
        ck("a failed override leaves the built-in active (rule 4)",
           m_half.active("google") is builtin_google, repr(m_half.active("google")))
        ck("a rolled-back override is not reported as a conflict",
           m_half.conflicts() == {}, str(m_half.conflicts()))

        # --- D18: one winner, the loser disabled with an explanation ----
        for tag in ("a", "b"):
            write_ext(
                conflict, "conflict_" + tag,
                manifest("ext.conflict_" + tag, replaces=["google"]),
                "def register(api):\n"
                "    api.register_provider('ext.conflict_%s',\n"
                "                          lambda t, s, g: '%s', replaces='google')\n"
                % (tag, tag))
        m_conf = ExtensionManager()
        conf_results = m_conf.load_dir(conflict)
        conf_by_id = {r["id"]: r for r in conf_results}
        ck("one override wins, the conflicting one is disabled (D18)",
           conf_by_id["ext.conflict_a"]["status"] == "loaded"
           and conf_by_id["ext.conflict_b"]["status"] == "disabled"
           and "pick the winner" in conf_by_id["ext.conflict_b"]["reason"],
           str(conf_by_id["ext.conflict_b"]))
        ck("the conflict is reported for the user",
           m_conf.conflicts().get("google") == "ext.conflict_a",
           str(m_conf.conflicts()))
        ck("the losing override's provider is not registered",
           "ext.conflict_b" not in m_conf.providers())

        ck("loading a directory with no extensions is a no-op",
           ExtensionManager().load_dir(os.path.join(load_root, "nope")) == [])
    finally:
        shutil.rmtree(load_root, ignore_errors=True)
finally:
    shutil.rmtree(root, ignore_errors=True)

# --- Paths adapter resolves the per-user extensions dir (D16) -----------
cur = P.current()
if sys.platform == "win32":
    ext_dir = cur.extensions_dir()
    ck("windows extensions_dir is the per-user app-data folder (D16)",
       ext_dir.endswith(os.path.join("QTranslate", "extensions")),
       ext_dir)
    ck("extensions_dir is never the install directory",
       "Program Files" not in ext_dir, ext_dir)

# --- tkinter-free / structural ------------------------------------------
_src = io.open("qtranslate/extensions.py", encoding="utf-8").read()
ck("extensions module imports no tkinter",
   re.search(r"^\s*(import|from)\s+tkinter", _src, re.M) is None)
ck("extensions module does not import app at module level",
   re.search(r"^\s*(import|from)\s+qtranslate\.app", _src, re.M) is None)

print("regress_extension_loading: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    try:
        print("FAIL:", f)
    except UnicodeEncodeError:
        print("FAIL:", f.encode("ascii", "replace").decode("ascii"))
sys.exit(1 if fails else 0)
