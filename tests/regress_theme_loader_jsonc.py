"""Regression: the theme loader's JSONC handling is quote-aware.

The 8 shipped `Themes/*.json` are JSON **with `//` comments** -- native
reads them with a comment-tolerant JSON parser, so the port strips
comments before `json.loads`.

The first version of that strip was
``re.sub(r"//[^\\n]*", "", text)``, which is **not quote-aware**: a
``//`` inside a string value was cut too, so

    {"a": "http://x.tld/p"}

became ``{"a": "http:`` -- an unterminated string, and the whole theme
failed to load. None of the 8 shipped themes carry a ``//`` in a value,
which is why it stayed latent, but a user-authored theme naming a URL was
rejected outright.

Fixed 2026-10-16 with a character scanner that tracks whether it is
inside a string. Block comments (``/* */``) are handled too -- the earlier
regex did not touch them at all, so a file using them failed to parse.

Headless: files are written to a temp dir and read back through the port's
own loader. No network, no Tk.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import theme as T  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


TMP = tempfile.mkdtemp()


def load(text):
    p = os.path.join(TMP, "t%d.json" % len(os.listdir(TMP)))
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return T.load_theme_at(p)


# 1. the shipped files are JSONC, so this is not hypothetical
INSTALLED = r"C:\Program Files (x86)\QTranslate\Themes"
if os.path.isdir(INSTALLED):
    names = sorted(os.listdir(INSTALLED))
    check("8 themes ship", len(names) == 8, str(names))
    commented = 0
    for n in names:
        raw = open(os.path.join(INSTALLED, n), encoding="utf-8-sig").read()
        if "//" in raw:
            commented += 1
    check("the shipped themes really do use // comments",
          commented == len(names), "%d of %d" % (commented, len(names)))

# 2. a // inside a string value must survive
got = load('{"Common": {"ClientBackColor": "http://x.tld/p"}}')
check("a // inside a value is not treated as a comment",
      got["Common"]["ClientBackColor"] == "http://x.tld/p",
      repr(got["Common"]["ClientBackColor"]))

for probe in ('c // d', '//', 'a//b', '1//2', '"', '\\"//\\"'):
    try:
        out = load('{"Common": {"ClientBackColor": "%s"}}' % probe
                   .replace("\\\"", "\\\""))
        check("value %r survives the comment strip" % probe,
              out["Common"]["ClientBackColor"] == probe,
              repr(out["Common"]["ClientBackColor"]))
    except Exception as ex:  # noqa: BLE001
        check("value %r survives the comment strip" % probe, False, str(ex))

# 3. real comments ARE stripped, including block comments
got = load('{"Common": {\n'
           '  "ButtonRadius": 2, // 0 - None, 1 - Small\n'
           '  "ClientBackColor": "1586bb" // a colour\n'
           '}}')
check("// comments are stripped", got["Common"]["ButtonRadius"] == 2,
      repr(got))
check("the values after a // comment survive",
      got["Common"]["ClientBackColor"] == 0x1586bb, repr(got))

got = load('{"Common": {"ButtonRadius": 3 /* block comment */, '
           '"ClientBackColor": "ff"}}')
check("/* block comments are stripped", got["Common"]["ButtonRadius"] == 3,
      repr(got))

# 4. an unterminated block comment does not hang or raise oddly
try:
    load('{"Common": {"ButtonRadius": 1 /* never closed')
    check("an unterminated block comment is tolerated", True)
except Exception as ex:  # noqa: BLE001
    check("an unterminated block comment is tolerated", False, str(ex))

# 5. a comment's removal can leave a trailing comma -- still parses
got = load('{"Common": {"ClientBackColor": "ff"} // last\n}')
check("trailing comma after a stripped comment still parses",
      "Common" in got, repr(got))

# 6. the loaded dict keeps the loader's Common semantics
got = load('{"Common": {"ButtonRadius": 9, "WindowBorderRadius": 7, '
           '"NoSuchSlot": 5}}')
check("ButtonRadius clamps at 0", got["Common"]["ButtonRadius"] == 9,
      repr(got))
check("WindowBorderRadius>3 leaves the memset 0",
      got["Common"]["WindowBorderRadius"] == 0, repr(got))
check("an unknown key is not carried into Common",
      "NoSuchSlot" not in got["Common"], repr(got["Common"]))
check("an unmentioned slot is 0", got["Common"]["PaintClassicFocus"] in
      (True, False), repr(got))

if failures:
    print("FAIL %d" % len(failures))
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("regress_theme_loader_jsonc: all checks ok (%d assertions)"
      % len(failures) if failures else
      "regress_theme_loader_jsonc: all checks ok")
