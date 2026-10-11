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


UNSET = None
"""`FUN_00464724` returns `0xffffffff` for an absent or unparseable colour.

Native's sentinel is not black: it is an out-of-range COLORREF, which the
renderers treat as "no colour from the theme". `_hex("")`'s `#000000` is
therefore not equivalent, so `slot()` reports absence instead of hiding it.
"""


def slot(record: dict, key: str):
    """One theme colour slot: a `#rrggbb` string, or None when unset.

    Mirrors `FUN_00464724`'s absent-key `0xffffffff` and its `0xffffffff`
    for a string `FUN_0046457a` cannot parse. `_hex` on its own would turn
    `"xyz"` into `"#xxyyzz"` — six characters that reach the renderer as a
    colour — so the guard has to live here.
    """
    if not isinstance(record, dict):
        return UNSET
    raw = record.get(key)
    if raw is None:
        return UNSET
    text = str(raw).strip()
    if not text:
        return UNSET
    body = text.lstrip("#")
    if body.strip("0123456789abcdefABCDEF") or len(body) not in (1, 2, 3, 6):
        return UNSET
    return _hex(text)


def load_theme_at(path: str) -> dict:
    """Load an already-located theme file (JSONC + trailing commas)."""
    import re
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def load_theme(name: str, themes_dir: str = THEMES_DIR) -> dict:
    """Theme files are JSONC (// comments) — strip them before parsing.

    Trailing commas are also stripped: the native writer emits them, so a
    hand-edited file can contain what `json` rejects.
    """
    return load_theme_at(os.path.join(themes_dir, name + ".json"))


def list_themes(themes_dir: str = THEMES_DIR) -> list:
    return sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(themes_dir, "*.json")))


def load_theme_native(name: str, themes_dir: str = THEMES_DIR) -> dict | None:
    """`FUN_00464c2f`'s file loader: `None` when no theme file can be applied.

    Native builds `<dir>\\<ThemeName>.json`, checks it exists, parses it, and
    on any failure returns 0. `ThemeName == ""` is normal — the *file* stage
    simply produces nothing.

    Returns `None` for "no theme file" only. It is **not** the fallback
    palette: native's factory `FUN_004654ca` returns NULL on failure and its
    caller `FUN_0044b44f` then installs `theme::DefaultColorTheme`, a
    `GetSysColor`-derived palette. Use `active_theme()` for the full
    "theme or default" behaviour.
    """
    if not name:
        return None
    path = os.path.join(themes_dir, name + ".json")
    if not os.path.exists(path):
        return None
    try:
        return load_theme_at(path)
    except (OSError, ValueError):
        return None


# theme::DefaultColorTheme's hardcoded slots (FUN_0044c9a6). All are
# achromatic; the rest of that object is GetSysColor() plus FUN_0044a163
# derivatives of those system colours, which only exist at runtime.
DEFAULT_THEME_GRAYS = (0x191919, 0x5e5e5e, 0xf9f9f9, 0x393939,
                       0x7e7e7e, 0xffffff, 0x111111, 0x383838, 0xc1c1c1)


def default_theme() -> dict:
    """The palette native installs when no theme file loads.

    `theme::DefaultColorTheme` (`FUN_0044c9a6`) sets its radii, then takes the
    user's Windows system colours — `COLOR_BTNFACE`, `COLOR_BTNHIGHLIGHT`,
    `COLOR_3DDKSHADOW`, `COLOR_WINDOWTEXT`, `COLOR_GRAYTEXT`, `COLOR_WINDOW` —
    and derives the remaining slots from those through `FUN_0044a163`, our
    `adjust_brightness`.

    Only its hardcoded greys are reproducible here. The `GetSysColor` values
    are Windows runtime state this host cannot supply, so those slots stay
    unset and `None` flows out of `state_colors`, which `tk_colors` then
    projects onto Tk's own system colours — the nearest equivalent available.
    """
    g = ["#%06x" % v for v in DEFAULT_THEME_GRAYS]
    return {
        "Common": {"ButtonRadius": 2, "WindowBorderRadius": 1},
        # FUN_0044c9a6 writes [0x11..0x13] and [0x16..0x18] for the window
        # buttons, then repeats the same nine greys at [0x65..0x6d].
        "WindowButton": {
            "Normal": {"Back": g[0], "Text": g[2], "Border": g[1]},
            "Hover": {"Back": g[3], "Text": g[5], "Border": g[4]},
            "Pressed": {"Back": g[6], "Text": g[7], "Border": g[8]},
        },
    }


def active_theme(name: str, themes_dir: str = THEMES_DIR) -> dict:
    """Theme file if one loads, `DefaultColorTheme` otherwise (`FUN_0044b44f`).

    Never returns `None`: native always has an active colour theme object.
    """
    theme = load_theme_native(name, themes_dir)
    return default_theme() if theme is None else theme


_STATE_SLOTS = ("Back", "Text", "Border", "BorderInner", "Caption")


def _state(theme, section: str, state: str) -> dict:
    """One state's colour slots, with native's inherit-from-Normal fallback.

    `FUN_00464c2f` copies the whole record from `Normal` when the requested
    state's key is absent, so an omitted `Disabled`/`Hover`/`Pressed` is
    rendered with `Normal`'s values rather than with nothing. The copy is a
    five-dword struct move, so all five slots inherit together.

    Measured: 20 section/state pairs are genuinely absent across the seven
    recovered themes, so this is the reachable path, not a defensive branch.

    `None` is accepted and yields no slots — the *unthemed* state.
    `load_theme_native` returns `None` when there is no theme to apply, and
    native renders without theme values rather than raising.
    """
    if not isinstance(theme, dict):
        return {}
    sec = theme.get(section, {})
    own = sec.get(state) or {}
    if own or state == "Normal":
        return own
    return sec.get("Normal", {}) or {}


def state_colors(theme, section: str, state: str = "Normal") -> dict:
    """All five colour slots of one section/state, `None` where unset.

    Uses `slot()`, so an unparseable or absent value is reported as `None`
    rather than as a colour.
    """
    rec = _state(theme, section, state)
    return {k: slot(rec, k) for k in _STATE_SLOTS}


def window_colors(theme, state: str = "Normal") -> dict:
    """Colors for the popup window in a state — `None` where the theme has none.

    Inherits `Normal` per `_state`. An unset slot is `None` rather than
    `#000000` because `FUN_00464724` returns `0xffffffff`, and neither the
    renderer nor `adjust_brightness` can tell that apart from a real black.
    Pass the result through `tk_colors()` before handing it to Tk.
    """
    c = state_colors(theme, "Window", state)
    return {"back": c["Back"], "text": c["Text"], "border": c["Border"]}


def button_colors(theme, state: str = "Normal") -> dict:
    """Colors for the window buttons — same inheritance rule."""
    c = state_colors(theme, "WindowButton", state)
    return {"back": c["Back"], "text": c["Text"], "border": c["Border"]}


# Native's own "no colour from the theme" rendering. `FUN_00464c2f` leaves the
# value unset and the caller paints with the system colour — it is not black,
# and painting black would invent a value native never had.
TK_UNSET = {"back": "SystemButtonFace", "text": "SystemWindowText",
            "border": "SystemButtonFace"}


def tk_colors(colors: dict) -> dict:
    """`window_colors`/`button_colors` output made safe for Tk `bg=`/`fg=`.

    `state_colors` reports an unset slot as `None` because native's sentinel
    is `0xffffffff`, but `None` is not a Tk colour and the `app.py` callers
    pass these straight through at ~60 sites. Each `None` becomes the
    matching system colour here, which is what native paints when the theme
    supplies nothing.
    """
    return {k: (v if v is not None else TK_UNSET[k]) for k, v in colors.items()}


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
