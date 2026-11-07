#!/usr/bin/env python3
"""system_spell + tesseract OCR backend checks.

system_spell ports .tmp system-services MacSpellCheckerBackend
(NSSpellChecker) in-process. The live macOS assertions only run on
darwin; the UTF-16 offset math is pure Python and runs everywhere.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import system_spell as SS  # noqa: E402
from qtranslate.services import ocr  # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


print("== system_spell UTF-16 offsets ==")
# BMP-only text: UTF-16 index == Python index.
ck("bmp identity", SS._utf16_to_py("teh quik", 4) == 4)
# Astral char (U+2764 U+FE0F is two code points but the emoji pair...
# use a true astral char): 'a' + U+1F600 + 'b' -> UTF-16 len 4.
emoji_text = "a\U0001F600b"
ck("astral counts 2", SS._utf16_to_py(emoji_text, 3) == 2)
ck("astral end", SS._utf16_to_py(emoji_text, 4) == 3)
# 'x' + emoji(2 UTF-16 units) + 'yz': UTF-16 offsets x=0-1,
# emoji=1-3, y=3-4, z=4-5.
ck("slice", SS._utf16_slice("x\U0001F600yz", 3, 5) == "yz")

print("== availability ==")
import sys as _s
ck("available is bool", isinstance(SS.available(), bool))
if _s.platform != "darwin":
    ck("non-darwin check -> None",
       SS.check("teh quik", "en") is None)

print("== tesseract backend ==")
ck("garbage bytes -> None, no crash",
   ocr._tesseract_ocr(b"this is not an image", "eng") in (None, ""))

if _s.platform == "darwin":
    print("== live NSSpellChecker ==")
    r = SS.check("teh quik brown foxx", "en")
    ck("returns dict", isinstance(r, dict), repr(r)[:80])
    if isinstance(r, dict):
        corr = r.get("corrections") or []
        ck("found corrections", len(corr) >= 2, repr(corr)[:120])
        by_orig = {c["original"]: c for c in corr}
        if "teh" in by_orig:
            ck("teh offsets", by_orig["teh"]["startIndex"] == 0
               and by_orig["teh"]["endIndex"] == 3)
            ck("teh suggests the",
               "the" in by_orig["teh"]["suggestions"])
        if "quik" in by_orig:
            ck("quik offsets", by_orig["quik"]["startIndex"] == 4
               and by_orig["quik"]["endIndex"] == 8)
        ck("correctedText has no teh/quik",
           "teh" not in (r.get("correctedText") or "")
           and "quik" not in (r.get("correctedText") or ""))
        ck("clean text -> no corrections",
           (SS.check("the quick brown fox", "en")
            or {}).get("corrections") == [])

print()
if FAIL:
    print("regress_system_spell: %d FAILED: %s" % (len(FAIL), FAIL))
    sys.exit(1)
print("regress_system_spell: all checks ok")
