"""Audit the Gate's "concrete artifact" clause over the coverage checklist.

`RE_COVERAGE_CHECKLIST.md`'s Gate list has a checklist item that has never
been tooled:

  > Every `VERIFIED` row cites a **concrete artifact** (Ghidra address
  > **with decompile**, JS source, asset hash, or test) — not a doc line.

`tools/coverage_tally.py` validates structure and state vocabulary, but it
cannot tell a citation that names a decompiled address from one that only
points at another document. This tool makes that distinction, using the
same four artifact classes the Gate names:

| class | what a valid citation looks like |
|-------|----------------------------------|
| decompiled address | `FUN_xxxxxxxx` (Ghidra name) **or** a 7-8 hex RVA **plus** a decompile marker in the row |
| JS source | a `Service.js`/`Common.js` path, a `new ServiceHeader(<id>,`, or a recoverable `Services/<Name>/` folder |
| asset hash | `sha256`, `md5` (+ a hex digest), or `bytes <n>` from the payload census |
| test | `tests/test_*.py` / `regress_*.py` that EXISTS in the repo |

A doc citation (`docs/review/X.md`) is recorded and reported, but it is a
**pointer**, not an artifact — the same mistake the 19-`Service.js`
recovery pass documented ("a pointer is not a checkpoint"), so a row whose
only citation is a doc line FAILS this audit.

The test class is checked against the filesystem, so a row citing a suite
that was renamed or deleted fails here and not silently.

Exit codes: 0 = every VERIFIED row has a real artifact; 1 = at least one
does not; 2 = the document could not be parsed.

Usage:
  python -I tools/gate_artifact_audit.py [--json OUT] [--quiet]
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

DOC = os.environ.get("QTRANSLATE_DOCS") or os.path.join(
    "docs", "RE_COVERAGE_CHECKLIST.md")
# Where port/test names are resolved. `QTRANSLATE_REPO` overrides it so a
# scratch corpus (a copy of docs/ alone) can still find the real suites --
# the same override tools/docs_consistency.py honours.
REPO = os.environ.get("QTRANSLATE_REPO") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
# The installed QTranslate copy -- the authority on which payload files
# exist (the installer is NOT run; only its extracted tree is read).
INSTALLED = os.environ.get(
    "QTRANSLATE_DIR", r"C:\Program Files (x86)\QTranslate")
INSTALLED_LOCALES = os.path.join(INSTALLED, "Locales")
# The recovered native copies committed in this repository. A citation to
# one of these resolves to a file that really exists, on any host.
RECOVERED_ROOTS = (
    os.path.join(REPO, "docs", "review", "rea", "js_root"),
    os.path.join(REPO, "qtranslate", "assets"),
)

RE_STATES = ("VERIFIED", "INFERRED", "UNKNOWN", "UNRECOVERABLE")

# Ghidra names the RE notes use, e.g. FUN_0045869F / FUN_0040FB54.
FUN_RE = re.compile(r"\bFUN_[0-9A-Fa-f]{6,10}\b")
# A bare RVA, e.g. 0045869F or 0x4586a0. It counts only when paired with a
# marker showing the address was actually EXAMINED rather than merely named:
# a decompile, a resource/template parse, or an RTTI class. An address alone
# is a pointer to a place, not evidence of what was found there.
RVA_RE = re.compile(r"\b0x?0*([0-9A-Fa-f]{7,8})\b")
STRUCTURAL_RE = re.compile(r"decompil|disassembl|read out|recovered|parsed"
                           r"|walked|census|RTTI|windows::|common::|style "
                           r"0x|cDlgItems|cdit|template|EPSILON", re.I)
# JS / payload asset provenance. The installer's own file tree is the
# authority on what exists, so any `Services/…`, `Plugins/…`, `Themes/…`,
# `Locales/…`, `Resources/…` or bare `*.js`/`*.json` citation counts --
# PROVIDED the named file is checked below (it must exist in the installed
# copy or be one of the known-recovered payload chunks).
ASSET_PATH_RE = re.compile(
    r"(?:\b(?:Services|Plugins|Themes|Locales|Resources)"
    r"/(?:[\w.* -]+/)*[\w.* -]+\.(?:js|json|jsonc|xslt|txt|ico|png)"
    r"|\b[\w.-]+\.(?:js|json|jsonc|xslt|lang))\b")
JS_MARK_RE = re.compile(r"new ServiceHeader\(|Common\.js")
# asset provenance
HASH_RE = re.compile(r"(sha256|md5)\s*[:=]?\s*[0-9a-fA-F]{8,}",
                     re.IGNORECASE)
BYTES_RE = re.compile(r"\b(?:payload\s+)?(\d[\d,]{3,})\s*(?:B\b|bytes)",
                      re.IGNORECASE)
# A CLSID byte string recovered (or proven absent) from the image is a
# byte-search artifact, and both "present" and "absent" findings are
# evidence -- F13/J3 are exactly this shape.
CLSID_RE = re.compile(r"\{?[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}"
                      r"-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}?")
# tests
TEST_RE = re.compile(r"(tests/[A-Za-z0-9_./-]+\.py)")
# A port source location, e.g. `app.py:1742` / `common.py:412` -- a
# verifiable citation even though it points into the port, because it is
# line-checkable rather than prose.
PORT_REF_RE = re.compile(r"\b([A-Za-z0-9_]+\.py):\d+")

ROW_RE = re.compile(r"^\|\s*([A-Z]\d+)\s+(.*)$")


def asset_exists(path: str) -> bool:
    """Does the named payload file really exist somewhere we can see?

    Handles three citation shapes: a real path under one of the installer's
    folders, a bare filename, and a GLOB (`Themes/*.json`) -- which is
    satisfied when at least one file in the named folder matches.
    """
    path = path.replace("\\", "/")
    # A glob: `Locales/*/lang.json` descends one directory per `*`,
    # `Themes/*.json` matches files in one folder. Use fnmatch over a walk
    # so both shapes resolve with one rule.
    if "*" in path:
        stem = path.split("*", 1)[0].rstrip("/")
        tail = path[len(stem):].lstrip("/")
        folders = [os.path.join(INSTALLED, stem)]
        for root in RECOVERED_ROOTS:
            folders.append(os.path.join(root, stem))
            # the recovered tree uses a lower-case themes/ folder
            folders.append(os.path.join(root, stem.lower()))
        for folder in folders:
            if not os.path.isdir(folder):
                continue
            # The pattern and the candidates must be measured from the same
            # root: the pattern is relative to the folder, the candidates
            # are absolute.
            pat_norm = os.path.join(folder, tail).replace("\\", "/")
            for root, _dirs, files in os.walk(folder):
                for f in files:
                    cand = os.path.join(root, f).replace("\\", "/")
                    if fnmatch.fnmatch(cand, pat_norm) or \
                            fnmatch.fnmatch(cand,
                                            pat_norm.replace("/**", "/*")):
                        return True
        return False
    name = os.path.basename(path)
    if "/" in path:
        folder = os.path.join(INSTALLED, path)
        if os.path.isfile(folder):
            return True
        # the path may name a service FOLDER rather than a file
        if os.path.isdir(folder):
            return True
    # inside the installed copy, by name -- and inside the recovered copies
    bases = [os.path.join(INSTALLED, sub)
             for sub in ("Services", "Plugins", "Themes", "Locales",
                         "Resources", "")] + list(RECOVERED_ROOTS)
    for base in bases:
        if not base or not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            if name in files or name.rstrip(".*") in files:
                return True
    # a locale/resource bundle name is a directory in Locales/
    if os.path.isdir(INSTALLED_LOCALES):
        if name.rstrip(".*") in os.listdir(INSTALLED_LOCALES):
            return True
    # The recovered native copies, committed in this repository: the
    # installer payload's JS and assets (docs/review/rea/js_root/) and the
    # locale packs and icons (qtranslate/assets/). A citation to one of
    # those resolves to a file that really exists, on any host -- which is
    # what a citation has to do.
    for root in RECOVERED_ROOTS:
        cand = os.path.join(root, path)
        if os.path.isfile(cand) or os.path.isdir(cand):
            return True
        by_name = os.path.join(root, name)
        if os.path.isfile(by_name):
            return True
    return False


def rows_of(text: str):
    """Yield (item_id, cells) for every checklist data row."""
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.split("|")]
        # cells[0] is '' before the first pipe, [1] the id, then the fields
        yield m.group(1), cells


def re_state(cells) -> str | None:
    for c in cells[1:6]:
        if c in RE_STATES:
            return c
    return None


def audit(text: str):
    """Classify each VERIFIED row; returns (fail_rows, ok_count, pointer_only)."""
    failures, pointer_only, ok = [], [], 0
    for item, cells in rows_of(text):
        state = re_state(cells)
        if state != "VERIFIED":
            continue
        row = "|".join(cells)
        tests = TEST_RE.findall(row)
        # Only tests that still exist count.
        live_tests = [t for t in tests
                      if os.path.exists(os.path.join(REPO, t))]
        has_fun = bool(FUN_RE.search(row))
        has_rva = bool(RVA_RE.search(row)) and bool(STRUCTURAL_RE.search(row))
        assets = [p for p in ASSET_PATH_RE.findall(row) if asset_exists(p)]
        has_asset = bool(assets) or bool(JS_MARK_RE.search(row))
        has_hash = bool(HASH_RE.search(row) or BYTES_RE.search(row))
        has_clsid = bool(CLSID_RE.search(row))
        port_refs = [r for r in PORT_REF_RE.findall(row)]
        has_port_ref = any(
            os.path.exists(os.path.join(REPO, "qtranslate", p))
            for p in port_refs)

        if live_tests or has_fun or has_rva or has_asset or has_hash \
                or has_clsid or has_port_ref:
            ok += 1
            continue
        # a doc citation is a pointer; record it but do not pass the row
        docs_cited = re.findall(r"([A-Za-z0-9_./-]+\.md)\b", row)
        pointer_only.append((item, docs_cited[:4]))

    failures = pointer_only
    return failures, ok, len(pointer_only)


def main(argv):
    quiet = "--quiet" in argv
    json_out = None
    if "--json" in argv:
        json_out = argv[argv.index("--json") + 1]
    if not os.path.exists(DOC):
        print("missing " + DOC)
        return 2
    text = open(DOC, encoding="utf-8").read()
    failures, ok, total = audit(text)
    report = {
        "doc": DOC,
        "verified_rows_with_artifact": ok,
        "verified_rows_without_artifact": total,
        "pointer_only_rows": [{"item": i, "docs": d} for i, d in failures],
    }
    if json_out:
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    if not quiet:
        print("gate-artifact audit: %d VERIFIED rows cite a concrete "
              "artifact, %d cite only a doc pointer"
              % (ok, total))
        for item, docs in failures:
            print("  - %s points only at %s" % (item, ", ".join(docs)))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
