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
    if len(v) == 3 and not len(set(v)) == 1:
        # CSS shorthand: abc -> aabbcc (but bbb stays grayscale bbbbbb)
        v = "".join(c * 2 for c in v)
    elif len(v) <= 2:  # grayscale shorthand used by QTranslate themes
        v = v * 3 if len(v) == 1 else v + v + v[:2]
    if len(v) == 3:  # grayscale triple -> full 6 digits for Tk
        v = v * 2
    return "#" + v[-6:]


def load_theme(name: str, themes_dir: str = THEMES_DIR) -> dict:
    """Theme files are JSONC (// comments) — strip them before parsing."""
    import re
    with open(os.path.join(themes_dir, name + ".json"),
              encoding="utf-8-sig") as f:
        text = f.read()
    text = re.sub(r"//[^\n]*", "", text)
    return json.loads(text)


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


def adjust_brightness(rgb_hex: str, delta: int) -> str:
    """Port of FUN_0044A163: RGB->HLS, shift L by delta, clamp, back.

    Native: ColorRGBToHLS -> L+=delta (clamp 1..0xF0, else black/white) ->
    ColorHLSToRGB. Used by themed fill (+/-10) for hover/pressed shading.
    """
    import colorsys
    h = rgb_hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    l256 = int(ll * 240) + delta
    if l256 < 1:
        return "#000000"
    if l256 >= 0xF0:
        return "#ffffff"
    r2, g2, b2 = colorsys.hls_to_rgb(hh, l256 / 240.0, ss)
    return "#{:02x}{:02x}{:02x}".format(int(r2 * 255), int(g2 * 255),
                                        int(b2 * 255))


if __name__ == "__main__":
    print(list_themes())
    print(window_colors(load_theme("Flat Dark")))
    print(window_colors(load_theme("Flat Dark"), "Disabled"))
