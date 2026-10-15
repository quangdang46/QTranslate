"""Layout-converter explicit pairs match the FUN_00404E09 decompile (P2).

Native evidence (checklist P2 evidence note): explicit special pairs for
the ambiguous-key set ``q w ' , . /`` — RU->EN ``'->w, comma->apostrophe,
.->/, /->q`` and EN->RU ``'->comma, /->., q->/, w->apostrophe`` — with the
generic VkKeyScanExW/ToUnicodeEx path as fallback.

History: the port's table used to restate the generic JCUKEN map as the
explicit set (``{"'": "э", ...}``), getting 6 of 8 pairs wrong while P2
read ``ported``. The note was right; the code was wrong. Fixed 2026-10-15.

Headless: imports only qtranslate.layout (no tkinter).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate.layout import EN2RU, RU2EN, convert_layout

# the 8 decompile-verified explicit pairs (lowercase)
for src, want in (("'", ","), ("/", "."), ("q", "/"), ("w", "'")):
    ck("EN %r -> %r" % (src, want), EN2RU.get(src) == want,
       repr(EN2RU.get(src)))
for src, want in (("'", "w"), (",", "'"), (".", "/"), ("/", "q")):
    ck("RU %r -> %r" % (src, want), RU2EN.get(src) == want,
       repr(RU2EN.get(src)))

# uppercase mirrors of the letter pairs
ck("EN Q -> /", EN2RU.get("Q") == "/")
ck("EN W -> '", EN2RU.get("W") == "'")

# generic JCUKEN fallback intact for non-ambiguous keys
ck("generic EN a -> ф", EN2RU.get("a") == "ф")
ck("generic RU ф -> a", RU2EN.get("ф") == "a")

# end-to-end sanity (direction auto-detect)
ck("Ghbdtn -> Привет", convert_layout("Ghbdtn") == "Привет",
   repr(convert_layout("Ghbdtn")))

print("regress_layout_pairs: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
