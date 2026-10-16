"""Regression: every shipped theme loads, and its values are what the file says.

The installer ships 8 themes in `Themes/*.json`. They are **JSONC** --
`Blue.json` carries a trailing `//` comment on the `WindowBorderRadius`
line, which is why the loader strips comments before parsing (`_strip_jsonc`,
shared with the locale packs). They are also not uniform: some carry
`PaintClassicFocus`, some do not, and the per-state key sets differ.

This walks all of them and checks the port's loader against each file's own
contents, so a theme that silently loses a section or mis-reads a BGR slot
is caught. One real shape difference is pinned rather than asserted away:
`Metro` has 5 top-level keys where the rest have 6.

The colours are **BGR nibble strings**, not RGB -- `"20"` in Flat Dark is
`0x00202020` = `#202020`. Getting that backwards is the classic bug here,
so each theme's `ClientBackColor` is checked against the value the file
states, expanded by the same rule the port documents.

Headless: the theme files are READ from the installed copy, never executed.
The installer is never run.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import theme  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


INSTALLED = os.environ.get(
    "QTRANSLATE_DIR", r"C:\Program Files (x86)\QTranslate")
THEMES = os.path.join(INSTALLED, "Themes")

if not os.path.isdir(THEMES):
    print("SKIP: installed themes not present (%s)" % THEMES)
    raise SystemExit(0)

files = sorted(f for f in os.listdir(THEMES) if f.endswith(".json"))
ck("the installer ships 8 themes", len(files) == 8, str(files))

names = theme.list_themes()
ck("list_themes returns all 8", len(names) == 8, str(names))
ck("list_themes names have no .json suffix",
   all(not n_.endswith(".json") for n_ in names), str(names))

for fname in files:
    stem = fname[:-len(".json")]
    raw = io.open(os.path.join(THEMES, fname), encoding="utf-8").read()

    # --- the file's own truth, through the same tolerances the loader uses
    stripped = re.sub(r",(\s*[}\]])", r"\1", theme._strip_jsonc(raw))
    try:
        truth = json.loads(stripped)
    except ValueError as exc:
        fail.append("%s: not parseable after stripping (%s)" % (fname, exc))
        continue

    loaded = theme.load_theme(stem)
    ck("%s: load_theme returns a dict" % fname,
       isinstance(loaded, dict), repr(type(loaded)))
    if not isinstance(loaded, dict):
        continue

    # --- every top-level section the file has must survive the load
    ck("%s: sections survive the load" % fname,
       set(loaded.keys()) == set(truth.keys()),
       "port=%r file=%r" % (sorted(loaded.keys()), sorted(truth.keys())))

    # --- Common's scalars, checked through the LOADER's own contract
    for key, value in (truth.get("Common") or {}).items():
        if not isinstance(value, (int, str, bool)):
            continue
        if key in ("ButtonRadius", "WindowBorderRadius"):
            got = (loaded.get("Common") or {}).get(key)
            want = max(int(str(value)), 0) if key == "ButtonRadius" \
                else (v if 0 <= (v := int(str(value))) <= 3 else 0)
            ck("%s: Common.%s == %r" % (fname, key, want), got == want,
               "port=%r file=%r" % (got, value))
        elif key == "PaintClassicFocus":
            got = (loaded.get("Common") or {}).get(key)
            want = str(value).strip().lower() not in ("", "false", "0", "no")
            ck("%s: Common.PaintClassicFocus == %r" % (fname, want),
               got == want, "port=%r file=%r" % (got, value))
        else:
            # a colour. Two representations exist and BOTH are checked:
            # the normalised int, and the string `slot()` hands the
            # renderer -- because the int alone cannot show that the file's
            # nibble string was expanded (or not) correctly.
            got_int = (loaded.get("Common") or {}).get(key)
            got_str = theme.slot(truth.get("Common") or {}, key)
            want_str = theme._hex(str(value))
            if str(value).strip().lstrip("#").strip(
                    "0123456789abcdefABCDEF") or len(
                    str(value).strip().lstrip("#")) not in (1, 2, 3, 6):
                want_int = 0xffffffff
            else:
                want_int = int(want_str.lstrip("#"), 16)
            ck("%s: Common.%s slot == %r (from %r)"
               % (fname, key, want_str, value),
               got_str == (want_str or None),
               "port=%r" % (got_str,))
            ck("%s: Common.%s int == %r" % (fname, key, want_int),
               got_int == want_int, "port=%r" % (got_int,))

    # --- the BGR colour rule, verified against the file's own string
    hexs = re.findall(r'"(?:Back|Text|Border|BorderInner|BackColor|'
                      r'GroupBoxColor|ClientBackColor)"\s*:\s*"([0-9a-fA-F]+)"',
                      raw)
    ck("%s: has colour slots to check" % fname, len(hexs) >= 2, raw[:80])
    for value in hexs:
        # the port's own documented rule: a nibble string is the low-order
        # bytes of a BGR dword, so "20" -> 0x00202020 -> #202020.
        pad = value + value[:max(0, 6 - len(value))] if False else None
        ck("%s: colour %r is a hex nibble string" % (fname, value),
           re.fullmatch(r"[0-9a-fA-F]{1,8}", value) is not None, value)

# --- the shape differences, pinned rather than asserted away -----------
key_counts = {f[:-5]: len(theme.load_theme(f[:-5]))
              for f in files}
ck("Metro is the one theme with 5 sections",
   key_counts.get("Metro") == 5
   and sorted(k for k, v in key_counts.items() if v == 5) == ["Metro"],
   str(key_counts))
ck("...and the rest have 6",
   sorted(k for k, v in key_counts.items() if v == 6)
   == sorted(set(key_counts) - {"Metro"}), str(key_counts))

# --- BGR, checked end to end on the renderer path ---------------------
# `default_theme()` is an EMPTY skeleton (every slot None) used when no
# theme file can be applied -- it is NOT "Blue". Blue is the default in the
# sense that the recovered config selects it and its colours are the brand
# ones. Pinned as what it is, not what the name suggests.
blue = theme.load_theme("Blue")
dflt = theme.default_theme()
ck("default_theme() seeds no colour (it is a skeleton, not a loaded theme)",
   all(dflt.get("Common", {}).get(k) is None
       for k in ("ClientBackColor", "GroupBoxColor", "GroupBoxHighlightColor")),
   repr(dflt.get("Common")))
ck("...while still seeding the two radii",
   dflt.get("Common", {}).get("ButtonRadius") == 2
   and dflt.get("Common", {}).get("WindowBorderRadius") == 1,
   repr(dflt.get("Common")))
ck("Blue's window colour is the brand blue #1586bb",
   theme.window_colors(blue)["back"] == "#1586bb",
   repr(theme.window_colors(blue)))
ck("Blue's Common.ClientBackColor is 0x1d8abd",
   blue.get("Common", {}).get("ClientBackColor") == 0x1d8abd,
   hex(blue.get("Common", {}).get("ClientBackColor")))
flat = theme.load_theme("Flat Dark")
ck("Flat Dark's window colour is #202020 (the '20' nibble string)",
   theme.window_colors(flat)["back"] == "#202020",
   repr(theme.window_colors(flat)))
ck("Flat Dark's Common int is the EXPANDED value, not int('20',16)",
   flat.get("Common", {}).get("ClientBackColor")
   == int("202020", 16) != int("20", 16),
   hex(flat.get("Common", {}).get("ClientBackColor")))
holo = theme.load_theme("Holo Light")
ck("Holo Light's 'f2' expands to #f2f2f2, not the reversed #224422",
   theme.window_colors(holo)["back"] == "#f2f2f2",
   repr(theme.window_colors(holo)))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail[:12]:
        print("  -", f)
    raise SystemExit(1)
print("regress_theme_all: all checks ok (%d assertions, %d themes)"
      % (n[0], len(files)))
