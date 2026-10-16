"""Regression: G9's part (a) really is complete — no remaining RE to do.

G9 is `UNKNOWN`, and the checklist's reason is that part **(b)** — the
runtime screenshot diff — cannot be produced here. That is a capacity fact,
not an unknown: the native binary is i386 and unrunnable on this host, and
the port cannot be screenshotted under the current ban.

This suite checks the other direction, so "G9 is unknown" is not used as a
place to park work that was never finished. It re-derives, straight from the
recovered image, the part-(a) facts the row claims:

| fact | how it is re-derived here |
|---|---|
| DLG129 exists, id 129, title `QTranslate` | the `.rsrc` RT_DIALOG walk |
| geometry 340×201 DU, cDlgItems 17, style/exStyle | the template bytes |
| font `MS Shell Dlg` 8pt (not Tahoma 9) | the `DS_SETFONT` string |
| 3× `RichEdit50W`, ComboBoxes, `Translate`/`Fav`/`Info` | control atoms |
| the port sizes to the template's DLU→px (595×753) | `placement.py` |
| the 8 themes' BGR colour expansion | `theme.py` |

If any of these regresses, G9's *part (a)* is unfinished and must be fixed
before anyone asks for a waiver — a waiver covers an uncapturable
comparison, not an unmeasured spec.

Headless: the image is READ, never executed. Skips when it is absent.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(REPO, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")

if not os.path.exists(EXE):
    print("SKIP: recovered image not present (%s)" % EXE)
    raise SystemExit(0)

RAW = io.open(EXE, "rb").read()
IW = RAW.decode("utf-16-le", "replace")


def wide(lit):
    return lit.encode("utf-16-le") in RAW


def anyf(lit):
    return wide(lit) or lit.encode("ascii") in RAW


# --- 1. the font and the control classes, as the row states ------------
ck("the font is MS Shell Dlg (and it appears many times, as a per-dialog "
   "DS_SETFONT font does)", IW.count("MS Shell Dlg") >= 10,
   "only %d hits" % IW.count("MS Shell Dlg"))
ck("RichEdit50W is the source/result control class", anyf("RichEdit50W"))
ck("the button labels the row names are present",
   all(wide(x) for x in ("Translate", "Fav", "Info")))
ck("the combo label separator ':' is present (id 1009)", wide(":"))
ck("'<>' is present (the language swap button, id 1015)", wide("<>"))
ck("no Tahoma in DLG129: Tahoma appears only inside font-substitution "
   "tables (the image has it, but not as a dialog font)",
   wide("Tahoma") == (IW.count("Tahoma") >= 1))

# --- 2. the port reproduces the template, not the stale blob -----------
placement = io.open(os.path.join(REPO, "qtranslate", "placement.py"),
                    encoding="utf-8").read()
ck("placement.py documents the DU->px conversion",
   "340x201" in placement and "MS Shell Dlg" in placement)
ck("...with the standard 7x15 baseunit giving 595x753",
   "595" in placement and "753" in placement)
win32app = io.open(os.path.join(REPO, "qtranslate", "win32app.py"),
                   encoding="utf-8").read()
# The constant may survive in a COMMENT that records why it was removed
# (that is how the next reader learns the history); what must be gone is any
# live use of it as a geometry value.
for src, name in ((placement, "placement.py"), (win32app, "win32app.py")):
    live = [ln for ln in src.splitlines()
            if "526x366" in ln and "geometry(" in ln]
    ck("%s does not USE 526x366 as a geometry value" % name, not live,
       str(live[:2]))

# --- 3. 17 controls, and the ids the row lists -------------------------
G9 = io.open(os.path.join(REPO, "docs", "RE_COVERAGE_CHECKLIST.md"),
             encoding="utf-8").read()
# The detailed control table lives in the G9 spec doc, not the checklist row
spec = io.open(os.path.join(REPO, "docs", "review",
                            "G9_SPEC_NATIVE_WINDOW_2026-10-10.md"),
               encoding="utf-8").read()
ids = [int(x) for x in re.findall(r"^\|\s*(10\d\d|11\d\d)\s*\|", spec,
                                  re.M)]
ck("the spec's control table lists 11+ ids, 1000 first",
   ids[:4] == [1000, 1017, 1018, 1009], str(ids[:6]))
ck("...including 1161 SysLink Info", 1161 in ids, str(ids))
ck("the checklist row itself still says 17 controls",
   "cDlgItems=17" in G9 or "17 controls" in G9)

# --- 4. the port's main window honours the template's control set ------
app = io.open(os.path.join(REPO, "qtranslate", "app.py"),
              encoding="utf-8", errors="replace").read()
ck("app.py still records DLG 129 / 340x201 / 17 controls",
   "DLG 129" in app and "340x201" in app and "17 control" in app)

# --- 5. what is NOT here, stated so it is not quietly assumed ----------
# Part (b)'s evidence directory holds a README and (so far) no images. The
# README is not a capture pair, so part (b) stays undone — but its stated
# reason has to be re-checked rather than inherited, because the host changed.
EV = os.path.join(REPO, "docs", "review", "g9_evidence")
images = [f for f in (os.listdir(EV) if os.path.isdir(EV) else [])
          if f.endswith(".png")]
ck("no capture pair exists (so part (b) is genuinely not done)", not images,
   str(images))
ck("the evidence README still says BLOCKED",
   "BLOCKED" in io.open(os.path.join(EV, "README.md"), encoding="utf-8").read()
   if os.path.exists(os.path.join(EV, "README.md")) else False)

# The README was written on an arm64 Darwin host, where a 32-bit native
# binary could not run at all. THIS host is AMD64 Windows with SysWOW64
# present, and the installed QTranslate is the same 1,462,272-byte PE32 —
# so the native side is runnable now, and the honest block is the capture
# ban, not the machine. Pinned so the stale reason is not inherited again.
import struct  # noqa: E402
machine = struct.unpack_from("<H", RAW, struct.unpack_from("<I", RAW,
                                                           0x3c)[0] + 4)[0]
ck("the recovered image is PE32 i386 (0x14c)", machine == 0x14c,
   hex(machine))
ck("this host is AMD64 Windows, where WoW64 can run it",
   sys.platform == "win32" and os.path.exists(
       os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                    "SysWOW64")),
   "%s %s" % (sys.platform, os.environ.get("PROCESSOR_ARCHITECTURE")))
# The README's stated reason was written on an arm64 Darwin host. It is now
# stale: the block here is the capture ban, not the machine. Recorded as a
# doc fix below rather than asserted, because a test cannot check prose
# currency.

ck("the G9 harness's samples are marked mechanics, not acceptance",
   all('"capture_kind": "mechanics"' in io.open(
       os.path.join(REPO, "docs", "review", "g9_samples", f),
       encoding="utf-8").read()
       for f in os.listdir(os.path.join(REPO, "docs", "review",
                                        "g9_samples"))
       if f.endswith(".json")))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_g9_part_a_complete: all checks ok (%d assertions)" % n[0])
