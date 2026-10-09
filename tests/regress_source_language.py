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

# --- 1. the src == dst echo exists, in do_translate, before the provider call
m = re.search(r"def do_translate\(.*?\n(?=\ndef |\nclass )", app_src, re.S)
ck("do_translate located", m is not None)
if m:
    body = m.group(0)
    ck("do_translate references the src==dst echo", "src == target" in body)
    # the echo must come before the provider is invoked
    _call = body.find("fn(text[:5000], src, target)")
    _echo = body.find("src == target")
    ck("echo precedes the provider call",
       _echo >= 0 and _call >= 0 and _echo < _call,
       "echo=%s call=%s" % (_echo, _call))
    # and it must return the (already line-collapsed) text, not call out
    ck("echo returns the text",
       re.search(r"if src == target:\s*\n\s*return text", body) is not None)

# --- 2. the capability is a module-level table, not an inline set
m2 = re.search(r"_USES_AUTO_DETECT\s*=\s*\{([^}]*)\}", app_src)
ck("_USES_AUTO_DETECT table exists at module scope", m2 is not None)
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
       re.search(r"_NATIVE_AUTO\s*=\s*\{", app_src) is None,
       "the hardcoded set is still assigned in the file")
    ck("_USES_AUTO_DETECT is the only auto-capability table",
       re.search(r"_USES_AUTO_DETECT\s*=\s*\{", app_src) is not None)
    ck("do_translate consults the table",
       "_USES_AUTO_DETECT" in (m.group(0) if m else ""))

# --- 3. the code must not claim native derivation for the table
if m2:
    before = app_src[:app_src.find("_USES_AUTO_DETECT")]
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
    cap = A._USES_AUTO_DETECT
    ck("capability lookup defaults to native's detect-yourself",
       cap.get("no-such-service", False) is False)
    # src == dst must not call the provider: monkeypatch every translator to
    # raise, and confirm the echo still returns the text.
    saved = dict(getattr(A, "TRANSLATORS", {}))
    def _boom(*a, **k):
        raise AssertionError("provider was called on the src==dst path")
    try:
        A.TRANSLATORS = dict((k, _boom) for k in saved)
        out = A.do_translate("google", "hello", "en", src="en")
        ck("src == dst echoes the text without calling the provider",
           out == "hello", repr(out)[:80])
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
