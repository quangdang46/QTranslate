"""UI language packs — port of Locales/*/lang.json loading (FUN_0045B716 path).

Pack layout (7 keys): Author, LanguageName, LanguageNativeName, LanguageCode,
Strings (36 UI strings), Windows (14 dialog titles), Menus (10 menu labels).
35 languages ship with QTranslate; Vietnamese (vi) verified loadable.
"""
import glob
import json
import os

LOCALES_DIR = "C:/Program Files (x86)/QTranslate/Locales"


def list_locales(locales_dir: str = LOCALES_DIR) -> list:
    out = []
    for p in glob.glob(os.path.join(locales_dir, "*", "lang.json")):
        try:
            d = json.load(open(p, encoding="utf-8-sig"))
            out.append((d.get("LanguageName", "?"), d.get("LanguageCode", "?")))
        except (OSError, ValueError):
            pass
    return sorted(out)


def load_pack(name: str, locales_dir: str = LOCALES_DIR) -> dict:
    with open(os.path.join(locales_dir, name, "lang.json"),
              encoding="utf-8-sig") as f:
        return json.load(f)


def t(pack: dict, section: str, index: int, default: str = "") -> str:
    """Get string #index from a section list (Strings/Windows/Menus)."""
    try:
        return pack[section][index]
    except (KeyError, IndexError, TypeError):
        return default


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(len(list_locales()), "locales")
    vi = load_pack("Vietnamese")
    print(vi["LanguageNativeName"], t(vi, "Strings", 0)[:40])
