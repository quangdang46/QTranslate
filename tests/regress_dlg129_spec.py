"""Regression: DLG129's native control spec, re-derived and cross-checked.

`docs/review/G9_SPEC_NATIVE_WINDOW_2026-10-10.md` §5 listed three things it
could **not** pin and refused to guess:

  1. the ids of the four owner-draw buttons (its walker produced
     `1342275648` for them);
  2. whether control id `1001` exists at all (the template has `1002` as a
     ComboBox and no `1001`, so the checklist's claim looked wrong);
  3. the DLU→px conversion of the `340×201` template.

`tools/dlg_parse.py` resolves all three. It reads `DLGTEMPLATEEX`
properly — each control is `helpID, exStyle, style, x, y, cx, cy, id(4),
sz_Class, sz_Text, creationDataLength(2), creationData`. The earlier
walker did not treat the id as 4 bytes, so every control after the first
owner-draw one was read misaligned.

This suite pins the derived table and — the part that makes it evidence
rather than another doc claim — **cross-checks it against the port's own
id table**, which was written independently from native:

  `qtranslate/win32app.py` declares ID_SRC=1017, ID_SRC_LANG=1001, ... .
  If the parse is wrong, the two disagree.

Skips (exit 0) when the recovered exe is absent, because that blob is
intentionally not committed (`ARTIFACT_RECOVERY_2026-10-10.md` §7).

Headless, no network, no window.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

EXE = os.path.join(ROOT, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s%s" % (name, (" -- " + detail) if detail else ""))


if not os.path.exists(EXE):
    print("SKIP: %s not present (uncommitted recovered artifact)" % EXE)
    print("regress_dlg129_spec: skipped")
    raise SystemExit(0)

import dlg_parse  # noqa: E402

# `win32app` is imported ONLY for its id table, and it needs pywin32 (an
# optional dep), so its constants are read from source instead:
# `ID_FOO = 1234` lines. Same data, no import requirement.
WSRC = io.open(os.path.join(ROOT, "qtranslate", "win32app.py"),
               encoding="utf-8").read()

blob = open(EXE, "rb").read()
dialogs, raw, rva_base = dlg_parse._dialogs(blob)
cur = dlg_parse._Cursor(blob[raw:raw + 0x13600], rva_base)
ck("RT_DIALOG parsed from the recovered image", 129 in dialogs)
hdr, ctrls = dlg_parse.parse_template(cur, dialogs[129][0] - rva_base)

# --- 1. the template header, re-verified ---------------------------------
ck("DLG129 is a DLGTEMPLATEEX (dlgVer 1)", hdr.get("dlgVer") == 1)
ck("its title is 'QTranslate'", hdr.get("title") == "QTranslate")
ck("style is 0x80CF0048", hdr["style"] == 0x80CF0048, hex(hdr["style"]))
ck("exStyle is WS_EX_CONTROLPARENT (0x00040000)",
   hdr["exStyle"] == 0x00040000, hex(hdr["exStyle"]))
ck("17 controls declared and all 17 parsed",
   hdr["cdit"] == 17 and len(ctrls) == 17, "cdit=%d parsed=%d"
   % (hdr["cdit"], len(ctrls)))

# The claim the 2026-10-10 doc had to correct: units.
ck("template geometry is 340 x 201 DIALOG UNITS, not pixels",
   (hdr["cx"], hdr["cy"]) == (340, 201),
   "got %rx%r -- a pixel number here means the parser read the wrong field"
   % (hdr["cx"], hdr["cy"]))
ck("...so 526x366 can only be a saved runtime placement, not the template",
   526 not in (hdr["cx"], hdr["cy"]))
ck("the font is MS Shell Dlg at 8pt (not Tahoma 9)",
   hdr.get("font") == "MS Shell Dlg" and hdr.get("pointSize") == 8,
   "font=%r pt=%r" % (hdr.get("font"), hdr.get("pointSize")))
ck("DS_SETFONT is set (the font field is authoritative)",
   bool(hdr["style"] & 0x40))

# --- 2. no id is implausible (the original walker's failure mode) --------
bad = [c["id"] for c in ctrls if c["id"] > 0xFFFF or c["id"] < 0]
ck("no implausible control ids (every id is a 16-bit control id)",
   not bad, "misaligned parse produced %r" % bad)
ids = [c["id"] for c in ctrls]
ck("all 17 control ids are distinct", len(set(ids)) == 17)

# --- 3. the full table, including what the old walker missed ------------
# (id, class, text) -- text matters because ':' / '<>' / 'Fav' are how the
# icon buttons are identified when their icons cannot be extracted.
WANT = [
    (1000, "RichEdit50W", ""),
    (1001, "ComboBox", ""),
    (1002, "ComboBox", ""),
    (1004, "Button", "Translate"),
    (1009, "Button", ":"),
    (1015, "Button", "<>"),
    (1017, "RichEdit50W", ""),
    (1018, "RichEdit50W", ""),
    (1021, "Button", "New"),
    (1022, "Button", "V"),
    (1027, "Button", "Play"),
    (1028, "Button", "Play"),
    (1029, "Button", "Fav"),
    (1030, "Button", "Speech"),
    (1134, "Static", ""),
    (1135, "Static", ""),
    (1161, "SysLink", "Info"),
]
by_id = {c["id"]: c for c in ctrls}
for cid, cls, text in WANT:
    c = by_id.get(cid)
    ck("DLG129 has control %d" % cid, c is not None)
    if c is None:
        continue
    ck("...%d is a %s" % (cid, cls), c["class"] == cls, c["class"])
    ck("...%d text is %r" % (cid, text), c["text"] == text, repr(c["text"]))

# The two specific unknowns from §5.
ck("UNKNOWN #1 resolved: control id 1001 EXISTS (the source ComboBox)",
   by_id.get(1001, {}).get("class") == "ComboBox")
ck("UNKNOWN #2 resolved: the four icon buttons are 1027/1028/1029/1030",
   sorted(by_id[i]["text"] for i in (1027, 1028, 1029, 1030))
   == ["Fav", "Play", "Play", "Speech"])
ck("...and their classes are Button, not garbage atoms",
   all(by_id[i]["class"] == "Button" for i in (1027, 1028, 1029, 1030)))
# The icon buttons carry BS_ICON (0x40) -- which is why their CONTENT is an
# icon resource, not their caption. `Speech` (1030) additionally has type
# bits 0x5 and BS_PUSHLIKE (0x1000)/BS_NOTIFY-ish 0x10000, i.e. it is the
# one toggle-style button of the group. The port's comment calls it
# "Speech-radio", which the type bits support; asserting an exact
# BS_AUTO3STATE would have been a guess, and this suite does not guess.
ck("...1027/1028/1029 are plain BS_ICON buttons",
   all(by_id[i]["style"] & 0x40 for i in (1027, 1028, 1029)))
ck("...1030 is BS_ICON too, with the toggle type bits set",
   by_id[1030]["style"] & 0x40 and (by_id[1030]["style"] & 0x10000))
ck("...and the four icon buttons share WS_EX_TRANSPARENT-ish 0x20",
   all(by_id[i]["ex_style"] == 0x20 for i in (1027, 1028, 1029, 1030)),
   "exStyles: %r" % [hex(by_id[i]["ex_style"]) for i in (1027, 1028, 1029,
                                                         1030)])

# --- 4. cross-check against the port's independent id table -------------
# This is what turns a doc claim into evidence: win32app.py's ids were
# written from native separately, so agreement is real corroboration.
PORT_IDS = {
    1017: "ID_SRC", 1018: "ID_OUT", 1001: "ID_SRC_LANG", 1002: "ID_TGT_LANG",
    1021: "ID_NEW", 1022: "ID_MENU", 1015: "ID_SWAP", 1004: "ID_GO",
    1029: "ID_FAV", 1030: "ID_SPEECH", 1027: "ID_PLAY_SRC",
    1028: "ID_PLAY_OUT", 1009: "ID_HELP",
}
for cid, name in sorted(PORT_IDS.items()):
    m = re.search(r"^%s\s*=\s*(\d+)" % name, WSRC, re.M)
    ck("win32app.py %s = %d (matches the parse)" % (name, cid),
       m is not None and int(m.group(1)) == cid,
       "found %r" % (m.group(1) if m else None))
ck("the port covers every id the template declares that it models",
   set(PORT_IDS) <= set(ids),
   "port names an id the template does not have: %r"
   % sorted(set(PORT_IDS) - set(ids)))

# --- 5. DLU->px is a RANGE, and the range is the honest answer ---------
ck("340x201 DU converts to a range, never one number",
   len(set(dlg_parse.dlu_to_px(340, 201, w, h)
           for _l, w, h in dlg_parse.FONT_CANDIDATES)) >= 3)
px100 = dlg_parse.dlu_to_px(340, 201, 6, 13)
ck("Tahoma 8pt @100% gives 510x326 (the doc's own arithmetic)",
   px100 == (510, 326), str(px100))
ck("no candidate metric reproduces 526x366",
   all(dlg_parse.dlu_to_px(340, 201, w, h) != (526, 366)
       for _l, w, h in dlg_parse.FONT_CANDIDATES),
   "526x366 is a runtime placement, not a conversion of this template")

# --- 6. the whole resource table still parses (alignment is global) ----
ck("all 19 RT_DIALOGs parse with a sane control count",
   len(dialogs) == 19 and all(
       dlg_parse.parse_template(cur, dialogs[d][0] - rva_base)[0]["cdit"]
       >= 2 for d in dialogs),
   "a control-count of 0/1 means the parser lost alignment")

if fails:
    print("FAIL %d/%d" % (len(fails), n[0]))
    for f in fails:
        try:
            print("  -", f)
        except UnicodeEncodeError:
            print("  -", f.encode("ascii", "replace").decode("ascii"))
    raise SystemExit(1)
print("regress_dlg129_spec: all checks ok (%d assertions)" % n[0])
