"""Regression: history export dispatches on the filename's extension.

Native rule (FUN_00428483, docs/review/HISTORY_EXT_DISPATCH_2026-10-14.md):
  * the writer is chosen from PathFindExtensionW(path) -- not a fixed
    HTML default;
  * first registered script whose historyFileExtension equals wins;
  * an extension-less path matches nothing (native bails to 0);
  * an unhandled extension matches nothing; native does NOT fall back to
    writing HTML (the port used to always write HTML, silently).

Pins exporter_for/describe_extension against those rules.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import history as H  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


items = [("google", "hello", "en", "xin chào", "vi")]
for ext, fn in (("out.html", H.html_export), ("out.csv", H.csv_export),
                ("out.json", H.json_export), ("out.txt", H.txt_export)):
    ck("%s picks the right writer" % ext, H.exporter_for(ext) is fn,
       repr(getattr(H.exporter_for(ext), "__name__", None)))

ck("uppercase extension still matches",
   H.exporter_for("OUT.HTML") is H.html_export)
ck("dotless/extension-less path selects nothing",
   H.exporter_for("history") is None)
ck("unknown extension selects nothing (no silent-HTML fallback)",
   H.exporter_for("history.doc") is None)
ck("empty path selects nothing", H.exporter_for("") is None)
ck("None path selects nothing", H.exporter_for(None) is None)

ck("describe html", H.describe_extension("html") == "HTML file")
ck("describe csv/json/txt", (H.describe_extension("csv"),
                             H.describe_extension("json"),
                             H.describe_extension("txt"))
   == ("CSV file", "JSON file", "Text file"))
ck("describe unknown is ''", H.describe_extension("doc") == "")
ck("describe tolerates a leading dot", H.describe_extension(".TXT")
   == "Text file")
ck("export order is the registration order",
   H.EXPORT_ORDER == ("html", "csv", "json", "txt"))

# the selected writer must actually run on the payload shape app.py sends
out = H.exporter_for("x.json")(items)
# json_export emits the array root, not an object (history.py json_header
# is "" and json_footer wraps the "trs" array) -- measured, not assumed.
ck("json writer round-trips", out.startswith("[") and "xin" in out)
out = H.exporter_for("x.txt")(items)
ck("txt writer round-trips", "xin chào" in out)

# The Save-dialog filter: FUN_0042856e formats each plugin as
# "%s (%s)" = historyFileDescription(historyFileExtension), one entry per
# registered script. app.py builds the same shape off EXPORT_ORDER.
try:
    _mask = [("%s (*.%s)" % (H.describe_extension(e), e), "*.%s" % e)
             for e in H.EXPORT_ORDER]
except Exception as e:
    _mask = []
    ck("filter build raised", False, repr(e))
WANT = [("HTML file (*.html)", "*.html"), ("CSV file (*.csv)", "*.csv"),
        ("JSON file (*.json)", "*.json"), ("Text file (*.txt)", "*.txt")]
ck("dialog filter matches native's \"%s (%s)\" shape", _mask == WANT,
   str(_mask))
ck("every mask entry pairs desc with its own pattern",
   all(lbl.split(" (*.")[0] and pat == "*." + lbl.split("(*.")[1][:-1]
       for lbl, pat in _mask))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_history_dispatch: all checks ok (%d assertions)" % n[0])
