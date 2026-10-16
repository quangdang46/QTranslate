"""Self-test: prove docs_consistency.py detects drift, then trusts valid cites.

A checker that reports 0 findings is worthless if it cannot fail. This
writes temp copies of the docs with each kind of drift injected and
asserts the tool catches it; then it asserts the REAL corpus is clean.

Exit 0 = the tool detects everything it claims and the corpus passes.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "docs_consistency.py")
DOCS = os.path.join(REPO, "docs")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


def run_tool(cwd, repo=None):
    """Run the tool from ``cwd``; ``repo`` overrides where it resolves
    module/citation names (the tool derives that from its own location)."""
    env = dict(os.environ)
    if repo:
        env["QTRANSLATE_REPO"] = repo
    p = subprocess.run([sys.executable, "-I", "docs_consistency.py"],
                       cwd=cwd, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


# --- 1. the real corpus must be clean -----------------------------------
rc, out = run_tool(os.path.join(REPO, "tools"))
ck("the real corpus passes", rc == 0, out[:400])

# --- 2. drift in a scratch copy must be caught --------------------------
tmp = tempfile.mkdtemp(prefix="docsconst-")
try:
    tmp_tools = os.path.join(tmp, "tools")
    shutil.copytree(os.path.join(REPO, "tools"), tmp_tools)
    shutil.copytree(DOCS, os.path.join(tmp, "docs"))

    # NOTE: the tool resolves port/test names against REPO, which it derives
    # from its own file location -- so the scratch copy resolves against the
    # real repo and still finds real test names. Injecting a genuinely
    # nonexistent module therefore tests the detector.
    target = os.path.join(tmp, "docs", "CURRENT_STATE.md")
    TEXT = io.open(target, encoding="utf-8").read()
    before = TEXT

    # a dead test citation
    TEXT = before.replace("*string/structural* match",
                          "*string/structural* match\nSee "
                          "`tests/regress_DOES_NOT_EXIST.py` for details.")
    io.open(target, "w", encoding="utf-8").write(TEXT)
    rc, out = run_tool(tmp_tools)
    ck("a dead test citation is reported",
       "dead-test" in out and "regress_DOES_NOT_EXIST.py" in out, out[:300])

    # a dead port citation
    TEXT = before.replace("*string/structural* match",
                          "*string/structural* match\nSee "
                          "`qtranslate/does_not_exist.py:99` for details.")
    io.open(target, "w", encoding="utf-8").write(TEXT)
    rc, out = run_tool(tmp_tools)
    ck("a dead port citation is reported",
       "dead-port" in out and "does_not_exist.py" in out, out[:300])

    # a dead doc citation
    TEXT = before.replace("*string/structural* match",
                          "*string/structural* match\nSee "
                          "`docs/review/NOT_A_REAL_DOC.md` for details.")
    io.open(target, "w", encoding="utf-8").write(TEXT)
    rc, out = run_tool(tmp_tools)
    ck("a dead doc citation is reported",
       "dead-doc" in out and "NOT_A_REAL_DOC.md" in out, out[:300])

    # a stale suite count in a living doc
    TEXT = before.replace("*string/structural* match",
                          "*string/structural* match\nThe suite count is 3 "
                          "suites, all green.")
    io.open(target, "w", encoding="utf-8").write(TEXT)
    rc, out = run_tool(tmp_tools)
    ck("a stale suite count is reported",
       "stale-suite-count" in out and "3 suites" in out, out[:300])

    # and a VALID citation must not be flagged (no false positive)
    TEXT = before.replace(
        "*string/structural* match",
        "*string/structural* match\nThe verified suites are "
        "`tests/regress_screens.py` and `qtranslate/common.py:412` and "
        "`docs/NATIVE_ARCH.md`.")
    io.open(target, "w", encoding="utf-8").write(TEXT)
    rc, out = run_tool(tmp_tools)
    ck("valid citations are not flagged", rc == 0 and "0 findings" in out,
       out[:300])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_docs_consistency: all checks ok (%d assertions)" % n[0])
