"""Pin the UI-language pack loader (row G i18n / FUN_0045B716 path).

Native loads Locales/<dir>/lang.json (7 keys incl. Strings/Windows/Menus
arrays). The port must list locales, load a pack, and do a safe indexed
lookup (missing section/index -> default, never raise). Pinned against a
synthetic locales dir so it runs without the installed tree, plus a live
check when the real dir exists.

Offline: temp dir; no window.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import locale as L

_tmp = tempfile.mkdtemp(prefix="qt_locale_")
try:
    for name, code, native in (("Vietnamese", "vi", "Tiếng Việt"),
                               ("German", "de", "Deutsch")):
        d = os.path.join(_tmp, name)
        os.makedirs(d)
        with open(os.path.join(d, "lang.json"), "w", encoding="utf-8") as f:
            json.dump({"LanguageName": name, "LanguageCode": code,
                       "LanguageNativeName": native,
                       "Strings": ["s0", "s1", "s2"],
                       "Windows": ["w0"], "Menus": ["m0", "m1"]}, f)
    # a broken pack must be skipped by list_locales, not crash it
    bad = os.path.join(_tmp, "Broken")
    os.makedirs(bad)
    with open(os.path.join(bad, "lang.json"), "w", encoding="utf-8") as f:
        f.write("{ not valid json")

    ck("list_locales returns the good packs, skips the broken one",
       L.list_locales(_tmp) == [("German", "de"), ("Vietnamese", "vi")],
       str(L.list_locales(_tmp)))
    ck("list_locales is sorted", L.list_locales(_tmp)
       == sorted(L.list_locales(_tmp)))

    vi = L.load_pack("Vietnamese", _tmp)
    ck("load_pack returns the parsed dict",
       vi.get("LanguageCode") == "vi", repr(vi.get("LanguageCode")))
    ck("native name present",
       vi.get("LanguageNativeName") == "Tiếng Việt")

    ck("t() indexes a section", L.t(vi, "Strings", 1) == "s1")
    ck("t() returns default on out-of-range index",
       L.t(vi, "Strings", 99, default="D") == "D")
    ck("t() returns default on a missing section",
       L.t(vi, "Nope", 0, default="D") == "D")
    ck("t() returns default when pack is not a dict",
       L.t(None, "Strings", 0, default="D") == "D")
    ck("t() default is empty string by default",
       L.t({}, "Strings", 0) == "")
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

# --- live: the installed tree, when present -----------------------------
if os.path.isdir(L.LOCALES_DIR):
    live = L.list_locales()
    ck("live locales list is non-empty", len(live) > 0, str(len(live)))
    ck("live list carries (name, code) tuples",
       all(isinstance(x, tuple) and len(x) == 2 for x in live))

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_locale: all checks ok (%d assertions)" % n[0])
