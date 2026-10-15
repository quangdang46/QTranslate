"""Dict-task source language follows General.LanguageDictionary.

Native builder FUN_00414f54 overwrites param_1[4] (target) with
DAT_005493f4 (General.LanguageDictionary, default 17 = "en") when it is
1 (auto). The port's ``go_all`` used to hardcode "en"; it must now read
the option, with the same default and the same auto-sentinel guard.

Offline: exercises the resolution logic (index -> code, auto/-1 -> "en",
bad index -> "en") without opening any window.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


import qtranslate.services.google_translate as G

T = list(G.SUPPORTED_LANGS)


def resolve(idx, default=17):
    """Mirror of the go_all resolution block in qtranslate/app.py."""
    try:
        ld = default if idx is None else idx
        code = T[ld] if 0 <= ld < len(T) else "en"
        if code in (-1, "auto"):
            code = "en"
    except Exception:
        code = "en"
    return code


# native default: LanguageDictionary=17 -> "en"
ck("default 17 -> en", resolve(17) == "en", resolve(17))
ck("None -> en", resolve(None) == "en", resolve(None))
# auto sentinel (index 1) resolves to the concrete default
ck("auto idx 1 -> en", resolve(1) == "en", resolve(1))
ck("placeholder -1 holder (idx 0) -> en", resolve(0) == "en",
   repr(resolve(0)))
# a real selection passes through (raw SUPPORTED_LANGS, which keeps the
# -1 placeholder at index 0 — this is the table LanguageDictionary indexes
# into, not the filtered A.LANGS; ui_match's langs-index pins that table)
ck("57 -> vi", resolve(57) == "vi", repr(resolve(57)))
ck("56 -> ur", resolve(56) == "ur", repr(resolve(56)))
# out-of-range / bad values fall back to "en"
ck("huge idx -> en", resolve(10**6) == "en", repr(resolve(10**6)))
ck("negative idx -> en", resolve(-5) == "en", repr(resolve(-5)))

# the call site must read the option, not hardcode "en"
src = io.open("qtranslate/app.py", encoding="utf-8").read()
ck("go_all reads LanguageDictionary",
   'LanguageDictionary' in src and 'fn(word_q, _dsl' in src,
   "call site must resolve _dsl from the option")

print("regress_dict_lang: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
