"""Regression: the OCR language codes come from the image's own list.

The recovered image carries ocr.space's 22 language codes as ONE wide
string, immediately after the response-field names `ParsedResults` /
`ParsedText` / `ErrorMessage` (measured 2026-10-16 around offset
1215480):

    ara bul chs cht hrv cze dan dut eng fin fre ger gre hun ita
    jpn kor nor pol por rus spa swe tur

Those are 3-letter codes, not Google's 2-letter ones, so the port has to
translate. Its map previously covered 8 of the 22 (`en vi fr de es ru ja
ko zh-CN`) and silently fell back to `eng` for every other language --
which native does only for a language it genuinely lacks, and would do for
e.g. Turkish, Polish, Greek, Czech, Croatian... all of which the list has.

Headless: the image is READ, never executed. Skips when absent.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(REPO, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")

NATIVE_CODES = ["ara", "bul", "chs", "cht", "hrv", "cze", "dan", "dut",
                "eng", "fin", "fre", "ger", "gre", "hun", "ita", "jpn",
                "kor", "nor", "pol", "por", "rus", "spa", "swe", "tur"]

if not os.path.exists(EXE):
    print("SKIP: recovered image not present (%s)" % EXE)
    raise SystemExit(0)

raw = io.open(EXE, "rb").read()

# --- 1. the list is really in the image, as ONE adjacent run ------------
# --- 1. the list is really in the image, as ONE adjacent run ------------
# It is NULL-separated (each code its own wide string), not space-joined.
joined = "\x00".join(NATIVE_CODES)
ck("the image carries all %d codes as one adjacent wide run"
   % len(NATIVE_CODES), joined.encode("utf-16-le") in raw,
   "joined wide run not found")
# and it sits right after the response-field names, which is what makes it
# recognisably the OCR list rather than some other string table.
anchor = raw.find("ErrorMessage".encode("utf-16-le"))
ck("the run follows the ErrorMessage field name",
   0 < anchor < raw.find(joined.encode("utf-16-le"))
   and raw.find(joined.encode("utf-16-le")) - anchor < 400,
   "anchor@%d run@%d" % (anchor, raw.find(joined.encode("utf-16-le"))))

# every code individually, so a partial match cannot pass
for code in NATIVE_CODES:
    ck("image contains %r" % code,
       code.encode("utf-16-le") in raw
       or code.encode("ascii") in raw)

# the response-field names that anchor the region
for anchor in ("ParsedResults", "ParsedText", "ErrorMessage"):
    ck("image contains the response field %r" % anchor,
       anchor.encode("utf-16-le") in raw
       or anchor.encode("ascii") in raw)

# --- 2. the port's map covers all of them ------------------------------
# The map belongs to the OCR SERVICE (it is ocr.space's own language
# table, and the native carries it in its image), so it lives in
# qtranslate/services/ocr.py and both views read it from there.
from qtranslate.services.ocr import OCR_LANGUAGES as _map
ck("the port builds the OCR language map", bool(_map))
ck("the map is a dict of >= 20 entries", isinstance(_map, dict)
   and len(_map) >= 20,
   "%d entries" % len(_map) if isinstance(_map, dict) else "not a dict")
for code in NATIVE_CODES:
    if code == "eng":            # the fallback is not a map entry
        continue
    ck("the port maps to %r" % code, code in _map.values(),
       "missing from the OCR language map")
# ...and the view sends the service's code, not Google's 2-letter one.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _view_src import view_source
ck("the view translates the language before the request",
   "ocr_language(" in view_source(),
   "the view must not send a 2-letter code to ocr.space")

# Google's own table must actually contain the codes the map keys on,
# otherwise the lookup can never fire.
from qtranslate.services.google_translate import SUPPORTED_LANGS  # noqa: E402
for google_code in ("vi", "bg", "hr", "cs", "da", "nl", "fi", "el", "hu",
                    "it", "no", "pl", "pt", "sv", "tr", "ar", "zh-TW"):
    ck("Google's table has %r so its map entry is reachable" % google_code,
       google_code in SUPPORTED_LANGS, "not in SUPPORTED_LANGS")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_ocr_languages: all checks ok (%d assertions)" % n[0])
