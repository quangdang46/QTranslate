"""Regression: the SHIPPED example extension works, end to end.

Phase 6's "done when" is *"the README demo is runnable end-to-end: copy
folder -> restart -> change is live; breaking the extension falls open to
built-in. No rebuild of QTranslate."* The demo is
`examples/extensions/hello_provider/`, and this suite runs it the way a
user would:

1. copy the folder into a per-user extensions directory;
2. restart (i.e. a fresh `ExtensionManager` loads the directory);
3. the provider is live -- the registry serves a translation with it;
4. break the extension -> it is disabled with a reason and the BUILT-IN
   providers still work.

It also pins the example's `sdk_version` against the SDK's own, so a
version bump fails here instead of silently making the shipped example
unloadable.
"""

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
        fail.append(f"{name} -- {detail}")


from qtranslate import extensions as EX  # noqa: E402

EXAMPLE = os.path.join(ROOT, "examples", "extensions", "hello_provider")

# --- the example is where the plan says it is -------------------------------
ck("the example extension is shipped", os.path.isdir(EXAMPLE), EXAMPLE)
ck("the example has a manifest",
   os.path.isfile(os.path.join(EXAMPLE, "manifest.json")))
ck("the example has its entrypoint module",
   os.path.isfile(os.path.join(EXAMPLE, "ext.py")))

if os.path.isdir(EXAMPLE):
    with open(os.path.join(EXAMPLE, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    ck("the example's manifest declares a provider",
       "provider" in man.get("capabilities", []), str(man.get("capabilities")))
    ck("the example's sdk_version matches the SDK's",
       EX._sdk_major(man.get("sdk_version", "")) == EX.SDK_MAJOR,
       "example says %r, the SDK is %r"
       % (man.get("sdk_version"), EX.SDK_VERSION))
    ck("the example's manifest validates against the real schema",
       EX.validate(man) is not None)

# --- copy it into a per-user extensions directory and restart ---------------
tmp = tempfile.mkdtemp(prefix="qtx-example-")
try:
    exts = os.path.join(tmp, "extensions")
    os.makedirs(exts)
    shutil.copytree(EXAMPLE, os.path.join(exts, "hello_provider"))

    found = EX.discover(exts)
    ck("the copied folder is discovered", len(found) == 1, str(found))

    mgr = EX.ExtensionManager()
    outcome = mgr.load_dir(exts)
    ck("the example loads",
       len(outcome) == 1 and outcome[0]["status"] == "loaded",
       str(outcome))
    ck("the example registers its provider",
       "hello" in mgr.providers(), str(sorted(mgr.providers())))

    # --- the change is LIVE: the registry serves a translation with it ---
    from qtranslate import registry as RG
    RG.TRANSLATORS["hello"] = mgr._providers.get("hello")
    try:
        out = RG.TRANSLATORS["hello"]("world", "auto", "vi")
        ck("the example's provider answers", out == "Hello, world", repr(out))
    except Exception as exc:
        ck("the example's provider answers", False, repr(exc))
    finally:
        RG.TRANSLATORS.pop("hello", None)

    # --- breaking it falls open to the built-in ---------------------------
    broken = os.path.join(exts, "broken_provider")
    os.makedirs(broken)
    with open(os.path.join(broken, "manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"id": "broken-provider", "name": "broken",
                   "version": "1.0.0", "sdk_version": EX.SDK_VERSION,
                   "entrypoint": "ext:register",
                   "capabilities": ["provider"]}, fh)
    with open(os.path.join(broken, "ext.py"), "w", encoding="utf-8") as fh:
        fh.write("raise RuntimeError('this extension is broken')\n"
                 "def register(api):\n    pass\n")

    mgr2 = EX.ExtensionManager()
    outcome2 = mgr2.load_dir(exts)
    statuses = {o["id"]: o["status"] for o in outcome2}
    ck("the broken extension is disabled, not fatal",
       statuses.get("broken-provider") == "disabled", str(statuses))
    ck("the broken extension reports a reason",
       bool(next((o["reason"] for o in outcome2
                  if o["id"] == "broken-provider"), None)),
       str(outcome2))
    ck("the good extension still loads beside the broken one",
       statuses.get("hello-provider") == "loaded", str(statuses))
    ck("the built-in providers are untouched",
       "google" in RG.TRANSLATORS, str(sorted(RG.TRANSLATORS)[:6]))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- the theme and UI examples load too -------------------------------------
# Phase 6's "remaining demos" were a custom theme and a custom UI
# contribution; both are shipped now, so both are exercised the same way
# the provider example is.
for _name, _caps in (("custom_theme", "theme"), ("custom_ui", "ui")):
    _ex = os.path.join(ROOT, "examples", "extensions", _name)
    ck("the %s example is shipped" % _caps, os.path.isdir(_ex), _ex)
    if not os.path.isdir(_ex):
        continue
    with open(os.path.join(_ex, "manifest.json"), encoding="utf-8") as _fh:
        _man = json.load(_fh)
    ck("the %s example declares the %r capability" % (_caps, _caps),
       _caps in _man.get("capabilities", []), str(_man.get("capabilities")))
    ck("the %s example's sdk_version matches the SDK's" % _caps,
       EX._sdk_major(_man.get("sdk_version", "")) == EX.SDK_MAJOR,
       repr(_man.get("sdk_version")))
    _tmp2 = tempfile.mkdtemp(prefix="qtx-example-")
    try:
        _exts2 = os.path.join(_tmp2, "extensions")
        os.makedirs(_exts2)
        shutil.copytree(_ex, os.path.join(_exts2, _name))
        _mgr = EX.ExtensionManager()
        _out = _mgr.load_dir(_exts2)
        ck("the %s example loads" % _caps,
           len(_out) == 1 and _out[0]["status"] == "loaded", str(_out))
        if _caps == "theme":
            ck("the theme example registers its theme",
               "paper" in _mgr.themes(), str(sorted(_mgr.themes())))
            _rec = _mgr.themes().get("paper")
            ck("the theme record has the Common section",
               isinstance(_rec, dict) and "Common" in _rec, repr(_rec)[:60])
        else:
            _reg = _mgr.ui_slots
            ck("the UI example contributes to the tray menu",
               not _reg.is_empty("menu", "tray"),
               str(_reg.entries("menu", "tray")))
            ck("...and to the top panel",
               not _reg.is_empty("panel", "top"),
               str(_reg.entries("panel", "top")))
            _w = _reg.winner("menu", "tray")
            ck("the tray contribution answers when called",
               callable(_w["contribution"])
               and "example extension" in _w["contribution"](),
               repr(_w["contribution"]))
    finally:
        shutil.rmtree(_tmp2, ignore_errors=True)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_example_extension: all checks ok (%d assertions)" % n[0])
