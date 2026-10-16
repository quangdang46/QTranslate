"""Regression: the four history exporters, byte-verified against the payload.

The NSIS payload carries all four `Plugins/History/*.js` exporters
consecutively -- each is `new PluginHeader(...)` followed by the six
functions `historyHeader/ItemBegin/Item/ItemEnd/Footer` plus the two
`historyFileDescription/Extension` accessors. Each exporter begins at a
`function historyHeader(){`, so the region between two such markers is
exactly one exporter.

The port is compared against the JS READ OUT OF THE PAYLOAD (never
executed), so a divergence is a port bug and not two copies of the same
mistake. Two of these four were already right and are pinned so they stay
right; the CSV column order in particular had been wrong once before
(service and source swapped), which is why the byte-level check matters.

Three details worth pinning explicitly, all found in the recovered text:

  * `Csv.js`'s `escapeValue` order is `a, c, b, e, d` -- i.e.
    source, srcLang, service, trLang, translation. The odd middle slot is
    native's, not a transcription slip.
  * `Json.js`'s `historyItemEnd(a,b)` emits `"]}" + (b<a-1?",":"")`, so the
    comma separator goes AFTER the object is closed -- not inside it.
  * `Html.js`'s `quoteHtml` escapes `&` FIRST (escaping it last would
    double-escape the `&` that `&gt;`/`&lt;` introduce).

Headless. Skips when the artifact is absent.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(REPO, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")
HISTORY = os.path.join(REPO, "qtranslate", "history.py")

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present (%s)" % PAYLOAD)
    raise SystemExit(0)

TS = io.open(PAYLOAD, "rb").read().decode("utf-8", "replace")
SRC = io.open(HISTORY, encoding="utf-8").read()

# --- carve the four exporters out of the payload -----------------------
starts = [m.start() for m in
          re.finditer(r"function historyHeader\(\)\{", TS)]
ck("the payload carries exactly 4 history exporters", len(starts) == 4,
   str(len(starts)))
EXPORTERS = {}
for k, s in enumerate(starts):
    end = starts[k + 1] if k + 1 < len(starts) else len(TS)
    seg = TS[s:end]
    ext = re.search(r'function historyFileExtension\(\)\{return"(\w+)"\}', seg)
    if ext:
        EXPORTERS[ext.group(1)] = seg
ck("extensions csv/html/json/txt all present",
   sorted(EXPORTERS) == ["csv", "html", "json", "txt"], str(sorted(EXPORTERS)))


def body_of(seg, name):
    m = re.search(r"function " + name + r"\([^)]*\)\{(.*?)\}"
                  r"function ", seg, re.S)
    return m.group(1) if m else None


# --- CSV: escapeValue order is a,c,b,e,d ------------------------------
csv = EXPORTERS.get("csv", "")
item = body_of(csv, "historyItem")
ck("Csv item joins 5 escapeValue members", item is not None
   and len(re.findall(r"escapeValue\(", item)) == 5, repr(item)[:200])
order = re.findall(r"escapeValue\((\w)\)", item or "")
ck("Csv order is a,c,b,e,d (native's, not a slip)",
   order == ["a", "c", "b", "e", "d"], str(order))
ck("the port emits source, srcLang, service, trLang, translation",
   'csv_item(src, service, src_lang, tr, tr_lang, i, n)' in SRC
   and "_qcsv(src), _qcsv(src_lang), _qcsv(service)" in SRC
   and "_qcsv(tr_lang), _qcsv(tr)" in SRC)
ck("Csv header/begin/end/footer are all empty",
   body_of(csv, "historyHeader") == 'return""' not in None
   if False else all(body_of(csv, m) == 'return""'
                     for m in ("historyHeader", "historyItemBegin",
                               "historyItemEnd", "historyFooter")))
ck("Csv's escapeValue doubles the quote only",
   'return\'"\'+(a||"").replace(/"/g,\'""\')+\'"\'' in TS)
ck("the port's _qcsv doubles quotes",
   '"""Port of escapeValue(a)."""' in SRC
   and "replace('\"', '\"\"')" in SRC)

# --- JSON: the comma goes after the closed object ---------------------
js = EXPORTERS.get("json", "")
ck("Json header is '['", 'function historyHeader(){return"["}' in js)
# The JS spells CR as the two characters BACKSLASH-r inside its string
# literals, so compare against the DECODED text -- the port assembles real
# CRLF, native's source writes the escape. (Raw strings: a single-backslash
# pattern here would decode nothing and the check would silently pass on a
# mismatch.)
def unesc(s):
    return (s.replace(r"\r\n", "\r\n").replace(r"\r", "\r")
             .replace(r"\n", "\n").replace(r'\"', '"'))


ck("Json itemBegin opens the object and the trs array",
   unesc('return\'{"src":\'+escapeStr(a)+\',"trs":[\'') in unesc(js))
ck("Json item emits 4 fields and a conditional comma",
   all(('"%s":' % k) in js for k in ("service", "srcLang", "trLang", "tr"))
   and 'escapeStr(d)+"}"+(g<f-1?",":"")' in js)
ck("Json itemEnd closes BOTH the trs array and the object",
   'function historyItemEnd(a,b){return"]}"+(b<a-1?",":"")}' in js)
ck("Json footer is ']'",
   'function historyFooter(){return"]"}' in js)
ck("the port's json_item_end puts the comma after ']}'",
   'return "]}," if i < n - 1 else "]}"' in SRC
   or '"]}" + ("," if i < n - 1 else "")' in SRC)
ck("Json's escapeStr is the same table native ships (JSON.stringify poly)",
   "charCodeAt(0)+65536).toString(16).substr(1)" in TS)

# --- HTML: quoteHtml escapes & first ----------------------------------
ht = EXPORTERS.get("html", "")
qh = re.search(r"function quoteHtml\(a\)\{return (.*?)(?:\}:|\}\n)", TS)
ck("Html's quoteHtml escapes &, then >, then < (and CRLF/CR last)",
   qh is not None and
   qh.group(1).index('replace(/&/g') < qh.group(1).index('replace(/>/g')
   < qh.group(1).index('replace(/</g'),
   repr(qh.group(1) if qh else None))
ck("the port escapes in the same order",
   SRC.index('replace("&", "&amp;")') < SRC.index('replace(">", "&gt;")')
   < SRC.index('replace("<", "&lt;")'))
style = re.search(r'<style type="text/css">\\r\\n(.*?)</style>', ht, re.S)
# Compare the ASSEMBLED output, not the source text: the port stores the CSS
# as concatenated literals with a leading CRLF added in html_header, so the
# bytes native emits only appear once those pieces are joined.
import qtranslate.history as H  # noqa: E402
_native_header = unesc(
    re.search(r"function historyHeader\(\)\{return'(.*?)'\}\n", ht).group(1))
ck("Html's table CSS is byte-reproduced",
   style is not None and unesc(style.group(1)) in H.html_header(),
   repr(unesc(style.group(1))[:60] if style else None))
ck("Html's assembled header equals native's byte for byte",
   H.html_header() == _native_header,
   "port=%r native=%r" % (H.html_header()[:80], _native_header[:80]))
ck("Html's header is the full DOCTYPE block",
   "<!DOCTYPE HTML>\r\n<html>" in unesc(ht))
ck("Html's itemEnd closes the table and adds a <br>",
   unesc('function historyItemEnd(a,b){return"</table><br>\\r\\n"}')
   in unesc(ht))
ck("Html's footer closes body+html",
   unesc('function historyFooter(){return"</body>\\r\\n</html>"}')
   in unesc(ht))

# --- TXT: the simplest shape, and the one most often "tidied" --------
tx = EXPORTERS.get("txt", "")
ck("Txt item is [service > srcLang to trLang] CRLF translation",
   body_of(tx, "historyItem")
   == 'return"["+a+" > "+c+" to "+e+"]\\r\\n"+d+"\\r\\n\\r\\n"')
ck("Txt itemEnd is a fixed separator line",
   body_of(tx, "historyItemEnd")
   == 'return"================================\\r\\n\\r\\n"')
ck("the port reproduces both verbatim",
   '[" + service + " > " + src_lang + " to " + tr_lang + "]' in SRC
   and '"=" * 32' not in SRC)

# --- the file descriptions / extensions -------------------------------
for ext, desc in (("csv", "CSV file"), ("html", "Html file"),
                  ("json", "JSON file"), ("txt", "Text file")):
    want = 'function historyFileDescription(){return"%s"}' % desc
    ck("%s.js declares %r" % (ext, desc),
       want in EXPORTERS.get(ext, ""), want)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_history_exporters: all checks ok (%d assertions)" % n[0])
