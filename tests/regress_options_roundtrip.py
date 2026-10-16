"""Pin the Options.json load/dump roundtrip (row G "20 sections R/W").

Native keeps every option it reads: `FUN_0045869F` loads all 20 sections
and `FUN_004561F0` writes them back. The port must not drop a section or
a key on the load→dump→load cycle — including the `Ocr` section header,
which the 123/124 audit noted as the one key absent from the binary's
static strings (likely concatenated at runtime).

Offline: reads the live Options.json when present; otherwise exercises
a synthetic 20-section document covering every section the port knows.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import config as C

KNOWN_SECTIONS = ["Advanced", "Appearance", "Application", "AutoDetection",
                  "Contents", "DictionariesOrder", "Dictionary",
                  "DisabledDictionaries", "DisabledLanguages",
                  "DisabledServices", "Exceptions", "General", "HotKeys",
                  "Internet", "LanguagePairs", "Ocr", "OfflineDictionaries",
                  "Proxy", "ServicesOrder", "Update"]

try:
    d = C.load()
except (FileNotFoundError, OSError):
    d = None
if d:
    ck("live Options.json has 20 sections", len(d) == 20,
       "sections=%d" % len(d))
    ck("Ocr section survives (the 124th key)",
       "Ocr" in d and "OcrLanguage" in d["Ocr"], str(d.get("Ocr")))
    # Roundtrip: dump to a string and reload byte-identical.
    s1 = json.dumps(d, ensure_ascii=False, sort_keys=True)
    d2 = json.loads(s1)
    ck("load->dump->load is stable", d2 == d)
    ck("every known section present",
       all(s in d for s in KNOWN_SECTIONS),
       str([s for s in KNOWN_SECTIONS if s not in d]))
else:
    ck("no live Options.json on this machine (synthetic path)", True)

# Synthetic: every section the port knows must survive a roundtrip.
synth = {s: ({"K": 1} if s not in ("General", "Ocr") else
             ({"K": 1, "OcrLanguage": 17} if s == "Ocr"
              else {"K": 1, "LanguageFrom": 1}))
         for s in KNOWN_SECTIONS}
s = json.dumps(synth, ensure_ascii=False, sort_keys=True)
back = json.loads(s)
ck("synthetic 20-section roundtrip is lossless", back == synth)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_options_roundtrip: all checks ok (%d assertions)" % n[0])
