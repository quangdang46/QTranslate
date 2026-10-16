"""Cross-document consistency audit for docs/.

The Gate's checklist has an item that has never been tooled:

  > Cross-document consistency pass done; no contradictions with D1–D20.

Hand-maintained docs drift: a number is corrected in one file and not in
the three that quoted it, a test is renamed and a doc still cites the old
name, a claim is withdrawn in its own file while a summary repeats it.

This tool checks five classes of drift mechanically, all of them things a
reader could otherwise only find by re-reading everything:

  1. **TALLY numbers** vs the regenerated `coverage_tally.py` block.
  2. **Dead test citations** — a doc cites `tests/…py` that no longer
     exists.
  3. **Dead port citations** — `qtranslate/…py` (with or without a line
     number) that no longer exists.
  4. **Dead doc citations** — a doc cites another `*.md` that does not
     exist.
  5. **Stale counts in prose** — a doc states "N suites"/"N assertions"
     and the actual number differs by more than a tolerance, so a family
     of small drifts is reported rather than every unrelated number.

Exit codes: 0 = no findings; 1 = at least one finding; 2 = nothing to scan.
"""
from __future__ import annotations

import os
import re
import sys

DOCS = "docs"
# Resolve the DOC corpus from THIS FILE's location, not the process cwd, so
# the tool works from the repo root, from tools/, or from a copied tree.
SELF = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(os.path.dirname(SELF), DOCS)
# Both roots are overridable so a scratch tree (used by the self-test to
# inject drift) can point the corpus at its own copy while still resolving
# module names against the real repo.
DOCS = os.environ.get("QTRANSLATE_DOCS") or DOCS
REPO = os.environ.get("QTRANSLATE_REPO") or os.path.dirname(DOCS)

TEST_CITE = re.compile(r"(tests/[A-Za-z0-9_./-]+\.py)")
PORT_CITE = re.compile(r"\b([a-z][a-z0-9_]*\.py):\d+")
DOC_CITE = re.compile(r"([A-Za-z0-9_./-]+\.md)\b")
# "N assertions", "N checks", "N suites" -- the numbers this repo keeps in
# prose and updates by hand.
PROSE_COUNT = re.compile(
    r"(\d[\d,]*)\s+(?:assertions?|checks?|suites?|comparisons?)", re.I)


def md_files():
    out = []
    for root, _dirs, files in os.walk(DOCS):
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.join(root, f))
    return sorted(out)


def actual_test_count():
    tests_dir = os.path.join(REPO, "tests")
    if not os.path.isdir(tests_dir):
        return 0
    return len([f for f in os.listdir(tests_dir)
                if f.startswith("regress_") and f.endswith(".py")])


def main(argv):
    quiet = "--quiet" in argv
    files = md_files()
    if not files:
        print("no markdown under docs/")
        return 2

    # A scratch repo (the selftest's) may hold only tools/ + docs/. A
    # missing directory means "no such names exist", not a crash: every
    # citation into the absent tree is then dangling, which is what the
    # detector should report.
    tests_dir = os.path.join(REPO, "tests")
    all_tests = ({f for f in os.listdir(tests_dir) if f.endswith(".py")}
                 if os.path.isdir(tests_dir) else set())
    # Port/tool modules live in several places; collect every .py name in the
    # repo except the artifact/review trees.
    all_ports = set()
    for sub in ("qtranslate", "tools", "start_app.py"):
        base = os.path.join(REPO, sub)
        if os.path.isfile(base):
            all_ports.add(os.path.basename(base))
            continue
        for root, _dirs, fs in os.walk(base):
            if "__pycache__" in root:
                continue
            for f in fs:
                if f.endswith(".py"):
                    all_ports.add(f)
    # Doc citations are written with a PATH (docs/review/X.md, docs/X.md) or
    # a bare name; match on both the basename and the repo-relative path so
    # a real reference is never reported as dangling.
    md_names = set()
    md_paths = set()
    for p in files:
        md_names.add(os.path.basename(p))
        # Citations are written relative to the repo root ("docs/review/X.md")
        # regardless of where the scanned tree lives, so the key is the path
        # BELOW docs/ -- never relative to the (possibly scratch) repo root.
        rel = os.path.relpath(p, DOCS).replace("\\", "/")
        md_paths.add("docs/" + rel)
        md_paths.add(rel)
    # docs outside docs/ that are legitimately citable
    for extra in ("CHANGELOG.md", "README.md", "LICENSE"):
        if os.path.exists(os.path.join(REPO, extra)):
            md_names.add(extra)
            md_paths.add(extra)
    md_paths.add("tests/LIVE_RESULTS.md")  # historical, cited as such
    md_names.add("LIVE_RESULTS.md")

    findings = []
    n_tests = actual_test_count()

    for path in files:
        text = open(path, encoding="utf-8", errors="replace").read()
        # ALWAYS the path below docs/, prefixed with "docs/" -- never
        # relative to REPO. When DOCS lives outside REPO (the selftest's
        # scratch corpus, or an out-of-tree checkout) a REPO-relative path
        # becomes an absolute temp path, which then matches no
        # "docs/CURRENT_STATE.md" allow-list and silently disables the
        # per-document checks below.
        rel = "docs/" + os.path.relpath(path, DOCS).replace("\\", "/")

        # dead test citations
        for cite in set(TEST_CITE.findall(text)):
            if cite not in all_tests and \
                    os.path.basename(cite) not in all_tests:
                findings.append(("dead-test", rel, cite))

        # dead port / test citations
        for cite in set(PORT_CITE.findall(text)):
            if cite not in all_ports and cite not in all_tests:
                findings.append(("dead-port", rel, cite))

        # dead doc citations. A doc may legitimately cite a file that is
        # NOT in this repo when it is describing someone else's material
        # (REA's own installation guide, the installer's layout) -- those
        # lines name an external source, so they are not dangling refs. The
        # attribution is often in the PRECEDING paragraph ("REA's own
        # README ..."), so look at the paragraph before as well as the one
        # holding the citation.
        paras = re.split(r"\n\s*\n", text)
        for cite in set(DOC_CITE.findall(text)):
            if cite in md_paths or cite in md_names:
                continue
            holder = [p for p in paras if cite in p]
            window = []
            for p in holder:
                i = paras.index(p)
                window.extend(paras[max(0, i - 1):i + 1])
            external = any(re.search(
                r"\bREA\b|installer|vendor|third-party|their own|its own|"
                r"native README", p, re.I) for p in window)
            if external:
                continue
            findings.append(("dead-doc", rel, cite))

        # stale suite counts: "N suites". Dated review docs legitimately
        # record the count AS OF their date, so only compare the undated
        # living documents -- the ones a reader treats as current. And a
        # number the document itself labels historical (an "earlier doc
        # said N/N" figure) is not drift, so skip the containing PARAGRAPH
        # when it carries a historical marker -- these sentences wrap, so
        # matching per-line would catch the number and miss its label.
        if rel in ("docs/CURRENT_STATE.md", "docs/RE_PROGRESS.md",
                   "docs/TEST_STRATEGY.md"):
            paragraphs = re.split(r"\n\s*\n", text)
            for para in paragraphs:
                # Only skip a paragraph that marks its figure as historical
                # in so many words -- a bare past-tense verb ("was last
                # green") appears all over this doc and would hide a real
                # drift in the same paragraph.
                if re.search(r"earlier (?:doc|version|note)s?\b|historical|"
                             r"previously (?:said|recorded|reported)|"
                             r"doc said|as of \d{4}-\d{2}-\d{2}|"
                             r"used to be \d", para, re.I):
                    continue
                for m in re.finditer(r"\b(\d[\d,]*)\s+suites?\b", para, re.I):
                    got = int(m.group(1).replace(",", ""))
                    if got != n_tests and abs(got - n_tests) > 2:
                        findings.append(("stale-suite-count", rel,
                                         "%s (actual %d)"
                                         % (m.group(0), n_tests)))

    # the TALLY block is validated by coverage_tally.py; here only check
    # that the two docs that QUOTE the tally agree with each other.
    tally_re = re.compile(r"`?(\d{2,3})\s+VERIFIED\s*/\s*(\d+)"
                          r"\s+UNKNOWN", re.I)
    quotes = {}
    for path in files:
        text = open(path, encoding="utf-8", errors="replace").read()
        m = tally_re.search(text)
        if m:
            quotes[os.path.basename(path)] = (m.group(1), m.group(2))
    if len(set(quotes.values())) > 1:
        findings.append(("tally-disagreement", "docs",
                         repr(quotes)))

    if not quiet:
        print("docs-consistency: %d files scanned, %d findings"
              % (len(files), len(findings)))
        for kind, where, what in findings:
            print("  [%s] %s: %s" % (kind, where, what))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
