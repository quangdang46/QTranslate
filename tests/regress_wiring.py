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
            if node.level:
                # A relative import: the module it names is a sibling of
                # this file (or of one of its parents). The modules are
                # keyed by their base name here, so the base name is
                # what counts.
                if node.module:
                    cand.append(node.module.split(".")[-1])
                else:
                    cand.extend(a.name for a in node.names)
            elif node.module == "qtranslate":
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
# screens      the UI-FULL.html 1:1 screen port, run standalone via
#              `python -m qtranslate.screens <name>`; app.py uses its own
#              widget code for the live app, screens.py is the reference/
#              capture tool compared against native screenshots, so it is
#              deliberately not imported by app.py
# speech_input dead:native-unavailable (checklist J5) -- the module is the
#              RE artifact for FUN_004434FE, not a wired feature
#
# reliability is NOT here any more: it was wired on 2026-10-10 (app.py's
# do_translate now routes through ProviderRouter), so these four are the
# complete orphan set. If reliability reappears here, the wiring regressed.
ENTRY_POINTS = {"win32app", "screens"}
KNOWN_DEAD = {"speech_input"}
# Slice 1–5 (2026-10-15) added Core/Extension modules that are published
# libraries not yet imported by app.py (the UI is frozen): the provider
# contract, the extension manager, the SDK surface, platform interfaces,
# and the tray-state helper. Each is exercised by its own suite.
# Slice 8 (2026-10-15) wired extension loading into app.main
# (`load_user_extensions`), so `extensions` left this set and `platforms`
# is now reached through it. `sdk` remains published-only.
# 2026-10-16: `tray_state` LEFT this set. The packaging pass (Phase 8)
# found `app._sync_icon` had inlined a DIFFERENT 3-state rule (hotkeys
# bound -> on) while `tray_state.select_state` held the real one from
# FUN_00418DA0 (mouse-capture arm flag + hook-availability bit) -- and
# nothing called it. `_sync_icon` now routes through the module, so the
# port follows the native rule and the module is reachable from a frozen
# build. `providers` is not an orphan concern here: only
# tests/regress_provider_contract.py imports it, and the packaging tool
# freezes it deliberately (see tools/build_bundle.py's hiddenimports).
KNOWN_UNWIRED = {"sdk"}

expected = sorted(ENTRY_POINTS | KNOWN_DEAD | KNOWN_UNWIRED)
ck("orphan set is exactly the known one",
   orphans == expected,
   "orphans=%r expected=%r -- a NEW orphan means something became dead code, "
   "and that is what this suite is here to catch" % (orphans, expected))

# --- regression pin: extension loading must STAY wired -------------------------
ck("extension loading is wired (app.main loads user extensions)",
   "extensions" not in orphans,
   "extensions is an orphan again -- app.main stopped calling "
   "load_user_extensions; the Phase-6 'copy folder -> restart -> live' path "
   "is dead")

# --- regression pin: reliability must STAY wired ---------------------------------
# Flipped 2026-10-10 the same day it was written: the wiring landed, the suite
# failed as designed, and this assertion is the durable half. It fails if
# do_translate ever stops routing through the layer again.
ck("reliability is wired (this suite's own reason for existing)",
   "reliability" not in orphans,
   "reliability is an orphan again -- do_translate stopped routing through "
   "the layer; see docs/review/RELIABILITY_UNWIRED_2026-10-10.md")

# --- the engine must actually reach a provider bare, not through the layer ---
# Slice 2 (2026-10-15): the orchestration lives in engine.translate now;
# app.do_translate is a thin forwarder. Read the engine body.
_app = open(os.path.join(ROOT, "qtranslate", "engine.py"),
            encoding="utf-8", errors="replace").read()
_dt = None
try:
    _tree = ast.parse(_app)
    for node in ast.walk(_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == "translate":
            _dt = ast.get_source_segment(_app, node)
except SyntaxError:
    pass
ck("engine.translate found", _dt is not None)
if _dt:
    # The intent is "do_translate actually reaches the reliability layer", not
    # "it spells the call exactly one way": the router takes an optional
    # romanization sink, so `_router()`, `_router(_sink)` and
    # `_router(sink=_sink)` all satisfy the rule. Matched structurally — a
    # call to _router with any argument list — so a legitimate change to the
    # argument list does not read as "the wiring was removed".
    _routes = any(
        isinstance(n, ast.Call) and (
            (isinstance(n.func, ast.Name) and n.func.id == "_router")
            or (isinstance(n.func, ast.Attribute) and n.func.attr == "_router"))
        for n in ast.walk(ast.parse(_dt)))
    ck("do_translate routes through the reliability layer",
       _routes and ".translate(service, text, src, target" in _dt,
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
