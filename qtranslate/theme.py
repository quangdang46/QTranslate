"""Theme palettes — port of Themes/*.json + FUN_0044FE1B state selection.

Theme files define per-state colors (Normal/Disabled/Hover/Pressed) as hex
strings for Window/WindowButton/Button sections. State indices match the
native selector: 0 empty, 1 has-text, 3 disabled, 4 focused.
"""
import glob
import json
import os

THEMES_DIR = "C:/Program Files (x86)/QTranslate/Themes"


def _hex(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return "#000000"
    v = v.lstrip("#")
    if len(v) <= 2:  # grayscale shorthand used by QTranslate themes
        v = v * 3 if len(v) == 1 else v + v + v[:2]
    return "#" + v[-6:]


def load_theme(name: str, themes_dir: str = THEMES_DIR) -> dict:
    with open(os.path.join(themes_dir, name + ".json"),
              encoding="utf-8-sig") as f:
        return json.load(f)


def list_themes(themes_dir: str = THEMES_DIR) -> list:
    return sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(themes_dir, "*.json")))


def window_colors(theme: dict, state: str = "Normal") -> dict:
    """Hex colors for the popup window in a given state (Normal/Disabled)."""
    w = theme.get("Window", {}).get(state, {})
    return {"back": _hex(w.get("Back", "")),
            "text": _hex(w.get("Text", "")),
            "border": _hex(w.get("Border", ""))}


if __name__ == "__main__":
    print(list_themes())
    print(window_colors(load_theme("Flat Dark")))
    print(window_colors(load_theme("Flat Dark"), "Disabled"))
