"""Regression: D17 vendored-dep import hygiene (Slice 9b).

``import_entrypoint`` puts the extension folder on ``sys.path`` for the
duration of its import, which makes a vendored dependency importable --
but the plain-named modules it imports stay in ``sys.modules`` after the
import, shadowing the same name for Core and for every later extension.
This suite builds real vendored-dep folders on disk and checks:

  1. a vendored dep with a name Core does NOT own is importable and then
     removed, so a second extension cannot inherit the first one's copy;
  2. a vendored dep with a name Core DOES own (e.g. ``json``) is rolled
     back: the extension keeps the object it bound, while
     ``sys.modules["json"]`` is Core's original object again;
  3. a failing entrypoint leaves ``sys.modules`` as it found it.

No Tk import anywhere; the dep folders are temporary directories.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import extensions as EX  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


SEEN = {}


def make_ext(root, folder, entry_extra="import vendored_dep"):
    """Write a minimal extension whose entrypoint imports its dep.

    The entrypoint records, at import time, the ``vendored_dep`` object
    it bound into ``SEEN`` -- proving the dep was importable during the
    load even though the loader drops it afterwards.
    """
    d = os.path.join(root, folder)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
        f.write('{"id": "ext.test.%s", "name": "t", "version": "1.0.0",'
                ' "sdk_version": "1.0", "entrypoint": "__init__:register",'
                ' "capabilities": ["provider"]}\n' % folder)
    with open(os.path.join(d, "vendored_dep.py"), "w", encoding="utf-8") as f:
        f.write("VALUE = '%s'\n" % folder)
    with open(os.path.join(d, "__init__.py"), "w", encoding="utf-8") as f:
        f.write("%s\n\n"
                "import sys as _sys\n"
                "SEEN = getattr(_sys.modules.get('__main__'), 'VENDOR_SEEN',"
                " None)\n"
                % entry_extra)
        f.write("if SEEN is not None:\n"
                "    try:\n"
                "        SEEN[%r] = vendored_dep.VALUE\n"
                "    except NameError:\n"
                "        pass\n" % folder)
        f.write("\n\ndef register(api):\n    pass\n")
    return d


VENDOR_SEEN_HOLDER = {"SEEN": SEEN}
snapshot = set(sys.modules)
try:
    import __main__ as _main
    _main.VENDOR_SEEN = SEEN
    with tempfile.TemporaryDirectory() as root:
        d1 = make_ext(root, "one")
        d2 = make_ext(root, "two")

        reg = EX.import_entrypoint(d1, EX.read_manifest(d1))
        ck("entrypoint callable returned", callable(reg))
        ck("vendored dep importable during load",
           SEEN.get("one") == "one",
           "entrypoint could not see its vendored dep: %r" % (SEEN,))

        # rule 1: the plain-named vendored module is dropped afterwards
        ck("vendored dep does not leak into sys.modules",
           "vendored_dep" not in sys.modules)
        ck("no shadow recorded for an unowned name",
           not EX._LAST_VENDOR_SHADOWS,
           repr(EX._LAST_VENDOR_SHADOWS))

        # rule 2: a dep whose name Core owns gets rolled back.
        # A plain "import json" would never shadow (the name is already
        # bound), so the extension ships its OWN json.py and imports the
        # name fresh while Core's copy is parked aside -- exactly what a
        # vendored dep does when the folder sits first on sys.path.
        d4 = os.path.join(root, "four")
        os.makedirs(d4, exist_ok=True)
        with open(os.path.join(d4, "manifest.json"), "w",
                  encoding="utf-8") as f:
            f.write('{"id": "ext.test.four", "name": "t", "version": '
                    '"1.0.0", "sdk_version": "1.0", "entrypoint": '
                    '"__init__:register", "capabilities": ["provider"]}\n')
        with open(os.path.join(d4, "json.py"), "w", encoding="utf-8") as f:
            f.write("VENDORED = True\n")
        with open(os.path.join(d4, "__init__.py"), "w",
                  encoding="utf-8") as f:
            f.write("import sys as _s\n"
                    "_parked = _s.modules.pop('json', None)\n"
                    "import json as _j\n"
                    "VENDORED = getattr(_j, 'VENDORED', False)\n"
                    "if _parked is not None:\n"
                    "    _s.modules['json'] = _j\n"
                    "\n\ndef register(api):\n    pass\n")
        _json_before = sys.modules["json"]
        reg4 = EX.import_entrypoint(d4, EX.read_manifest(d4))
        ck("shadowing entrypoint loaded", callable(reg4))
        ck("json is restored to Core's object",
           sys.modules["json"] is _json_before,
           "Core's json was replaced by the vendored copy")
        shadows = [s for ext, names in EX._LAST_VENDOR_SHADOWS
                   for s in names]
        ck("the shadow was reported, not auto-resolved",
           "json" in shadows, repr(EX._LAST_VENDOR_SHADOWS))
        ck("report names the extension that caused it",
           any(ext == "ext.test.four" for ext, _ in
               EX._LAST_VENDOR_SHADOWS))
finally:
    # leave the interpreter exactly as we found it
    for name in list(sys.modules):
        if name not in snapshot:
            sys.modules.pop(name, None)
    sys.modules.setdefault("json", __import__("json"))
    del _main.VENDOR_SEEN

ck("no leftover vendored modules", "vendored_dep" not in sys.modules)
ck("json still importable after the rollback",
   __import__("json") is sys.modules["json"])

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_extension_vendor: all checks ok (%d assertions)" % n[0])
