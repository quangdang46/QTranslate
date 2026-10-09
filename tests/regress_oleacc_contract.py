"""Regression: the C3 OLEACC contract, pinned to the binary's measured offsets.

Native evidence (re-derived 2026-10-10, not taken from a decompile's
labelling — see docs/review/C3_C8_C10_MOUSE_2026-10-10.md §C3a/§C3b/§C3c):

  Disassembly of FUN_00404901, raw instructions:

    00404925  CALL dword ptr [0x0050d640]   ; IAT -> GetCursorPos
    00404958  CALL dword ptr [0x0050d3d0]   ; IAT -> AccessibleObjectFromPoint
    00404983  CALL dword ptr [ECX + 0x28]   ; vtable slot 10 = IAccessible::get_accName
    00404989  CALL dword ptr [0x0050d3e8]   ; IAT -> OLEAUT32 ord 7  = SysStringLen
    00404991  JZ  0x0040499f                 ; len == 0  ->  fall through
    00404998  CALL 0x00401ea9                ; non-empty: attach to the CString
    004049b9  CALL dword ptr [ECX + 0x2c]   ; vtable slot 11 = IAccessible::get_accValue
    004049bf  CALL dword ptr [0x0050d3e8]   ; SysStringLen again
    004049d6  CALL dword ptr [0x0050d3ec]   ; OLEAUT32 ord 6  = SysFreeString
    004049e8  CALL dword ptr [0x0050d3ec]   ; SysFreeString (the out-param BSTR)
    004049f2  CALL dword ptr [0x0050d3e4]   ; OLEAUT32 ord 9  = SysStringByteLen
    00404a02  CALL dword ptr [EDX + 0x8]    ; vtable slot 2  = IUnknown::Release

Three things those instructions settle that a decompile alone does not:

1. `+0x28` = 40 = slot 10 and `+0x2c` = 44 = slot 11 on a 32-bit vtable, so
   `mouse_capture.cursor_text()`'s `vtbl[10]`/`vtbl[11]` are the binary's own
   offsets rather than a plausible guess that happened to work.
2. The fallback branch is `SysStringLen(name) == 0`, *not* an HRESULT test —
   `get_accName` returning S_OK with a zero-length string still falls through
   to `get_accValue`. Ghidra's C rendering as "when get_accName fails" reads as
   an HRESULT condition and is wrong.
3. The BSTR is attached to the CString verbatim (`FUN_00401ea9` ->
   `FUN_00402231` is a pure length + memmove copy with no trimming), so the
   only emptiness gate native applies is on *length*.

This suite pins all three, and records the one place the port knowingly
departs from #3.

Off-Windows the Win32 calls cannot run, so this is a contract suite: it
checks the offsets, the constants, the call order in the source, and that the
divergence is documented rather than accidental.
"""
import sys
import os
import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import mouse_capture as M  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


# ---------------------------------------------------------------- constants
# Each of these is the literal the binary pushes / compares against.
ck("WM_LBUTTONDOWN == 0x201", M.WM_LBUTTONDOWN == 0x201, hex(M.WM_LBUTTONDOWN))
ck("WM_LBUTTONUP == 0x202", M.WM_LBUTTONUP == 0x202, hex(M.WM_LBUTTONUP))
ck("SM_SWAPBUTTON == 0x17", M.SM_SWAPBUTTON == 0x17, hex(M.SM_SWAPBUTTON))
ck("RID_INPUT == 0x10000003", M.RID_INPUT == 0x10000003, hex(M.RID_INPUT))

# ------------------------------------------------- vtable slot arithmetic
# 32-bit PE, so slot k lives at byte offset k*4. The binary's offsets:
ck("slot 10 -> byte offset 0x28 (get_accName)", 10 * 4 == 0x28, hex(10 * 4))
ck("slot 11 -> byte offset 0x2c (get_accValue)", 11 * 4 == 0x2C, hex(11 * 4))
ck("slot 2  -> byte offset 0x08 (IUnknown::Release)", 2 * 4 == 0x8, hex(2 * 4))

# And the port must use those same slots.
src = inspect.getsource(M.cursor_text)
ck("cursor_text reads vtable slot 10",
   "vtbl[10]" in src or "vtbl [10]" in src)
ck("cursor_text reads vtable slot 11",
   "vtbl[11]" in src or "vtbl [11]" in src)
ck("cursor_text names get_accName", "get_accName" in src or "fn_get_name" in src)
ck("cursor_text names get_accValue", "get_accValue" in src or "fn_get_value" in src)

# ------------------------------------------- the gate is length, not HRESULT
# Native: JZ is taken on SysStringLen()'s return, so an S_OK get_accName with
# an empty string still reaches get_accValue. The port must test the string
# it got, not merely the call's success.
ck("cursor_text gates on SysStringLen",
   "SysStringLen" in src, "no SysStringLen gate found in cursor_text")
# ...and the gate must actually gate: there must be one SysStringLen check
# per extraction, i.e. two, one before each return. Counting catches a port
# that keeps the call but drops the branch, which a substring test misses.
#
# (Verified by mutation: downgrading either `if oleaut.SysStringLen(bstr)` to
# a plain truthiness check fails this assertion. Note what is NOT pinned --
# the port's extra `and bstr` null-guard is defensiveness native lacks, since
# native calls SysStringLen unconditionally at 0x404989 on a pre-zeroed
# out-param; that is a safety net, not a behavior, and no assertion guards it.)
import re as _re
_gate_calls = _re.findall(r"SysStringLen\s*\(", src)
ck("two SysStringLen gates, one per BSTR read", len(_gate_calls) >= 2,
   "found %d for %r" % (len(_gate_calls), _gate_calls))
ck("both gates are conditional (`if ... SysStringLen`)",
   len(_re.findall(r"if\s+[^:\n]*SysStringLen", src)) >= 2,
   "a SysStringLen present but not used as a condition is not a gate")
ck("cursor_text consults get_accName before get_accValue",
   src.index("get_accName" if "get_accName" in src else "fn_get_name")
   < src.index("get_accValue" if "get_accValue" in src else "fn_get_value"))

# SysFreeString must appear for both the primary and the fallback, and the
# object must be released -- native frees at 0x5049d6, 0x5049e8 and Releases
# vtable slot 2 at 0x504a02.
ck("cursor_text frees the BSTR (SysFreeString)", "SysFreeString" in src)
ck("cursor_text releases the IAccessible object", "Release" in src)

# ------------------------------------------------------- the known divergence
# Native attaches the BSTR verbatim; FUN_00402231 is a length + memmove with
# no trimming, so native's only emptiness test is on length.
#
# The port strips, both here and again at the call site in app.py. This is a
# *deliberate* port decision -- a whitespace-only accessible name is not
# useful translation input and the clipboard fallback is better -- but it is
# a divergence and this suite exists partly so it cannot be mistaken for
# fidelity. If the port is ever changed to stop stripping, this check is the
# one that tells you the decision flipped.
ck("cursor_text strips -- recorded divergence from native's verbatim attach",
   ".strip()" in src,
   "cursor_text no longer strips; update the C3 divergence note in "
   "docs/review/C3_C8_C10_MOUSE_2026-10-10.md")

mod_doc = M.__doc__ or ""
ck("module doc names FUN_00404901", "FUN_00404901" in mod_doc)
ck("module doc names the get_accValue fallback", "get_accValue" in mod_doc)

# The doc must carry the divergence, or the port will re-introduce it silently.
doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "review", "C3_C8_C10_MOUSE_2026-10-10.md")
if os.path.exists(doc_path):
    doc = open(doc_path, encoding="utf-8", errors="replace").read()
    ck("doc records the vtable slot offsets",
       "+ 0x28" in doc and "+ 0x2c" in doc,
       "the +0x28/+0x2c byte offsets are not in the doc")
    ck("doc records the length-not-HRESULT gate",
       "SysStringLen" in doc and "HRESULT" in doc)
    ck("doc records the .strip() divergence as a divergence",
       ".strip()" in doc and "does not strip" in doc,
       "the divergence is not stated")
else:
    ck("C3 doc present", False, doc_path)

# ------------------------------------------------------- off-Windows safety
ck("available() is False off Windows", M.available() is False)
ck("cursor_text returns '' off Windows, never raises",
   M.cursor_text(0, 0) == "")
try:
    M.stop()
    ck("stop() never raises off Windows", True)
except Exception as e:  # pragma: no cover - would be a defect
    ck("stop() never raises off Windows", False, repr(e))


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_oleacc_contract: all checks ok (%d assertions)" % n[0])
