"""Regression: history exporters reproduce native Plugins/History/*.js.

Covers the JSON exporter bug fixed 2026-10-09: json_item_end returned "]"
instead of the native "]}" (which closes both the "trs" array and the
enclosing {"src":..,"trs":..} object), making the whole export invalid JSON.
Also checks the CSV column order [a,c,b,e,d] and the TXT framing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))

import json  # noqa: E402

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
check("json export is valid JSON", ok is True, str(ok))
check("json export has 2 top-level entries", ok is True and len(data) == 2)
if ok is True:
    check("json entry shape {src,trs:[{service,srcLang,trLang,tr}]}",
          data[0]["src"] == "hello"
          and data[0]["trs"][0] == {"service": "Google", "srcLang": "en",
                                    "trLang": "vi", "tr": "xin chao"},
          json.dumps(data[0]))
check("json_item_end closed the object (native ']}')",
      H.json_item_end("s", "x", 0, 1).startswith("]}"))
check("json_item_end adds separator comma between entries only",
      H.json_item_end("s", "x", 0, 2) == "]},"
      and H.json_item_end("s", "x", 1, 2) == "]}")

# single + empty still valid
json.loads(H.json_export(ITEMS[:1]))
json.loads(H.json_export([]))
check("json single/empty still parse", True)

# --- CSV: native Csv.js order [a,c,b,e,d] --------------------------------
line = H.csv_item("Google", "hello", "en", "xin chao", "vi", 0, 1)
check("csv order service,srcLang,src,trLang,tr",
      line == '"Google","en","hello","vi","xin chao"\n', line)

# --- TXT: native Txt.js framing ------------------------------------------
txt = H.txt_export([("Google", "hello", "en", "xin chao", "vi")])
check("txt begins with source + blank line", txt.startswith("hello\r\n\r\n"))
check("txt bracket line [service > srcLang to trLang]",
      "[Google > en to vi]\r\n" in txt)
check("txt separator line", "================================" in txt)

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: history exporters match native (JSON fix verified)")
