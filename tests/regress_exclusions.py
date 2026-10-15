"""Pin the foreground-exclusion matcher (rows B/C: FUN_004631DE + FUN_004470B7).

Native skips capture when the foreground window class/process matches the
Exceptions list: case-insensitive exact (wcsicmp), empty side matches
anything. DisabledMode=true → Disabled is a blocklist; false → Enabled
is an allowlist (everything else blocked).

Offline: `_fg_class_and_exe` is not called (lists passed directly);
`_live_lists` is monkey-patched for the mode tests.
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


from qtranslate import exclusions as X

# --- wcsicmp matcher: case-insensitive exact ---------------------------
D = [("", "SysListView32"), ("mstsc.exe", "")]
ck("class match is case-insensitive",
   X.is_excluded("syslistview32", "x.exe", D) is True)
ck("class match exact only (no substring)",
   X.is_excluded("SysListView32X", "x.exe", D) is False)
ck("process match works", X.is_excluded("Any", "MSTSC.EXE", D) is True)
ck("process match is exact (no substring)",
   X.is_excluded("Any", "mstsc.exe.bak", D) is False)
ck("empty class side matches any class",
   X.is_excluded("Whatever", "mstsc.exe", D) is True)
ck("empty process side matches any process",
   X.is_excluded("SysListView32", "anything", D) is True)
ck("no match -> not excluded",
   X.is_excluded("Edit", "notepad.exe", D) is False)
ck("empty list -> nothing excluded",
   X.is_excluded("Anything", "x.exe", []) is False)

# --- DisabledMode: blocklist vs allowlist ------------------------------
_orig_live = X._live_lists
_orig_fg = X._fg_class_and_exe
X._fg_class_and_exe = lambda: ("Edit", "notepad.exe")

# blocklist mode (default): only listed entries blocked
X._live_lists = lambda: ([("", "Edit")], [], True)
try:
    ck("blocklist mode blocks a listed class",
       X.foreground_excluded() is True)
finally:
    X._live_lists = _orig_live

# allowlist mode: blocked unless explicitly enabled
X._live_lists = lambda: ([], [("", "Edit")], False)
try:
    ck("allowlist mode allows an enabled class",
       X.foreground_excluded() is False)
finally:
    X._live_lists = _orig_live

X._live_lists = lambda: ([], [("other.exe", "")], False)
try:
    ck("allowlist mode blocks anything not enabled",
       X.foreground_excluded() is True)
finally:
    X._live_lists = _orig_live

# allowlist mode with an empty allowlist: nothing blocked (fail-open)
X._live_lists = lambda: ([], [], False)
try:
    ck("allowlist mode with empty list does not block",
       X.foreground_excluded() is False)
finally:
    X._live_lists = _orig_live
    X._fg_class_and_exe = _orig_fg

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_exclusions: all checks ok (%d assertions)" % n[0])
