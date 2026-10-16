"""Regression: the theme loader's JSONC handling is quote-aware.

**Some** of the shipped `Themes/*.json` use `//` comments -- 3 of the 8
(Blue, Brackets, Metro); the other 5 are plain JSON. Native reads them
with a comment-tolerant JSON parser, so the port strips comments before
`json.loads`.

The first version of that strip was
``re.sub(r"//[^\\n]*", "", text)``, which is **not quote-aware**: a
``//`` inside a string value was cut too, so

    {"a": "http://x.tld/p"}

became ``{"a": "http:`` -- an unterminated string, and the whole theme
failed to load. No shipped theme carries a ``//`` in a value, which is why
it stayed latent, but a user-authored theme naming a URL was rejected
outright.

Fixed 2026-10-16 with a character scanner that tracks whether it is
inside a string. Block comments (``/* */``) are now handled too -- the
earlier regex did not touch them, so a file using them failed to parse.

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
count = [0]


def check(name, cond, detail=""):
    count[0] += 1
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


TMP = tempfile.mkdtemp()
_seq = [0]


def load(text):
    _seq[0] += 1
    p = os.path.join(TMP, "t%d.json" % _seq[0])
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return T.load_theme_at(p)


# --- 1. the shipped files really are (sometimes) JSONC -------------------
INSTALLED = r"C:\Program Files (x86)\QTranslate\Themes"
if os.path.isdir(INSTALLED):
    names = sorted(os.listdir(INSTALLED))
    check("8 themes ship", len(names) == 8, str(names))
    commented = [n for n in names
                 if "//" in open(os.path.join(INSTALLED, n),
                                 encoding="utf-8-sig").read()]
    check("3 of the 8 use // comments (Blue, Brackets, Metro)",
          len(commented) == 3, commented)
    check("all 8 load through the port's loader",
          all(isinstance(T.load_theme_at(os.path.join(INSTALLED, n)), dict)
              for n in names), "one failed")

# --- 2. the fix: a // inside a value must not be cut --------------------
# "Common" keys go through the colour parser, so use a key that is NOT a
# Common slot -- it survives into the dict verbatim and is directly
# observable. ("a://b" is not a hex colour, so asserting on the parsed
# colour would test the colour parser, not the comment strip.)
for probe in ("http://x.tld/p", "c // d", "//", "a//b", "1//2",
              "leading // trailing", "https://a.b/c"):
    doc = json.dumps({"Common": {"ClientBackColor": "ff"},
                      "Url": probe})
    try:
        got = load(doc)
        check("value %r survives the comment strip" % probe,
              got.get("Url") == probe, repr(got.get("Url")))
    except Exception as ex:  # noqa: BLE001
        check("value %r survives the comment strip" % probe, False, str(ex))

# an escaped quote inside the value must not end the string-tracking
try:
    got = load(json.dumps({"Url": 'a\\"b//c'}) + " // tail")
    check("an escaped quote then // inside a value survives",
          got["Url"] == 'a\\"b//c', repr(got["Url"]))
except Exception as ex:  # noqa: BLE001
    check("an escaped quote then // inside a value survives", False, str(ex))

# --- 3. real comments ARE stripped --------------------------------------
text = ('{\n'
        '  "Common": {\n'
        '    "ButtonRadius": 2, // 0 - None, 1 - Small\n'
        '    "ClientBackColor": "1586bb" // a colour\n'
        '  },\n'
        '  "Url": "http://q/" // and one after\n'
        '}')
got = load(text)
check("// comments are stripped", got["Common"]["ButtonRadius"] == 2,
      repr(got))
check("the value after a // comment survives",
      got["Common"]["ClientBackColor"] == 0x1586bb, repr(got))
check("a // comment AFTER a value does not eat the value",
      got["Url"] == "http://q/", repr(got))

got = load('{"Common": {"ButtonRadius": 3 /* block */, '
           '"ClientBackColor": "ff"}}')
check("/* block comments are stripped", got["Common"]["ButtonRadius"] == 3,
      repr(got))

# --- 4. degenerate comment shapes ---------------------------------------
# An unterminated block comment truncates the file, which is genuinely
# malformed JSON -- the contract is that it FAILS LOUDLY (a clear
# json.JSONDecodeError naming the line), never that it silently loads a
# partial palette, and never that it hangs.
try:
    load('{"Common": {"ButtonRadius": 1 /* never closed')
    check("an unterminated block comment raises, not silently loads", False,
          "loaded without error")
except json.JSONDecodeError as ex:
    check("an unterminated block comment raises, not silently loads", True)
    check("...and the error names a position", ex.pos > 0, str(ex))
except Exception as ex:  # noqa: BLE001
    check("an unterminated block comment raises, not silently loads", False,
          "raised %r instead of JSONDecodeError" % ex)

try:
    load('{"Common": {"ButtonRadius": 1}, // last\n}')
    check("a trailing comment plus trailing comma still parses", True)
except Exception as ex:  # noqa: BLE001
    check("a trailing comment plus trailing comma still parses", False,
          str(ex))

# --- 5. the loader's Common semantics are unchanged ---------------------
#  a key inside "Common" that is not a slot is a colour-parser concern, not
#  a comment concern -- it is normalized away, as native's memset does.
got = load('{"Common": {"ButtonRadius": 9, "WindowBorderRadius": 7, '
           '"NoSuchSlot": 5}}')
check("a non-slot key inside Common is normalized away",
      "NoSuchSlot" not in got["Common"], repr(got["Common"]))
check("ButtonRadius is passed through as parsed",
      got["Common"]["ButtonRadius"] == 9, repr(got))
check("WindowBorderRadius>3 leaves the memset 0",
      got["Common"]["WindowBorderRadius"] == 0, repr(got))
check("an unmentioned Common slot is still populated",
      set(T.COMMON_SLOTS) <= set(got["Common"]),
      repr(sorted(got["Common"])))

# ...but a non-Common SECTION survives untouched: the theme's palette is
# the whole point of the file.
got = load('{"Common": {"ClientBackColor": "ff"}, '
           '"Window": {"Normal": {"Back": "1586bb"}}, '
           '"Custom": {"x": 1} // trailing\n}')
check("the Window section is carried through verbatim",
      got["Window"] == {"Normal": {"Back": "1586bb"}}, repr(got))
check("an arbitrary top-level section survives",
      got.get("Custom") == {"x": 1}, repr(got))

if failures:
    print("FAIL %d/%d" % (len(failures), count[0]))
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("regress_theme_loader_jsonc: all checks ok (%d assertions)"
      % count[0])
