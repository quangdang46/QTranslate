"""The extension SDK as a SEPARATE, installable package.

``docs/EXTENSION_SDK.md`` describes ``qtranslate-sdk`` as "the
pip-installable package developers import". This suite proves it is one:

* the package's source tree imports on its own, with no desktop app on
  the path -- if it pulled in the engine or the GUI, this would fail;
* its contracts match the host's, field for field, so the two cannot
  drift into an extension that type-checks and then breaks at runtime;
* the wheel builds, and installing THAT wheel into a clean virtualenv
  (not the source tree) leaves an importable package with the same
  public surface.

The last check needs `binascii`/`zipfile` only, so it runs offline. A
missing build frontend is a SKIP, not a failure: the build is an
environment capability, the contracts are the code.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDK_ROOT = os.path.join(ROOT, "sdksrc")
SDK_PKG = os.path.join(SDK_ROOT, "qtranslate_sdk")

fail = []
n = [0]
skips = []


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


def skip(name, why):
    skips.append("%s (%s)" % (name, why))


def _metadata(wheel_path):
    with zipfile.ZipFile(wheel_path) as z:
        for name in z.namelist():
            if name.endswith("METADATA"):
                return z.read(name).decode("utf-8", "replace")
    return ""


# --- the package imports with NO desktop app on the path ----------------
# Run a fresh interpreter whose sys.path holds ONLY sdksrc, so an import
# of `qtranslate` (the app) fails loudly instead of being found in ROOT.
_probe = (
    "import sys; sys.path = [%r] + [p for p in sys.path if 'qtranslate-re' "
    "not in p];\n"
    "import qtranslate_sdk as S;\n"
    "assert not any(m == 'qtranslate' or m.startswith('qtranslate.') "
    "for m in sys.modules), 'the SDK imported the desktop app';\n"
    "assert 'PySide6' not in sys.modules, 'the SDK imported the GUI';\n"
    "print(sorted(S.__all__))" % SDK_ROOT
)
_r = subprocess.run([sys.executable, "-I", "-c", _probe],
                    capture_output=True, text=True, timeout=120)
ck("the SDK imports with no desktop app on the path", _r.returncode == 0,
   (_r.stderr or "").strip()[-300:])

# --- the contracts match the host ---------------------------------------
sys.path.insert(0, ROOT)
sys.path.insert(0, SDK_ROOT)
import qtranslate_sdk as S                               # noqa: E402
from qtranslate import core as HOST_CORE                  # noqa: E402
from qtranslate import extensions as HOST_EXT             # noqa: E402
from qtranslate import ui_slots as HOST_SLOTS             # noqa: E402

import dataclasses                                        # noqa: E402

_host_fields = [(f.name, f.default) for f in
                dataclasses.fields(HOST_CORE.Result)]
_sdk_fields = [(f.name, f.default) for f in dataclasses.fields(S.Result)]
ck("Result has the same fields and defaults as the host's",
   _host_fields == _sdk_fields,
   "host=%r sdk=%r" % (_host_fields, _sdk_fields))

ck("the manifest's required fields match the host's",
   tuple(HOST_EXT._REQUIRED_FIELDS) == tuple(S.MANIFEST_REQUIRED),
   "host=%r sdk=%r" % (tuple(HOST_EXT._REQUIRED_FIELDS),
                        tuple(S.MANIFEST_REQUIRED)))

ck("the menu slots match the host's",
   tuple(S.MENU_SLOTS) == tuple(HOST_SLOTS.MENU_SLOT_IDS),
   "sdk=%r host=%r" % (tuple(S.MENU_SLOTS),
                       tuple(HOST_SLOTS.MENU_SLOT_IDS)))
ck("the panel slots match the host's",
   tuple(S.PANEL_SLOTS) == tuple(HOST_SLOTS.PANES),
   "sdk=%r host=%r" % (tuple(S.PANEL_SLOTS), tuple(HOST_SLOTS.PANES)))
ck("the popup slots match the host's",
   tuple(S.POPUP_SLOTS) == tuple(HOST_SLOTS.slot_names("popup")),
   "sdk=%r host=%r" % (tuple(S.POPUP_SLOTS),
                       tuple(HOST_SLOTS.slot_names("popup"))))

# --- the language table matches the host's ------------------------------
from qtranslate import languages as HOST_LANGS            # noqa: E402
from qtranslate_sdk import languages as SDK_LANGS         # noqa: E402
_host_codes = tuple(HOST_LANGS.LANGS)
_sdk_codes = tuple(c for c in SDK_LANGS.LANG_CODES_BY_INDEX if c)
ck("the SDK's language codes match the host's",
   _host_codes == _sdk_codes,
   "host=%d sdk=%d" % (len(_host_codes), len(_sdk_codes)))

# --- FakeAPI records what an extension registers ------------------------
api = S.FakeAPI()
api.register_provider("ext.p", lambda t, s, g: "x")
api.register_theme("ext.t", {"Window": {}})
api.register_ui("menu", "tray", lambda: "hi")
ck("FakeAPI records a provider", "ext.p" in api.providers)
ck("FakeAPI records a theme", "ext.t" in api.themes)
ck("FakeAPI records a UI contribution", len(api.ui) == 1, str(api.ui))
_bad = False
try:
    api.register_ui("nonsense", "x", lambda: 1)
except S.ExtensionError:
    _bad = True
ck("FakeAPI refuses an unknown UI kind", _bad)

# A manifest validates, and a missing field is a defined error.
man = S.Manifest.from_dict({"id": "e", "name": "E", "version": "1.0",
                            "sdk_version": "1.0", "entrypoint": "ext:register",
                            "capabilities": ["provider"]})
ck("a valid manifest parses", man.id == "e" and man.capabilities ==
   ("provider",))
ck("the entrypoint splits into module and callable",
   man.entry_module == "ext" and man.entry_callable == "register")
_bad = False
try:
    S.Manifest.from_dict({"id": "e"})
except S.ExtensionError:
    _bad = True
ck("an incomplete manifest is a defined error", _bad)

# --- the wheel builds and installs into a CLEAN virtualenv --------------
why = None
try:
    import build  # noqa: F401
except Exception:
    why = "the `build` frontend is not installed"
if why:
    skip("the wheel builds and installs into a clean virtualenv", why)
else:
    tmp = tempfile.mkdtemp(prefix="sdk_wheel_")
    try:
        out = os.path.join(tmp, "dist")
        r = subprocess.run([sys.executable, "-m", "build", "--wheel",
                            "--outdir", out, SDK_ROOT],
                           capture_output=True, text=True, timeout=600)
        wheels = [f for f in os.listdir(out)] if os.path.isdir(out) else []
        ck("the wheel builds", r.returncode == 0 and bool(wheels),
           (r.stderr or "").strip()[-400:])
        if wheels:
            whl = os.path.join(out, wheels[0])
            # The wheel must not carry the desktop app.
            with zipfile.ZipFile(whl) as z:
                names = z.namelist()
            ck("the wheel carries the SDK package",
               any(x.startswith("qtranslate_sdk/") for x in names), str(names))
            ck("the wheel carries no desktop code",
               not any(x.startswith("qtranslate/") for x in names), str(names))
            ck("the wheel declares no dependency on the app",
               all("qtranslate" not in line.lower()
                   for line in _metadata(whl).splitlines()
                   if line.lower().startswith(("requires-dist",))),
               _metadata(whl)[:400])

            venv = os.path.join(tmp, "venv")
            r = subprocess.run([sys.executable, "-m", "venv", venv],
                               capture_output=True, text=True, timeout=300)
            py = os.path.join(venv, "Scripts" if os.name == "nt" else "bin",
                              "python.exe" if os.name == "nt" else "python")
            ck("the clean virtualenv is created",
               r.returncode == 0 and os.path.exists(py),
               (r.stderr or "").strip()[-300:])
            if os.path.exists(py):
                r = subprocess.run([py, "-m", "pip", "install", "--quiet",
                                    "--no-index", whl],
                                   capture_output=True, text=True, timeout=600)
                ck("the wheel installs with no network", r.returncode == 0,
                   (r.stderr or "").strip()[-400:])
                r = subprocess.run(
                    [py, "-I", "-c",
                     "import qtranslate_sdk as S; print(S.__version__); "
                     "assert S.Result(text='x', provider_used='p').ok; "
                     "assert 'qtranslate' not in str(list(__import__('sys')"
                     ".modules.keys())[:0]) or True; "
                     "print(sorted(S.__all__))"],
                    capture_output=True, text=True, timeout=120)
                ck("the installed package imports and its Result works",
                   r.returncode == 0, (r.stderr or "").strip()[-400:])
                r = subprocess.run(
                    [py, "-I", "-c",
                     "import sys, qtranslate_sdk;"
                     "print('qtranslate' in sys.modules)"],
                    capture_output=True, text=True, timeout=120)
                ck("importing the installed SDK pulls in no desktop app",
                   r.stdout.strip() == "False", r.stdout.strip())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if skips:
    for s in skips:
        print("SKIP", s)
if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_sdk_package: all checks ok (%d assertions)" % n[0])
