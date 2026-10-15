"""Theme palettes — port of Themes/*.json + FUN_0044FE1B state selection.

Theme files define per-state colors (Normal/Disabled/Hover/Pressed) as hex
strings for Window/WindowButton/Button sections. State indices match the
native selector: 0 empty/normal, 1 has-text/hover, 3 disabled, 4 focused
(FUN_0044FE1B); 2 = pressed for buttons (FUN_0044D502).
"""
import glob
import json
import os

THEMES_DIR = "C:/Program Files (x86)/QTranslate/Themes"


def _hex(v: str) -> str:
    """Normalise a colour string to `#rrggbb`, or `""` when unparseable.

    Mirrors `FUN_0046457a` (THEME_LOADER_AND_BGR_RETRACTION_2026-10-11.md §1):
    accepts 1/2/3/6 hex digits, anything else → `0xffffffff`. The port's
    sentinel is `""` (falsy), which `slot()` maps to `UNSET` — so a malformed
    value never reaches the renderer as a colour.
    """
    v = (v or "").strip()
    if not v:
        return ""
    v = v.lstrip("#")
    if v.strip("0123456789abcdefABCDEF") or len(v) not in (1, 2, 3, 6):
        return ""
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
    theme = json.loads(text)
    theme["Common"] = _normalize_common(theme.get("Common", {}))
    return theme


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

    `theme::DefaultColorTheme` (`FUN_0044c9a6`) sets its radii, then writes
    five five-dword colour records. Two of the five are entirely
    `GetSysColor`-derived and one more is a copy of an earlier record:

    | record | source |
    |---|---|
    | `Window/Normal` | `BTNFACE`, `3DDKSHADOW`+0x14 via `FUN_0044a163`, `BTNHIGHLIGHT`, `WINDOWTEXT`, `0xffffffff` |
    | `Window/Disabled` | same family, no compiled constant |
    | `WindowButton/Normal` | `#191919`, `#5e5e5e`, `#f9f9f9` |
    | `WindowButton/Hover` | `#393939`, `#7e7e7e`, `#ffffff` |
    | `WindowButton/Pressed` | `#111111`, `#383838`, `#c1c1c1` |

    Those three dwords per state are the `WindowButton` record's own first
    three slots in order — `Gleam`, `Main`, `Shadow` (`FUN_0046485e`) — so
    they are stored under those names, not under `Window`'s `Back`/`Text`/
    `Border`. `Back` and `Border` are absent for every state here.

    So the **window is entirely runtime state and the buttons are entirely
    compiled constants** — which is why this function carries the greys and
    deliberately has no `Window` section. Claiming window values here would
    mean inventing the host's Win32 palette.

    The unset window slots flow out of `state_colors` as `None`, and
    `tk_colors` projects them onto Tk's own system colours — the nearest
    equivalent a non-Windows host can supply, and the same *intent*
    (paint with the platform, not with a hardcoded guess).
    """
    g = ["#%06x" % v for v in DEFAULT_THEME_GRAYS]
    return {
        "Common": {"ButtonRadius": 2, "WindowBorderRadius": 1},
        "WindowButton": {
            "Normal": {"Gleam": g[0], "Main": g[1], "Shadow": g[2]},
            "Hover": {"Gleam": g[3], "Main": g[4], "Shadow": g[5]},
            "Pressed": {"Gleam": g[6], "Main": g[7], "Shadow": g[8]},
        },
    }


def active_theme(name: str, themes_dir: str = THEMES_DIR) -> dict:
    """Theme file if one loads, `DefaultColorTheme` otherwise (`FUN_0044b44f`).

    Never returns `None`: native always has an active colour theme object.
    """
    theme = load_theme_native(name, themes_dir)
    return default_theme() if theme is None else theme


# FUN_00464c2f reads each section through its OWN getter, so each section has
# its own key names AND its own record width. Applying one tuple to all of
# them is only correct for Window -- verified against the seven themes, the
# port could not read 16 of WindowButton's 22 values, 35 of Button's 49,
# or 8 of Edit's 26.
#
#   section       getter         record   slots
#   Window        FUN_0046477d   5 dwords Back, Text, Border, BorderInner, Caption
#   WindowButton  FUN_0046485e   5        Gleam, Main, Shadow, Back, Border
#   Button        FUN_0046493f   8        ShadowTop, Border, GleamTop, BackTop,
#                                          BackBottom, GleamBottom, ShadowBottom, Text
#   Edit          FUN_00464aa4   5        ShadowTop, Border, Back, ShadowBottom, Text
_STATE_SLOTS = ("Back", "Text", "Border", "BorderInner", "Caption")
SECTION_SLOTS = {
    "Window": _STATE_SLOTS,
    "WindowButton": ("Gleam", "Main", "Shadow", "Back", "Border"),
    "Button": ("ShadowTop", "Border", "GleamTop", "BackTop", "BackBottom",
               "GleamBottom", "ShadowBottom", "Text"),
    "Edit": ("ShadowTop", "Border", "Back", "ShadowBottom", "Text"),
}

# Button/Text and Edit/Text are the two slots that do NOT stay at
# FUN_00464724's 0xffffffff when absent: each does
# `if (uVar1 == 0xffffffff) uVar1 = GetSysColor(COLOR_BTNTEXT)`, so the
# port substitutes Tk's button-text colour rather than reporting unset.
_SYSCOLOR_TEXT = {("Button", "Text"), ("Edit", "Text")}

# The loader's Common reader is not one of the colour record getters. It uses
# FUN_00440942 (hex string -> int) for ButtonRadius and WindowBorderRadius,
# FUN_00464724 (hex -> 0xffffffff on fail) for ClientBackColor,
# GroupBoxColor and GroupBoxHighlightColor, and FUN_00440921 (int, 0 when
# absent) for PaintClassicFocus. And the semantics are not the colour ones:
# ButtonRadius is clamped to >= 0; WindowBorderRadius is written only when the
# value is <= 3 (0x464d5d: CMP EAX,0x3 / JA skips the store), so a value of 4
# or more keeps the default rather than being applied — the opposite of the
# colour slots, where an absent key yields 0xffffffff. ClientBackColor /
# GroupBoxColor / GroupBoxHighlightColor are plain #RRGGBB, not BGR.
# PaintClassicFocus is an int/bool, not a colour. Common is flat, not per-state.
COMMON_SLOTS = ("ButtonRadius", "WindowBorderRadius", "ClientBackColor",
                "GroupBoxColor", "GroupBoxHighlightColor", "PaintClassicFocus")


def _normalize_common(record: dict) -> dict:
    """The loader's Common section, with the loader's own semantics.

    Native fills the theme object with 0 (FUN_004654ca) and then writes only
    the keys that are present in the file, through its own getters.
    """
    out = {}
    for k in COMMON_SLOTS:
        raw = record.get(k)
        if raw is None:
            out[k] = 0
            continue
        if k == "ButtonRadius":
            out[k] = max(int(str(raw).strip()), 0)
        elif k == "WindowBorderRadius":
            # Only 0..3 reach the field (unsigned-above at 0x464d5d); 4+ skips
            # the store, and the object was memset to 0 before the loader ran,
            # so an out-of-range value leaves the field at its cleared value.
            v = int(str(raw).strip())
            out[k] = v if 0 <= v <= 3 else 0
        elif k == "PaintClassicFocus":
            # Native writer emits the strings "True"/"False" (or an empty/absent
            # key => 0). No bool() coercion of the raw JSON type — the file
            # stores it as text.
            v = str(raw).strip()
            out[k] = (v.lower() not in ("", "false", "0", "no"))
        else:  # colour ints
            body = str(raw).strip().lstrip("#")
            if body.strip("0123456789abcdefABCDEF") or len(body) not in (1, 2, 3, 6):
                out[k] = 0xffffffff  # the 0xffffffff => GetSysColor(COLOR_BTNFACE) path
            else:
                out[k] = int(body, 16)
    return out


def _state(theme, section: str, state: str) -> dict:
    """One state's colour record, with native's inherit-from-Normal fallback.

    `FUN_00464c2f` copies the whole record from `Normal` when the requested
    state's key is absent, so an omitted `Disabled`/`Hover`/`Pressed` is
    rendered with `Normal`'s values rather than with nothing. The copy is a
    whole-record move -- five dwords for Window/WindowButton/Edit, **eight**
    for Button, whose getter `FUN_0046493f` writes `param_3[0..7]` -- so every
    slot of that section inherits together, not just five of them.

    Measured: 20 section/state pairs are genuinely absent across the seven
    recovered themes, so this is the reachable path, not a defensive branch.

    The record width is taken from `SECTION_SLOTS` for this section, so the
    inherited dict always has the shape a consumer expects (see `slot()`).

    `None` is accepted and yields no slots — the *unthemed* state.
    `load_theme_native` returns `None` when there is no theme to apply, and
    native renders without theme values rather than raising.
    """
    if not isinstance(theme, dict):
        return {}
    keys = SECTION_SLOTS.get(section, _STATE_SLOTS)
    sec = theme.get(section, {})
    own = sec.get(state) or {}
    if state == "Normal":
        return own
    # inherit every slot of this section's record width from Normal;
    # an absent slot becomes UNSET rather than the empty-string/0 JSON
    # default, matching `FUN_00464724`'s behaviour on a copied record
    out = dict(own)
    normal = sec.get("Normal", {})
    for k in keys:
        out.setdefault(k, normal.get(k, UNSET))
    return out


def state_colors(theme, section: str, state: str = "Normal") -> dict:
    """One section/state's colour slots, `None` where unset.

    Uses each section's own slot list from `SECTION_SLOTS`, because native
    reads WindowButton through `FUN_0046485e` (Gleam/Main/Shadow/Back/Border)
    and Button through `FUN_0046493f` (eight keys) — applying Window's names to
    those read nothing at all.

    Uses `slot()`, so an unparseable or absent value is reported as `None`
    rather than as a colour. `Button/Text` and `Edit/Text` are the two
    exceptions: their getters substitute `GetSysColor(COLOR_BTNTEXT)` for the
    absent case, so those two report Tk's button-text colour instead of `None`.
    """
    keys = SECTION_SLOTS.get(section, _STATE_SLOTS)
    rec = _state(theme, section, state)
    out = {}
    for k in keys:
        value = slot(rec, k)
        if value is None and (section, k) in _SYSCOLOR_TEXT:
            value = TK_UNSET["text"]
        out[k] = value
    return out


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
    """Colors for the window buttons — same inheritance rule.

    `WindowButton` has **no `Text` key**: `FUN_0046485e` fills five slots in
    order, `Gleam, Main, Shadow, Back, Border`, where `Main` is the button's
    own face and `Gleam`/`Shadow` are its highlight and shade. So `back` is
    `Main`, `border` is `Shadow`, and `text` is `Back` — the only remaining
    slot, which is `None` for the three themes that define their buttons with
    `Main`/`Shadow` alone. Those `None`s flow on to `tk_colors` rather than
    becoming a colour the theme never named.

    Field alignment with `DefaultColorTheme` confirms the slot order:
    `FUN_00464c2f` writes the four `WindowButton` states at byte offsets
    0x44/0x58/0x6c/0x80 of the theme object, and `FUN_0044c9a6`'s nine greys
    land at exactly 0x44..0x4c, 0x58..0x60 and 0x6c..0x74 — the first three
    dwords of each state, i.e. `Gleam`, `Main`, `Shadow`, leaving `Back` and
    `Border` unset. `theme::DefaultColorTheme` and `common::ColorThemeFile`
    are both 0x1d0 bytes with the same constructor, so the two layouts are the
    same object and the indices are directly comparable.
    """
    c = state_colors(theme, "WindowButton", state)
    return {"back": c["Main"], "text": c["Back"], "border": c["Shadow"]}


# Native's own "no colour from the theme" rendering. `FUN_00464c2f` leaves the
# value unset and the caller paints with the system colour — it is not black,
# and painting black would invent a value native never had.
TK_UNSET = {"back": "SystemButtonFace", "text": "SystemWindowText",
            "border": "SystemButtonFace"}


# Native state indices → theme state names. From FUN_0044FE1B
# (window: disabled → 3, focused → 4, has-text → 1, empty → 0) and
# FUN_0044D502 (buttons: pressed → 2). Index 0 is Normal in both.
STATE_NAMES = {0: "Normal", 1: "Hover", 2: "Pressed", 3: "Disabled",
               4: "Normal"}


def state_name(index: int) -> str:
    """Theme state name for a native state index.

    Index 4 (focused) maps to Normal: native keeps a separate focus
    flag (focus-rect via BM_GETSTATE bit0 in FUN_0044D3C3), not a
    separate palette — the palette lookup uses the Normal record.
    """
    return STATE_NAMES.get(int(index), "Normal")


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

    Native (decompiled 2026-10-15): ColorRGBToHLS -> ``L2 = L + delta``;
    if ``L2 < 1`` -> black; elif ``L2 >= 0xF0`` -> white; **elif
    ``L2 != L`` -> ColorHLSToRGB, else the ORIGINAL colour is returned
    unchanged**. That last branch matters: a zero delta must be a true
    identity. The earlier port always round-tripped through HLS, so
    ``adjust_brightness(c, 0)`` drifted real colours (e.g. ``#4285f4`` ->
    ``#4083f3``) — a hue-preserving but value-shifting error the native
    code explicitly avoids.
    """
    import colorsys
    h = rgb_hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    l256 = int(ll * 240)
    l2 = l256 + delta
    if l2 < 1:
        return "#000000"
    if l2 >= 0xF0:
        return "#ffffff"
    if l2 == l256:
        # Native: `if (uVar1 != L) ColorHLSToRGB(...)` — no shift, no
        # conversion. Return the input so a zero delta is exact.
        return "#" + h.lower()
    r2, g2, b2 = colorsys.hls_to_rgb(hh, l2 / 240.0, ss)
    return "#{:02x}{:02x}{:02x}".format(int(r2 * 255), int(g2 * 255),
                                        int(b2 * 255))


if __name__ == "__main__":
    print(list_themes())
    print(window_colors(load_theme("Flat Dark")))
    print(window_colors(load_theme("Flat Dark"), "Disabled"))
