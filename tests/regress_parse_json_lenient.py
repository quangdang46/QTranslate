"""Regression: ``parse_json_lenient`` really is lenient (native parseJSON).

The recovered `Common.js` (NSIS chunk at `0x13af4`) is explicit::

    function parseJSON(a){return(new Function("return "+a))()}

So native does not use ``JSON.parse`` -- it **evaluates** the text as a
JS expression. Shapes strict JSON rejects that native therefore accepts:
single-quoted keys/strings, unquoted keys, trailing commas, hex literals,
wrapping parentheses and a trailing semicolon.

The port's ``parse_json_lenient`` was a bare ``json.loads`` while calling
itself "lenient", so all of those raised ``JSONDecodeError`` here and
parsed fine in the real app. 28 call sites funnel every provider response
through it, so a provider emitting single quotes looked broken to the port.

SECURITY, and the reason this is not implemented with eval/exec: native's
``new Function`` genuinely executes, and the port must NOT. The last
block pins that: injected code raises, never runs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.common import parse_json_lenient as P  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


BS, Q = chr(92), chr(39)   # backslash, single quote


def sq(s):
    """A single-quoted JS string body."""
    return Q + s + Q


# --- the shapes native accepts and strict JSON does not -------------------
ck("strict JSON still works", P('{"a":1}') == {"a": 1})
ck("single-quoted key", P("{" + sq("a") + ":1}") == {"a": 1})
ck("single-quoted key AND value",
   P("{" + sq("a") + ":" + sq("x") + "}") == {"a": "x"})
ck("unquoted key", P("{a:1}") == {"a": 1})
ck("trailing comma in object", P('{"a":1,}') == {"a": 1})
ck("trailing comma in array", P("[1,2,]") == [1, 2])
ck("nested trailing comma", P('{"a":[1,]}') == {"a": [1]})
ck("hex literal value", P('{"a":0x1F}') == {"a": 31})
ck("wrapping parens + semicolon", P('({"a":1});') == {"a": 1})
ck("double-wrapped parens", P('(({"a":1}));') == {"a": 1})
ck("surrounding whitespace", P('  {"a":1}  ') == {"a": 1})
ck("apostrophe inside a double-quoted value",
   P('{"a":"x' + Q + 'y"}') == {"a": "x'y"})
ck("escaped single quote inside a single-quoted value",
   P("{" + sq("a") + ":" + Q + "it" + BS + Q + "s" + Q + "}")
   == {"a": "it's"})
ck("JS '' doubling of an apostrophe",
   P("{" + sq("a") + ":" + Q + "say " + BS + Q + Q + " ok" + Q + "}")
   == {"a": "say ' ok"})
ck("escaped double quote inside a double-quoted value",
   P('{"a":"say \\"hi\\""}') == {"a": 'say "hi"'})
ck("bare array", P("[1,2,3]") == [1, 2, 3])
ck("bare string", P(sq("hello")) == "hello")
ck("bare number", P("42") == 42)
ck("true/false/null", (P("true"), P("false"), P("null")) == (True, False,
                                                              None))

# --- malformed input still raises (callers keep their error handling) ----
for bad in ("", "   ", "{", "}", "{'a':", "not json at all", "[1,2"):
    try:
        P(bad)
        ck("malformed %r raises ValueError" % bad, False)
    except ValueError:
        ck("malformed %r raises ValueError" % bad, True)
    except Exception as e:
        ck("malformed %r raises ValueError" % bad, False,
           "wrong type %s" % type(e).__name__)

try:
    P(None)
    ck("None raises ValueError", False)
except ValueError:
    ck("None raises ValueError", True)

# --- SECURITY: no eval/exec, so no code execution -------------------------
marker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "_pwned_marker")
if os.path.exists(marker):
    os.remove(marker)
EVIL = [
    '(function(){require("fs").writeFileSync("%s","x");return 1})()' % marker,
    'require("fs").writeFileSync("%s","y")' % marker,
    'globalThis.__pwned=1',
    '1+1',
    'alert(1)',
    'process.exit(0)',
    'new Function("return 1")()',
]
for e in EVIL:
    try:
        P(e)
        ck("injected %r raises instead of running" % e[:24], False)
    except ValueError:
        ck("injected %r raises instead of running" % e[:24], True)
    except Exception as exc:
        ck("injected %r raises instead of running" % e[:24], False,
           "wrong type %s" % type(exc).__name__)
ck("no file was written by any injected payload",
   not os.path.exists(marker))
ck("no global was set by any injected payload",
   "__pwned" not in globals() and "__pwned" not in dir(sys.modules["builtins"]))

src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "common.py"),
    encoding="utf-8").read()
ck("the implementation does not use eval",
   "eval(" not in src)
ck("the implementation does not use exec",
   "exec(" not in src)
ck("the implementation documents the native source",
   'new Function("return "+a)' in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_parse_json_lenient: all checks ok (%d assertions)" % n[0])
