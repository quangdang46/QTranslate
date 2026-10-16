"""UI language packs — port of Locales/*/lang.json loading (FUN_0045B716 path).

Pack layout (7 keys): Author, LanguageName, LanguageNativeName, LanguageCode,
Strings, Windows, Menus. 35 languages ship with QTranslate.

The three sections have three DIFFERENT shapes, and getting this wrong is
easy because all three are JSON arrays:

| section | shape | a member is |
|---------|-------|-------------|
| `Strings` | `[[id, "text"], …]` | a 2-element **pair** — index is the string id |
| `Windows` | `[{"Id":n,"Caption":"…",…}, …]` | an **object** keyed by dialog id |
| `Menus` | `[{"Id":n,"Items":[[id,"text"],…]}, …]` | an **object** holding a pair list |

`t()` used to do ``pack[section][index]`` for all three, which returns the
wrong type in every case: a `[id, text]` list instead of the text for
`Strings`, and a whole dialog/menu object for the other two. Fixed
2026-10-16 to resolve by **id**, which is what the array position is not.

Not every pack parses: `English/lang.json` is truncated upstream (it ends
at `"Id": 10`), so `list_locales()` skips it rather than dropping every
language after it alphabetically.
"""
import glob
import json
import os

LOCALES_DIR = "C:/Program Files (x86)/QTranslate/Locales"


def list_locales(locales_dir: str = LOCALES_DIR) -> list:
    out = []
    for p in glob.glob(os.path.join(locales_dir, "*", "lang.json")):
        try:
            with open(p, encoding="utf-8-sig") as f:
                d = json.load(f)
            out.append((d.get("LanguageName", "?"), d.get("LanguageCode", "?")))
        except (OSError, ValueError):
            pass  # English/lang.json is truncated upstream (ends at Id:10)
    return sorted(out)


def load_pack(name: str, locales_dir: str = LOCALES_DIR) -> dict:
    with open(os.path.join(locales_dir, name, "lang.json"),
              encoding="utf-8-sig") as f:
        return json.load(f)


def t(pack: dict, section: str, index: int, default: str = "") -> str:
    """String ``index`` from ``section``, resolved by id.

    Handles all three shapes: a ``[id, text]`` pair list (`Strings`), an
    object list (`Windows`), and an object list whose members hold their
    own pair list (`Menus`). Falls back to ``default`` when the id is
    absent -- an untranslated string, not an error.
    """
    try:
        section_data = pack[section]
    except (KeyError, TypeError):
        return default

    # a pair list: [[id, text], ...]
    for member in section_data:
        if isinstance(member, list) and len(member) > 1 \
                and member[0] == index:
            return member[1]

    # an object list, optionally with its own pair list inside
    for member in section_data:
        if not isinstance(member, dict) or member.get("Id") != index:
            continue
        if section == "Windows":
            return member.get("Caption", default)
        # Menus: the object holds its own pair list, and `index` there is
        # a *string* id within that menu, not the menu object's Id.
        for pair in member.get("Items", ()):
            if isinstance(pair, list) and len(pair) > 1:
                return pair[1]
        return default
    return default


def window_caption(pack: dict, dialog_id: int, default: str = "") -> str:
    """The Caption of dialog ``dialog_id`` (the Windows section)."""
    for member in pack.get("Windows", ()):
        if isinstance(member, dict) and member.get("Id") == dialog_id:
            return member.get("Caption", default)
    return default


def menu_labels(pack: dict, menu_id: int) -> list:
    """The ``[id, text]`` pairs of menu ``menu_id`` (the Menus section)."""
    for member in pack.get("Menus", ()):
        if isinstance(member, dict) and member.get("Id") == menu_id:
            return list(member.get("Items", ()))
    return []


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    packs = list_locales()
    print(len(packs), "locales (of 35 shipped)")
    vi = load_pack("Vietnamese")
    print(vi["LanguageNativeName"], "|", t(vi, "Strings", 174))
    print("dialog 1 caption:", window_caption(vi, 1))
    print("menu 1 first label:", menu_labels(vi, 1)[0])
