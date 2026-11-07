"""Regression: one-time Options.json <-> Kotlin DataStore migration.

Pins the contract of ``qtranslate/migrate.py``:

* the Kotlin ``app_settings.preferences_pb`` is a protobuf
  ``PreferenceMap`` whose ``configuration_json`` string holds the whole
  Kotlin ``Configuration`` -- the codec must read/write it without a
  protobuf dependency and must preserve untouched entries (e.g.
  ``disabled_plugin_ids``) byte-for-byte;
* newer mtime wins, the loser is backed up to ``<file>.bak`` first;
* the two marker files make the migration one-time;
* shared keys map both ways (General/Appearance/HotKeys/AutoDetection)
  while Kotlin-only fields survive a Python->Kotlin push.

Offline: everything runs against temp files via the
``QTRANSLATE_KOTLIN_DATASTORE`` override.
"""
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import migrate as M
from qtranslate import config as C


def fresh_env():
    tmp = tempfile.mkdtemp(prefix="mig_")
    opts = os.path.join(tmp, "Options.json")
    pb = os.path.join(tmp, "datastore", "app_settings.preferences_pb")
    os.makedirs(os.path.dirname(pb), exist_ok=True)
    os.environ["QTRANSLATE_KOTLIN_DATASTORE"] = pb
    M._DONE = False
    return tmp, opts, pb


def write_pb(pb, config_json, extra_entries=()):
    out = b""
    if config_json is not None:
        val = M._string_value_bytes(config_json)
        out += M._len_field(1, M._entry_for(M.CONFIG_JSON_KEY, val))
    for key, value_msg in extra_entries:
        out += M._len_field(1, M._entry_for(key, value_msg))
    with open(pb, "wb") as f:
        f.write(out)


def read_pb(pb):
    entries, cj = M._read_datastore(pb)
    return entries, (json.loads(cj) if cj else None)


# ---------------------------------------------------------------- Kotlin -> Python
tmp, opts, pb = fresh_env()
kcfg = {
    "configVersion": 7,
    "interfaceLanguage": "vi",
    "isHistoryEnabled": False,
    "isInstantTranslationEnabled": True,
    "uiFontConfig": {"name": "Inter", "size": 15},
    "closeButtonBehavior": "MINIMIZE_TO_TRAY",
    "selectionBehavior": "TRANSLATE",
    "isPopupAutoSizeEnabled": False,
    "popupTransparencyPercentage": 20,
    "popupIdleTimeoutSeconds": 33,
    "isGlobalHotkeysEnabled": False,
    "hotkeys": [
        {"action": "SHOW_QUICK_TRANSLATE", "keyCode": 81, "modifiers": 128,
         "isEnabled": True, "scope": "GLOBAL", "isDoubleCtrlEnabled": True},
        {"action": "SHOW_MAIN_WINDOW", "keyCode": 0, "modifiers": 0,
         "isEnabled": True, "scope": "GLOBAL", "isDoubleCtrlEnabled": True},
    ],
    "preferredSourceLanguage": "auto",
    "preferredTargetLanguage": "fr",
    "servicePresets": [{"id": "p", "name": "__default__",
                        "selectedServices": {}, "comparisonTranslatorIds": []}],
    "activeServicePresetId": "p",
}
ss = M._len_field(1, b"plugin-a")
write_pb(pb, json.dumps(kcfg),
         extra_entries=[("disabled_plugin_ids", M._len_field(6, ss))])
C.save(C.default_config(), opts)
os.utime(opts, (time.time() - 100, time.time() - 100))
os.utime(pb, None)

rep = M.migrate_if_needed(opts)
ck("kotlin->python reported", rep["from_kotlin"] and not rep["to_kotlin"], str(rep))
o = json.load(open(opts))
ck("interfaceLanguage -> LocaleFoderName", o["General"]["LocaleFoderName"] == "Vietnamese",
   o["General"].get("LocaleFoderName"))
ck("isHistoryEnabled -> EnableHistory", o["General"]["EnableHistory"] is False)
ck("instant translation mapped", o["General"]["InstantTranslation"] is True)
ck("font mapped", o["General"]["FontName"] == "Inter" and o["General"]["TextSize"] == 15)
ck("close behavior mapped", o["General"]["MinimizeToTrayOnClose"] is True)
ck("selection -> mouse mode", o["General"]["MouseMode"] == 1 and o["General"]["MouseModeOn"] is True,
   str((o["General"].get("MouseMode"), o["General"].get("MouseModeOn"))))
ck("popup autosize mapped", o["Appearance"]["PopupAutoSize"] is False)
ck("transparency alpha", o["Appearance"]["Transparency"] == 204,
   o["Appearance"].get("Transparency"))
ck("popup timeout mapped", o["Appearance"]["PopupTimeout"] == 33)
ck("hotkeys disabled flag", o["HotKeys"]["EnableHotKeys"] is False)
ck("Ctrl+Q -> 593", o["HotKeys"]["HotKeyPopupWindow"] == 593,
   o["HotKeys"].get("HotKeyPopupWindow"))
ck("double-ctrl preserved as 0x8000", o["HotKeys"]["HotKeyMainWindow"] == 0x8000,
   hex(o["HotKeys"].get("HotKeyMainWindow", 0)))
ck("auto -> index 1", o["AutoDetection"]["LanguageFirst"] == 1)
ck("fr -> LanguageSecond", o["AutoDetection"]["LanguageSecond"] == 21,
   o["AutoDetection"].get("LanguageSecond"))
ck("options backup written", os.path.isfile(opts + ".bak"))
ck("both markers written",
   os.path.isfile(os.path.join(tmp, ".migrated_from_kotlin"))
   and os.path.isfile(os.path.join(tmp, ".migrated_to_kotlin")))
# untouched pb entry must still parse
entries, _ = read_pb(pb)
ck("disabled_plugin_ids entry preserved", any(k == "disabled_plugin_ids" for k, _, _ in entries))

# second run is a no-op
M._DONE = False
rep2 = M.migrate_if_needed(opts)
ck("second run skipped", rep2["skipped"] == "markers-present", str(rep2))

# ---------------------------------------------------------------- Python -> Kotlin
tmp, opts, pb = fresh_env()
kcfg2 = {
    "configVersion": 7,
    "interfaceLanguage": "en",
    "hotkeys": [{"action": "SHOW_QUICK_TRANSLATE", "keyCode": 81, "modifiers": 128,
                 "isEnabled": True, "scope": "GLOBAL", "isDoubleCtrlEnabled": True}],
    "kotlinOnlyField": {"nested": [1, 2, 3]},
    "servicePresets": [{"id": "p1", "name": "__default__",
                        "selectedServices": {"TRANSLATOR": "google-services:default:google-translator"},
                        "comparisonTranslatorIds": []}],
    "activeServicePresetId": "p1",
}
write_pb(pb, json.dumps(kcfg2),
         extra_entries=[("disabled_plugin_ids", M._len_field(6, M._len_field(1, b"plugin-x")))])
options = C.default_config()
options["General"]["LocaleFoderName"] = "French"
options["General"]["EnableHistory"] = False
options["General"]["InstantTranslation"] = True
options["General"]["FontName"] = "Courier New"
options["General"]["TextSize"] = 12
options["General"]["MinimizeToTrayOnClose"] = True
options["General"]["MinimizeToTrayOnMinimize"] = True
options["General"]["MouseModeOn"] = True
options["General"]["MouseMode"] = 2
options["General"]["ShowServicesPane"] = False
options["Appearance"]["PopupAutoSize"] = False
options["Appearance"]["PopupAutoPos"] = False
options["Appearance"]["Transparency"] = 128
options["Appearance"]["PopupTimeout"] = 45
options["HotKeys"]["EnableHotKeys"] = False
options["HotKeys"]["HotKeyPopupWindow"] = 593
options["HotKeys"]["HotKeyReplaceSelection"] = 343  # Alt+W
options["HotKeys"]["HotKeyDictionary"] = 0
options["AutoDetection"]["LanguageFirst"] = 57
options["AutoDetection"]["LanguageSecond"] = 17
C.save(options, opts)
os.utime(pb, (time.time() - 100, time.time() - 100))
os.utime(opts, None)

rep = M.migrate_if_needed(opts)
ck("python->kotlin reported", rep["to_kotlin"] and not rep["from_kotlin"], str(rep))
entries, k2 = read_pb(pb)
ck("interfaceLanguage fr", k2.get("interfaceLanguage") == "fr", k2.get("interfaceLanguage"))
ck("history off", k2.get("isHistoryEnabled") is False)
ck("instant on", k2.get("isInstantTranslationEnabled") is True)
ck("font config", k2.get("uiFontConfig") == {"name": "Courier New", "size": 12},
   str(k2.get("uiFontConfig")))
ck("close behavior", k2.get("closeButtonBehavior") == "MINIMIZE_TO_TRAY")
ck("minimize behavior", k2.get("minimizeButtonBehavior") == "HIDE_TO_TRAY")
ck("selection translate-and-read", k2.get("selectionBehavior") == "TRANSLATE_AND_READ")
ck("services pane hidden",
   (k2.get("toolbarVisibility") or {}).get("isServicesPanelVisible") is False)
ck("popup flags", k2.get("isPopupAutoSizeEnabled") is False
   and k2.get("isPopupAutoPositionEnabled") is False)
ck("transparency pct", k2.get("popupTransparencyPercentage") == 50,
   k2.get("popupTransparencyPercentage"))
ck("popup timeout", k2.get("popupIdleTimeoutSeconds") == 45)
ck("global hotkeys off", k2.get("isGlobalHotkeysEnabled") is False)
binds = {b["action"]: b for b in k2.get("hotkeys", [])}
ck("Ctrl+Q kept", binds.get("SHOW_QUICK_TRANSLATE", {}).get("keyCode") == 81
   and binds.get("SHOW_QUICK_TRANSLATE", {}).get("modifiers") == 128)
ck("Alt+W -> REPLACE_WITH_TRANSLATION",
   binds.get("REPLACE_WITH_TRANSLATION", {}).get("keyCode") == 87
   and binds.get("REPLACE_WITH_TRANSLATION", {}).get("modifiers") == 512,
   str(binds.get("REPLACE_WITH_TRANSLATION")))
ck("unbound dictionary", binds.get("SHOW_DICTIONARY", {}).get("isEnabled") is False)
ck("vi source", k2.get("preferredSourceLanguage") == "vi", k2.get("preferredSourceLanguage"))
ck("en target", k2.get("preferredTargetLanguage") == "en")
ck("kotlin-only field preserved", k2.get("kotlinOnlyField") == {"nested": [1, 2, 3]})
ck("presets preserved", k2.get("servicePresets") == kcfg2["servicePresets"])
ck("pb backup written", os.path.isfile(pb + ".bak"))

# ---------------------------------------------------------------- fresh Kotlin side
tmp, opts, pb = fresh_env()
C.save(C.default_config(), opts)
rep = M.migrate_if_needed(opts)
ck("fresh datastore created", rep["to_kotlin"], str(rep))
entries, k3 = read_pb(pb)
ck("fresh config has default preset",
   len(k3.get("servicePresets", [])) == 1
   and k3.get("activeServicePresetId") == k3["servicePresets"][0]["id"])
ck("fresh config version stamped", k3.get("configVersion") == 7)
ck("fresh config has hotkey defaults", len(k3.get("hotkeys", [])) == 18)
ck("fresh markers", os.path.isfile(os.path.join(tmp, ".migrated_from_kotlin"))
   and os.path.isfile(os.path.join(tmp, ".migrated_to_kotlin")))

# pb with no configuration_json counts as "no Kotlin side"
tmp, opts, pb = fresh_env()
write_pb(pb, None, extra_entries=[("disabled_plugin_ids",
         M._len_field(6, M._len_field(1, b"p")))])
C.save(C.default_config(), opts)
rep = M.migrate_if_needed(opts)
ck("config-less pb does not clobber options", rep["to_kotlin"], str(rep))
entries, k4 = read_pb(pb)
ck("config-less pb got configuration_json", isinstance(k4, dict))

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_config_migration: all checks ok (%d assertions)" % n[0])
