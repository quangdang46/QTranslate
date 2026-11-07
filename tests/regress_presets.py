#!/usr/bin/env python3
"""Service presets (.tmp ServicePreset/PresetManager reduced to the
port's selection points): CRUD on General.ServicePresets,
apply -> General.ActiveService + ComparisonServices + ActivePresetId,
manual switch_service detaches the preset, and _load_session prefers
General.ActiveService over the ServicesOrder fallback."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate import presets as P  # noqa: E402

cfg = {}
p1 = P.create(cfg, "Google+Yandex", "google", ["yandex", "deepl"])
ck("create returns preset", p1["name"] == "Google+Yandex")
ck("uuid id", len(p1["id"]) == 12)
ck("stored", P.presets(cfg)[0]["translator"] == "google")
ck("comparison kept", P.presets(cfg)[0]["comparison"] ==
   ["yandex", "deepl"])

p2 = P.create(cfg, "DeepL only", "deepl", [])
ck("two presets", len(P.presets(cfg)) == 2)
ck("distinct ids", p1["id"] != p2["id"])

# rename / delete
ck("rename", P.rename(cfg, p1["id"], "G+Y") and
   P.find(cfg, p1["id"])["name"] == "G+Y")
ck("rename missing", not P.rename(cfg, "nope", "x"))
ck("delete", P.delete(cfg, p2["id"]) and len(P.presets(cfg)) == 1)
ck("delete missing", not P.delete(cfg, "nope"))

# malformed entries dropped
cfg2 = {"General": {"ServicePresets": [
    {"id": "a", "name": "ok", "translator": "google"},
    {"id": "", "name": "bad", "translator": "x"},
    "junk", None,
    {"name": "no-id"},
]}}
ck("malformed dropped", [p["name"] for p in P.presets(cfg2)] == ["ok"])
# string-encoded list tolerated
cfg3 = {"General": {"ServicePresets":
                    '[{"id":"s","name":"n","translator":"t"}]'}}
ck("json string parsed", len(P.presets(cfg3)) == 1)

# apply writes all three keys + active id
cfg4 = {}
pa = P.create(cfg4, "P", "deepl", ["google"])
P.apply(cfg4, pa)
g = cfg4["General"]
ck("apply translator", g["ActiveService"] == "deepl")
ck("apply comparison", g["ComparisonServices"] == ["google"])
ck("apply active id", g["ActivePresetId"] == pa["id"])
ck("find by id", P.find(cfg4, pa["id"])["name"] == "P")

# apply unknown id -> None, no writes
before = dict(cfg4["General"])
ck("apply unknown", P.apply(cfg4, "nope") is None)
ck("unknown no writes", cfg4["General"] == before)

# clear_active only when set
P.clear_active(cfg4)
ck("cleared", g["ActivePresetId"] == "")
cfg5 = {}
P.clear_active(cfg5)
ck("clear on empty ok", "ActivePresetId" not in cfg5["General"])

# deleting the active preset clears the marker
cfg6 = {}
px = P.create(cfg6, "X", "google", [])
P.apply(cfg6, px)
P.delete(cfg6, px["id"])
ck("delete clears active", P.active_id(cfg6) == "")

# snapshot reads live keys
cfg7 = {"General": {"ActiveService": "yandex",
                    "ComparisonServices": ["baidu"]}}
snap = P.snapshot(cfg7)
ck("snapshot", snap["translator"] == "yandex" and
   snap["comparison"] == ["baidu"])

# ---- app-level: switch_service persists + detaches; apply_preset
# ordering keeps the preset active; _load_session prefers ActiveService
from PySide6.QtWidgets import QApplication  # noqa: E402
_qapp = QApplication.instance() or QApplication([])

from qtranslate import config as _C  # noqa: E402
_saved = _C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
_C.DEFAULT_PATH = _tmp
try:
    from qtranslate.qt.app import QtApp  # noqa: E402
    from qtranslate.qt.main_window import MainWindow  # noqa: E402

    app = QtApp([])
    app.win = MainWindow(app)

    app.switch_service("deepl")
    cfg = _C.load()
    ck("switch persists ActiveService",
       cfg["General"].get("ActiveService") == "deepl")
    ck("switch cleared preset", cfg["General"].get("ActivePresetId") in
       (None, ""))

    # preset apply: translator + comparison + active id all land
    preset = {"id": "p1", "name": "Mix", "translator": "google",
              "comparison": ["deepl"]}
    ok = app.apply_preset(preset)
    ck("apply_preset ok", ok is True)
    cfg = _C.load()
    g = cfg["General"]
    ck("preset translator", g.get("ActiveService") == "google")
    ck("preset comparison", g.get("ComparisonServices") == ["deepl"])
    ck("preset still active", g.get("ActivePresetId") == "p1")
    ck("app service moved", app.service == "google")

    # manual switch AFTER apply detaches the preset again
    app.switch_service("yandex")
    cfg = _C.load()
    ck("manual switch re-detaches",
       cfg["General"].get("ActivePresetId") in (None, ""))
    ck("manual switch service",
       cfg["General"].get("ActiveService") == "yandex")

    # _load_session prefers ActiveService over ServicesOrder[0]
    # (the entry point calls it; the constructor does not)
    app2 = QtApp([])
    app2.win = MainWindow(app2)
    app2._load_session()
    ck("session restored ActiveService", app2.service == "yandex")

    # unknown preset id -> False, nothing applied
    ck("apply unknown preset", app.apply_preset("nope") is False)
finally:
    _C.DEFAULT_PATH = _saved
    try:
        os.unlink(_tmp)
    except OSError:
        pass

if FAIL:
    print("\nregress_presets: %d FAILURES" % len(FAIL))
    sys.exit(1)
print("\nregress_presets: all checks ok")
