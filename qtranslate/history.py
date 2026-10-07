"""History export plugins — port of Plugins/History/*.js.

Each exporter implements: header/item_begin/item/item_end/footer +
file description/extension. Item args: (service, src, srcLang, tr, trLang,
index, total) matching the JS signature historyItem(a,b,c,d,e,f,g).
"""
import json as _json


def _qcsv(v):
    return '"{}"'.format((v or "").replace('"', '""'))


def csv_item(service, src, src_lang, tr, tr_lang, i, n):
    return ",".join([_qcsv(service), _qcsv(tr), _qcsv(src),
                      _qcsv(tr_lang), _qcsv(src_lang)]) + "\n"


def _qhtml(v):
    return (v or "").replace("&", "&amp;").replace(">", "&gt;") \
        .replace("<", "&lt;").replace("\r\n", "<br>").replace("\r", "<br>") \
        or "&nbsp;"


def html_export(items):
    out = ["<!DOCTYPE HTML>\r\n<html>\r\n<head></head>\r\n<body>\r\n"]
    for service, src, sl, tr, tl in items:
        out.append("<table>\r\n<tr><td></td><td>{}</td></tr>\r\n"
                   .format(_qhtml(src)))
        out.append("<tr><td>{} ({} to {})</td><td>{}</td></tr>\r\n"
                   .format(service, sl, tl, _qhtml(tr)))
        out.append("</table><br>\r\n")
    out.append("</body>\r\n</html>")
    return "".join(out)


def json_export(items):
    return _json.dumps(
        [{"service": s, "src": src, "srcLang": sl, "tr": tr, "trLang": tl}
         for s, src, sl, tr, tl in items],
        ensure_ascii=False, indent=1)


def txt_export(items):
    out = []
    for service, src, sl, tr, tl in items:
        out.append("{}\r\n\r\n[{} > {} to {}]\r\n{}\r\n\r\n"
                   "================================\r\n\r\n"
                   .format(src, service, sl, tl, tr))
    return "".join(out)


def csv_export(items):
    return "".join(csv_item(s, src, sl, tr, tl, i, len(items))
                    for i, (s, src, sl, tr, tl) in enumerate(items))


EXPORTERS = {"csv": csv_export, "html": html_export,
             "json": json_export, "txt": txt_export}
