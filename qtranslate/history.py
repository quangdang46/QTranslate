"""1:1 port of Plugins/History/*.js (Csv/Html/Json/Txt).

Each exporter implements the exact JS functions:
header/item_begin/item/item_end/footer + file description/extension.
Item signature historyItem(a,b,c,d,e,f,g) =
(service, src, srcLang, tr, trLang, index, total).
"""
import json as _json

# ------------------------------------------------------------------- Csv.js
CSV_DESCRIPTION = "CSV file"
CSV_EXTENSION = "csv"


def _qcsv(v):
    """Port of escapeValue(a)."""
    return '"{}"'.format((v or "").replace('"', '""'))


def csv_header():
    return ""


def csv_item_begin(service, src):
    return ""


def csv_item(service, src, src_lang, tr, tr_lang, i, n):
    # note the native column order: service, tr, src, trLang, srcLang
    return ",".join([_qcsv(service), _qcsv(tr), _qcsv(src),
                     _qcsv(tr_lang), _qcsv(src_lang)]) + "\n"


def csv_item_end(service, src):
    return ""


def csv_footer():
    return ""


def csv_export(items):
    out = [csv_header()]
    total = len(items)
    for i, (s, src, sl, tr, tl) in enumerate(items):
        out.append(csv_item_begin(s, src))
        out.append(csv_item(s, src, sl, tr, tl, i, total))
        out.append(csv_item_end(s, src))
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


def html_item_begin(service, src):
    return ("<table>\r\n<tr><td class='th'></td><td>" + _qhtml(src)
            + "</td></tr>\r\n")


def html_item(service, src, src_lang, tr, tr_lang, i, n):
    return ("<tr><td class='th'>" + service + " (" + src_lang + " to "
            + tr_lang + ")</td><td>" + _qhtml(tr) + "</td></tr>\r\n")


def html_item_end(service, src):
    return "</table><br>\r\n"


def html_footer():
    return "</body>\r\n</html>"


def html_export(items):
    out = [html_header()]
    for s, src, sl, tr, tl in items:
        out.append(html_item_begin(s, src))
        out.append(html_item(s, src, sl, tr, tl, 0, 0))
        out.append(html_item_end(s, src))
    out.append(html_footer())
    return "".join(out)


# ------------------------------------------------------------------ Json.js
JSON_DESCRIPTION = "JSON file"
JSON_EXTENSION = "json"


def json_header():
    return "["


def json_item_begin(service, src):
    return '{"src":' + _json.dumps(src) + ',"trs":['


def json_item(service, src, src_lang, tr, tr_lang, i, n):
    return ('{"service":' + _json.dumps(service)
            + ',"srcLang":' + _json.dumps(src_lang)
            + ',"trLang":' + _json.dumps(tr_lang)
            + ',"tr":' + _json.dumps(tr) + "}"
            + ("," if i < n - 1 else ""))


def json_item_end(service, src, i, n):
    return "]" + ("," if i < n - 1 else "")


def json_footer():
    return "]"


def json_export(items):
    out = [json_header()]
    total = len(items)
    for i, (s, src, sl, tr, tl) in enumerate(items):
        out.append(json_item_begin(s, src))
        out.append(json_item(s, src, sl, tr, tl, i, total))
        out.append(json_item_end(s, src, i, total))
    out.append(json_footer())
    return "".join(out)


# ------------------------------------------------------------------- Txt.js
TXT_DESCRIPTION = "Text file"
TXT_EXTENSION = "txt"


def txt_header():
    return ""


def txt_item_begin(service, src):
    return src + "\r\n\r\n"


def txt_item(service, src, src_lang, tr, tr_lang, i, n):
    return ("[" + service + " > " + src_lang + " to " + tr_lang + "]\r\n"
            + tr + "\r\n\r\n")


def txt_item_end(service, src):
    return "================================\r\n\r\n"


def txt_footer():
    return ""


def txt_export(items):
    out = [txt_header()]
    for s, src, sl, tr, tl in items:
        out.append(txt_item_begin(s, src))
        out.append(txt_item(s, src, sl, tr, tl, 0, 0))
        out.append(txt_item_end(s, src))
    out.append(txt_footer())
    return "".join(out)


EXPORTERS = {"csv": csv_export, "html": html_export,
             "json": json_export, "txt": txt_export}
