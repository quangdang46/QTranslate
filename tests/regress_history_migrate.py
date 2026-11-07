"""History compat: History.json triples <-> Kotlin HistorySnapshot.

Covers qtranslate/history_migrate.py (bead qt-mef):

* export_history_snapshots maps [service, src, res(, fav)] rows to
  HistorySnapshot-shaped dicts (service -> translatorId ServiceId,
  langs "auto", synthetic ordering timestamps).
* import_history_snapshots merges snapshots back, dedupes on
  service+texts, appends in timestamp order, and keeps the fav 4th
  slot on pre-existing duplicate rows.
* extract_datastore_history pulls the JSON array out of a
  history.preferences_pb-style protobuf blob with no protobuf lib.

Fixture mixes 3-slot and 4-slot (favorite) entries; the round-trip
must keep the fav flag lossless.
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import history_migrate as HM          # noqa: E402

# Mixed fixture: 3-slot plain rows and 4-slot favorite rows, in the
# order History.json stores them (oldest first).
FIXTURE = [
    ["google", "hello", "xin chao"],
    ["deepl", "good morning", "chao buoi sang", 1],
    ["yandex", "thank you", "cam on"],
    ["promt", "unmapped service", "dich vu khong co", 0],
]


def _write_history(items, directory):
    path = os.path.join(directory, "History.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False)
    return path


def _read_history(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


tmp = tempfile.mkdtemp()
hist_path = _write_history(FIXTURE, tmp)

# --- export -------------------------------------------------------------
snaps = HM.export_history_snapshots(hist_path)
ck("export count", len(snaps) == 4, str(len(snaps)))
ck("export order", [s["inputText"] for s in snaps] ==
   ["hello", "good morning", "thank you", "unmapped service"])
ck("export google id",
   snaps[0]["translatorId"] == "google-services:default:google-translator",
   snaps[0]["translatorId"])
ck("export deepl id",
   snaps[1]["translatorId"] == "deepl-services:default:deepl-services-translator")
ck("export yandex id",
   snaps[2]["translatorId"] == "yandex-web-services:default:yandex-web-translator")
ck("export unmapped passthrough",
   snaps[3]["translatorId"] == "promt", snaps[3]["translatorId"])
ck("export langs auto",
   all(s["sourceLanguage"] == "auto" and s["targetLanguage"] == "auto"
       and s["detectedSourceLanguage"] is None for s in snaps))
ck("export snapshot keys",
   all(set(s) == set(HM.SNAPSHOT_FIELDS) for s in snaps))
ck("export timestamps monotonic",
   all(snaps[i]["timestamp"] < snaps[i + 1]["timestamp"]
       for i in range(len(snaps) - 1)))

# --- import round-trip ----------------------------------------------------
# Re-import the exported snapshots into a FRESH History.json: fav flags
# cannot survive a snapshot (the Kotlin type has no such field), so all
# rows come back 3-slot -- but a second merge against the ORIGINAL file
# must not disturb its fav slots.
empty_path = os.path.join(tmp, "empty.json")
with open(empty_path, "w") as fh:
    json.dump([], fh)
added = HM.import_history_snapshots(snaps, path=empty_path)
ck("import added", added == 4, str(added))
roundtrip = _read_history(empty_path)
ck("roundtrip rows",
   [[r[0], r[1], r[2]] for r in roundtrip] ==
   [["google", "hello", "xin chao"],
    ["deepl", "good morning", "chao buoi sang"],
    ["yandex", "thank you", "cam on"],
    ["promt", "unmapped service", "dich vu khong co"]],
   repr(roundtrip))
ck("roundtrip no fav fabricated",
   all(len(r) == 3 for r in roundtrip))

# Merge the same snapshots into the ORIGINAL file: every row duplicates
# an existing key, so nothing is added and fav slots stay put.
before = _read_history(hist_path)
added2 = HM.import_history_snapshots(snaps, path=hist_path)
ck("reimport dedupes", added2 == 0, str(added2))
ck("fav preserved", _read_history(hist_path) == before)

# --- import ordering + fav preservation on duplicates ---------------------
# Existing starred row + imported snapshots containing the same
# translation plus a NEWER one (higher timestamp): the new row lands
# after, the starred row keeps its flag.
existing_path = _write_history(
    [["google", "hello", "xin chao", 1]], tmp)
new_snaps = [
    {"inputText": "hi", "translatedText": "chao",
     "translatorId": "google-services:default:google-translator",
     "timestamp": 2000},
    {"inputText": "hello", "translatedText": "xin chao",
     "translatorId": "google-services:default:google-translator",
     "timestamp": 1000},   # older than the new one; still deduped
]
added3 = HM.import_history_snapshots(new_snaps, path=existing_path)
ck("merge adds only new", added3 == 1, str(added3))
merged_rows = _read_history(existing_path)
ck("fav kept on dup",
   merged_rows[0] == ["google", "hello", "xin chao", 1],
   repr(merged_rows[0]))
ck("new row appended", merged_rows[-1] == ["google", "hi", "chao"],
   repr(merged_rows[-1]))

# Reverse mapping sanity.
ck("id->service google",
   HM.translator_id_to_service(
       "google-services:default:google-translator") == "google")
ck("id->service unmapped plugin",
   HM.translator_id_to_service("foo-services:default:bar") == "foo-services")
ck("id->service bare passthrough",
   HM.translator_id_to_service("promt") == "promt")

# --- preferences_pb extraction ---------------------------------------------
# Build a minimal protobuf wire blob: outer message with a
# length-delimited field holding a nested message whose field 5 (string)
# is the JSON array -- the shape androidx DataStore produces.
def _varint(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _field_bytes(num, payload):
    return _varint((num << 3) | 2) + _varint(len(payload)) + payload


json_payload = json.dumps(snaps, ensure_ascii=False).encode("utf-8")
inner = _field_bytes(1, b"translation_history_json") \
    + _field_bytes(5, json_payload)          # Value.string = field 5
entry = _field_bytes(1, b"translation_history_json") \
    + _field_bytes(2, inner)                 # map entry: key=1, value=2
outer = _field_bytes(1, entry)               # PreferenceMap.strings = 1
pb_path = os.path.join(tmp, "history.preferences_pb")
with open(pb_path, "wb") as fh:
    fh.write(outer)

extracted = HM.extract_datastore_history(pb_path)
ck("pb extract count", len(extracted) == 4, str(len(extracted)))
ck("pb extract content",
   extracted and extracted[0]["inputText"] == "hello"
   and extracted[0]["translatorId"] ==
   "google-services:default:google-translator")
ck("pb missing file", HM.extract_datastore_history(
    os.path.join(tmp, "nope.preferences_pb")) == [])

# --- interchange file round-trip -------------------------------------------
snap_path = os.path.join(tmp, "snapshots.json")
HM.save_snapshots_file(snaps, snap_path)
loaded = HM.load_snapshots_file(snap_path)
ck("interchange file", len(loaded) == 4
   and loaded[1]["translatedText"] == "chao buoi sang")

print("{} checks, {} failed".format(n[0], len(fail)))
for f in fail:
    print("FAIL:", f)
sys.exit(1 if fail else 0)
