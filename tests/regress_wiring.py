"""Regression: which modules are actually wired into the app.

Why this suite exists. `docs/review/RELIABILITY_UNWIRED_2026-10-10.md` found
`qtranslate/reliability.py` -- 28KB of finished logic (ErrorKind, classify(),
FallbackRouter, ProviderHealth) -- with **no production caller**. The
compatibility matrix called the layer "design only / not-started", so a reader
planning work would have budgeted build time for something already built, and
`tests/regress_reliability.py` passed green against nothing.

The general failure: a module can be complete, tested, and dead at the same
time, and nothing in a green test run says which. This suite names the orphan
set explicitly so it cannot grow silently.

Method: parse every qtranslate/*.py, resolve both `import X` and
`from qtranslate import X` / `from qtranslate.services import X`, and report
modules no other production module references. An entry point is NOT an
orphan -- app.py is imported by nothing and must not be.
"""
import ast
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


prod_files = [f for f in glob.glob(os.path.join(ROOT, "qtranslate", "**", "*.py"),
                                   recursive=True)
              if "__pycache__" not in f]
ck("found qtranslate/*.py files", len(prod_files) >= 20, str(len(prod_files)))

mods = set(os.path.splitext(os.path.basename(f))[0] for f in prod_files)
mods.discard("__init__")

importers = dict((m, set()) for m in mods)
for f in prod_files:
    try:
        tree = ast.parse(open(f, encoding="utf-8").read())
    except SyntaxError as e:
        ck("parses: %s" % os.path.basename(f), False, str(e))
        continue
    this = os.path.splitext(os.path.basename(f))[0]
    for node in ast.walk(tree):
        cand = []
        if isinstance(node, ast.Import):
            cand.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "qtranslate":
                cand.extend("qtranslate." + a.name for a in node.names)
            elif node.module and node.module.startswith("qtranslate."):
                cand.append(node.module)
                for a in node.names:
                    cand.append(node.module + "." + a.name)
        for name in cand:
            base = name.split(".")[-1]
            if base in importers and base != this:
                importers[base].add(this)
            if name.startswith("qtranslate."):
                tgt = name.split(".", 1)[1]
                if tgt in importers and tgt != this:
                    importers[tgt].add(this)

orphans = sorted(m for m in mods
                 if not [i for i in importers[m] if i != "__init__"])

# --- the known, intentional orphans ------------------------------------
# app          the Tk entry point; win32app imports it, so it is NOT an orphan
# win32app     a runnable script (`uv run python qtranslate/win32app.py`), not
#              a library; it self-documents that in its docstring
# speech_input dead:native-unavailable (checklist J5) -- the module is the
#              RE artifact for FUN_004434FE, not a wired feature
#
# reliability is NOT here any more: it was wired on 2026-10-10 (app.py's
# do_translate now routes through ProviderRouter), so these three are the
# complete orphan set. If reliability reappears here, the wiring regressed.
ENTRY_POINTS = {"win32app"}
KNOWN_DEAD = {"speech_input"}

expected = sorted(ENTRY_POINTS | KNOWN_DEAD)
ck("orphan set is exactly the known one",
   orphans == expected,
   "orphans=%r expected=%r -- a NEW orphan means something became dead code, "
   "and that is what this suite is here to catch" % (orphans, expected))

# --- regression pin: reliability must STAY wired ---------------------------------
# Flipped 2026-10-10 the same day it was written: the wiring landed, the suite
# failed as designed, and this assertion is the durable half. It fails if
# do_translate ever stops routing through the layer again.
ck("reliability is wired (this suite's own reason for existing)",
   "reliability" not in orphans,
   "reliability is an orphan again -- do_translate stopped routing through "
   "the layer; see docs/review/RELIABILITY_UNWIRED_2026-10-10.md")

# --- the app must actually reach a provider bare, not through the layer ---
_app = open(os.path.join(ROOT, "qtranslate", "app.py"),
            encoding="utf-8", errors="replace").read()
_dt = None
try:
    _tree = ast.parse(_app)
    for node in ast.walk(_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == "do_translate":
            _dt = ast.get_source_segment(_app, node)
except SyntaxError:
    pass
ck("do_translate found", _dt is not None)
if _dt:
    ck("do_translate routes through the reliability layer",
   "_router()" in _dt and ".translate(service, text, src, target" in _dt,
   "do_translate no longer calls the router")
# the None-guard matters: a failed import must degrade to the bare provider
# call rather than failing the translation outright.
ck("do_translate degrades gracefully if the layer is unavailable",
   "_r is None" in _dt,
   "no fallback if the reliability layer cannot be imported")
# and the layer's ordering rule must hold: from the result onward the service
# that matters is the one that ANSWERED, not the one the user picked.
ck("do_translate rebinds service to the provider that answered",
   "service = res.provider_used" in _dt,
   "back-translation and J7 phonetics would use the user's pick instead of "
   "the provider that actually answered")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_wiring: all checks ok (%d assertions, orphans=%s)"
      % (n[0], orphans))
