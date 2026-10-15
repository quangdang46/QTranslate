"""Pin CLI positional parsing (row A9 / FUN_0043CD68).

Native parses GetCommandLineW and applies the positional overrides
(service, target, theme) over the restored session — an explicit launch
wins over remembered state. The port factors this into
qtranslate.cli.parse_args; app.py asserts its module-level SERVICE/
TARGET/THEME match this parse.

Offline: pure list parsing, no window.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate.cli import parse_args, DEFAULT_SERVICE, DEFAULT_TARGET, \
    DEFAULT_THEME

ck("defaults: google / vi / Blue",
   parse_args([]) == (DEFAULT_SERVICE, DEFAULT_TARGET, DEFAULT_THEME,
                      False, False), str(parse_args([])))
ck("service only", parse_args(["deepl"]) == ("deepl", "vi", "Blue",
                                             True, False),
   str(parse_args(["deepl"])))
ck("service+target", parse_args(["deepl", "en"]) == ("deepl", "en", "Blue",
                                                     True, True),
   str(parse_args(["deepl", "en"])))
ck("all three", parse_args(["deepl", "en", "Dark"]) == ("deepl", "en",
                                                        "Dark", True, True))
ck("cli_service flag true when arg0 given", parse_args(["x"])[3] is True)
ck("cli_target flag false when only arg0 given",
   parse_args(["x"])[4] is False)
ck("extra args beyond three are ignored",
   parse_args(["a", "b", "c", "d", "e"])[:3] == ("a", "b", "c"))
ck("None argv is treated as empty", parse_args(None)[:3]
   == (DEFAULT_SERVICE, DEFAULT_TARGET, DEFAULT_THEME))

# --- app.py's module-level parse agrees with the helper ----------------
import io
_app = io.open("qtranslate/app.py", encoding="utf-8").read()
ck("app.py asserts its parse matches cli.parse_args",
   "_parse_args(sys.argv[1:])[:5] ==" in _app)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_cli_args: all checks ok (%d assertions)" % n[0])
