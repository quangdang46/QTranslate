"""Pin the once-crash-reporter (row G "Crash once-reporter").

Native `FUN_00462C03` (decompiled 2026-10-15): if `Exceptions.json`
exists, parse it, process the entries (`FUN_00462A82`), then
`DeleteFileW` it — so a crash is reported exactly ONCE, on the next
launch, and the file is gone afterwards. The port mirrors this:
`_consume_crash_reports` reads type==2 entries, prints them, removes the
file; `_install_crash_hook` appends a type==2 entry on an unhandled
exception.

Offline: writes/reads a temp Exceptions.json next to a patched
config.DEFAULT_PATH; no window, no real crash.
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import config as C
import qtranslate.app as A

_tmp = tempfile.mkdtemp(prefix="qt_crash_")
_orig_path = C.DEFAULT_PATH
C.DEFAULT_PATH = os.path.join(_tmp, "Options.json")
_exc = os.path.join(_tmp, "Exceptions.json")


def _capture(fn):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        fn()
    finally:
        sys.stdout = old
    return buf.getvalue()


# --- no file: nothing happens, no crash ---------------------------------
ck("no Exceptions.json is a no-op",
   _capture(A._consume_crash_reports) == "" and not os.path.exists(_exc))

# --- a type==2 entry is reported once, then the file is deleted ---------
with open(_exc, "w", encoding="utf-8") as f:
    json.dump([{"type": 2, "path": "boom"}], f)
out = _capture(A._consume_crash_reports)
ck("type==2 entry is reported", "previous crash" in out, repr(out))
ck("Exceptions.json is deleted after reporting (native DeleteFileW)",
   not os.path.exists(_exc))

# --- second run: already consumed, nothing to report --------------------
out2 = _capture(A._consume_crash_reports)
ck("second run reports nothing (reported exactly once)", out2 == "",
   repr(out2))

# --- non-type-2 entries are not reported --------------------------------
with open(_exc, "w", encoding="utf-8") as f:
    json.dump([{"type": 1, "path": "x"}], f)
out3 = _capture(A._consume_crash_reports)
ck("type!=2 entries are silent", out3 == "", repr(out3))
ck("file is still deleted when only non-type-2 entries exist",
   not os.path.exists(_exc))

# --- the hook appends a type==2 entry -----------------------------------
A._install_crash_hook()
_err = io.StringIO()
_old_err = sys.stderr
sys.stderr = _err  # __excepthook__ writes the traceback here; keep it quiet
try:
    raise ValueError("simulated crash")
except ValueError:
    sys.excepthook(*sys.exc_info())
finally:
    sys.stderr = _old_err
ck("crash hook writes an entry", os.path.exists(_exc))
if os.path.exists(_exc):
    with open(_exc, encoding="utf-8") as f:
        ents = json.load(f)
    ck("appended entry is type==2", ents and ents[-1].get("type") == 2,
       str(ents)[:120])
    ck("appended entry carries the traceback",
       "simulated crash" in (ents[-1].get("path") or ""),
       str(ents[-1].get("path"))[:80])

C.DEFAULT_PATH = _orig_path
import shutil
shutil.rmtree(_tmp, ignore_errors=True)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_crash_reporter: all checks ok (%d assertions)" % n[0])
