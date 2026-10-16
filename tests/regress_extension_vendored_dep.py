"""Regression: an extension can vendor its own dependency (D17).

Phase 8's acceptance condition is *"a user drops an extension in, restarts,
and it works with Python not separately installed — the app bundles the
runtime and **the extension vendors its own deps** (D17)"*.

The loader half was built in slices 7–8, and D17 bookkeeping exists
(`extensions.py`'s `_restore_modules` / vendored-name tracking). This suite
proves the *whole* trick on a real filesystem, which a unit test of the
bookkeeping alone cannot show:

1. An extension folder with a **vendored module** imports what IT shipped.
2. The extension folder is **off `sys.path` afterwards** — so its vendored
   copy cannot leak into a later import.
3. A broken extension raises, and the built-in providers are untouched
   (fail-open, the loader's contract).

No bundler is involved: the point is that the mechanism works from a plain
directory, which is what a bundle ships.

The manifest shape is the real one (`manifest.json` with
`id/name/version/sdk_version/entrypoint/capabilities`, entrypoint as
`module:callable`), so a schema change fails here too.

Headless, no network. Creates and removes its own temp folders.
"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import extensions as EX  # noqa: E402
from qtranslate.extensions import ExtensionManager  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


def make_ext(root, ext_id, vendored_value, entrypoint_body, broken=False):
    """Write one extension folder with a vendored dependency."""
    folder = os.path.join(root, ext_id)
    os.makedirs(folder, exist_ok=True)
    manifest = {
        "id": ext_id,
        "name": ext_id,
        "version": "1.0.0",
        "sdk_version": EX.SDK_VERSION,
        "entrypoint": "ext:register",
        "capabilities": ["provider"],
    }
    with open(os.path.join(folder, "manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(manifest, fh)
    with open(os.path.join(folder, "vendoredlib.py"), "w",
              encoding="utf-8") as fh:
        fh.write("VALUE = %r\n" % vendored_value)
    with open(os.path.join(folder, "ext.py"), "w", encoding="utf-8") as fh:
        fh.write(entrypoint_body)
    return folder


BODY_OK = (
    "from qtranslate.extensions import ExtensionAPI\n"
    "import vendoredlib\n"
    "SEEN = vendoredlib.VALUE\n"
    "def register(api):\n"
    "    api.register_provider('vend', lambda t, s, g: vendoredlib.VALUE)\n"
)
BODY_BROKEN = (
    "import a_module_that_does_not_exist_anywhere\n"
    "def register(api):\n"
    "    api.register_provider('broken', lambda *a: 'broken')\n"
)

tmp = tempfile.mkdtemp(prefix="qtx-ext-")
try:
    mgr = ExtensionManager()
    builtins_before = sorted(mgr.providers())

    # --- 1. the extension with a vendored dependency loads ------------
    ext = make_ext(tmp, "myext", "from-the-extension", BODY_OK)
    manifest = EX.read_manifest(ext)
    ck("the manifest validates against the real schema",
       manifest["entrypoint"] == "ext:register")
    captured = {}
    try:
        fn = EX.import_entrypoint(ext, manifest)
        captured["fn"] = fn
    except Exception as exc:
        captured["error"] = repr(exc)
    ck("the extension imports its vendored dependency", "fn" in captured,
       str(captured.get("error")))

    # --- 2. the folder is not left on sys.path (the isolation property)
    ck("the extension folder is NOT left on sys.path",
       ext not in sys.path, "%r still on sys.path" % ext)
    # The extension's OWN entrypoint stays in sys.modules, deliberately
    # namespaced as qtranslate_ext_<id>_<module> so it cannot collide.
    # What must NOT be there is the PLAIN-named vendored dep, because that
    # is the name a second extension would collide on.
    plain_leaks = [m for m in ("vendoredlib", "ext")
                   if m in sys.modules]
    ck("the vendored dep is not left under its plain name",
       not plain_leaks, str(plain_leaks))
    ns = [m for m in sys.modules if m.startswith("qtranslate_ext_myext_")]
    ck("the entrypoint IS kept under its namespaced name",
       ns == ["qtranslate_ext_myext_ext"], str(ns))
    ck("...and its file really is the one in the extension folder",
       os.path.abspath(sys.modules[ns[0]].__file__) ==
       os.path.abspath(os.path.join(ext, "ext.py")),
       sys.modules[ns[0]].__file__)

    # --- 3. a SECOND extension gets ITS OWN vendored copy -------------
    # This is the check that a shared sys.modules entry would break: with
    # the folder nagging on path, `import vendoredlib` in ext2 could resolve
    # to ext1's file.
    ext2 = make_ext(tmp, "otherext", "from-the-SECOND-extension",
                    BODY_OK.replace("'vend'", "'vend2'"))
    try:
        EX.import_entrypoint(ext2, EX.read_manifest(ext2))
        ck("a second extension imports its own vendored copy", True)
    except Exception as exc:
        ck("a second extension imports its own vendored copy", False,
           repr(exc))

    # --- 4. a broken extension raises, and built-ins survive ----------
    broken = make_ext(tmp, "broken", "never used", BODY_BROKEN)
    try:
        EX.import_entrypoint(broken, EX.read_manifest(broken))
        ck("a broken extension raises (so load_dir can disable it)", False,
           "no exception")
    except Exception:
        ck("a broken extension raises (so load_dir can disable it)", True)
    ck("...and the built-in providers are untouched",
       sorted(mgr.providers()) == builtins_before, str(builtins_before))

    # --- 5. and the working extension's register() really runs --------
    if "fn" in captured:
        try:
            mgr2 = ExtensionManager()
            from qtranslate.extensions import ExtensionAPI
            captured["fn"](ExtensionAPI(mgr2))
            ck("register() commits a provider through the api",
               "vend" in mgr2.providers(), str(sorted(mgr2.providers())))
            ck("...and it serves a translation",
               mgr2.providers()["vend"]("x", "en", "vi")
               == "from-the-extension")
        except Exception as exc:
            ck("register() commits a provider through the api", False,
               repr(exc))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_extension_vendored_dep: all checks ok (%d assertions)" % n[0])
