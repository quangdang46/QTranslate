"""Teach the gate-artifact audit about the recovered native copies.

19 VERIFIED rows cite a native asset -- `Services/<Name>/Service.js`,
`Themes/*.json` -- and the audit only looked for those in a *Windows
install*, which does not exist on any other host. The same files are now
committed in this repository (the recovered JS in `docs/review/rea/js_root/`,
the locale packs and the icons in `qtranslate/assets/`), so the audit can
resolve a citation against a file that really exists, anywhere.

Also: the H1 row cited "the dictionary services are the `Service.js` set
verified in group E" -- a cross-reference, not an artifact. It now names the
committed files.
"""

from __future__ import annotations

import sys
from pathlib import Path

EDITS: list[tuple[Path, str, str]] = []

EDITS.append((
    Path("tools/gate_artifact_audit.py"),
    '''    # a locale/resource bundle name is a directory in Locales/
    if os.path.isdir(INSTALLED_LOCALES):
        if name.rstrip(".*") in os.listdir(INSTALLED_LOCALES):
            return True
    return False
''',
    '''    # a locale/resource bundle name is a directory in Locales/
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
'''))

EDITS.append((
    Path("tools/gate_artifact_audit.py"),
    '''    if "*" in path:
        stem = path.split("*", 1)[0].rstrip("/")
        folder = os.path.join(INSTALLED, stem)
        if not os.path.isdir(folder):
            return False
        pattern = os.path.join(folder, path[len(stem):].lstrip("/"))
        pat_norm = pattern.replace("\\\\", "/")
        for root, _dirs, files in os.walk(folder):
            for f in files:
                cand = os.path.join(root, f).replace("\\\\", "/")
                if fnmatch.fnmatch(cand, pat_norm) or \\
                        fnmatch.fnmatch(cand, pat_norm.replace("/**", "/*")):
                    return True
        return False
''',
    '''    if "*" in path:
        stem = path.split("*", 1)[0].rstrip("/")
        pattern = os.path.join(stem, path[len(stem):].lstrip("/"))
        pat_norm = pattern.replace("\\\\", "/")
        for folder in [os.path.join(INSTALLED, stem)] + [
                os.path.join(root, stem) for root in RECOVERED_ROOTS]:
            if not os.path.isdir(folder):
                continue
            for root, _dirs, files in os.walk(folder):
                for f in files:
                    cand = os.path.join(root, f).replace("\\\\", "/")
                    if fnmatch.fnmatch(cand, pat_norm) or \\
                            fnmatch.fnmatch(cand,
                                            pat_norm.replace("/**", "/*")):
                        return True
        return False
'''))

EDITS.append((
    Path("tools/gate_artifact_audit.py"),
    '''INSTALLED_LOCALES = os.path.join(INSTALLED, "Locales")
''',
    '''INSTALLED_LOCALES = os.path.join(INSTALLED, "Locales")
# The recovered native copies committed in this repository. A citation to
# one of these resolves to a file that really exists, on any host.
RECOVERED_ROOTS = (
    os.path.join(REPO, "docs", "review", "rea", "js_root"),
    os.path.join(REPO, "qtranslate", "assets"),
)
'''))


def main() -> int:
    for path, old, new in EDITS:
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            print(f"{path}: anchor found {count} times (expected 1): "
                  f"{old[:60]!r}", file=sys.stderr)
            return 2
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"patched {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
