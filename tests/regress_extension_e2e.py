"""Slice 8 pin: extension loading end-to-end — a loaded provider actually
serves a translation through the engine, an override replaces a built-in,
and a bad extension leaves the built-in untouched.

This is the pin the reviewer required: not "load_dir returned ok" but
"``engine.translate`` called the extension". Mutates the live
``registry.TRANSLATORS`` table on purpose and restores it at the end.

Offline, no window, no network (temp folders + fake providers only).
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


from qtranslate import engine
from qtranslate import registry as RG
from qtranslate.extensions import ExtensionManager, load_user_extensions

# Snapshot the live table + router so this suite leaves no trace.
_TABLE = RG.TRANSLATORS
_ORIGINAL = dict(RG.TRANSLATORS)


def write_ext(root, name, ext_id, source, replaces=None):
    folder = os.path.join(root, name)
    os.makedirs(folder)
    man = {"id": ext_id, "name": ext_id, "version": "0.1.0",
           "sdk_version": "1.0", "entrypoint": "__init__:register",
           "capabilities": ["provider"]}
    if replaces:
        man["replaces"] = replaces
    with io.open(os.path.join(folder, "manifest.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(man))
    with io.open(os.path.join(folder, "__init__.py"), "w",
                 encoding="utf-8") as fh:
        fh.write(source)
    return folder


root = tempfile.mkdtemp(prefix="qt_e2e_")
try:
    # --- missing folder: fail-open, nothing committed -------------------
    before = len(RG.TRANSLATORS)
    ck("a missing extensions folder is a no-op",
       load_user_extensions(extensions_dir=os.path.join(root, "nope")) == [])
    ck("a no-op load does not touch the dispatch table",
       len(RG.TRANSLATORS) == before, str(len(RG.TRANSLATORS)))

    # --- a loaded provider actually serves through the engine -----------
    add = os.path.join(root, "add")
    os.makedirs(add)
    write_ext(add, "ext_e2e", "ext.e2e",
              "def register(api):\n"
              "    api.register_provider('ext.e2e',\n"
              "                          lambda t, s, g: 'EXT:' + t)\n")
    report = load_user_extensions(extensions_dir=add)
    ck("the extension loads", report and report[0]["status"] == "loaded",
       str(report))
    ck("commit wrote it into the live dispatch table (in place)",
       "ext.e2e" in RG.TRANSLATORS and RG.TRANSLATORS is _TABLE)
    ck("the extension provider joins the fallback chain (router_order)",
       "ext.e2e" in RG.router_order(), str(RG.router_order()))

    res = engine.translate("ext.e2e", "hello", "vi", src="en")
    ck("engine.translate routes to the extension provider", res.ok, repr(res))
    ck("the extension's own text is returned",
       res.text == "EXT:hello", repr(res.text))
    ck("the engine names the extension as the provider used",
       res.provider_used == "ext.e2e", repr(res.provider_used))

    # public SDK path uses the same engine
    from qtranslate import sdk
    ck("the SDK path also reaches the extension provider",
       sdk.translate("ext.e2e", "world", "vi", src="en").text == "EXT:world")

    # --- an override replaces a built-in in the real call path ----------
    builtin_google = RG.TRANSLATORS["google"]
    rep = os.path.join(root, "rep")
    os.makedirs(rep)
    write_ext(rep, "ext_goog", "ext.goog",
              "def register(api):\n"
              "    api.register_provider('ext.goog',\n"
              "                          lambda t, s, g: 'OVR:' + t,\n"
              "                          replaces='google')\n",
              replaces=["google"])
    load_user_extensions(extensions_dir=rep)
    ck("a declared override replaces the built-in under its id",
       RG.TRANSLATORS.get("google") is RG.TRANSLATORS.get("ext.goog")
       and RG.TRANSLATORS["google"] is not builtin_google,
       repr(RG.TRANSLATORS.get("google")))

    res = engine.translate("google", "hi", "vi", src="en")
    ck("selecting the overridden built-in calls the extension",
       res.ok and res.text == "OVR:hi", repr(res))
    ck("the overriding callable is not a duplicate fallback entry (rule b)",
       "ext.goog" not in RG.router_order(), str(RG.router_order()))

    # --- a broken override never damages the built-in -------------------
    RG.TRANSLATORS["google"] = builtin_google  # undo the override first
    bad = os.path.join(root, "bad")
    os.makedirs(bad)
    write_ext(bad, "ext_bad", "ext.bad",
              "def register(api):\n"
              "    api.register_provider('ext.bad', lambda t, s, g: 'X',\n"
              "                          replaces='google')\n"
              "    raise RuntimeError('boom')\n",
              replaces=["google"])
    bad_report = load_user_extensions(extensions_dir=bad)
    ck("the broken override is disabled, not fatal",
       bad_report and bad_report[0]["status"] == "disabled", str(bad_report))
    ck("the built-in is still the callable behind its id (rule 4)",
       RG.TRANSLATORS["google"] is builtin_google,
       repr(RG.TRANSLATORS["google"]))
    ck("the broken extension added no provider",
       "ext.bad" not in RG.TRANSLATORS)

    # --- startup wiring is present (static; main() is not run) ----------
    app_src = io.open("qtranslate/app.py", encoding="utf-8").read()
    main_body = app_src.split("def main():", 1)[1]
    ck("app.main wires extension loading at startup",
       re.search(r"load_user_extensions\s*\(", main_body) is not None)

    # --- the loader core stays tkinter-free -----------------------------
    src = io.open("qtranslate/extensions.py", encoding="utf-8").read()
    ck("extensions module imports no tkinter",
       re.search(r"^\s*(import|from)\s+tkinter", src, re.M) is None)
finally:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIGINAL)
    RG.reset_router()
    shutil.rmtree(root, ignore_errors=True)

print("regress_extension_e2e: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    try:
        print("FAIL:", f)
    except UnicodeEncodeError:
        print("FAIL:", f.encode("ascii", "replace").decode("ascii"))
sys.exit(1 if fails else 0)
