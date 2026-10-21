"""Second pass on the gate-artifact audit + two citation corrections.

1. `ASSET_PATH_RE` stopped at the first whitespace, so a citation to a
   directory with a space in it (`Services/ABBYY Lingvo Live/Service.js`)
   matched only `Services/ABBYY` and never resolved.
2. The "by name" lookup only walked the Windows install.
3. The glob lookup only walked the Windows install, and the recovered tree
   uses a lower-case `themes/`.
4. **E6 cited `Services/Naver/Service.js`** -- native's directory is
   `Papago` (the port's service id is `naver`; native's is `Papago`). The
   audit surfaced a wrong citation, and it is corrected.
5. **H1 cited a cross-reference** ("the dictionary services are the
   `Service.js` set verified in group E") rather than an artifact. It now
   names the committed files.
"""

from __future__ import annotations

import sys
from pathlib import Path

EDITS: list[tuple[Path, str, str]] = []

# 1. the path regex must allow spaces inside a path component.
EDITS.append((
    Path("tools/gate_artifact_audit.py"),
    '''ASSET_PATH_RE = re.compile(
    r"(?:\\b(?:Services|Plugins|Themes|Locales|Resources)"
    r"/[^\\s`|,()]+|\\b[\\w.-]+\\.(?:js|json|jsonc|xslt|lang))\\b")''',
    '''ASSET_PATH_RE = re.compile(
    r"(?:\\b(?:Services|Plugins|Themes|Locales|Resources)"
    r"/(?:[\\w. -]+/)*[\\w. -]+\\.(?:js|json|jsonc|xslt|txt|ico|png)"
    r"|\\b[\\w.-]+\\.(?:js|json|jsonc|xslt|lang))\\b")'''))

# 2. the by-name lookup must also walk the recovered copies.
EDITS.append((
    Path("tools/gate_artifact_audit.py"),
    '''    # inside the installed copy, by name
    for sub in ("Services", "Plugins", "Themes", "Locales", "Resources", ""):
        if not sub:
            continue
        base = os.path.join(INSTALLED, sub)
        if os.path.isdir(base):
            for root, _dirs, files in os.walk(base):
                for f in files:
                    if name in files or name.rstrip(".*") in files:
                        return True''',
    '''    # inside the installed copy, by name -- and inside the recovered copies
    for base in [os.path.join(INSTALLED, sub)
                 for sub in ("Services", "Plugins", "Themes", "Locales",
                             "Resources", "")] + list(RECOVERED_ROOTS):
        if not base or not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            if name in files or name.rstrip(".*") in files:
                return True'''))

# 3. the glob lookup must also consider the recovered tree, whose themes
#    folder is lower-case.
EDITS.append((
    Path("tools/gate_artifact_audit.py"),
    '''        for folder in [os.path.join(INSTALLED, stem)] + [
                os.path.join(root, stem) for root in RECOVERED_ROOTS]:''',
    '''        folders = [os.path.join(INSTALLED, stem)]
        for root in RECOVERED_ROOTS:
            folders.append(os.path.join(root, stem))
            # the recovered tree uses a lower-case themes/ folder
            folders.append(os.path.join(root, stem.lower()))
        for folder in folders:'''))

# 4. E6 cited native's directory under the port's service id.
EDITS.append((
    Path("docs/RE_COVERAGE_CHECKLIST.md"),
    '''| E6 Naver/Papago (30) | `Services/Naver/Service.js`: POST''',
    '''| E6 Naver/Papago (30) | `Services/Papago/Service.js` (native's directory; the port's service id is `naver`): POST'''))

# 5. H1 cited a cross-reference, not an artifact.
EDITS.append((
    Path("docs/RE_COVERAGE_CHECKLIST.md"),
    '''| H1 Dict providers (11) | the dictionary services are the `Service.js` set verified in group E (E11–E20: Babylon Dict, ImTranslator, Reverso, Lingvo, Multitran, Oxford, Urban, Wikipedia, WordReference, Google Search, youdao-dict) |''',
    '''| H1 Dict providers (11) | the dictionary services' own `Service.js` files, recovered and committed under `docs/review/rea/js_root/Services/` (Babylon Dictionary, ImTranslator, Reverso, ABBYY Lingvo Live, Multitran, Oxford Learner Dictionary, Urban Dictionary, Wikipedia, WordReference, Google Search, youdao) — the per-service detail is in group E (E11–E20) |'''))


def main() -> int:
    for path, old, new in EDITS:
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            print(f"{path}: anchor found {count} times (expected 1): "
                  f"{old[:70]!r}", file=sys.stderr)
            return 2
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"patched {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
