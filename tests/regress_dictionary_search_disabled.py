"""Regression: dictionary_search.search() honours DisabledDictionaries.

Qt path note: ``qt/dictionary.py`` already filters the enabled ids for
the strip and passes an explicit ``services`` list, but
``dictionary_search.search(services=None)`` -- the headless/direct path
-- used to fan out to EVERY ``registry.DICTS`` entry, resurrecting
dictionaries the user unchecked on the Services page (bead qt-fo0).

The settings file names dictionaries by numeric id
(``DictionariesOrder`` / ``DisabledDictionaries``); ``config.DICT_DISPLAY``
maps id -> display name and ``service_key`` maps the display name to the
``registry.DICTS`` key. This test stubs every DICTS callable (offline,
no network) and proves a disabled id is never queried -- neither by the
services=None fan-out nor by an explicit ``services=[display name]``.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))

from qtranslate import config, dictionary_search as DS  # noqa: E402
from qtranslate import registry as RG  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


# ---- stub every registry dict: record the key, return a fragment -------
called = []
_orig = dict(RG.DICTS)
for key in list(RG.DICTS):
    def _mk(k):
        def fn(word, sl, tl):
            called.append(k)
            return "frag-%s" % k
        return fn
    RG.DICTS[key] = _mk(key)

try:
    # A settings file with two disabled ids: 10 = "Google Search"
    # (registry key google-search) and 24 = "Urban Dictionary" (urban).
    cfg = config.default_config()
    cfg["DisabledDictionaries"] = [10, 24]
    fd, cfgpath = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(cfgpath, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        old_path = config.DEFAULT_PATH
        config.DEFAULT_PATH = cfgpath
        try:
            # 1. services=None: the fan-out must skip the disabled ids.
            called.clear()
            cards, _summary = DS.search("hello", services=None)
            check("disabled google-search never queried (services=None)",
                  "google-search" not in called, str(called))
            check("disabled urban never queried (services=None)",
                  "urban" not in called, str(called))
            check("enabled wikipedia still queried (services=None)",
                  "wikipedia" in called, str(called))
            kinds = [c[0] for c in cards]
            check("no disabled card in results",
                  "google-search" not in kinds and "urban" not in kinds,
                  str(kinds))

            # 2. explicit services= is honoured but intersected: naming a
            #    disabled display name must not resurrect it.
            called.clear()
            DS.search("hello", services=["Google Search", "Wikipedia"])
            check("explicit disabled name filtered out",
                  "google-search" not in called, str(called))
            check("explicit enabled name still runs",
                  "wikipedia" in called, str(called))

            # 3. cfg= argument path (what the Qt window passes) applies
            #    the same filter without touching DEFAULT_PATH.
            called.clear()
            cfg2 = config.default_config()
            cfg2["DisabledDictionaries"] = [14]  # Wikipedia
            DS.search("hello", services=None, cfg=cfg2)
            check("cfg= DisabledDictionaries honoured",
                  "wikipedia" not in called
                  and "google-search" in called, str(called))
        finally:
            config.DEFAULT_PATH = old_path
    finally:
        os.unlink(cfgpath)
finally:
    RG.DICTS.clear()
    RG.DICTS.update(_orig)

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: dictionary_search honours DisabledDictionaries")
