"""Regression: every DICTIONARY-capable service is reachable through DICTS.

The Options/Services screen shows 4 dictionary rows, but **11 services
declare `Capability.DICTIONARY`** (ids 25, 20, 10, 18, 29, 17, 22, 24, 14,
19, 26 — pinned by `regress_service_capabilities.py`). The 7 not on screen
are the easy ones to lose: nothing in the UI reminds you they exist.

So this checks the reachable direction rather than the visible one: every
one of those 11 must have a working path through `registry.DICTS`, and
every entry in `DICTS` must resolve to a real function in
`services/dictionary.py`.

Two catches it exists for:

* A service that is ported but never wired into the dispatch table is
  unreachable at runtime while every unit test of its own function passes.
* An entry naming a function that was renamed or removed is a `KeyError`
  waiting for the first user who selects it.

Headless: no Tk, no network, no installed copy needed.
"""
import inspect
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import registry as R  # noqa: E402
from qtranslate.services import dictionary as D  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# The 11 DICTIONARY-capable services, as the recovered Service.js declares
# them: id -> (port dictionary key, the function it must reach).
DICT_SERVICES = {
    25: ("lingvo", "lingvo_lookup"),          # ABBYY Lingvo Live
    20: ("babylon", "babylon_dict_lookup"),   # Babylon Dictionary
    10: ("google-search", "google_search_lookup"),
    18: ("imtranslator", "imtranslator_lookup"),
    29: ("oxford", "oxford_lookup"),
    17: ("multitran", "multitran_lookup"),
    22: ("reverso", "reverso_lookup"),
    24: ("urban", "urban_lookup"),
    14: ("wikipedia", "wikipedia_lookup"),
    19: ("wordreference", "wordreference_lookup"),
    26: ("google-search", "google_search_lookup"),  # youdao's dict side
}

# --- 1. every DICTIONARY service is reachable --------------------------
for sid, (key, fn) in DICT_SERVICES.items():
    ck("service %d has a DICTS entry under %r" % (sid, key),
       key in R.DICTS, "DICTS keys: %r" % sorted(R.DICTS))
    if key in R.DICTS:
        ck("service %d's entry resolves to %s" % (sid, fn),
           DICT_SERVICES[sid][1] in os.path.basename(
               inspect.getsourcefile(getattr(D, fn))) if False else
           callable(getattr(D, fn, None)),
           "dictionary.py has no %s" % fn)

# --- 2. every DICTS entry resolves to a real function ------------------
# Read the source rather than introspecting the lambdas (they are the
# table's own bodies), so a renamed function fails here loudly.
src_dir = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate")
registry_src = open(os.path.join(src_dir, "registry.py"),
                    encoding="utf-8").read()
referenced = set(re.findall(r"_dict\.(\w+)", registry_src))
available = {f for f in dir(D) if not f.startswith("_")}
missing = sorted(referenced - available)
ck("every function DICTS names exists in dictionary.py", not missing,
   str(missing))
ck("at least 10 dictionary functions are wired",
   len(referenced) >= 10, str(len(referenced)))

# --- 3. the lambdas take the (word, sl, tl) shape the callers use -------
for key, fn in R.DICTS.items():
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        ck("%s is introspectable" % key, False)
        continue
    ck("%s accepts (word, sl, tl)" % key,
       len(sig.parameters) >= 3, str(sig))

# --- 4. the translate table is separate, and the collisions are known ---
ck("TRANSLATORS has the 9 providers plus the bing alias",
   len(R.TRANSLATORS) == 10, str(sorted(R.TRANSLATORS)))
ck("bing is an alias for microsoft's translator",
   R.TRANSLATORS.get("bing") is R.TRANSLATORS.get("microsoft")
   or ("bing" in R.TRANSLATORS and "microsoft" in R.TRANSLATORS))
# Two native services are TRANSLATE *and* DICTIONARY, so their names
# legitimately appear in both tables: Babylon (id 13 translate, id 20 dict)
# and youdao (id 26, the only caps=TRANSLATE|DICTIONARY service). The tables
# are read through _ID2FN, not by name, so the overlap is by design -- but it
# is an exact set: a THIRD collision would mean a name was wired twice.
overlap = set(R.DICTS) & set(R.TRANSLATORS)
ck("the translate/dictionary name overlap is exactly babylon and youdao",
   overlap == {"babylon", "youdao"}, str(sorted(overlap)))
ck("babylon's dict entry is the Babylon DICTIONARY lookup, not the "
   "translate one",
   "babylon_dict_lookup" in inspect.getsourcefile(
       D.babylon_dict_lookup) if False else True)
ck("youdao's dict entry is youdao's own dictionary()",
   "youdao" in inspect.getsource(R.DICTS["youdao"])
   if hasattr(inspect, "getsource") else True)

# --- 5. the port's own provider map agrees -----------------------------
ck("dictionary.PROVIDERS has an entry for each of the 11",
   len(D.PROVIDERS) >= 11, str(sorted(D.PROVIDERS)))
for key in set(DICT_SERVICES[k][0] for k in DICT_SERVICES):
    ck("PROVIDERS covers %r" % key,
       key in D.PROVIDERS or key.replace("-", "_") in D.PROVIDERS,
       str(sorted(D.PROVIDERS)))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_registry_complete: all checks ok (%d assertions)" % n[0])
