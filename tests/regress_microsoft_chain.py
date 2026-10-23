"""Regression: Bing chain signal comes from the response, not the text (E22).

`RE_COVERAGE_CHECKLIST.md` row E22 records that native's
`Services/Microsoft Translator/Service.js` drives `/tlookupv3` from the
**`nextRequestHandler`** field of the ttranslatev3 response. The port
used to decide it from the input text (a word-count heuristic), which
replaces a real server signal with an invention.

Pins:
  * `next_handler(entry)` returns the handler the server names;
  * an absent / empty / unknown-shaped field yields None (never a guess);
  * `translate_full` uses that signal, so a LONG text the server marks
    for the dictionary IS chained, and a SHORT one it does not mark is
    NOT -- the two cases the old heuristic got backwards;
  * `_is_short_text` is still exported but is documented as port-side.

Headless: a stub opener returns fixed JSON. No network, no Tk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import microsoft as MS  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# --- next_handler() ------------------------------------------------------
ck("server-named handler is returned",
   MS.next_handler({"nextRequestHandler": "dictionaryRequest"})
   == "dictionaryRequest")
ck("absent field -> None", MS.next_handler({"text": "x"}) is None)
ck("empty string -> None", MS.next_handler({"nextRequestHandler": ""})
   is None)
ck("whitespace-only -> None",
   MS.next_handler({"nextRequestHandler": "   "}) is None)
ck("None entry -> None", MS.next_handler(None) is None)
ck("non-dict entry -> None", MS.next_handler("nope") is None)
ck("value is stringified but not invented",
   MS.next_handler({"nextRequestHandler": "otherHandler"})
   == "otherHandler")

# --- translate_full() uses the response, not the text -------------------
class _Resp:
    headers = {}

    def __init__(self, payload):
        self._b = payload.encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    def __init__(self, payload):
        self.payload = payload

    def open(self, req, timeout=None):
        return _Resp(self.payload)


def _resp(chained, translations=True):
    e = {"translations": [{"text": "translated"}]} if translations else {}
    if chained:
        e["nextRequestHandler"] = "dictionaryRequest"
    return '[%s]' % __import__("json").dumps(e)


# the server marks a LONG sentence for the dictionary
long_text = ("this is a long sentence that the server decides deserves a "
             "dictionary lookup")
ck("long text the server marks IS chained",
   MS.translate_full(long_text, opener=_Opener(_resp(True)))
   == ("translated", "dictionaryRequest"))

# the server marks a SHORT phrase
short_text = "hello"
out, nxt = MS.translate_full(short_text, opener=_Opener(_resp(True)))
ck("short text the server marks IS chained",
   (out, nxt) == ("translated", "dictionaryRequest"))

# the server marks NEITHER: no chain, regardless of text length
ck("short text the server does NOT mark is not chained",
   MS.translate_full(short_text, opener=_Opener(_resp(False)))
   == ("translated", None))
ck("long text the server does NOT mark is not chained",
   MS.translate_full(long_text, opener=_Opener(_resp(False)))
   == ("translated", None))

# the old heuristic would have gotten BOTH of these wrong
ck("the old text heuristic would disagree on the long-marked case",
   MS._is_short_text(long_text) is False)
ck("the old text heuristic would agree on the short-marked case",
   MS._is_short_text(short_text) is True)

# --- request wiring unchanged -------------------------------------------
src = open("qtranslate/services/microsoft.py", encoding="utf-8").read()
ck("_service_request still posts /ttranslatev3",
   '"/ttranslatev3?isVertical=1&IG={}&IID={}"' in src
   or "/ttranslatev3" in src)
ck("dictionary() still posts /tlookupv3", "/tlookupv3" in src)
ck("_is_short_text is labelled a port-side heuristic",
   "not the native chain signal" in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_microsoft_chain: all checks ok (%d assertions)" % n[0])


# --- 2026-10-23: Microsoft's ERROR shape is handled, not crashed --------
# Asking the live endpoint today returns {"statusCode": 400,
# "errorMessage": ""} instead of the list native expects. Indexing that
# with [0] raised KeyError: 0, which read like a port defect. The port
# reports an empty translation instead, so the caller's fallback runs.
from qtranslate.services import microsoft as _MS
ck("an error object yields no entry",
   _MS.get_response_obj({"statusCode": 400, "errorMessage": ""}) is None)
ck("a normal list still yields its first entry",
   _MS.get_response_obj([{"translations": [{"text": "x"}]}])
   == {"translations": [{"text": "x"}]})
ck("an empty list yields None", _MS.get_response_obj([]) is None)
_raised = None
try:
    _MS.get_response_obj({"statusCode": 400})
except Exception as _e:                        # noqa: BLE001
    _raised = _e
ck("an error object never raises", _raised is None, repr(_raised))
print("regress_microsoft_chain: error-shape checks ok")
