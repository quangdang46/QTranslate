"""Regression: read-phonetically display (J7, FUN_0042ED3F phonetics branch).

Native evidence (Ghidra decompile of the recovered image,
`docs/review/ARTIFACT_RECOVERY_2026-10-10.md`):

```c
uVar1 = FUN_00403897(param_1);              // 1 - (CString::Find(L"<Error>") != 0)
if ((((char)uVar1 == '\0') && (*(int *)(param_1[5] + -0xc) != 0))
    && (DAT_00549414 != '\0')) {
    FUN_00401f21(&DAT_0052284c);              // append "\r\r"   @ 0x12184c
    FUN_00451d23(&param_2, 0xba);            // append "Romanization: " @ 0x158c00
    FUN_004089fe(param_1 + 5, 0);            // append entry[5] (phonetics)
}
```

Three gates, all required:
  1. `FUN_00403897` — `"<Error>"` is **absent** from the result.
  2. `entry[5]` (the phonetics field) is **non-empty**.
  3. `DAT_00549414` (`General.ReadPhonetically`) is **non-zero**.

Every literal below is located by wide-char content offset, so the assertions
pin the port to measured bytes rather than to chosen wording.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import phonetics as P  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


# --- the three literals must match the recovered bytes exactly ---
ck("separator is exactly CR CR (0x12184c)", P.PHONETICS_SEPARATOR == "\r\r",
   repr(P.PHONETICS_SEPARATOR))
ck("separator is 2 chars, not 4 escaped", len(P.PHONETICS_SEPARATOR) == 2)
ck("label is the native RT_STRING 186 wording",
   P.PHONETICS_LABEL == "Romanization: ", repr(P.PHONETICS_LABEL))
ck("label keeps native's trailing space", P.PHONETICS_LABEL.endswith(" "))
ck("gate marker is the native <Error> string",
   P.ERROR_MARKER == "<Error>", repr(P.ERROR_MARKER))

# --- gate 3: flag off -> nothing appended, whatever else is supplied ---
ck("flag off, phonetics present -> unchanged",
   P.append_phonetics("T", "phon", enabled=False) == "T")
ck("flag off, empty phonetics -> unchanged",
   P.append_phonetics("T", "", enabled=False) == "T")
ck("flag off, no label -> unchanged",
   P.append_phonetics("T", "phon", enabled=False, label=None) == "T")

# --- gate 2: flag on but phonetics empty -> nothing appended ---
ck("flag on, phonetics empty -> unchanged",
   P.append_phonetics("T", "", enabled=True) == "T")
ck("flag on, phonetics whitespace -> unchanged",
   P.append_phonetics("T", "   ", enabled=True) == "T")
ck("flag on, phonetics None -> unchanged",
   P.append_phonetics("T", None, enabled=True) == "T")

# --- gate 1: result is an <Error> marker -> nothing appended ---
ck("error result alone -> unchanged",
   P.append_phonetics("<Error>", "phon", enabled=True) == "<Error>")
ck("error marker mid-result -> unchanged",
   P.append_phonetics("boom <Error> tail", "phon", enabled=True)
   == "boom <Error> tail")
ck("error marker wins even with a label",
   P.append_phonetics("<Error>", "phon", enabled=True, label="L: ") == "<Error>")
ck("the <Error> match is exact, so a lowercase variant is not suppressed",
   P.append_phonetics("<error>", "p", True)
   == "<error>\r\r" + "Romanization: " + "p")

# --- all three gates open -> separator + native label + phonetics ---
got = P.append_phonetics("hello", "/haɪ/", enabled=True)
ck("appends separator before the label",
   got.startswith("hello" + "\r\r"), repr(got))
ck("appends the native label then the phonetics",
   got.endswith("Romanization: /haɪ/"), repr(got))
ck("no double separator", got.count("\r\r") == 1, repr(got))
ck("assemble matches native field order",
   got == "hello" + "\r\r" + "Romanization: " + "/haɪ/", repr(got))

ck("a caller-supplied label still replaces the default",
   P.append_phonetics("hello", "/haɪ/", enabled=True, label="Pronunciation: ")
   == "hello\r\rPronunciation: /haɪ/")
ck("with label=None the separator still precedes the phonetics",
   P.append_phonetics("hello", "/haɪ/", enabled=True, label=None)
   == "hello\r\r/haɪ/")

# --- text is preserved verbatim, no strip/mutation of the base ---
ck("base text is not stripped",
   P.append_phonetics("  x  ", "p", True) == "  x  \r\r" + "Romanization: " + "p")
ck("empty base text still gets the block",
   P.append_phonetics("", "p", True) == "\r\r" + "Romanization: " + "p")
ck("None base text is treated as empty, not as a crash",
   P.append_phonetics(None, "p", True) == "\r\r" + "Romanization: " + "p")

# --- the phonetics field keeps off-by-whitespace content, like the native ---
ck("leading whitespace inside phonetics is stripped (native .GetBuffer)",
   P.append_phonetics("t", "  /a/  ", True).endswith("Romanization: /a/"))

# --- the config gate helper ---
ck("phonetics_enabled true",
   P.phonetics_enabled({"General": {"ReadPhonetically": True}}))
ck("phonetics_enabled false",
   not P.phonetics_enabled({"General": {"ReadPhonetically": False}}))
ck("phonetics_enabled missing -> off (native default)",
   not P.phonetics_enabled({"General": {}}))
ck("phonetics_enabled bad shape -> off",
   not P.phonetics_enabled(None) and not P.phonetics_enabled({}))
ck("phonetics_enabled truthy non-bool -> on",
   P.phonetics_enabled({"General": {"ReadPhonetically": 1}}))
ck("helper reads through a load() callable",
   P.is_phonetics_enabled_from_config(
       lambda: {"General": {"ReadPhonetically": True}}))
ck("helper tolerates load() raising",
   not P.is_phonetics_enabled_from_config(
       lambda: (_ for _ in ()).throw(OSError())))

# --- the module must not claim the label is unrecovered any more ---
_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(_here, "qtranslate", "phonetics.py"),
          encoding="utf-8") as f:
    src = f.read()
ck("module no longer says the label is NOT recovered",
   "NOT recovered" not in src)
ck("module cites the RT_STRING id the native passes",
   "0xBA" in src or "186" in src)
ck("module cites the wide-char offset of the label", "0x158c00" in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_phonetics: all checks ok (%d assertions)" % n[0])
