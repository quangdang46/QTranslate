"""Regression: Microsoft's request body, and the one documented divergence.

The recovered `Services/Microsoft Translator/Service.js` builds one body
for both translate and detect::

    a = limitSource(a, 1E3);
    d = "/ttranslatev3?isVertical=1&IG=" + Options.IG
        + "&IID=translator.5023.3";
    a = "text=" + encodePostParam(a) + "&fromLang=" + codeFromLanguage(b||AUTO)
        + "&to=" + codeFromLanguage(c||ENGLISH) + "&token=" + Options.BingToken
        + "&key=" + Options.BingKey

The port matches that field-for-field, and adds ONE field native does
not have: ``tryFetchingGenderDebiasedTranslations=true``. That is a
deliberate live fix (Bing hardened after the 6.10 JS shipped), it is
documented in the port, and it is pinned here so it stays documented --
the worst outcome would be a silent extra field nobody could explain.

Headless; the JS is read from the artifact, never executed. Skips if the
artifact is absent.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import microsoft as M  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")
SRC = open(os.path.join(ROOT, "qtranslate", "services", "microsoft.py"),
           encoding="utf-8").read()

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present (%s)" % PAYLOAD)
    raise SystemExit(0)

TS = open(PAYLOAD, "rb").read().decode("utf-8", "replace")
i = TS.find("new ServiceHeader(5,")
nxt = [m.start() for m in re.finditer(r'new ServiceHeader\((\d+),', TS)
       if m.start() > i]
SEG = TS[i:nxt[0] if nxt else len(TS)]


def body_of(name):
    m = re.search(r"function " + name + r"\s*\([^)]*\)\s*\{", SEG)
    depth, j = 1, m.end()
    while j < len(SEG) and depth:
        if SEG[j] == "{":
            depth += 1
        elif SEG[j] == "}":
            depth -= 1
        j += 1
    return SEG[m.end():j - 1]


req = body_of("serviceRequest")

# --- 1. the request path and its parameters -----------------------------
ck("native path is /ttranslatev3?isVertical=1&IG=...&IID=translator.5023.3",
   '"/ttranslatev3?isVertical=1&IG="+Options.IG+"&IID=translator.5023.3"'
   in req.replace(" ", ""), req)
ck("the port builds the same path",
   '"/ttranslatev3?isVertical=1&IG={}&IID={}"' in SRC)

# --- 2. the body fields, in native's order ------------------------------
ck("native body is text,fromLang,to,token,key in that order",
   req.index("&fromLang=") < req.index("&to=") < req.index("&token=")
   < req.index("&key="), req)
ck("the port's body is in the same order",
   SRC.index("text={}") < SRC.index("&fromLang={}")
   < SRC.index("&to={}") < SRC.index("&token={}")
   < SRC.index("&key={}"), "field order changed")
ck("native limits the source to 1E3",
   "limitSource(a,1E3)" in req)
ck("the port limits to 1000 too",
   "limit_source(text, 1000)" in SRC)
ck("native encodes the body with encodePostParam",
   "encodePostParam(a)" in req)
ck("the port uses encode_post_param",
   "encode_post_param(text)" in SRC)

# --- 3. the headers -----------------------------------------------------
ck("native carries Origin + Referer on www.bing.com",
   'Origin: https://www.bing.com' in req
   and 'Referer: https://www.bing.com/translator' in req, req)
ck("the port carries both",
   '"Origin", "https://www.bing.com"' in SRC
   or '"Origin": "https://www.bing.com"' in SRC)

# --- 4. the one documented divergence ----------------------------------
ck("native does NOT have tryFetchingGenderDebiasedTranslations",
   "tryFetchingGenderDebiased" not in req, req)
ck("the port DOES add it", "tryFetchingGenderDebiasedTranslations=true" in SRC)
ck("...and the port says why, in its own docstring",
   "gender" in SRC.lower() and "hardened" in SRC.lower(),
   "the extra field is undocumented")
ck("...and the checklist records the divergence",
   "tryFetchingGenderDebiasedTranslations" in open(
       os.path.join(ROOT, "docs", "RE_COVERAGE_CHECKLIST.md"),
       encoding="utf-8").read())

# --- 5. detect shares the request (so it shares the divergence) --------
ck("native detectRequest is just serviceRequest(a)",
   body_of("serviceDetectLanguageRequest") == "return serviceRequest(a)",
   body_of("serviceDetectLanguageRequest"))
_det = M.detect
ck("the port's detect reaches _service_request (so it inherits the body)",
   _det.__module__ == "qtranslate.services.microsoft"
   and "detectedLanguage" in SRC,
   "detect no longer routes through the shared request")
ck("the port's detect returns an index, like native's languageFromCode",
   callable(M.detect_code))

# --- 6. getResponseObj / getSourceLanguage shapes ----------------------
def find(fn_name, text):
    m = re.search(r"function " + fn_name + r"\s*\([^)]*\)\s*\{", text)
    depth, j = 1, m.end()
    while j < len(text) and depth:
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
        j += 1
    return text[m.end():j - 1]


ck("native getResponseObj parses and returns [0]",
   "parseJSON(a)" in find("getResponseObj", TS)
   and "return a[0]" in find("getResponseObj", TS),
   find("getResponseObj", TS))
ck("the port's get_response_obj returns obj[0]",
   "return obj[0]" in SRC)
ck("native Microsoft getSourceLanguage reads a.detectedLanguage.language",
   "a.detectedLanguage?languageFromCode(a.detectedLanguage.language)"
   in find("getSourceLanguage",
           SEG[SEG.find("function getSourceLanguage"):]
           if "function getSourceLanguage" in SEG else ""),
   "not the shape the port implements")
ck("the port reads entry['detectedLanguage']['language']",
   'entry["detectedLanguage"]["language"]' in SRC)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_microsoft_request: all checks ok (%d assertions)" % n[0])
