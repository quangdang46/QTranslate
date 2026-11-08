"""History compatibility between the two apps' history stores.

Python (``qtranslate/qt/app.py``) persists ``History.json`` -- a JSON
array of ``[service, sourceText, resultText]`` entries, with an optional
4th slot holding the History window's favorite flag. The Kotlin port
(``.tmp/QTranslate``) persists ``HistorySnapshot`` objects::

    {inputText, translatedText, sourceLanguage, targetLanguage,
     translatorId, timestamp, detectedSourceLanguage,
     extraOutputText, extraOutputType}

as a JSON string inside the DataStore preferences file
``datastore/history.preferences_pb`` (key ``translation_history_json``,
cap ``AppConstants.MAX_HISTORY_ENTRIES`` = 1000 -- see
``core/.../shared/AppConstants.kt`` and ``history/HistoryRepository.kt``).

This module converts between the two shapes:

* :func:`export_history_snapshots` reads ``History.json`` and returns a
  list of ``HistorySnapshot``-shaped dicts -- the same JSON the Kotlin
  ``kotlinx.serialization`` decoder accepts, so the file doubles as the
  interchange format both sides can read.
* :func:`import_history_snapshots` merges such dicts back into
  ``History.json``. Entries already present (same service + texts) keep
  their existing row -- including the favorite 4th slot, which has no
  counterpart in ``HistorySnapshot`` -- and imported rows are appended
  ordered by ``timestamp``.
* :func:`extract_datastore_history` reads a ``history.preferences_pb``
  file directly with a minimal protobuf wire-format scan (no protobuf
  dependency) and returns the same snapshot dicts.

Known losses, by design:

* Python stores no languages or timestamps. Exported snapshots get
  ``sourceLanguage``/``targetLanguage`` = ``"auto"`` and a synthetic
  timestamp that only preserves row order; ``detectedSourceLanguage``
  is ``None``.
* ``HistorySnapshot`` has no favorite flag, so imports produce 3-slot
  rows. Re-exporting a merged ``History.json`` keeps each row's fav
  slot because export reads the file, not the snapshot list.
* ``extraOutputText``/``extraOutputType`` have no Python slot; imports
  drop them (documented here rather than smuggled into slot 4, which
  the History window reads as a boolean favorite).

CLI (manual use)::

    python -m qtranslate.history_migrate export [--history FILE] [--out FILE]
    python -m qtranslate.history_migrate import --snapshots FILE [--history FILE]
    python -m qtranslate.history_migrate extract-pb --pb FILE [--out FILE]
"""
import argparse as _argparse
import json as _json
import os as _os
import sys as _sys
import time as _time

from qtranslate import history as _history

# Kotlin ``AppConstants.MAX_HISTORY_ENTRIES`` -- wider than the Python
# app's own 500-entry ``HISTORY_LIMIT`` so an imported Kotlin history
# survives intact in the file even though the Python UI trims to 500
# on its next load.
KOTLIN_HISTORY_LIMIT = 1000

# Snapshot field names, mirroring
# ``core/.../history/HistorySnapshot.kt`` (@Serializable data class).
SNAPSHOT_FIELDS = (
    "inputText", "translatedText", "sourceLanguage", "targetLanguage",
    "translatorId", "timestamp", "detectedSourceLanguage",
    "extraOutputText", "extraOutputType",
)

# ---------------------------------------------------------------------
# service name <-> Kotlin translatorId (ServiceId "plugin:instance:key")
# ---------------------------------------------------------------------
# ``qtranslate/config.py::SERVICE_NAMES`` -> the Kotlin plugin that
# covers the same engine. Only engines present in BOTH apps are mapped;
# everything else passes through verbatim (a bare Python name is not a
# parseable ServiceId, so it round-trips losslessly as "unknown").
_SERVICE_TO_TRANSLATOR_ID = {
    "google":    "google-services:default:google-translator",
    # Python "microsoft" is the Edge/Microsoft translator; the Kotlin
    # port's closest engine is Bing (same Microsoft backend family).
    "microsoft": "bing-services:default:bing-translator",
    "yandex":    "yandex-web-services:default:yandex-web-translator",
    "deepl":     "deepl-services:default:deepl-services-translator",
}

# Reverse of the above, keyed by the ServiceId's serviceKey (3rd
# segment). Built once so both directions stay in sync.
_TRANSLATOR_KEY_TO_SERVICE = {
    "google-translator":          "google",
    "bing-translator":            "microsoft",
    "yandex-web-translator":      "yandex",
    "deepl-services-translator":  "deepl",
}


def service_to_translator_id(service):
    """Map a Python service name to a Kotlin ``ServiceId`` string.

    Unmapped services (promt, babylon, baidu, youdao, naver, ...) have
    no Kotlin plugin; they are returned unchanged so the value remains
    a faithful, if unresolvable, record of what produced the text.
    """
    name = str(service or "")
    return _SERVICE_TO_TRANSLATOR_ID.get(name, name)


def translator_id_to_service(translator_id):
    """Map a Kotlin ``translatorId`` back to a Python service name.

    Parses ``pluginId:instanceId:serviceKey``; known service keys map
    back to the Python engine name. Anything else falls back to the
    plugin id, then the raw string -- which for an unmapped Python name
    (stored verbatim by :func:`service_to_translator_id`) is exactly
    the original service.
    """
    tid = str(translator_id or "")
    parts = tid.split(":")
    if len(parts) == 3:
        mapped = _TRANSLATOR_KEY_TO_SERVICE.get(parts[2])
        if mapped:
            return mapped
        return parts[0] or tid
    return tid


# ---------------------------------------------------------------------
# History.json <-> snapshot dicts
# ---------------------------------------------------------------------

def _load_history_entries(path):
    """Raw ``History.json`` rows (lists, len >= 3), oldest first."""
    try:
        with open(path, encoding="utf-8") as fh:
            items = _json.load(fh)
    except Exception:                       # noqa: BLE001 -- fresh install
        return []
    return [list(x) for x in items
            if isinstance(x, (list, tuple)) and len(x) >= 3]


def _entry_key(entry):
    """Identity of a history row for merge dedup: service + both texts.

    The fav 4th slot is deliberately excluded -- two rows differing
    only in favorite-ness are the same translation.
    """
    return (str(entry[0]), str(entry[1]), str(entry[2]))


def snapshot_from_history_entry(entry, timestamp=None):
    """One ``History.json`` row -> ``HistorySnapshot``-shaped dict.

    Python rows carry no languages, so both language fields export as
    ``"auto"`` (the Kotlin ``LanguageCode.AUTO`` tag) and
    ``detectedSourceLanguage`` stays ``None``. ``timestamp`` defaults
    to the current time in ms; callers exporting a whole file should
    pass a per-row synthetic value to preserve ordering -- see
    :func:`export_history_snapshots`.
    """
    service, src, res = entry[0], entry[1], entry[2]
    return {
        "inputText": str(src),
        "translatedText": str(res),
        "sourceLanguage": "auto",
        "targetLanguage": "auto",
        "translatorId": service_to_translator_id(service),
        "timestamp": int(timestamp if timestamp is not None
                         else _time.time() * 1000),
        "detectedSourceLanguage": None,
        "extraOutputText": "",
        "extraOutputType": "None",
    }


def history_entry_from_snapshot(snapshot):
    """One snapshot dict -> ``History.json`` row ``[service, src, res]``.

    Returns ``None`` for snapshots missing the required text fields.
    Language fields are ignored (Python has nowhere to put them) and
    the favorite slot is never fabricated -- imports are always
    3-slot rows; a later merge keeps any pre-existing fav on a
    duplicate row instead.
    """
    try:
        src = snapshot.get("inputText")
        res = snapshot.get("translatedText")
        if src is None or res is None:
            return None
        service = translator_id_to_service(snapshot.get("translatorId"))
        return [service, str(src), str(res)]
    except Exception:                       # noqa: BLE001
        return None


def export_history_snapshots(path=None):
    """Export ``History.json`` as a list of ``HistorySnapshot`` dicts.

    ``path`` defaults to :func:`qtranslate.history.history_file_path`.
    Rows are returned oldest-first; ``timestamp`` is synthetic
    (1 ms apart, ending at "now") because ``History.json`` records no
    time -- it exists only to keep the Kotlin list's ordering stable.
    The 4th fav slot has no snapshot field and is dropped here; it is
    preserved on disk and restored by :func:`import_history_snapshots`.
    """
    path = path or _history.history_file_path()
    if not path:
        return []
    entries = _load_history_entries(path)
    now_ms = int(_time.time() * 1000)
    n = len(entries)
    return [snapshot_from_history_entry(
                e, timestamp=now_ms - (n - 1 - i))
            for i, e in enumerate(entries)]


def import_history_snapshots(snapshots, path=None,
                             limit=KOTLIN_HISTORY_LIMIT):
    """Merge ``HistorySnapshot`` dicts into ``History.json``.

    Existing rows win on duplicates (matched on service + texts), so a
    re-import never strips a favorite flag or reorders what is already
    there. New rows are appended ordered by ``timestamp`` (stable for
    ties and for entries lacking one), then the file is capped to the
    last ``limit`` rows -- Kotlin's own ``takeLast(1000)`` semantics.

    Returns the number of rows newly added. Persistence keeps up to
    four slots per row, same as ``qtranslate.history.save_history_items``.
    """
    path = path or _history.history_file_path()
    if not path:
        return 0
    existing = _load_history_entries(path)
    existing_keys = {_entry_key(e) for e in existing}

    stamped = []
    for pos, snap in enumerate(snapshots or []):
        entry = history_entry_from_snapshot(snap)
        if entry is None:
            continue
        key = _entry_key(entry)
        if key in existing_keys:
            continue
        try:
            ts = int((snap or {}).get("timestamp"))
        except (TypeError, ValueError):
            ts = 0
        stamped.append((ts, pos, entry))
        existing_keys.add(key)          # dedupe within the import too

    stamped.sort(key=lambda t: (t[0], t[1]))
    merged = existing + [e for _, _, e in stamped]
    merged = merged[-limit:] if limit else merged
    if not _save_history_entries(path, merged):
        return 0
    return len(stamped)


def _save_history_entries(path, entries):
    """Write rows to an explicit ``History.json`` path, 4-slot safe.

    Mirrors ``qtranslate.history.save_history_items`` but honours the
    caller's path (that helper always resolves the app data dir, which
    would make imports in tests/tools write the wrong file).
    """
    try:
        directory = _os.path.dirname(_os.path.abspath(path))
        if directory:
            _os.makedirs(directory, exist_ok=True)
        kept = [list(x)[:4] for x in list(entries or [])]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            _json.dump(kept, fh, ensure_ascii=False)
        _os.replace(tmp, path)
        return True
    except Exception:                       # noqa: BLE001 -- read-only disk
        return False


def load_snapshots_file(path):
    """Read a snapshot interchange JSON file -> list of dicts."""
    with open(path, encoding="utf-8") as fh:
        data = _json.load(fh)
    if isinstance(data, dict):
        data = data.get("history") or data.get("snapshots") or []
    if not isinstance(data, list):
        return []
    return [d for d in data if isinstance(d, dict)]


def save_snapshots_file(snapshots, path):
    """Write snapshot dicts as the interchange JSON (pretty, utf-8)."""
    directory = _os.path.dirname(_os.path.abspath(path))
    if directory:
        _os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        _json.dump(list(snapshots or []), fh, ensure_ascii=False,
                   indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------
# DataStore preferences_pb extraction
# ---------------------------------------------------------------------
# ``history.preferences_pb`` is an androidx DataStore Preferences proto:
# a ``PreferenceMap`` whose ``strings`` map holds
# ``"translation_history_json" -> Value{string = <json array>}``.
# Rather than depend on protobuf, walk the wire format generically and
# JSON-probe every length-delimited payload -- the history value is the
# only field whose payload decodes to a list of snapshot dicts.

def _read_varint(buf, pos):
    result = 0
    shift = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
        if shift > 63:
            break
    raise ValueError("truncated varint")


def _scan_wire_strings(buf, out, depth=0):
    """Collect every length-delimited payload, recursing into messages."""
    if depth > 6:
        return
    pos = 0
    n = len(buf)
    while pos < n:
        try:
            key, pos = _read_varint(buf, pos)
        except ValueError:
            return
        wire = key & 7
        if wire == 0:                       # varint
            try:
                _, pos = _read_varint(buf, pos)
            except ValueError:
                return
        elif wire == 1:                     # 64-bit
            pos += 8
        elif wire == 2:                     # length-delimited
            try:
                length, pos = _read_varint(buf, pos)
            except ValueError:
                return
            payload = buf[pos:pos + length]
            pos += length
            if len(payload) != length:
                return
            out.append(payload)
            _scan_wire_strings(payload, out, depth + 1)
        elif wire == 5:                     # 32-bit
            pos += 4
        else:
            return                          # groups/unknown: bail


def _looks_like_snapshots(data):
    return (isinstance(data, list) and bool(data)
            and all(isinstance(d, dict) for d in data)
            and any("inputText" in d or "translatedText" in d
                    for d in data))


def extract_datastore_history(pb_path):
    """Read ``history.preferences_pb`` -> list of ``HistorySnapshot`` dicts.

    Generic protobuf wire scan: every embedded string is JSON-probed and
    the payload that decodes to a non-empty list of snapshot-shaped dicts
    wins. Returns ``[]`` when the file is missing, unreadable, or holds
    no history (fresh install stores nothing under the key).
    """
    try:
        with open(pb_path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return []
    candidates = []
    _scan_wire_strings(raw, candidates)
    # Longest-first: the outermost container that still decodes as the
    # snapshot array is preferred over a coincidental inner match.
    for payload in sorted(candidates, key=len, reverse=True):
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            continue
        try:
            data = _json.loads(text)
        except ValueError:
            continue
        if _looks_like_snapshots(data):
            return data
    return []


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def _default_history_arg(parser):
    parser.add_argument("--history", default=None,
                        help="History.json path (default: app data dir)")


def main(argv=None):
    ap = _argparse.ArgumentParser(
        prog="python -m qtranslate.history_migrate",
        description="Convert history between History.json and the "
                    "Kotlin HistorySnapshot JSON format.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("export", help="History.json -> snapshots JSON")
    _default_history_arg(p)
    p.add_argument("--out", default=None,
                   help="output file (default: stdout)")

    p = sub.add_parser("import", help="snapshots JSON -> History.json")
    _default_history_arg(p)
    p.add_argument("--snapshots", required=True,
                   help="snapshot JSON file (from export or extract-pb)")
    p.add_argument("--limit", type=int, default=KOTLIN_HISTORY_LIMIT,
                   help="max History.json rows to keep (default 1000)")

    p = sub.add_parser("extract-pb",
                       help="history.preferences_pb -> snapshots JSON")
    p.add_argument("--pb", required=True,
                   help="path to datastore/history.preferences_pb")
    p.add_argument("--out", default=None,
                   help="output file (default: stdout)")

    args = ap.parse_args(argv)

    if args.cmd == "export":
        snaps = export_history_snapshots(args.history)
        text = _json.dumps(snaps, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            save_snapshots_file(snaps, args.out)
        else:
            _sys.stdout.write(text)
        return 0

    if args.cmd == "import":
        snaps = load_snapshots_file(args.snapshots)
        added = import_history_snapshots(snaps, path=args.history,
                                         limit=args.limit)
        print("imported {} new entr{}".format(
            added, "y" if added == 1 else "ies"), file=_sys.stderr)
        return 0

    if args.cmd == "extract-pb":
        snaps = extract_datastore_history(args.pb)
        if args.out:
            save_snapshots_file(snaps, args.out)
        else:
            _sys.stdout.write(_json.dumps(snaps, ensure_ascii=False,
                                          indent=2) + "\n")
        return 0

    return 2


if __name__ == "__main__":
    _sys.exit(main())
