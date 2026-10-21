"""Convert the three source-text assertions to behavioural ones.

The auto-detect capability table is no longer a literal dict in the source --
it is derived from the provider tables by native's own rule. Three suites
read the old literal out of the source text with a regex, so they now fail on
a *shape* change rather than on a behaviour change.

These edits make the suites assert the behaviour instead: import the
registry and ask it.
"""

from __future__ import annotations

import sys
from pathlib import Path

EDITS: list[tuple[Path, str, str]] = []

# --- 1. tests/regress_provider_auto.py -------------------------------------
EDITS.append((
    Path("tests/regress_provider_auto.py"),
    '''# microsoft/bing are in the native-auto set (no detect round-trip expected).
# Since 2026-10-15 the table lives in qtranslate/registry.py as
# USES_AUTO_DETECT (Phase 2 slice); read the canonical source so this suite
# stays tkinter-free like the rest of the file.
import io as _io
import os as _os
import re as _re
_reg_src = _io.open(_os.path.join(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))), "qtranslate", "registry.py"),
    encoding="utf-8").read()
_m = _re.search(r"USES_AUTO_DETECT\\s*=\\s*(\\{.*?\\})", _reg_src, _re.S)
_cap = eval(_m.group(1)) if _m else {}
check("microsoft/bing are native-auto services",
      _cap.get("bing") is True and _cap.get("microsoft") is True,
      repr(_cap))
''',
    '''# microsoft/bing are in the native-auto set (no detect round-trip expected).
# The table lives in qtranslate/registry.py and is DERIVED from the provider
# language tables by native's own rule (Common.js's usesAutoDetectCode), so
# ask the registry for the answer rather than reading a literal out of the
# source text -- a source-text assertion pins the *shape* of the code, not
# the behaviour, and it broke the moment the table stopped being a literal.
from qtranslate import registry as _RG  # noqa: E402
check("microsoft/bing are native-auto services",
      _RG.uses_auto_detect("bing") is True
      and _RG.uses_auto_detect("microsoft") is True,
      repr(_RG.USES_AUTO_DETECT))
'''))

# --- 2. tests/regress_registry.py ------------------------------------------
EDITS.append((
    Path("tests/regress_registry.py"),
    '''ck("registry owns USES_AUTO_DETECT + uses_auto_detect()",
   re.search(r"^USES_AUTO_DETECT = \\{", REG_SRC, re.M) is not None
   and "def uses_auto_detect(" in REG_SRC)
''',
    '''ck("registry owns USES_AUTO_DETECT + uses_auto_detect()",
   "def uses_auto_detect(" in REG_SRC
   and hasattr(REG, "USES_AUTO_DETECT")
   and REG.uses_auto_detect("microsoft") is True
   and REG.uses_auto_detect("no-such-service") is False)
'''))

# --- 3. tests/regress_source_language.py ------------------------------------
EDITS.append((
    Path("tests/regress_source_language.py"),
    '''# --- 2. the capability is a module-level table, not an inline set ---
# Since 2026-10-15 the table lives in qtranslate/registry.py as
# USES_AUTO_DETECT (Phase 2 slice); app.py holds an alias. Read the
# canonical table from the registry source — headless-safe.
reg_src = open(os.path.join(ROOT, "qtranslate", "registry.py"),
               encoding="utf-8", errors="replace").read()
m2 = re.search(r"USES_AUTO_DETECT\\s*=\\s*(\\{.*?\\})", reg_src, re.S)
ck("USES_AUTO_DETECT table exists in registry", m2 is not None)
if m2:
    entries = dict(re.findall(r'["\\']([^"\\']+)["\\']\\s*:\\s*(True|False)',
                              m2.group(1)))
    ck("the table has entries", len(entries) >= 4, repr(entries))
    ck("it is keyed by service id -> bool",
       all(isinstance(k, str) and v in ("True", "False")
           for k, v in entries.items()), repr(entries))
    # no leftover inline set: an ASSIGNMENT, not a mention. A comment that
    # names the old set to explain the migration is fine and expected.
    ck("no _NATIVE_AUTO assignment remains",
       re.search(r"_NATIVE_AUTO\\s*=\\s*\\{", app_src) is None
       and re.search(r"_NATIVE_AUTO\\s*=\\s*\\{", reg_src) is None,
       "the hardcoded set is still assigned somewhere")
    ck("app.py holds an alias, not a second literal",
       "from qtranslate.registry import USES_AUTO_DETECT" in app_src
       and re.search(r"^_USES_AUTO_DETECT\\s*=\\s*\\{", app_src,
                     re.M) is None,
       "two tables = two sources of truth again")
    ck("engine.translate consults the capability",
       "uses_auto_detect(" in (m.group(0) if m else ""))

# --- 3. the code must not claim native derivation for the table
if m2:
    # Anchor on the DEFINITION line, not the first mention: the module
    # docstring names the table when describing the design, so a plain
    # .find() lands in the docstring and the "25 lines above" window
    # misses the attribution comment entirely (false FAIL, 2026-10-15).
    _def = re.search(r"^USES_AUTO_DETECT\\s*=\\s*\\{", reg_src, re.M)
    before = reg_src[:_def.start()] if _def else ""
    # find the comment block immediately above the table
    lines = before.splitlines()
    block = "\\n".join(lines[-25:])
    ck("the table's comment says it is NOT native-derived",
       "NOT native-derived" in block,
       "a port-side capability presented without attribution")
    ck("the comment cites the loader proof",
       "PLUGIN_LOADER_FOUND" in block)
''',
    '''# --- 2. the capability is a module-level table, not an inline set ---
# Since 2026-10-15 the table lives in qtranslate/registry.py as
# USES_AUTO_DETECT (Phase 2 slice); app.py holds an alias. Since
# 2026-10-21 it is DERIVED from the provider language tables by native's own
# rule (Common.js's usesAutoDetectCode), so ask the registry for the answer
# rather than reading a literal out of the source text.
reg_src = open(os.path.join(ROOT, "qtranslate", "registry.py"),
               encoding="utf-8", errors="replace").read()
try:
    from qtranslate import registry as _RG
    _reg_ok = True
except Exception as e:  # pragma: no cover - registry is stdlib-only
    _reg_ok = False
    _RG = None
    ck("registry importable", False, repr(e))
ck("USES_AUTO_DETECT table exists in registry",
   _reg_ok and hasattr(_RG, "USES_AUTO_DETECT"))
if _reg_ok:
    entries = dict(_RG.USES_AUTO_DETECT)
    ck("the table has entries", len(entries) >= 4, repr(entries))
    ck("it is keyed by service id -> bool",
       all(isinstance(k, str) and isinstance(v, bool)
           for k, v in entries.items()), repr(entries))
    # no leftover inline set: an ASSIGNMENT, not a mention. A comment that
    # names the old set to explain the migration is fine and expected.
    ck("no _NATIVE_AUTO assignment remains",
       re.search(r"_NATIVE_AUTO\\s*=\\s*\\{", app_src) is None
       and re.search(r"_NATIVE_AUTO\\s*=\\s*\\{", reg_src) is None,
       "the hardcoded set is still assigned somewhere")
    ck("app.py holds an alias, not a second literal",
       "from qtranslate.registry import USES_AUTO_DETECT" in app_src
       and re.search(r"^_USES_AUTO_DETECT\\s*=\\s*\\{", app_src,
                     re.M) is None,
       "two tables = two sources of truth again")
    ck("engine.translate consults the capability",
       "uses_auto_detect(" in (m.group(0) if m else ""))

# --- 3. the table IS native-derived (the premise changed) ---
# The old suite pinned "NOT native-derived" because the Services/*/Service.js
# files were thought to be unrecoverable. They are not: the plugin loader
# reads them from the installed tree at runtime, and the installer's payload
# carries all 19 of them. The hook is a FRAMEWORK function in Common.js --
# `SupportedLanguages[AUTO_DETECT_LANGUAGE] !== UNKNOWN_LANGUAGE_CODE` -- so
# the truth table is derivable from the recovered JS and the port's own
# transcribed language tables.
#   docs/review/AUTO_DETECT_CAPABILITY_2026-10-21.md
if _reg_ok:
    ck("the capability is derived, not a hand-listed literal",
       "_auto_capability()" in reg_src
       and re.search(r"^USES_AUTO_DETECT\\s*=\\s*_auto_capability\\(\\)",
                     reg_src, re.M) is not None,
       "the table is a literal again")
    ck("the derivation cites native's rule",
       "usesAutoDetectCode" in reg_src
       and "AUTO_DETECT_LANGUAGE" in reg_src)
    ck("the derivation cites the measured truth table",
       "AUTO_DETECT_CAPABILITY" in reg_src)
    # Behaviour: the answers native gives, measured from the recovered JS.
    ck("microsoft accepts an auto source",
       _RG.uses_auto_detect("microsoft") is True)
    ck("bing aliases microsoft's capability",
       _RG.uses_auto_detect("bing") is True)
    ck("yandex does not accept an auto source",
       _RG.uses_auto_detect("yandex") is False)
    ck("baidu does not accept an auto source",
       _RG.uses_auto_detect("baidu") is False)
    ck("babylon does not accept an auto source",
       _RG.uses_auto_detect("babylon") is False)
    ck("naver accepts an auto source (Papago slot 1 is 'auto')",
       _RG.uses_auto_detect("naver") is True)
    ck("youdao accepts an auto source (slot 1 is 'AUTO')",
       _RG.uses_auto_detect("youdao") is True)
    ck("promt accepts an auto source (slot 1 is 'au')",
       _RG.uses_auto_detect("promt") is True)
    ck("an unknown service defaults to detect-yourself",
       _RG.uses_auto_detect("no-such-service") is False)
    # And each provider's OWN auto code -- native sends codeFromLanguage(1),
    # not a literal "auto".
    ck("microsoft's own auto code is 'auto-detect'",
       _RG.auto_detect_code("microsoft") == "auto-detect")
    ck("youdao's own auto code is 'AUTO'",
       _RG.auto_detect_code("youdao") == "AUTO")
    ck("promt's own auto code is 'au'",
       _RG.auto_detect_code("promt") == "au")
    ck("google's own auto code is 'auto'",
       _RG.auto_detect_code("google") == "auto")
'''))


def main() -> int:
    for path, old, new in EDITS:
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            print(f"{path}: anchor found {count} times (expected 1): {old[:60]!r}",
                  file=sys.stderr)
            return 2
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"patched {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
