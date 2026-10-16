"""Regression: history exporters reproduce native Plugins/History/*.js.

Read against the four installed plugin files, expression for expression.

Three things this pins, all fixed or recorded 2026-10-16:

* **CSV -- columns 1 and 3 were swapped.** ``[a,c,b,e,d]`` is
  ``src, srcLang, service, trLang, tr``: all four plugins agree ``a`` is
  the SOURCE TEXT (Txt's begin prints it, Json's begin keys it as
  ``"src"``). The port emitted ``service, srcLang, src, trLang, tr``, so
  a spreadsheet read the service name under the source column.
* **JSON -- native writes the separator TWICE** (once in
  ``historyItem``, once in ``historyItemEnd``), which makes native's own
  multi-entry export invalid JSON. The port emits it once, in
  ``item_end``: a port-side fix for a native bug, documented in
  ``docs/review/HISTORY_JSON_NATIVE_BUG_2026-10-16.md``. The suite
  asserts the fix, not native's broken output.

Also kept from 2026-10-09: ``json_item_end`` returns ``"]}"``, not ``"]"``.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from qtranslate import history as H  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


ITEMS = [("Google", "hello", "en", "xin chao", "vi"),
         ("DeepL", "bye", "en", "tam biet", "vi")]

# --- JSON: must parse and round-trip the native shape ---------------------
j = H.json_export(ITEMS)
try:
    data = json.loads(j)
    ok = True
except Exception as e:
    data, ok = None, str(e)
check("json export is valid JSON (the fixed comma placement)", ok is True,
      str(ok))
check("json export has 2 top-level entries", ok is True and len(data) == 2)
if ok is True:
    check("json entry shape {src,trs:[{service,srcLang,trLang,tr}]}",
          data[0]["src"] == "hello"
          and data[0]["trs"][0] == {"service": "Google", "srcLang": "en",
                                    "trLang": "vi", "tr": "xin chao"},
          json.dumps(data[0]))
    check("json entry 2 is its own object",
          data[1]["src"] == "bye" and data[1]["trs"][0]["service"] == "DeepL",
          json.dumps(data[1]))

# the separator lives in json_item_end (port fix for the native double
# comma -- see the module docstring and the 2026-10-16 note).
check("json_item emits NO separator (native's would be one of two)",
      not H.json_item("a", "Google", "en", "x", "vi", 0, 2).endswith(","))
check("json_item_end closes ']}' and adds ONE separator mid-list",
      H.json_item_end("a", "Google", 0, 2) == "]},"
      and H.json_item_end("a", "Google", 1, 2) == "]}")
check("json_item_end called with no indices just closes (2-arg callers)",
      H.json_item_end("a", "Google") == "]}")

# single + empty still valid
json.loads(H.json_export(ITEMS[:1]))
json.loads(H.json_export([]))
json.loads(H.json_export([("G", "", "", "", "")]))
check("json single/empty/blank still parse", True)

# --- CSV: native Csv.js order [a,c,b,e,d] = src,srcLang,service,trLang,tr --
# the port's signature is now native's: csv_item(src, service, src_lang,
# tr, tr_lang, i, n), where `src` is the SOURCE TEXT.
line = H.csv_item("hello", "Google", "en", "xin chao", "vi", 0, 1)
check("csv order src,srcLang,service,trLang,tr",
      line == '"hello","en","Google","vi","xin chao"\n', line)
check("csv quotes and doubles an embedded quote",
      H.csv_item('he"llo', "G", "en", "x", "vi", 0, 1)
      == '"he""llo","en","G","vi","x"\n',
      H.csv_item('he"llo', "G", "en", "x", "vi", 0, 1))
check("csv with an empty field still quotes it",
      H.csv_item("", "G", "en", "x", "vi", 0, 1)
      == '"","en","G","vi","x"\n',
      H.csv_item("", "G", "en", "x", "vi", 0, 1))

# --- TXT: native Txt.js framing ------------------------------------------
txt = H.txt_export([("Google", "hello", "en", "xin chao", "vi")])
check("txt begins with source + blank line (native 'a' is the src)",
      txt.startswith("hello\r\n\r\n"))
check("txt bracket line [service > srcLang to trLang]",
      "[Google > en to vi]\r\n" in txt)
check("txt separator line", "================================" in txt)

# --- HTML: the node.js quoteHtml order and the empty -> &nbsp; -----------
from qtranslate.history import _qhtml  # noqa: E402

check("quoteHtml & first, then >, then < (order matters)",
      _qhtml("&<>") == "&amp;&lt;&gt;", _qhtml("&<>"))
check("quoteHtml of empty is &nbsp;", _qhtml("") == "&nbsp;"
      and _qhtml(None) == "&nbsp;")
check("quoteHtml turns CR/LF and CRLF into <br>",
      _qhtml("a\r\nb\rc") == "a<br>b<br>c", _qhtml("a\r\nb\rc"))

# --- byte-verified against the payload's own copies of the four plugins ---
# This half reads the JS out of the artifact (never executed), so a
# divergence is a port bug and not two copies of the same mistake. The
# four exporters appear consecutively, each starting at
# `function historyHeader(){`, so the region up to the next such marker is
# exactly one exporter.
import io  # noqa: E402

PAYLOAD = os.path.join(REPO, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")
if os.path.exists(PAYLOAD):
    TS = io.open(PAYLOAD, "rb").read().decode("utf-8", "replace")
    starts = [m.start() for m in
              re.finditer(r"function historyHeader\(\)\{", TS)]
    check("the payload carries exactly 4 history exporters",
          len(starts) == 4, str(len(starts)))
    EXPORTERS = {}
    for k, s in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(TS)
        m = re.search(r'function historyFileExtension\(\)\{return"(\w+)"\}',
                      TS[s:end])
        if m:
            EXPORTERS[m.group(1)] = TS[s:end]
    check("extensions csv/html/json/txt all present",
          sorted(EXPORTERS) == ["csv", "html", "json", "txt"],
          str(sorted(EXPORTERS)))

    csv, js, ht = (EXPORTERS.get("csv", ""), EXPORTERS.get("json", ""),
                   EXPORTERS.get("html", ""))
    # NOTE on the slicing: the payload concatenates the plugin files, so a
    # region cut at the next `function historyHeader(){` ends with the NEXT
    # file's leading helper -- csv's region ends with Html.js's `quoteHtml`,
    # html's ends with Json.js's `escapeStr` preamble. That is why the
    # csv/html checks below look in the *neighbouring* region: the helper
    # belongs to the file whose region it trails.
    check("Csv's argument order is a,c,b,e,d (source first)",
          csv.index("escapeValue(a)") < csv.index("escapeValue(c)")
          < csv.index("escapeValue(b)") < csv.index("escapeValue(e)")
          < csv.index("escapeValue(d)"), "argument order changed")
    check("Csv joins with ',' (JS [].join() default)",
          '].join()+"\\n"' in csv, "the row separator changed")
    check("Html's quoteHtml escapes &, then >, then <, CRLF last",
          re.search(r'function quoteHtml\(a\)\{return a\?'
                    r'a\.replace\(/&/g\).*?replace\(/>/g\)'
                    r'.*?replace\(/</g\).*?replace\(/\\r\\n\|\\r/g', csv)
          is not None or
          re.search(r'function quoteHtml\(a\)\{return a\?'
                    r'a\.replace\(/&/g\).*?replace\(/>/g\)'
                    r'.*?replace\(/</g\).*?replace\(/\\r\\n\|\\r/g', ht)
          is not None,
          "quoteHtml not found in the expected order")
    check("Html's quoteHtml maps empty to &nbsp;",
          ':"&nbsp;"' in csv or ':"&nbsp;"' in ht)
    check("Html's table CSS is the port's HTML_STYLE",
          all(part in ht for part in
              ("border-collapse:collapse", "#c1c1c2", "#e7e7e8", "#1382ce"))
          and "Segoe UI" in ht)
    check("Json itemBegin opens {\"src\":...,\"trs\":[",
          '\'{"src":\'+escapeStr(a)+\',"trs":[\'' in js)
    check("Json item emits the 4 fields native names",
          all(('"%s":' % k) in js for k in ("service", "srcLang", "trLang",
                                            "tr")))
    check("Json historyItem carries its own comma (g<f-1) -- the native "
          "double-comma's first half",
          '+escapeStr(d)+"}"+(g<f-1?",","")}' in js)
    check("Json historyItemEnd carries the second half (b<a-1)",
          'function historyItemEnd(a,b){return"]}"+(b<a-1?",","")}' in js)
    check("Json footer is ']'", 'function historyFooter(){return"]"}' in js)
    check("Json's escapeStr is the JSON.stringify poly's table",
          'escMap={\'"\':\'\\\\"\',"\\\\":"\\\\\\\\"' in ht
          and "charCodeAt(0)+65536).toString(16).substr(1)" in ht)


if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: history exporters match native (JSON comma + CSV order verified)")
