"""Run every offline suite and report by EXIT CODE, not by grepping output.

`README.md` has warned about this for weeks: the regress suites print
`FAIL n/m` (no colon, and the number is at the END of the line), so a
`tail -1 | grep FAIL` sweep misses a suite that raised before reaching its
own summary. That is not hypothetical -- three stale known-answer vectors
lived in the suite this way, aborting with a traceback, while a grep-based
sweep reported everything green.

This is the check that would have caught them.

Scope: `tests/regress_*.py`, `tests/smoke_dict.py` and `tests/ui_match.py`.
The `live_*.py` suites hit real endpoints and are excluded (they are
optional/nightly per `docs/TEST_STRATEGY.md`, not a merge gate).

Exit codes: 0 = every suite exited 0; 1 = at least one failed; 2 = none
found / the tests directory is missing.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tests")

# The GUI suite builds a real Tk root; it runs wherever tkinter is
# importable, but it is reported separately because a headless host skips
# it rather than failing it.
GUI_SUITES = {"ui_match.py"}


def suites():
    out = sorted(glob.glob(os.path.join(TESTS, "regress_*.py")))
    for extra in ("smoke_dict.py", "ui_match.py"):
        p = os.path.join(TESTS, extra)
        if os.path.exists(p):
            out.append(p)
    return out


def main(argv):
    quiet = "--quiet" in argv
    want_json = "--json" in argv
    if not os.path.isdir(TESTS):
        print("no tests directory")
        return 2
    found = suites()
    if not found:
        print("no suites found")
        return 2

    results = []
    started = time.time()
    for path in found:
        name = os.path.basename(path)
        proc = subprocess.run([sys.executable, "-I", path], cwd=REPO,
                              capture_output=True, text=True)
        rc = proc.returncode
        tail = (proc.stdout.strip().splitlines() or [""])[-1]
        results.append({"suite": name, "rc": rc, "last": tail[:160]})

    failed = [r for r in results if r["rc"] != 0]
    took = time.time() - started

    if want_json:
        import json
        print(json.dumps({"total": len(results), "failed": len(failed),
                          "seconds": round(took, 1),
                          "results": results}, indent=2))
    elif not quiet:
        for r in results:
            mark = "ok  " if r["rc"] == 0 else "FAIL"
            gui = " (gui)" if r["suite"] in GUI_SUITES else ""
            print("%s %-46s%s%s" % (mark, r["suite"], gui,
                                    "" if r["rc"] == 0
                                    else "  rc=%d  %s" % (r["rc"], r["last"])))
        print("\n%d suites, %d failed, %.1fs" % (len(results), len(failed), took))
    else:
        print("%d suites, %d failed" % (len(results), len(failed)))

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
