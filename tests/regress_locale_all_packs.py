"""Regression: every shipped locale pack loads through the port's reader.

The installer ships 35 language packs. `qtranslate/locale.py` reads them
with a hand-rolled three-shape parser (`Strings` is a `[id, text]` pair
list, `Windows` an object list, `Menus` an object list holding its own pair
list). A pack that deviates in any of those shapes -- and the pack set is
35 third-party-authored files, so some do -- is either mis-read or crashes.

This walks ALL of them and asserts, per pack, that the port's reader
returns what the file actually contains. It is the difference between
"the one pack we happened to test loads" and "the pack set does".

Two things found while writing it (pinned below):
  * English's pack ends VALIDLY at `"Id": 10` -- an earlier doc called it
    "truncated mid-Items", which was imprecise.
  * Several packs carry a UTF-8 BOM, which a plain `open(...).read()`
    feeds to `json.loads` as a spurious first character.

Headless: the packs are READ from the installed copy, never executed. The
installer itself is never run, and only QTranslate's own `Locales/` tree
is read.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import locale  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


INSTALLED = os.environ.get(
    "QTRANSLATE_DIR", r"C:\Program Files (x86)\QTranslate")
LOCALES = os.path.join(INSTALLED, "Locales")

if not os.path.isdir(LOCALES):
    print("SKIP: installed locale packs not present (%s)" % LOCALES)
    raise SystemExit(0)

packs = sorted(d for d in os.listdir(LOCALES)
               if os.path.isdir(os.path.join(LOCALES, d)))
ck("the installer ships a non-trivial pack set", len(packs) >= 30,
   str(len(packs)))

names = locale.list_locales()
ck("list_locales returns every pack", len(names) >= len(packs),
   "%d vs %d packs" % (len(names), len(packs)))

bom_packs, valid_ends, sections_seen, lenient = [], [], set(), {}


def t_of(pack_dict, idx):
    """String ``idx`` straight from the parsed file, bypassing the port."""
    for pair in pack_dict.get("Strings", ()):
        if isinstance(pair, list) and pair and pair[0] == idx:
            return pair[1]
    return ""


for pack_name in packs:
    path = os.path.join(LOCALES, pack_name, "lang.json")
    if not os.path.exists(path):
        continue

    # --- read it the way the PORT does, plus the raw file for comparison
    try:
        pack = locale.load_pack(pack_name)
    except Exception as exc:
        fail.append("%s: load_pack raised %r" % (pack_name, exc))
        continue

    raw_text = io.open(path, encoding="utf-8-sig").read()
    # The packs are NOT strict JSON: 7 of them carry trailing commas and
    # Bulgarian/Mongolian a double comma (all documented in
    # qtranslate/locale.py:_read_pack, which is what native's lenient JS
    # parser tolerates). Assert THAT, then compare against the same
    # tolerances so the comparison is meaningful rather than a way of
    # reporting every well-formed-but-trailing-comma pack as a bug.
    strict_ok = True
    try:
        json.loads(raw_text)
    except ValueError:
        strict_ok = False
        lenient[pack_name] = True
    from qtranslate.theme import _strip_jsonc
    truth_text = re.sub(r",(\s*[}\]])", r"\1",
                        _strip_jsonc(raw_text))
    truth_text = re.sub(r",(\s*,)+\s*", ",", truth_text)
    truth = json.loads(truth_text)
    sections_seen.update(truth.keys())

    # and what the PORT returns must agree with the tolerant parse above
    ck("%s: load_pack returns the same sections as the tolerant parse"
       % pack_name, set(pack.keys()) == set(truth.keys()),
       "port=%r file=%r" % (sorted(pack.keys()), sorted(truth.keys())))

    # 1. the pack's declared identity matches what the reader returns
    ck("%s: LanguageName round-trips" % pack_name,
       locale.t(pack, "Strings", 0, "")
       == t_of(truth, 0) if "Strings" in truth else True)

    # 2. every Windows caption the reader returns must exist in the file
    caps = {m.get("Id"): m.get("Caption")
            for m in pack.get("Windows", ())}
    truth_caps = {m.get("Id"): m.get("Caption")
                  for m in truth.get("Windows", ())}
    ck("%s: Windows captions match the file" % pack_name,
       caps == truth_caps,
       "port=%r file=%r" % (list(caps.items())[:2],
                            list(truth_caps.items())[:2]))

    # 3. menu labels match
    menus = {m.get("Id"): locale.menu_labels(pack, m.get("Id"))
             for m in pack.get("Menus", ()) if isinstance(m, dict)}
    truth_menus = {m.get("Id"): m.get("Items")
                   for m in truth.get("Menus", ()) if isinstance(m, dict)}
    ck("%s: menu label lists match the file" % pack_name,
       menus == truth_menus,
       "ids port=%r file=%r" % (sorted(menus), sorted(truth_menus)))

    # 4. the file's own tail -- a pack that ends inside a JSON structure is
    #    a real defect worth reporting rather than swallowing.
    if io.open(path, "rb").read()[:3] == b"\xef\xbb\xbf":
        bom_packs.append(pack_name)
    if truth.get("Menus") and isinstance(truth["Menus"], list) \
            and truth["Menus"] and isinstance(truth["Menus"][-1], dict):
        valid_ends.append(truth["Menus"][-1].get("Id"))

# --- the JSON leniency the packs actually need ------------------------
ck("exactly 7 packs are not strict JSON (trailing commas)",
   len(lenient) == 7, "%d: %r" % (len(lenient), sorted(lenient)))
ck("...and they are the ones locale.py names",
   sorted(lenient) == sorted(["Bulgarian", "Danish", "English", "Indonesia",
                              "Italian", "Mongolian", "Turkish"]),
   str(sorted(lenient)))
dobule = [name for name in packs
          if os.path.exists(os.path.join(LOCALES, name, "lang.json"))
          and ",," in io.open(os.path.join(LOCALES, name, "lang.json"),
                              encoding="utf-8-sig").read()]
ck("exactly 2 packs carry a double comma (Bulgarian, Mongolian)",
   sorted(dobule) == ["Bulgarian", "Mongolian"], str(dobule))

ck("some packs carry a UTF-8 BOM and the reader survives it",
   bom_packs != [], "none found -- the BOM case is untested")
ck("the last Menus entry is an object with an Id in every such pack",
   all(i is not None for i in valid_ends), str(valid_ends[-3:]))
ck("the three documented sections are all present across the set",
   {"Strings", "Windows", "Menus"} <= sections_seen, str(sections_seen))


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail[:12]:
        print("  -", f)
    raise SystemExit(1)
print("regress_locale_all_packs: all checks ok (%d assertions, %d packs)"
      % (n[0], len(packs)))
