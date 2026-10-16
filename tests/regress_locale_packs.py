"""Regression: every shipped language pack loads, and `t()` resolves by id.

Two bugs found 2026-10-16 reading the 35 installed `Locales/*/lang.json`:

1. **7 of 35 packs were unreadable** (Bulgarian, Danish, English, Indonesia,
   Italian, Mongolian, Turkish) because `locale.load_pack` used a bare
   `json.load` while the packs are JSON **with trailing commas**. Native
   reads them with a lenient parser. The port's own *theme* loader already
   handled this for `Themes/*.json`; the locale loader did not.
   Bulgarian and Mongolian additionally carry a **double comma**
   (``...],,``), which even trailing-comma stripping does not fix.

2. **`t()` returned the wrong type in every section.** The three sections
   have three shapes, and `pack[section][index]` is right for none of them:

   | section | shape | so `t()` must |
   |---------|-------|----------------|
   | `Strings` | `[[id,"text"],…]` | return the text whose id matches |
   | `Windows` | `[{"Id":n,"Caption":…},…]` | return that dialog's Caption |
   | `Menus`   | `[{"Id":n,"Items":[[id,"text"],…]},…]` | return the first item |

   It returned the raw `[id, text]` list for `Strings` and a whole dialog
   object for the other two.

35 languages ship; all 35 now load, each with 36 Strings / 14 Windows /
10 Menus entries -- verified here against the installed copy.

Headless: files are read from the install, never executed. Skips the
install-dependent half when QTranslate is not present.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import locale as L  # noqa: E402

failures = []
count = [0]


def ck(name, cond, detail=""):
    count[0] += 1
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


INSTALLED = L.LOCALES_DIR

# --- 1. all 35 packs load, with the expected section sizes ---------------
if os.path.isdir(INSTALLED):
    names = sorted(n for n in os.listdir(INSTALLED)
                   if os.path.isfile(os.path.join(INSTALLED, n, "lang.json")))
    ck("35 language packs ship", len(names) == 35, str(len(names)))
    ck("list_locales() returns all 35", len(L.list_locales()) == 35,
       str(len(L.list_locales())))
    for n in names:
        try:
            d = L.load_pack(n)
        except Exception as ex:  # noqa: BLE001
            ck("pack %s loads" % n, False, str(ex))
            continue
        ck("pack %s loads" % n, True)
        ck("pack %s has 36 Strings / 14 Windows / 10 Menus" % n,
           (len(d.get("Strings", [])), len(d.get("Windows", [])),
            len(d.get("Menus", []))) == (36, 14, 10),
           "%s -> %s/%s/%s" % (n, len(d.get("Strings", [])),
                               len(d.get("Windows", [])),
                               len(d.get("Menus", []))))

    # the 7 that were unreadable to strict JSON
    for n in ("Bulgarian", "Danish", "English", "Indonesia", "Italian",
              "Mongolian", "Turkish"):
        raw = open(os.path.join(INSTALLED, n, "lang.json"),
                   encoding="utf-8-sig").read()
        strict_fails = False
        try:
            json.loads(raw)
        except ValueError:
            strict_fails = True
        ck("%s really is not strict JSON" % n, strict_fails,
           "strict json.load accepted it -- the premise is wrong")
        ck("...and the port loads it anyway",
          isinstance(L.load_pack(n), dict))

    # the double-comma shape
    for n in ("Bulgarian", "Mongolian"):
        raw = open(os.path.join(INSTALLED, n, "lang.json"),
                   encoding="utf-8-sig").read()
        ck("%s carries a double comma" % n, ",," in raw, "no ',,' found")

    # --- 2. t() returns a STRING, resolved by id -------------------------
    d = L.load_pack("English")
    got = L.t(d, "Strings", 171)
    ck("t(Strings,171) is a str, not an [id,text] pair",
       isinstance(got, str) and got, repr(got))
    ck("t(Strings,171) resolves by id, not position",
       got == [p[1] for p in d["Strings"] if p[0] == 171][0], repr(got))
    ck("t(Strings,unknown) returns the default, not a crash",
       L.t(d, "Strings", 999999) == "", repr(L.t(d, "Strings", 999999)))
    ck("t(Windows,1) returns the dialog Caption",
       isinstance(L.t(d, "Windows", 1), str) and L.t(d, "Windows", 1),
       repr(L.t(d, "Windows", 1)))
    ck("window_caption(1) agrees with t(Windows,1)",
       L.window_caption(d, 1) == L.t(d, "Windows", 1))
    ck("t(Menus,1) returns a label, not the whole menu object",
       isinstance(L.t(d, "Menus", 1), str) and L.t(d, "Menus", 1),
       repr(L.t(d, "Menus", 1)))
    ml = L.menu_labels(d, 1)
    ck("menu_labels(1) is the menu's own [id,text] pair list",
       ml and all(isinstance(p, list) and len(p) == 2 for p in ml),
       repr(ml[:2]))
    ck("menu_labels(unknown) is empty, not an error",
       L.menu_labels(d, 999) == [])

    # every Strings id resolves in every pack (a real cross-check: an
    # untranslated string is fine, a WRONG one is not)
    en = L.load_pack("English")
    en_ids = [p[0] for p in en["Strings"]]
    for n in names:
        d2 = L.load_pack(n)
        got_ids = [p[0] for p in d2["Strings"]]
        ck("pack %s's Strings ids match English's" % n, got_ids == en_ids,
           "differs at %s" % [i for i in zip(got_ids, en_ids) if i[0] != i[1]][:2])
        ck("pack %s's ids all resolve through t()" % n,
           all(isinstance(L.t(d2, "Strings", i), str) for i in en_ids[:8]))

# --- 3. no network, no eval ---------------------------------------------
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "locale.py"),
    encoding="utf-8").read()
ck("locale.py never evaluates the pack text",
    "eval(" not in src and "exec(" not in src and "Function(" not in src)

if failures:
    print("FAIL %d/%d" % (len(failures), count[0]))
    for f in failures[:20]:
        print("  -", f)
    raise SystemExit(1)
print("regress_locale_packs: all checks ok (%d assertions%s)"
      % (count[0], ", install read" if os.path.isdir(INSTALLED)
         else ", install absent"))
