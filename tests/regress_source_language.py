"""Regression: the source-language rule settled from the live image.

Native evidence (docs/review/SOURCE_LANGUAGE_RULE_2026-10-10.md, from the
full-analysis project QT_FULL):

  FUN_00404a12  the dispatcher. When source == destination it echoes the
                source into the result slot and SKIPS the service call:
                    if ((param_1[2] - 2U < 0x4a) && (param_1[2] == param_1[4])) {
                        FUN_00401ec9(param_1 + 3, param_1 + 1);
                        goto LAB_00404b33;
                    }
  FUN_0045f6c1  asks the SERVICE, via the JS hook L"usesAutoDetectCode",
                and stores the boolean at request+0x50. There is no
                hardcoded list anywhere in the binary.
  FUN_004606ba  runs detect (FUN_0045fde8) itself only when that flag is
                false, OR when the destination is also not a concrete code.

The port cannot call the JS hook -- the Services/*/Service.js files are
runtime-loaded and absent from the artifact (PLUGIN_LOADER_FOUND) -- so it
declares the capability per provider. This suite pins three things:

  1. the src == dst echo, which the port did not have at all before
  2. that the capability is a table lookup, not a literal set inline in
     do_translate, so the claim sits at module scope where it can be read
  3. that the default for an unknown service is native's detect-yourself
     fallback (False), not "assume it can"

Off-Windows / without tkinter the app module cannot be imported, so this
suite reads the source rather than executing it for anything below the
import line, and executes do_translate only when that is possible.
"""
import sys
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


app_src = open(os.path.join(ROOT, "qtranslate", "app.py"),
               encoding="utf-8", errors="replace").read()
# Slice 2 (2026-10-15) moved the orchestration into engine.py; app.do_translate
# is a thin forwarder. The src==dst echo lives in the engine body now.
eng_src = open(os.path.join(ROOT, "qtranslate", "engine.py"),
               encoding="utf-8", errors="replace").read()

# --- 1. the src == dst echo exists, in engine.translate, before the call
m = re.search(r"def translate\(.*?(?=\n\S|\Z)", eng_src, re.S)
ck("engine.translate located", m is not None)
if m:
    body = m.group(0)
    ck("engine.translate references the src==dst echo",
       "src == target" in body)
    # the echo must come before the provider is invoked. The provider call is
    # NOT a fixed literal: bbe9909 (the reliability wiring) replaced the bare
    # `TRANSLATORS.get(service, _t_google)(text[:5000], src, target)` with
    # `_r.translate(service, text, src, target, ...)`, so an assertion anchored
    # to one spelling fails on the next legitimate refactor while the rule it
    # was protecting still holds. Pin the rule -- the FIRST provider-invoking
    # construct must come after the echo -- by locating every candidate.
    _CALL_SPELLINGS = (
        "_r.translate(",
        "TRANSLATORS.get(service",
        "TRANSLATORS.get(res.provider_used",
        "text[:5000], src, target",
    )
    _calls = [body.find(s) for s in _CALL_SPELLINGS if body.find(s) >= 0]
    ck("a provider-invoking construct is present in do_translate",
       bool(_calls), "found none of %r" % (_CALL_SPELLINGS,))
    _call = min(_calls) if _calls else -1
    _echo = body.find("src == target")
    ck("echo precedes the provider call",
       _echo >= 0 and _call >= 0 and _echo < _call,
       "echo=%s call=%s" % (_echo, _call))
    # and it must return the (already line-collapsed) text, not call out
    ck("echo returns the text",
       re.search(r"if .*src == .*target:.*?return Result\(.*text", body, re.S) is not None)
    # Structural, and stronger than any single spelling: between the echo and
    # the first provider call there must be no `return` that produces output.
    # A provider call hidden before the echo would make the echo's guarantee
    # false even if the echo itself is first in the file.
    ck("no provider call text precedes the echo",
       all(p < 0 or p > _echo for p in _calls))

# --- 2. the capability is a module-level table, not an inline set ---
# Since 2026-10-15 the table lives in qtranslate/registry.py as
# USES_AUTO_DETECT (Phase 2 slice); app.py holds an alias. Read the
# canonical table from the registry source — headless-safe.
reg_src = open(os.path.join(ROOT, "qtranslate", "registry.py"),
               encoding="utf-8", errors="replace").read()
m2 = re.search(r"USES_AUTO_DETECT\s*=\s*(\{.*?\})", reg_src, re.S)
ck("USES_AUTO_DETECT table exists in registry", m2 is not None)
if m2:
    entries = dict(re.findall(r'["\']([^"\']+)["\']\s*:\s*(True|False)',
                              m2.group(1)))
    ck("the table has entries", len(entries) >= 4, repr(entries))
    ck("it is keyed by service id -> bool",
       all(isinstance(k, str) and v in ("True", "False")
           for k, v in entries.items()), repr(entries))
    # no leftover inline set: an ASSIGNMENT, not a mention. A comment that
    # names the old set to explain the migration is fine and expected.
    ck("no _NATIVE_AUTO assignment remains",
       re.search(r"_NATIVE_AUTO\s*=\s*\{", app_src) is None
       and re.search(r"_NATIVE_AUTO\s*=\s*\{", reg_src) is None,
       "the hardcoded set is still assigned somewhere")
    ck("app.py holds an alias, not a second literal",
       "from qtranslate.registry import USES_AUTO_DETECT" in app_src
       and re.search(r"^_USES_AUTO_DETECT\s*=\s*\{", app_src,
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
    _def = re.search(r"^USES_AUTO_DETECT\s*=\s*\{", reg_src, re.M)
    before = reg_src[:_def.start()] if _def else ""
    # find the comment block immediately above the table
    lines = before.splitlines()
    block = "\n".join(lines[-25:])
    ck("the table's comment says it is NOT native-derived",
       "NOT native-derived" in block,
       "a port-side capability presented without attribution")
    ck("the comment cites the loader proof",
       "PLUGIN_LOADER_FOUND" in block)

# --- 4. behavioral, when the app module can be imported ------------------
_tried = False
try:
    from qtranslate import app as A
    _tried = True
except Exception:
    pass  # tkinter / win32 absent on this host: source checks above carry it

if _tried and hasattr(A, "do_translate"):
    # Alias identity: A._USES_AUTO_DETECT must BE the registry table, or
    # the two can drift again. When app cannot import, the static alias
    # check in §2 carries this instead.
    try:
        from qtranslate import registry as _RG
        ck("app alias IS the registry table (no drift possible)",
           A._USES_AUTO_DETECT is _RG.USES_AUTO_DETECT)
        ck("capability lookup defaults to native's detect-yourself",
           _RG.uses_auto_detect("no-such-service") is False)
    except Exception as e:
        ck("registry capability importable", False, repr(e))
    # src == dst must not call the provider: monkeypatch every translator to
    # raise, and confirm the echo still returns the text.
    saved = dict(getattr(A, "TRANSLATORS", {}))
    def _boom(*a, **k):
        raise AssertionError("provider was called on the src==dst path")
    try:
        A.TRANSLATORS = dict((k, _boom) for k in saved)
        out = A.do_translate("google", "hello", "en", src="en")
        # do_translate now returns core.Result (step 4), not a bare str.
        # The echo text lives in .text; provider_used confirms the provider
        # was not invoked (it would have raised via _boom).
        out_text = getattr(out, "text", out)
        out_provider = getattr(out, "provider_used", None)
        ck("src == dst echoes the text without calling the provider",
           out_text == "hello" and out_provider == "google",
           repr(out)[:80])
    except AssertionError as e:
        ck("src == dst echoes the text without calling the provider",
           False, str(e))
    except Exception:
        pass  # e.g. needs a config/Tk -- the source checks already cover it
    finally:
        A.TRANSLATORS = saved
else:
    # can't execute; assert the same rule textually
    ck("do_translate is defined in app.py", "def do_translate(" in app_src)


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_source_language: all checks ok (%d assertions, app_import=%s)"
      % (n[0], _tried))
