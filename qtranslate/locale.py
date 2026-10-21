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

Not every pack is well-formed: all 35 carry **trailing commas**, and 7
(Bulgarian, Danish, English, Indonesia, Italian, Mongolian, Turkish) were
unreadable to strict `json` before 2026-10-16 — they are read with the
trailing commas stripped, the same way `theme.load_theme_at` handles
`Themes/*.json`.
"""
import glob
import json
import os
import re

# The port ships the native locale packs, recovered from the QTranslate
# 6.10.0 installer payload and committed under `qtranslate/assets/locales/`
# (35 `lang.json` files, byte-identical to the installed
# `Locales/<dir>/lang.json`). The Windows install is only a fallback: with
# the path hardcoded to it, the port had NO locales off Windows.
#   docs/review/PAYLOAD_CHUNK_CENSUS_2026-10-15.md §3 (35/35 identical)
_BUNDLED_LOCALES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "assets", "locales")
LOCALES_DIR = (_BUNDLED_LOCALES if os.path.isdir(_BUNDLED_LOCALES)
               else "C:/Program Files (x86)/QTranslate/Locales")


def _read_pack(path: str) -> dict:
    """Read one ``lang.json``, tolerating what the packs actually contain.

    The shipped packs are JSON **with trailing commas** (all 35 have them
    -- e.g. Danish's Appearance dialog closes its ``Controls`` array with
    ``],`` before ``"Id": 14``). Native reads them with a lenient parser,
    so strict ``json.load`` rejects **7 of the 35 languages outright**:
    Bulgarian, Danish, English, Indonesia, Italian, Mongolian, Turkish.

    Strip the trailing commas before parsing, exactly as the theme loader
    does (``theme.load_theme_at``). ``//`` comments are not used in any
    pack, but the same reason applies, so this goes through the theme
    loader's quote-aware scanner rather than a second regex.
    """
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    from qtranslate.theme import _strip_jsonc
    text = _strip_jsonc(text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    # Bulgarian and Mongolian carry a DOUBLE comma ("...],,") -- a
    # hand-editing slip that is malformed even for a lenient parser, and
    # that no amount of trailing-comma stripping fixes. Dropping a whole
    # language over one redundant comma is a worse outcome than ignoring
    # it, so collapse runs of commas before the value they separate.
    text = re.sub(r",(\s*,)+\s*", ",", text)
    return json.loads(text)


def list_locales(locales_dir: str = LOCALES_DIR) -> list:
    out = []
    for p in glob.glob(os.path.join(locales_dir, "*", "lang.json")):
        try:
            d = _read_pack(p)
        except (OSError, ValueError):
            continue
        out.append((d.get("LanguageName", "?"), d.get("LanguageCode", "?")))
    return sorted(out)


def load_pack(name: str, locales_dir: str = LOCALES_DIR) -> dict:
    return _read_pack(os.path.join(locales_dir, name, "lang.json"))


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
