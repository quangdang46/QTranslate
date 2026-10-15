"""1:1 port of Plugins/History/*.js (Csv/Html/Json/Txt).

Each exporter implements the exact JS functions:
header/item_begin/item/item_end/footer + file description/extension.
Item signature historyItem(a,b,c,d,e,f,g) =
(service, src, srcLang, tr, trLang, index, total).
"""
import json as _json
import os as _os

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
