"""Regression: ``codeFromLanguage`` semantics for dictionary URIs.

Every dictionary provider's ``buildUri`` resolves a language index
through its own ``SupportedLanguages`` with ``Common.js``'s
``codeFromLanguage``. The measured rules (recovered Common.js, chunk[5]
of the NSIS stream, `docs/review/COMMON_JS_RECOVERED_2026-10-11.md`)::

    function isLanguage(a){return a>AUTO_DETECT_LANGUAGE&&
                                a<SupportedLanguages.length}
    function codeFromLanguage(a){return a===AUTO_DETECT_LANGUAGE||isLanguage(a)
            ?SupportedLanguages[a]:UNKNOWN_LANGUAGE_CODE}

i.e. the entry is returned **unguarded** (the index is tested, never the
value), so an in-bounds unsupported entry interpolates as ``None`` in the
port (the table's ``None`` slot) while an out-of-bounds index becomes
``-1``. Refusing instead of sending ``-1`` would invent policy the
artifact does not have.

The reference below is a transcription of those two lines, so a wrong port
cannot make these pass. Headless.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.common import code_from_language  # noqa: E402
from qtranslate.services import dictionary as DU  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


AUTO = 1
UNKNOWN = -1


def ref(table, a):
    """Transcription of isLanguage + codeFromLanguage."""
    if a == AUTO or (a > AUTO and a < len(table)):
        return table[a]
    return UNKNOWN


TABLES = {
    "LINGVO_LANGS": DU.LINGVO_LANGS,
    "REVERSO_LANGS": getattr(DU, "REVERSO_LANGS", DU.LINGVO_LANGS),
    "BABYLON_DICT_LANGS": DU.BABYLON_DICT_LANGS,
}

for name, table in TABLES.items():
    ck("%s has 76 entries (native count)" % name, len(table) == 76,
       str(len(table)))
    for a in (-5, 0, AUTO, 2, 3, 17, 40, len(table) - 1, len(table),
              len(table) + 5, 999):
        got = code_from_language(a, table)
        exp = ref(table, a)
        ck("%s index %d" % (name, a), got == exp,
           "%r != %r" % (got, exp))

# the three measured rules, stated one by one
T = DU.LINGVO_LANGS
ck("auto (index 1) resolves to the table's auto entry",
   code_from_language(1, T) == ref(T, 1))
ck("out-of-bounds index -> -1 (UNKNOWN_LANGUAGE_CODE), not a refusal",
   code_from_language(len(T), T) == -1
   and code_from_language(999, T) == -1)
ck("index 0 -> -1 (below auto)", code_from_language(0, T) == -1)
ck("in-bounds unsupported slot passes through as None (unguarded read)",
   all(code_from_language(i, T) is None
       for i, v in enumerate(T) if v is None and i > 1))
ck("a supported slot returns its own code",
   code_from_language(75, T) == T[75])

# _codes() goes through _resolve, which adds ONE documented rule on top of
# codeFromLanguage: a None/empty table entry becomes -1 for an INDEX leg
# (native interpolates it), while a code that is no language at all passes
# through untouched (unresolvable input, kept visible). So index 1 here --
# LINGVO_LANGS[1] is None, i.e. auto is unsupported -- resolves to -1.
ck("index-1 (auto) leg resolves to -1 when the table has no auto entry",
   DU._codes(T, 1, 17) == (-1, "en"), str(DU._codes(T, 1, 17)))
ck("_codes keeps -1 for out-of-bounds legs (native ships it)",
   DU._codes(T, 0, 999) == (-1, -1))
ck("a real code pair resolves to that provider's own values",
   DU._codes(T, 17, 17) == ("en", "en"))
ck("a code that is no language at all passes through unchanged",
   DU._codes(T, "xx", 17) == ("xx", "en"),
   str(DU._codes(T, "xx", 17)))
ck("a KNOWN language with no entry here becomes -1 (not passed through)",
   DU._codes(T, "vi", 17) == (-1, "en"),
   str(DU._codes(T, "vi", 17)))

# supported() is the stricter predicate a caller may use INSTEAD of asking
# the table by hand; it must not claim support for a -1 or None leg.
ck("supported() rejects an out-of-bounds leg", not DU.supported(T, 0, 17))
ck("supported() rejects a pair whose table entry is None",
   not DU.supported(T, 1, 17))
ck("supported() accepts a pair coded by this provider",
   DU.supported(T, 17, 17) is True)

src = open("qtranslate/services/dictionary.py", encoding="utf-8").read()
ck("docstring records the measured Common.js rules",
   "UNKNOWN_LANGUAGE_CODE=-1" in src)
ck("docstring states the port does not invent a refusal",
   "inventing policy" in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_codes: all checks ok (%d assertions)" % n[0])
