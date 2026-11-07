"""Regression: the shipped Wiktionary example extension.

Port of the .tmp ``wikimedia-reference`` plugin's WiktionaryService:
MediaWiki REST search -> with_html -> h3/h4 sense groups, the ignored
headings and the 12x12 caps, edition-language mapping (zh variants ->
zh), miss = empty result.

Offline: the HTTP layer is stubbed -- the suite pins the parser, the
edition map and the lookup contract, never the network.
"""
import importlib.util
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


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(ROOT, "examples", "extensions", "wiktionary")
EXT_PY = os.path.join(EXAMPLE, "ext.py")

spec = importlib.util.spec_from_file_location("wiktionary_ext", EXT_PY)
WT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(WT)

ck("the wiktionary example is shipped", os.path.isdir(EXAMPLE), EXAMPLE)
with open(os.path.join(EXAMPLE, "manifest.json"), encoding="utf-8") as fh:
    man = json.load(fh)
ck("the manifest declares the dictionary capability",
   "dictionary" in man.get("capabilities", []), str(man.get("capabilities")))

# --- the parser ---------------------------------------------------------
html = ("<section><h3>Noun</h3><ol>"
        "<li>The first sense.<sup class=\"reference\">[1]</sup></li>"
        "<li>Second <b>sense</b> with <ul><li>nested</li></ul> tail.</li>"
        "</ol><h3>Etymology</h3><ol><li>origin story</li></ol>"
        "<h4>Verb</h4><ol><li>to act</li></ol></section>")
groups = WT._parse(html)
ck("the parser keeps real POS groups", [h for h, _ in groups]
   == ["Noun", "Verb"], str(groups))
ck("definitions lose the reference sup and nested lists",
   groups[0][1] == ["The first sense.", "Second sense with tail."],
   str(groups[0][1]))
ck("the ignored Etymology heading is dropped",
   all(h.lower() != "etymology" for h, _ in groups), str(groups))
ck("a top-level <ul> does not leak items as definitions",
   WT._parse("<h3>Noun</h3><ul><li>not a sense</li></ul>") == [],
   "ul-only section")

# --- the edition map -----------------------------------------------------
ck("zh variants map to the zh edition",
   WT._edition("zh-Hans") == "zh" and WT._edition("zh-TW") == "zh")
ck("a base language maps to its edition",
   WT._edition("en") == "en" and WT._edition("vi") == "vi")
ck("an unsupported language has no edition",
   WT._edition("xx") is None and WT._edition("") is None)

# --- the lookup contract (HTTP stubbed) ----------------------------------
_orig_search, _orig_page = WT._search_page, WT._page_html
try:
    WT._search_page = lambda lang, word: {"key": "hello", "title": "hello"}
    WT._page_html = lambda lang, key: (html, "hello")
    frag = WT._lookup("hello", "en", "vi")
    ck("a hit renders an HTML fragment with the senses",
       "Second sense with tail." in frag and "Noun" in frag,
       repr(frag[:160]))
    WT._search_page = lambda lang, word: None
    ck("a search miss is an empty result, not an error",
       WT._lookup("hello", "en", "vi") == "", "miss")
    ck("an unsupported source language never hits the network",
       WT._lookup("hello", "xx", "vi") == "", "bad lang")
    WT._search_page = _orig_search
    WT._page_html = lambda lang, key: (_ for _ in ()).throw(OSError("down"))
    WT._search_page = lambda lang, word: {"key": "x"}
    ck("a network failure is an empty result, not a crash",
       WT._lookup("hello", "en", "vi") == "", "offline")
finally:
    WT._search_page, WT._page_html = _orig_search, _orig_page

# --- it loads through the real manager ------------------------------------
from qtranslate import config as _CFG          # noqa: E402
_CFG.DEFAULT_PATH = os.path.join(
    tempfile.mkdtemp(prefix="qt-wt-cfg-"), "Options.json")
from qtranslate import extensions as EX         # noqa: E402
from qtranslate import registry as RG           # noqa: E402

tmp = tempfile.mkdtemp(prefix="qt-wt-ext-")
try:
    exts = os.path.join(tmp, "extensions")
    os.makedirs(exts)
    shutil.copytree(EXAMPLE, os.path.join(exts, "wiktionary"))
    mgr = EX.ExtensionManager()
    outcome = mgr.load_dir(exts)
    ck("the extension loads",
       len(outcome) == 1 and outcome[0]["status"] == "loaded",
       str(outcome))
    ck("it commits into DICT_EXT",
       "wiktionary" in RG.DICT_EXT,
       str(sorted(getattr(RG, "DICT_EXT", {}))))

    from qtranslate import dictionary_search as DS
    # Stub the committed provider: the search path must reach DICT_EXT,
    # and the suite never touches the network.
    _orig_lk = RG.DICT_EXT.get("wiktionary")
    try:
        RG.DICT_EXT["wiktionary"] = lambda w, s, t: "<b>stub</b>"
        cards, summary = DS.search("hello", services=["wiktionary"],
                                   cfg={})
        ck("search() resolves the extension dictionary",
           any("stub" in (f or "") for _k, _t, f in cards),
           repr(summary[:120]))
    finally:
        if _orig_lk is not None:
            RG.DICT_EXT["wiktionary"] = _orig_lk
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    RG.DICT_EXT.pop("wiktionary", None)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_wiktionary: all checks ok (%d assertions)" % n[0])
