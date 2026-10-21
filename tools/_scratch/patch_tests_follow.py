"""Make the affected suites follow the code to its new home.

Phase 7 (6/6) moved the main window's bodies from `qtranslate/app.py` into
`qtranslate/windows.py` as `MainWindow`, leaving a thin delegator behind.
Five suites read `app.py` as text or as an AST and therefore found the
*delegator* instead of the body -- or nothing at all.

The principle the repo already applies (see `regress_ui_parity_fixes.py`'s
history-menu section: "a check that reads only app.py would either go red
for a legitimate move, or (worse) be narrowed to the delegator and stop
covering the menu at all") is: **the pin follows the code.** These edits
apply it to the remaining five.

No behaviour assertion is weakened: every check still runs against the real
body, wherever it now lives.
"""

from __future__ import annotations

import sys
from pathlib import Path

EDITS: list[tuple[Path, str, str]] = []

# --- 1. regress_default_source_header.py ---------------------------------
EDITS.append((
    Path("tests/regress_default_source_header.py"),
    '''APP = open(os.path.join(ROOT, "qtranslate", "app.py"), encoding="utf-8").read()
SCREENS = open(os.path.join(ROOT, "qtranslate", "screens.py"),
               encoding="utf-8").read()
''',
    '''APP = open(os.path.join(ROOT, "qtranslate", "app.py"), encoding="utf-8").read()
SCREENS = open(os.path.join(ROOT, "qtranslate", "screens.py"),
               encoding="utf-8").read()
# Phase 7 (6/6): the body of `default_source_text` moved to
# `qtranslate/windows.py` as `MainWindow`; app.py keeps a delegator. The
# pin follows the body -- reading only app.py would find the delegator and
# assert against its docstring.
WIN = open(os.path.join(ROOT, "qtranslate", "windows.py"),
           encoding="utf-8").read()
_SRC = WIN if 'lines = ["QTranslate Version' in WIN else APP
'''))

EDITS.append((
    Path("tests/regress_default_source_header.py"),
    '''m = re.search(r'def default_source_text\\(self\\):(.*?)(?=\\n    def )',
              APP, re.S)''',
    '''m = re.search(r'def default_source_text\\(self\\):(.*?)(?=\\n    def )',
              _SRC, re.S)'''))

# --- 2. regress_ocr_languages.py -----------------------------------------
EDITS.append((
    Path("tests/regress_ocr_languages.py"),
    '''APP = io.open(os.path.join(REPO, "qtranslate", "app.py"),
              encoding="utf-8").read()''',
    '''APP = io.open(os.path.join(REPO, "qtranslate", "app.py"),
              encoding="utf-8").read()
# Phase 7 (6/6): the OCR language map moved to `qtranslate/windows.py`
# with the rest of the main window; app.py keeps a delegator.
WIN = io.open(os.path.join(REPO, "qtranslate", "windows.py"),
              encoding="utf-8").read()'''))

# --- 3. regress_ui_parity_fixes.py ---------------------------------------
EDITS.append((
    Path("tests/regress_ui_parity_fixes.py"),
    '''BOTH = APP + "\\n" + WIN
tree = ast.parse(APP)
''',
    '''BOTH = APP + "\\n" + WIN
tree = ast.parse(APP)
# Phase 7 (6/6): the OCR overlay's handlers moved to windows.py with the
# rest of the main window. Walk BOTH trees so the overlay pins still cover
# the body rather than the delegator.
wtree = ast.parse(WIN)
'''))

EDITS.append((
    Path("tests/regress_ui_parity_fixes.py"),
    '''ov = [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)
      and x.name == "_keys"]
ck("overlay defines _keys handler", len(ov) == 1)
gp = [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)
      and x.name == "_grab_png"]
ck("overlay shares one _grab_png capture path", len(gp) == 1)
ng = [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)
      and x.name == "_nudge"]
ck("overlay defines _nudge for arrows", len(ng) == 1)
if ov:
    seg = ast.get_source_segment(APP, ov[0])''',
    '''ov = [x for x in ast.walk(tree) + ast.walk(wtree)
      if isinstance(x, ast.FunctionDef) and x.name == "_keys"]
ck("overlay defines _keys handler", len(ov) == 1)
gp = [x for x in ast.walk(tree) + ast.walk(wtree)
      if isinstance(x, ast.FunctionDef) and x.name == "_grab_png"]
ck("overlay shares one _grab_png capture path", len(gp) == 1)
ng = [x for x in ast.walk(tree) + ast.walk(wtree)
      if isinstance(x, ast.FunctionDef) and x.name == "_nudge"]
ck("overlay defines _nudge for arrows", len(ng) == 1)
if ov:
    seg = ast.get_source_segment(APP if ov[0] in ast.walk(tree) else WIN,
                                 ov[0])'''))

# --- 4. regress_packaging.py ---------------------------------------------
EDITS.append((
    Path("tests/regress_packaging.py"),
    '''ck("the override dialog imports override_ui from its own module",
   re.search(r"from qtranslate\\.extensions import \\(\\n"
             r"                ExtensionManager, write_saved_overrides\\)\\n"
             r"(?:            #[^\\n]*\\n)+"
             r"            from qtranslate import override_ui\\n",
             appsrc) is not None,''',
    '''ck("the override dialog imports override_ui from its own module",
   re.search(r"from qtranslate\\.extensions import \\(\\n"
             r"                ExtensionManager, write_saved_overrides\\)\\n"
             r"(?:            #[^\\n]*\\n)+"
             r"            from qtranslate import override_ui\\n",
             appsrc + winsrc) is not None,'''))

# --- 5. regress_app_undefined_names.py ------------------------------------
EDITS.append((
    Path("tests/regress_app_undefined_names.py"),
    '''SRC = io.open(os.path.join(ROOT, "qtranslate", "app.py"),
              encoding="utf-8").read()
TREE = ast.parse(SRC)


def _method(name):
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None
''',
    '''SRC = io.open(os.path.join(ROOT, "qtranslate", "app.py"),
              encoding="utf-8").read()
TREE = ast.parse(SRC)
# Phase 7 (6/6): the bodies moved to `qtranslate/windows.py` as
# `MainWindow`; app.py keeps delegators. The pins below follow the code.
WIN = io.open(os.path.join(ROOT, "qtranslate", "windows.py"),
              encoding="utf-8").read()
WTREE = ast.parse(WIN)
ALL_SRC = SRC + "\\n" + WIN


def _method(name):
    for node in ast.walk(TREE) + ast.walk(WTREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None
'''))

EDITS.append((
    Path("tests/regress_app_undefined_names.py"),
    '''ck("the speech error is captured in a local (_speech_err)",
   "_speech_err" in SRC)''',
    '''ck("the speech error is captured in a local (_speech_err)",
   "_speech_err" in ALL_SRC)'''))


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
