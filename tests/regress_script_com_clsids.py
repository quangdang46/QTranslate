"""Regression: the script-engine CLSIDs, and how the bytes must be read.

Three rows (F1 engine creation, F3 the parser, F13 the engine requested)
rest on the same byte-to-GUID conversion, and that conversion is where a
silent inversion lives:

* Windows stores a GUID in memory with **`Data1`/`Data2`/`Data3`
  little-endian** and the last 8 bytes big-endian. Reading the raw bytes
  left-to-right therefore gives a *different* GUID from the one the
  constant names.
* `CLSID_JScript` is `{F414C260-6AC0-11CF-B6D1-00AA00BBBB58}`. Stored
  little-endian, that appears in the image as ``f4 14 c2 60 6a c0 11
  cf b6 d1 00 aa 00 bb bb 58``.

Checked both directions here, against the image, so the two spellings
cannot be confused later — the same way `F1` got it right and a naive
byte-for-GUID read would get it wrong.

Headless; the image is read, never executed. Skips if it is absent.
"""
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append("%s -- %s" % (name, detail) if detail else name)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "docs", "review", "artifacts", "QTranslate.6.10.0.exe")

JSCRIPT = uuid.UUID("F414C260-6AC0-11CF-B6D1-00AA00BBBB58")
IACTIVESCRIPT = uuid.UUID("BB1A2AE1-A4F9-11CF-8F20-00805F2CD064")
IACTIVESCRIPTPARSE = uuid.UUID("BB1A2AE2-A4F9-11CF-8F20-00805F2CD064")
CHAKRA = uuid.UUID("16D51579-A30B-4C8B-A276-0FF4DC41E755")

# --- 1. the storage convention itself ----------------------------------
ck("a GUID's first three fields are stored little-endian",
   JSCRIPT.bytes_le != JSCRIPT.bytes,
   "the LE form is identical to the BE form")
ck("JScript's LE form is 60c214f4c06acf11...",
   JSCRIPT.bytes_le.hex() == "60c214f4c06acf11b6d100aa00bbbb58",
   JSCRIPT.bytes_le.hex())
ck("...and IActiveScript's is e12a1abb...",
   IACTIVESCRIPT.bytes_le.hex() == "e12a1abbf9a4cf118f2000805f2cd064",
   IACTIVESCRIPT.bytes_le.hex())
ck("the round trip restores the named GUID",
   uuid.UUID(bytes_le=JSCRIPT.bytes_le) == JSCRIPT)
ck("...for both spellings (LE and BE differ only in field order)",
   uuid.UUID(bytes=JSCRIPT.bytes) == JSCRIPT)

BLOBS = [
    # (label, GUID, expected presence in the image)
    ("CLSID_JScript", JSCRIPT, True),
    ("IActiveScript", IACTIVESCRIPT, True),
    ("IActiveScriptParse", IACTIVESCRIPTPARSE, True),
    ("Chakra/JScript9", CHAKRA, False),
]

if os.path.exists(EXE):
    img = open(EXE, "rb").read()
    for label, guid, present in BLOBS:
        n_le = img.count(guid.bytes_le)
        n_be = img.count(guid.bytes)
        ck("%s: stored little-endian in the image" % label,
           (n_le > 0) == present, "le=%d be=%d" % (n_le, n_be))
        # a GUID whose first three fields are non-symmetric appears in only
        # ONE of the two spellings -- which is the trap: taking the bytes at
        # face value yields a different GUID than the one named.
        if present:
            ck("%s: exactly one of the two spellings appears" % label,
               (n_le > 0) != (n_be > 0), "le=%d be=%d" % (n_le, n_be))
    ck("the JScript CLSID is in the image exactly once",
       img.count(JSCRIPT.bytes_le) == 1, str(img.count(JSCRIPT.bytes_le)))

    # --- 2. the name strings: 'CLSID_JScript' is a LABEL, not native's ----
    # F1/F13 write the GUID's familiar name, but the name itself is nowhere
    # in the image -- only the 16 bytes are. Chakra is likewise absent.
    for name in ("Chakra", "JScript9", "VBScript", "JavaScript"):
        ck("no %r string in the image" % name,
           img.count(name.encode("utf-16-le")) == 0,
           str(img.count(name.encode("utf-16-le"))))
    for name in ("JScript", "CLSID_JScript"):
        ck("no %r string either -- the name is the checklist's label, "
           "not native's" % name,
           img.count(name.encode("utf-16-le")) == 0,
           str(img.count(name.encode("utf-16-le"))))

    # --- 3. all three GUIDs sit in one adjacent const block -------------
    # Each appears more than once (the crash reporter's GUID table and the
    # COM registration both carry them), so take the LAST occurrence of
    # each and check THAT trio is adjacent -- the block F1 quotes.
    def last(guid):
        hits = [m.start() for m in
                re.finditer(re.escape(guid.bytes_le), img)]
        return hits[-1] if hits else -1

    trio = sorted(last(g) for g in
                  (JSCRIPT, IACTIVESCRIPT, IACTIVESCRIPTPARSE))
    ck("all three GUIDs are present", all(o >= 0 for o in trio), str(trio))
    ck("...and their last occurrences are within 64 bytes of each other",
       trio[2] - trio[0] < 64, str(trio))
    # They are stored 16 bytes apart, in order IActiveScript,
    # IActiveScriptParse, CLSID_JScript -- a COM GUID table, which is the
    # adjacency F1's "crypto section"-style evidence rests on.
    ck("...each exactly 16 bytes after the previous one",
       trio[1] - trio[0] == 16 and trio[2] - trio[1] == 16, str(trio))
    ck("...so JScript's 16 bytes are the LAST of the three (not first)",
       last(JSCRIPT) == max(trio), str(trio))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail[:15]:
        print("  -", f)
    raise SystemExit(1)
print("regress_script_com_clsids: all checks ok (%d assertions%s)"
      % (n[0], ", image verified" if os.path.exists(EXE)
         else ", image absent"))
