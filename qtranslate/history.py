"""1:1 port of Plugins/History/*.js (Csv/Html/Json/Txt).

Each exporter implements the exact JS functions:
header/item_begin/item/item_end/footer + file description/extension.
Item signature historyItem(a,b,c,d,e,f,g) =
(service, src, srcLang, tr, trLang, index, total).
"""
import json as _json
import os as _os

# ------------------------------------------------------- persistence I/O
# The History window's own save path. ``qtranslate.qt.app`` owns the
# canonical ``_load_history``/``_save_history`` pair, but its writer
# truncates every entry to ``list(x)[:3]`` -- which silently drops the
# 4th "favorite" slot the History window toggles. These helpers persist
# the same ``History.json`` file while keeping up to four slots, so a
# starred entry survives a save issued from the window itself. Until
# ``app._save_history`` is widened the same way, a later ``push_hist``
# still strips the flag -- see the call-site note in
# ``clear_history_on_exit``'s docstring / module docs.

# Mirrors ``qtranslate.qt.app.HISTORY_LIMIT`` (500, oldest dropped).
# Duplicated rather than imported: history.py is imported lazily and
# must not pull in the Qt app module at import time.
HISTORY_LIMIT = 500
HISTORY_FILE_NAME = "History.json"


def history_file_path():
    """Resolve ``History.json``'s path.

    Prefers ``qtranslate.qt.app._history_path`` so test harnesses that
    monkeypatch ``app.HISTORY_PATH`` redirect this writer too; falls
    back to ``app_data_dir()/History.json`` when the app module is not
    importable (e.g. a headless context that only uses the exporters).
    """
    try:
        from qtranslate.qt.app import _history_path as _app_path
        path = _app_path()
        if path:
            return path
    except Exception:                       # noqa: BLE001
        pass
    try:
        from qtranslate.platforms import app_data_dir
        return _os.path.join(app_data_dir(), HISTORY_FILE_NAME)
    except Exception:                       # noqa: BLE001
        return ""


def save_history_items(items, limit=HISTORY_LIMIT):
    """Persist ``items`` to ``History.json``, oldest first, capped.

    Each entry keeps up to four slots: ``(service, source, result)``
    plus the optional favorite flag the History window stores in slot
    3. Returns True on success; persistence is best-effort like the
    app's own writer, so failures return False rather than raise.
    """
    try:
        path = history_file_path()
        if not path:
            return False
        directory = _os.path.dirname(path)
        if directory:
            _os.makedirs(directory, exist_ok=True)
        kept = [list(x)[:4] for x in list(items or [])[-limit:]]
        # Write-then-rename like config.save: a crash mid-write must not
        # leave a truncated History.json behind.
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            _json.dump(kept, fh, ensure_ascii=False)
        _os.replace(tmp, path)
        return True
    except Exception:                       # noqa: BLE001 -- read-only disk
        return False


def clear_history_on_exit(app=None):
    """Consume ``General.ClearHistoryOnExit`` at shutdown.

    Native clears the persisted history when the app exits if the
    setting is on (``qtranslate.config`` defaults it to True). Nothing
    in ``qtranslate/`` called this before: the option was written by
    the Settings page but never read, so history always survived a
    restart.

    ``app`` is the ``QtApp`` instance when the caller has one; its
    in-memory ``history`` list is emptied too. Returns True when the
    setting was on and the file was cleared (or already empty), False
    when the setting is off or persistence failed.

    CALL SITE NEEDED (this module cannot reach the event loop itself):
    ``qtranslate/qt/app.py`` should invoke this once the Qt loop ends --
    either at the top of ``QtApp.quit`` (app.py:~1270, which the tray's
    Quit also funnels through) or immediately after
    ``app.qapp.exec()`` returns in ``main()`` (app.py:~1867). A bare
    ``atexit`` hook inside this module would NOT be reliable: the module
    is imported lazily (first Save-as / history-window use), so it is
    often absent from ``sys.modules`` at interpreter exit.
    """
    try:
        from qtranslate import config as _C
        enabled = bool((_C.load() or {}).get("General", {})
                       .get("ClearHistoryOnExit", True))
    except Exception:                       # noqa: BLE001
        # The config default for this key is True; mirror it when the
        # settings file cannot be read at all.
        enabled = True
    if not enabled:
        return False
    try:
        if app is not None:
            app.history = []
    except Exception:                       # noqa: BLE001
        pass
    return save_history_items([])

# ------------------------------------------------------------------- Csv.js
CSV_DESCRIPTION = "CSV file"
CSV_EXTENSION = "csv"


def _qcsv(v):
    """Port of escapeValue(a)."""
    return '"{}"'.format((v or "").replace('"', '""'))


def csv_header():
    return ""


def csv_item_begin(src, service):
    return ""


def csv_item(src, service, src_lang, tr, tr_lang, i, n):
    # native Csv.js: [escapeValue(a),escapeValue(c),escapeValue(b),
    # escapeValue(e),escapeValue(d)]. With Txt/Json/Html all agreeing
    # that `a` is the SOURCE TEXT and `b` the service, that order is
    # src, srcLang, service, trLang, tr -- NOT the service-first order
    # this function used to emit. Columns 1 and 3 were swapped; a
    # spreadsheet user read the service name under the source column.
    return ",".join([_qcsv(src), _qcsv(src_lang), _qcsv(service),
                     _qcsv(tr_lang), _qcsv(tr)]) + "\n"


def csv_item_end(src, service):
    return ""


def csv_footer():
    return ""


def csv_export(items):
    out = [csv_header()]
    total = len(items)
    for i, (s, src, sl, tr, tl) in enumerate(items):
        out.append(csv_item_begin(src, s))
        out.append(csv_item(src, s, sl, tr, tl, i, total))
        out.append(csv_item_end(src, s))
    out.append(csv_footer())
    return "".join(out)


# ------------------------------------------------------------------ Html.js
HTML_DESCRIPTION = "Html file"
HTML_EXTENSION = "html"
HTML_STYLE = (
    "table {font:normal 80% Segoe UI,arial,sans-serif;"
    "border-collapse:collapse;}\r\n"
    ".th {vertical-align:top;padding: 4px;border: 1px solid #c1c1c2;"
    "color:#1e1e1f;background-color: #e7e7e8;}\r\n"
    "table td {padding: 4px;border: 1px solid #c1c1c2;color:#1382ce;"
    "background-color: #f7f7f8;}\r\n")


def _qhtml(v):
    """Port of quoteHtml(a)."""
    if not v:
        return "&nbsp;"
    return v.replace("&", "&amp;").replace(">", "&gt;") \
        .replace("<", "&lt;").replace("\r\n", "<br>").replace("\r", "<br>")


def html_header():
    return ('<!DOCTYPE HTML>\r\n<html>\r\n<head><style type="text/css">\r\n'
            + HTML_STYLE + '</style>\r\n</head>\r\n<body>\r\n')


def html_item_begin(src, service):
    return ("<table>\r\n<tr><td class='th'></td><td>" + _qhtml(src)
            + "</td></tr>\r\n")


def html_item(src, service, src_lang, tr, tr_lang, i, n):
    return ("<tr><td class='th'>" + service + " (" + src_lang + " to "
            + tr_lang + ")</td><td>" + _qhtml(tr) + "</td></tr>\r\n")


def html_item_end(src, service):
    return "</table><br>\r\n"


def html_footer():
    return "</body>\r\n</html>"


def html_export(items):
    out = [html_header()]
    for s, src, sl, tr, tl in items:
        out.append(html_item_begin(src, s))
        out.append(html_item(src, s, sl, tr, tl, 0, 0))
        out.append(html_item_end(src, s))
    out.append(html_footer())
    return "".join(out)


# ------------------------------------------------------------------ Json.js
JSON_DESCRIPTION = "JSON file"
JSON_EXTENSION = "json"


def json_header():
    return "["


def json_item_begin(src, service):
    return '{"src":' + _json.dumps(src, ensure_ascii=False) + ',"trs":['


def json_item(src, service, src_lang, tr, tr_lang, i, n):
    """The translation object, with NO trailing separator.

    Native Json.js writes one here too -- ``...+"}"+(g<f-1?",":"")`` --
    AND its ``historyItemEnd`` writes ``"]}"+(b<a-1?",":"")``. Read the
    only coherent way (7-arg signature; the trailing pair is (count,
    index) in both), **both tests fire for every non-last entry**, so
    native emits two commas per separator: one inside ``trs`` (a trailing
    comma, illegal) and one between the top-level objects. Transcribed and
    run, native's 2-entry export is invalid JSON:

        [{"src":"a","trs":[{...},]},{"src":"b","trs":[{...}]}]

    The port emits exactly one separator, in ``json_item_end`` where it is
    well-formed, and none here. **That is a port-side fix for a native
    bug, recorded as a divergence** -- see
    `docs/review/HISTORY_JSON_NATIVE_BUG_2026-10-16.md`. Single-entry
    exports are byte-identical to native, because with n==1 neither test
    fires.
    """
    return ('{"service":' + _json.dumps(service, ensure_ascii=False)
            + ',"srcLang":' + _json.dumps(src_lang, ensure_ascii=False)
            + ',"trLang":' + _json.dumps(tr_lang, ensure_ascii=False)
            + ',"tr":' + _json.dumps(tr, ensure_ascii=False) + "}")


def json_item_end(src, service, i=None, n=None):
    # Native Json.js historyItemEnd: "]}" closes the "trs" array AND the
    # enclosing {"src":..,"trs":..} object -- which is where the separator
    # belongs. (An earlier port returned "]" and never closed the object,
    # so the whole export was invalid JSON.)
    #
    # The port takes native's "(b<a-1)" as "not the last entry" and puts
    # the ONE comma here, after the closed object.
    if i is None or n is None:
        return "]}"
    return "]}" + ("," if i < n - 1 else "")


def json_footer():
    return "]"


def json_export(items):
    out = [json_header()]
    total = len(items)
    for i, (s, src, sl, tr, tl) in enumerate(items):
        out.append(json_item_begin(src, s))
        out.append(json_item(src, s, sl, tr, tl, i, total))
        out.append(json_item_end(src, s, i, total))
    out.append(json_footer())
    return "".join(out)


# ------------------------------------------------------------ Kotlin compat
# ``History.json`` <-> the .tmp port's ``HistorySnapshot`` DataStore
# format lives in ``qtranslate.history_migrate`` (kept out of this file
# so the exporters above stay a 1:1 native port). These thin aliases
# keep the public names reachable from ``history``.
def export_history_snapshots(path=None):
    """``History.json`` -> list of HistorySnapshot-shaped dicts."""
    from qtranslate import history_migrate
    return history_migrate.export_history_snapshots(path)


def import_history_snapshots(snapshots, path=None, limit=None):
    """Merge HistorySnapshot dicts into ``History.json``; returns added."""
    from qtranslate import history_migrate
    kwargs = {} if limit is None else {"limit": limit}
    return history_migrate.import_history_snapshots(
        snapshots, path=path, **kwargs)


# ------------------------------------------------------------------- Txt.js
TXT_DESCRIPTION = "Text file"
TXT_EXTENSION = "txt"


def txt_header():
    return ""


def txt_item_begin(src, service):
    return src + "\r\n\r\n"


def txt_item(src, service, src_lang, tr, tr_lang, i, n):
    return ("[" + service + " > " + src_lang + " to " + tr_lang + "]\r\n"
            + tr + "\r\n\r\n")


def txt_item_end(src, service):
    return "================================\r\n\r\n"


def txt_footer():
    return ""


def txt_export(items):
    out = [txt_header()]
    for s, src, sl, tr, tl in items:
        out.append(txt_item_begin(src, s))
        out.append(txt_item(src, s, sl, tr, tl, 0, 0))
        out.append(txt_item_end(src, s))
    out.append(txt_footer())
    return "".join(out)


EXPORTERS = {"csv": csv_export, "html": html_export,
             "json": json_export, "txt": txt_export}

# Extension -> exporter, and a human description per extension, mirroring
# the `historyFileDescription` string native pairs with each
# `historyFileExtension` (FUN_00428483). Native's history export is not
# hardwired to HTML: it walks the registered `plugins::HistoryScript`
# objects, asks each for its `historyFileExtension`, and uses the first
# plugin whose extension matches `PathFindExtensionW(path)`. The port
# ships the same four formats as built-ins rather than plugin DLLs, so
# the dispatch shape is reproduced with a dict instead of a vtable walk;
# the selection RULE (first match on the file's own extension) is native's.
EXT_DESCRIPTIONS = {
    "html": "HTML file",
    "csv": "CSV file",
    "json": "JSON file",
    "txt": "Text file",
}

# Native's first registered format wins a collision. dict insertion order
# gives us that for free, so keep this list in the order the port's
# exporters were registered above.
EXPORT_ORDER = ("html", "csv", "json", "txt")


def exporter_for(path):
    """The exporter native's FUN_00428483 would pick for ``path``.

    PathFindExtensionW yields the file's extension INCLUDING the dot;
    native compares it against each plugin's historyFileExtension. We
    normalise to lowercase and strip the dot. Returns ``None`` when no
    built-in handles the extension -- the caller must then report that,
    because native would either fall through to its remaining plugins or
    write nothing, never silently write HTML.
    """
    ext = _os.path.splitext(str(path or ""))[1].lower().lstrip(".")
    if not ext:
        # No extension at all: FUN_00428483 bails before asking any plugin
        # ("if (*(int *)(LPCWSTR)*param_2 + -6) == 0)" -> return 0), so an
        # extension-less path selects nothing.
        return None
    for cand in EXPORT_ORDER:
        if cand == ext:
            return EXPORTERS[cand]
    return None


def describe_extension(ext):
    """Human label for an extension (native's historyFileDescription)."""
    return EXT_DESCRIPTIONS.get(str(ext or "").lower().lstrip("."), "")
