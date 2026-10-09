"""Regression: dictionary provider language tables match native length/content.

Native Services/*/Service.js each declare SupportedLanguages with 76 entries
(index 0 unused, aligned to the shared language index). A short table silently
shifts every language code after the gap. Reverso was 75 (missing a trailing
slot) until 2026-10-09.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))

from qtranslate.services import dictionary as D  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


TABLES = ["MULTITRAN_LANGS", "URBAN_LANGS", "OXFORD_LANGS", "REVERSO_LANGS",
          "WORDREF_LANGS", "WIKI_LANGS", "GSEARCH_LANGS", "LINGVO_LANGS",
          "BABYLON_LANGS", "BABYLON_DICT_LANGS", "IMTRANS_LANGS"]

for name in TABLES:
    tbl = getattr(D, name, None)
    check("%s exists" % name, isinstance(tbl, list))
    if isinstance(tbl, list):
        check("%s has 76 entries (native length)" % name, len(tbl) == 76,
              "len=%d" % len(tbl))

# Spot values byte-verified from the native Service.js files.
check("MULTITRAN en(idx17)=1", D.MULTITRAN_LANGS[17] == 1)
check("MULTITRAN ru(idx46)=2", D.MULTITRAN_LANGS[46] == 2)
check("REVERSO tail slots present", D.REVERSO_LANGS[74] is None
      and D.REVERSO_LANGS[75] is None)
check("REVERSO german(idx23)", str(D.REVERSO_LANGS[23]).lower() == "german")

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: all %d dict language tables are 76 entries + spot values match"
      % len(TABLES))
