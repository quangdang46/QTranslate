"""Regression: the default source pane's version header has TWO spaces.

`FUN_0042F2CC` builds the default source text with the format
``%s %s %s\\n\\n%s`` -- three fields, a blank line, then the locale's
``help.txt``. Recovered from the image's UTF-16 string table at
``0x11E5C8``, the three fields are:

| field | value | where it comes from |
|-------|-------|---------------------|
| 1 | ``QTranslate`` | the app name resource, ``\\|QTranslate\\|`` |
| 2 | ``Version `` | the resource string immediately after ``\\x08About`` — **with a trailing space** |
| 3 | ``6.10.0`` | ``FileVersion`` / ``ProductVersion`` |

The format joins with a space *and* field 2 already ends in one, so the
rendered line is ``QTranslate Version  6.10.0`` — **two spaces** before
the version.

The port emitted one space until 2026-10-16. It read better and was
wrong. `ui_match.py`'s existing "default-text==help.txt" check compares
the port against its own hardcoded header, so it could not catch it; this
suite compares against the SPEC's literal and the recovered resource
string instead.

Headless: the spec and the app's own module are read as text, so no Tk.
Skips the install-dependent assertion when QTranslate isn't present.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(ROOT, "qtranslate", "app.py"), encoding="utf-8").read()
SCREENS = open(os.path.join(ROOT, "qtranslate", "screens.py"),
               encoding="utf-8").read()
# Phase 7 (6/6): the body of `default_source_text` moved to
# `qtranslate/windows.py` as `MainWindow`; app.py keeps a delegator. The
# pin follows the body -- reading only app.py would find the delegator and
# assert against its docstring.
WIN = open(os.path.join(ROOT, "qtranslate", "windows.py"),
           encoding="utf-8").read()
_SRC = WIN if 'lines = ["QTranslate Version' in WIN else APP

# --- 1. the port's header literal, read from the CODE not the runtime ----
# the function body, cut at the next `def` rather than at the first blank
# line -- the docstring contains blank lines of its own.
m = re.search(r'def default_source_text\(self\):(.*?)(?=\n    def )',
              _SRC, re.S)
ck("default_source_text exists", m is not None)
body = m.group(1) if m else ""
# the literal on the `lines = [...]` statement, not the docstring's copy
lit = re.search(r'^\s*lines = \["([^"]*)"', body, re.M)
ck("the header is a plain literal", lit is not None,
   repr(body[:300]))
header = lit.group(1) if lit else ""
ck("the header carries TWO spaces before the version",
   header == "QTranslate Version  6.10.0", repr(header))
ck("it is not the collapsed one-space form",
   "Version 6.10.0" not in header, repr(header))

# --- 2. the two independent renderers agree ------------------------------
# screens.py concatenates the header and the help body in one literal, whose
# line breaks are the two characters \ + n. Compare the first FRAGMENT.
s = re.search(r'help_text = \(\s*"([^"]*)"', SCREENS)
ck("screens.py's help_text is found", s is not None)
scr_lit = s.group(1) if s else ""
ck("screens.py's help_text starts with the same header",
   scr_lit.split("\\n")[0] == header, repr(scr_lit[:44]))
ck("screens.py separates the header from the body with a blank line",
   scr_lit.startswith(header + "\\n\\n"), repr(scr_lit[:44]))

spec_path = os.path.join(ROOT, "ui-html-port-need-strict-follow",
                         "UI-FULL.html")
if os.path.isfile(spec_path):
    spec = open(spec_path, encoding="utf-8").read()
    sp = re.search(r'QTranslate Version[^"\\]*', spec)
    ck("the UI spec's literal has the same two-space header",
       sp is not None and sp.group(0).split("\n")[0] == header,
       repr(sp.group(0)[:40] if sp else None))

# --- 3. the resource string really ends in a space ----------------------
EXE = os.path.join(ROOT, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")
if os.path.isfile(EXE) and os.path.getsize(EXE) > 2_000_000:
    blob = open(EXE, "rb").read()
    needle = "Version ".encode("utf-16-le")
    hits = [m.start() for m in re.finditer(re.escape(needle), blob)]
    ck("the image holds a 'Version ' resource WITH a trailing space",
       bool(hits), "no utf-16 'Version ' found")
    for h in hits:
        window = blob[h - 40:h + 40].decode("utf-16-le", "replace")
        if "About" in window.replace("\x00", ""):
            ck("...and it sits right after 'About', as the middle field",
               True)
            break
    else:
        ck("...and it sits right after 'About', as the middle field",
           False, "no 'About' landmark next to it")
    fmt = "%s %s %s".encode("utf-16-le")
    ck("the image holds the '%s %s %s' header format",
       bool(re.search(re.escape(fmt), blob)),
       "the three-field format is not in the image")

# --- 4. the rest of the pane is the locale's help.txt -------------------
ck("the pane's body comes from the locale help.txt, not a hardcoded copy",
   "help.txt" in body, "default_source_text no longer reads help.txt")
ck("...and it keeps a fallback when that file is missing",
   "except Exception" in body or "except OSError" in body,
   "no fallback for a missing install")
ck("the header and the body are separated by a blank line",
   re.search(r'lines = \["[^"]*",\s*""\s*\]', body) is not None,
   "no empty line after the header")

if failures:
    print("FAIL %d/%d" % (len(failures), n[0]))
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("regress_default_source_header: all checks ok (%d assertions)" % n[0])
