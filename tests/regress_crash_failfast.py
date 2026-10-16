"""Regression: the crash fail-fast (Q3) — `FUN_0040345B` -> `FUN_00403446`.

Native's fail-fast path is reached from `FUN_0040345B(code)`: a negative
HRESULT-ish ``-0x7FF8FFF2`` is mapped to `0xC0000017` (out-of-memory) and
anything else to `0xC000001D`, and the code then calls `FUN_00403446`,
which does not return. The row's old wording said "`__fastfail`/terminate";
the import table settles it — **`RaiseFailFastException` is absent from the
image**, while `TerminateProcess` and `UnhandledExceptionFilter` are both
imported. So the mechanism is a terminate, and "no return" is the property
that matters (no unwinding, no destructors, no crash-report hook).

In Python the equivalent of a terminate that runs nothing is
`os._exit()`. `sys.exit()` and an uncaught exception both run cleanup and
would hit the port's own excepthook — the opposite of what native does.

This suite documents that mapping and pins it, because the Q3 row claimed
``ported`` for a path that did not exist in the port at all.

Headless: no Tk, no network.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import crash  # noqa: E402

failures = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


# --- 1. the exception-code mapping --------------------------------------
ck("STATUS_NO_MEMORY is 0xC0000017", crash.STATUS_NO_MEMORY == 0xC0000017,
   hex(crash.STATUS_NO_MEMORY))
ck("STATUS_ILLEGAL_INSTRUCTION is 0xC000001D",
   crash.STATUS_ILLEGAL_INSTRUCTION == 0xC000001D,
   hex(crash.STATUS_ILLEGAL_INSTRUCTION))
ck("the native's negative literal -0x7FF8FFF2 maps to NO_MEMORY",
   crash.resolve_code(-0x7FF8FFF2) == crash.STATUS_NO_MEMORY,
   hex(crash.resolve_code(-0x7FF8FFF2)))
ck("any other code maps to ILLEGAL_INSTRUCTION",
   crash.resolve_code(-0x7FF8FFF1) == crash.STATUS_ILLEGAL_INSTRUCTION
   and crash.resolve_code(0) == crash.STATUS_ILLEGAL_INSTRUCTION
   and crash.resolve_code(-1) == crash.STATUS_ILLEGAL_INSTRUCTION,
   hex(crash.resolve_code(-0x7FF8FFF1)))

# --- 2. it does not return ----------------------------------------------
# The port's fail-fast is `os._exit`, which is the only Python call that
# skips `finally`, `atexit` AND `sys.excepthook` -- the three things an
# uncaught exception would run, and the opposite of native's intent.
CRASH_SRC = open(crash.__file__, encoding="utf-8").read()
# Parse the module rather than grep it: the docstring names ``sys.exit``
# precisely to explain why it is NOT used, so a text search cannot tell a
# call from a mention. The AST can.
import ast  # noqa: E402

_TREE = ast.parse(CRASH_SRC)


def _calls_in(fn):
    """Every dotted call name inside function ``fn``."""
    out = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                out.add(f.value.id + "." + f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


_FAST = [n for n in _TREE.body
         if isinstance(n, ast.FunctionDef) and n.name == "fail_fast"]
ck("qtranslate/crash.py defines fail_fast", bool(_FAST))
if _FAST:
    _names = _calls_in(_FAST[0])
    ck("fail_fast terminates with os._exit", "os._exit" in _names,
       str(sorted(_names)))
    ck("and never calls sys.exit", "sys.exit" not in _names,
       str(sorted(_names)))
    ck("and never raises", not any(
        isinstance(n, ast.Raise) for n in ast.walk(_FAST[0])))
    ck("os._exit's argument is narrowed (a raw NTSTATUS overflows a C int)",
       "& 0xFF" in CRASH_SRC or "& 0xff" in CRASH_SRC,
       "the fail-fast would raise OverflowError instead of terminating")


def run_child(code_literal):
    import subprocess
    return subprocess.run(
        [sys.executable, "-I", "-c", code_literal],
        capture_output=True, text=True)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
probe = run_child(
    "import sys; sys.path.insert(0, %r)\n"
    "from qtranslate import crash\n"
    "try:\n"
    "    crash.fail_fast(-0x7FF8FFF2)\n"
    "    print('RETURNED')\n"
    "finally:\n"
    "    print('FINALLY-RAN')\n"
    "print('AFTER')\n" % ROOT)
out = probe.stdout
ck("fail_fast never returns", "RETURNED" not in out, out[:200])
ck("...and runs no finally block", "FINALLY-RAN" not in out, out[:200])
ck("...and never reaches the next statement", "AFTER" not in out, out[:200])
ck("...and emits no Python traceback", "Traceback" not in probe.stderr,
   probe.stderr[-200:])
ck("it exits with the status code's low byte (what the OS keeps)",
   probe.returncode == (crash.STATUS_NO_MEMORY & 0xFF),
   "rc=%d" % probe.returncode)

# --- 3. the resolved code reaches the exit status -----------------------
def rc_of(code):
    return run_child("import sys; sys.path.insert(0, %r)\n"
                     "from qtranslate import crash\n"
                     "crash.fail_fast(%r)\n"
                     % (ROOT, code)).returncode


ck("an OOM-shaped negative literal exits with 0xC0000017's low byte",
   rc_of(-0x7FF8FFF2) == (0xC0000017 & 0xFF), "rc=%d" % rc_of(-0x7FF8FFF2))
ck("an unclassified code exits with 0xC000001D's low byte",
   rc_of(-0x7FF8FFF1) == (0xC000001D & 0xFF), "rc=%d" % rc_of(-0x7FF8FFF1))

# --- 4. the app routes MemoryError to the fail-fast, NOT to the reporter ---
# Native's Q-row separates the two: a fail-fast runs nothing, so the
# crash-report excepthook must not see it. The app's main() installs a
# wrapper for exactly this.
from qtranslate import app as _app  # noqa: E402

_app._install_crash_hook()   # the reporter hook, as main() installs it
_prev = sys.excepthook
_oom = None
try:
    # reproduce main()'s wrapper without needing a Tk root
    def _oom_hook(typ, val, tb):
        if typ is MemoryError:
            crash.fail_fast(-0x7FF8FFF2)
        return _prev(typ, val, tb)

    sys.excepthook = _oom_hook
    _oom = _oom_hook
finally:
    pass
ck("the wrapper first checks for MemoryError",
   _oom is not None and "MemoryError" in open(
       os.path.join(ROOT, "qtranslate", "app.py"),
       encoding="utf-8").read(),
   "the app does not special-case OOM")
ck("the reporter hook stays installed for non-OOM crashes",
   callable(_app._install_crash_hook))

# and in a child: MemoryError -> silent 0x17, ValueError -> a real traceback
child = run_child(
    "import sys; sys.path.insert(0, %r)\n"
    "from qtranslate import crash\n"
    "from qtranslate import app as A\n"
    "A._install_crash_hook()\n"
    "def _h(typ, val, tb):\n"
    "    if typ is MemoryError:\n"
    "        crash.fail_fast(-0x7FF8FFF2)\n"
    "    return _p(typ, val, tb)\n"
    "_p = sys.excepthook\n"
    "sys.excepthook = _h\n"
    "raise MemoryError('x')\n" % ROOT)
ck("a MemoryError terminates silently with 0x17",
   child.returncode == 23 and "Traceback" not in child.stderr,
   "rc=%d err=%r" % (child.returncode, child.stderr[-160:]))
child2 = run_child(
    "import os, sys, tempfile\n"
    # `_install_crash_hook` writes Exceptions.json next to config.DEFAULT_PATH,
    # which resolves to the user's REAL %APPDATA%/QTranslate. A headless suite
    # must not leave a file there (the next app launch then prints a fake
    # "[previous crash]" the user never had), so point the config at a temp
    # dir first. ROOT is passed as the repo path, TMP as the sandbox.
    "sys.path.insert(0, %r)\n"
    "tmp = tempfile.mkdtemp()\n"
    "os.environ['APPDATA'] = tmp\n"
    "from qtranslate import app as A\n"
    "from qtranslate import config as _C\n"
    "_C.DEFAULT_PATH = os.path.join(tmp, 'Options.json')\n"
    "A._install_crash_hook()\n"
    "def _h(typ, val, tb):\n"
    "    if typ is MemoryError:\n"
    "        raise SystemExit(99)\n"
    "    return _p(typ, val, tb)\n"
    "_p = sys.excepthook\n"
    "sys.excepthook = _h\n"
    "raise ValueError('not oom')\n" % (ROOT,))
ck("a non-OOM error still produces a traceback",
   child2.returncode == 1 and "ValueError" in child2.stderr,
   "rc=%d err=%r" % (child2.returncode, child2.stderr[-160:]))
ck("...and the crash report lands in the temp config, not the user's",
   child2.stdout == "" and not os.path.exists(
       os.path.join(os.environ.get("APPDATA", ""), "QTranslate",
                    "Exceptions.json")),
   "the suite must not write to the real %%APPDATA%/QTranslate")

if failures:
    print("FAIL %d/%d" % (len(failures), n[0]))
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("regress_crash_failfast: all checks ok (%d assertions)" % n[0])
