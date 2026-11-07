"""Regression: the shipped CSV Dictionary example extension.

Port of the .tmp ``csv-services`` plugin contract: a user-supplied CSV
(glossary, abbreviations, error codes) looked up locally -- header-name
or 1-based column settings, ``\\t`` delimiter, optional notes column,
case sensitivity, miss = empty result not an error.

Offline: the CSV is a temp file, the extension loads through the real
ExtensionManager into DICT_EXT, and dictionary_search.search() must
resolve it -- the gap this suite pins is that DICT_EXT providers were
registered but unreachable from the dictionary window's search path.
"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append("%s -- %s" % (name, detail))


from qtranslate import config as _CFG          # noqa: E402
# Settings writes must not touch the developer's real Options.json.
_CFG.DEFAULT_PATH = os.path.join(
    tempfile.mkdtemp(prefix="qt-csv-cfg-"), "Options.json")

from qtranslate import extensions as EX         # noqa: E402
from qtranslate import registry as RG           # noqa: E402

EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "examples", "extensions", "csv_dictionary")

ck("the csv_dictionary example is shipped", os.path.isdir(EXAMPLE), EXAMPLE)
ck("it has a manifest and entrypoint",
   os.path.isfile(os.path.join(EXAMPLE, "manifest.json"))
   and os.path.isfile(os.path.join(EXAMPLE, "ext.py")))

with open(os.path.join(EXAMPLE, "manifest.json"), encoding="utf-8") as fh:
    man = json.load(fh)
ck("the manifest declares the dictionary capability",
   "dictionary" in man.get("capabilities", []), str(man.get("capabilities")))
ck("the manifest validates against the real schema",
   EX.validate(man) is not None)
ck("the manifest declares a settings schema",
   isinstance(man.get("settings_schema"), dict)
   and "file.path" in man["settings_schema"],
   str(man.get("settings_schema")))

# --- load it the way the app does ---------------------------------------
tmp = tempfile.mkdtemp(prefix="qt-csv-ext-")
try:
    exts = os.path.join(tmp, "extensions")
    os.makedirs(exts)
    shutil.copytree(EXAMPLE, os.path.join(exts, "csv_dictionary"))

    mgr = EX.ExtensionManager()
    outcome = mgr.load_dir(exts)
    ck("the extension loads",
       len(outcome) == 1 and outcome[0]["status"] == "loaded",
       str(outcome))
    ck("it commits into DICT_EXT under its key",
       "csv-dictionary" in RG.DICT_EXT,
       str(sorted(getattr(RG, "DICT_EXT", {}))))

    # --- point it at a temp CSV and drive the lookup --------------------
    csvdir = tempfile.mkdtemp(prefix="qt-csv-data-")
    glossary = os.path.join(csvdir, "glossary.csv")
    with open(glossary, "w", encoding="utf-8", newline="") as fh:
        fh.write("term,meaning,example\n"
                 "DNS,Dublin Naming System,a naming system\n"
                 "HTTP,HyperText Transfer Protocol,the web's protocol\n"
                 "comma,\"a, b, c\",list separator\n")
    for key, val in (("file.path", glossary),
                     ("columns.term", "term"),
                     ("columns.definition", "meaning"),
                     ("columns.notes", "example"),
                     ("matching.label", "abbreviation")):
        mgr.set_setting("csv-dictionary", key, val)

    fn = RG.DICT_EXT["csv-dictionary"]
    frag = fn("dns", "en", "vi")          # case-insensitive default
    ck("a lowercase query finds the uppercase row",
       "Dublin Naming System" in frag, repr(frag[:120]))
    ck("the notes column lands in the entry",
       "a naming system" in frag, repr(frag[:200]))
    ck("the label shows as the part-of-speech",
       "abbreviation" in frag, repr(frag[:120]))
    ck("a quoted comma inside a definition survives",
       "a, b, c" in fn("comma", "en", "vi"), "csv quoting")
    ck("a miss is an empty result, not an error",
       fn("not-in-the-file", "en", "vi") == "", "miss")

    # numeric columns + no header row + tab delimiter
    plain = os.path.join(csvdir, "plain.tsv")
    with open(plain, "w", encoding="utf-8", newline="") as fh:
        fh.write("E001\tboot failure\trestart required\n"
                 "E002\tdisk full\tfree space\n")
    for key, val in (("file.path", plain),
                     ("file.delimiter", "\\t"),
                     ("columns.term", "1"),
                     ("columns.definition", "2"),
                     ("columns.notes", "3")):
        mgr.set_setting("csv-dictionary", key, val)
    frag2 = fn("E002", "en", "vi")
    ck("numeric columns read a headerless tab file",
       "disk full" in frag2 and "free space" in frag2, repr(frag2[:160]))

    # case sensitivity on
    mgr.set_setting("csv-dictionary", "matching.case_sensitive", True)
    ck("case-sensitive matching misses the lowercase query",
       fn("e002", "en", "vi") == "", "case on")
    ck("case-sensitive matching hits the exact row",
       "disk full" in fn("E002", "en", "vi"), "case on hit")

    # --- dictionary_search sees it: point the settings back at the
    # glossary first (the TSV checks above repointed file.path) ---------
    for key, val in (("file.path", glossary),
                     ("file.delimiter", ","),
                     ("columns.term", "term"),
                     ("columns.definition", "meaning"),
                     ("columns.notes", "example")):
        mgr.set_setting("csv-dictionary", key, val)
    from qtranslate import dictionary_search as DS
    cards, summary = DS.search("DNS", services=["csv-dictionary"],
                               cfg={})
    ck("search() resolves the extension dictionary by key",
       any("Dublin Naming System" in (f or "") for _k, _t, f in cards),
       repr(summary[:120]))
    ck("service_key maps the ext key to itself",
       DS.service_key("csv-dictionary") == "csv-dictionary")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(csvdir, ignore_errors=True)
    RG.DICT_EXT.pop("csv-dictionary", None)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_csv_dictionary: all checks ok (%d assertions)" % n[0])
