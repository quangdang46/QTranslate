"""Window geometry: WINDOWPLACEMENT codec + restore helpers (Phase 2 slice).

Moved verbatim from ``qtranslate/app.py`` (2026-10-15). Pure stdlib
(``struct``/``json``/``re``) plus ``config`` — no tkinter import in this
module. The ``widget``/``root`` parameters are duck-typed (anything with
``.geometry()`` / ``.protocol()``), so Core/headless callers and tests
use fakes without a display.

Native evidence: ``FUN_00422DDD`` restores via ``GetWindowPlacement``
(checklist A7); ``FUN_0045869F`` maps the ``Window*Placement`` keys;
``FUN_004561F0`` saves them back.
"""
from __future__ import annotations


def decode_placement(hexs: str):
    """Decode a WINDOWPLACEMENT hex blob -> (x, y, w, h, showCmd).

    Layout: length, flags, showCmd, ptMin(2), ptMax(2), rcNormal(4)
    little-endian LONGs. Verified vs the real WindowMainPlacement blob
    (length=44, flags=0, show=1, ptMin=ptMax=(-1,-1); rcNormal varies
    per machine — e.g. 530x430 at (786,228) here).
    """
    try:
        import struct
        b = bytes.fromhex((hexs or "").strip())
        if len(b) < 44:
            return None
        _, _, show, _, _, _, _, l, t, r, bo = struct.unpack("<11i", b[:44])
        if r > l and bo > t:
            return (l, t, r - l, bo - t, show)
    except Exception:
        pass
    return None


def encode_placement(x: int, y: int, w: int, h: int,
                     show: int = 1) -> str:
    """Tk geometry -> WINDOWPLACEMENT hex blob.

    Matches the real `WindowMainPlacement` bytes, not a guessed
    WINDOWPLACEMENT: `length=44`, `flags=0`, and --- verified against the
    actual blob in Options.json (2026-10-15) --- `ptMin == (-1, -1)` and
    `ptMax == (-1, -1)` (`FFFFFFFF` pairs). The blob in Options.json reads
    `...01000000 FFFFFFFF FFFFFFFF FFFFFFFF FFFFFFFF 12030000...`, i.e.
    four -1 LONGs before rcNormal.
    """
    import struct
    return struct.pack("<11i", 44, 0, show, -1, -1, -1, -1,
                       x, y, x + w, y + h).hex().upper()


# Native DLG129 template size, 340x201 dialog units at MS Shell Dlg 8pt
# (docs/review/G9_SPEC_NATIVE_WINDOW_2026-10-10.md). Converted with the
# standard dialog baseunit for that font (7x15 px). The two axes use
# DIFFERENT divisors -- that is the whole trap: MapDialogRect converts
#   px_x = (du_x * avg_char_w) / 4
#   px_y = (du_y * char_h)     / 8
# so 340*7/4 = 595 wide but 201*15/8 = 376 tall. (An earlier revision of
# this comment divided BOTH by 4 and got 201*15/4 = 753 -- a window nearly
# twice as tall as native's. The arithmetic is pinned in
# tests/regress_placement.py; see G9_PART_A_CLOSED_2026-10-16.md §1.)
#
# This is the FIRST-RUN fallback only: once native saves a placement blob,
# place_main restores the saved rect instead.
# (The old "526x366" fallback was a stale pixel constant from another
# machine's saved placement — see
# docs/review/G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md. It matched neither
# the template (595x376) nor this machine's real blob (530x430).)
TEMPLATE_GEOMETRY = "595x376"

# The dialog templates in the EXE's .rsrc, in DIALOG UNITS, from
# `tools/dlg_parse.py`:
#
#   DLG129 QTranslate       340 x 201
#   DLG154 Options          429 x 223
#   DLG162 Virtual keyboard 308 x 102
#   DLG164 History          316 x 177
#   DLG184 Dictionary       316 x 185
#
# The main window's own template fixes the conversion (340 DU -> 595 px
# horizontally, 201 DU -> 376 px vertically), and every dialog template uses
# the same dialog font, so the same factor applies to all of them. The
# aux windows' first-run sizes were previously arbitrary pixel constants
# (the keyboard's was even the raw DU numbers used as pixels: 308x102).
#
# This is the FIRST-RUN fallback only: once native saves a placement blob,
# place_aux restores the saved rect instead.
DLG_TEMPLATES_DU = {
    "main": (340, 201),
    "options": (429, 223),
    "keyboard": (308, 102),
    "history": (316, 177),
    "dictionary": (316, 185),
}


def template_geometry(name: str) -> str:
    """A dialog template's size in pixels, as a Tk geometry string.

    Derived from the template's dialog units and the main window's own
    template, so the two cannot drift apart.
    """
    du_w, du_h = DLG_TEMPLATES_DU[name]
    main_w, main_h = (int(v) for v in TEMPLATE_GEOMETRY.split("x"))
    du_main_w, du_main_h = DLG_TEMPLATES_DU["main"]
    return "%dx%d" % (round(du_w * main_w / du_main_w),
                      round(du_h * main_h / du_main_h))


def place_main(root, template: str = TEMPLATE_GEOMETRY) -> None:
    """Restore main-window geometry from General.WindowMainPlacement;
    fall back to the native template size (no saved placement yet)."""
    try:
        from qtranslate import config as _C
        hexs = _C.load().get("General", {}).get("WindowMainPlacement",
                                                "")
        rc = decode_placement(hexs)
    except Exception:
        rc = None
    if rc:
        x, y, w, h, _ = rc
        try:
            root.geometry(f"{w}x{h}+{x}+{y}")
            return
        except Exception:
            pass
    root.geometry(template)


def place_aux(widget, key: str, default: str) -> tuple | None:
    """Restore aux-window geometry from General.<key> blob (native
    WindowOptions/History/Dictionary/KeyboardPlacement); save on
    close via WM_DELETE_WINDOW hook.

    Returns the placement that was applied -- (x, y, w, h) -- or None
    when there was no saved placement and the default was used. A window
    that sizes itself to its content (the virtual keyboard does, like
    native's) needs to know which of the two happened.
    """
    try:
        from qtranslate import config as _C
        rc = decode_placement(
            _C.load().get("General", {}).get(key, ""))
    except Exception:
        rc = None
    _applied = None
    if rc:
        x, y, w, h, _ = rc
        try:
            widget.geometry(f"{w}x{h}+{x}+{y}")
            _applied = (x, y, w, h)
        except Exception:
            widget.geometry(default)
    else:
        widget.geometry(default)
    try:
        widget.protocol("WM_DELETE_WINDOW")

        def _close():
            save_placement(key, widget)
            try:
                widget.destroy()
            except Exception:
                pass

        widget.protocol("WM_DELETE_WINDOW", _close)
    except Exception:
        pass
    return _applied


def save_placement(key: str, widget) -> None:
    """Persist a window's geometry into General.<key> blob."""
    try:
        from qtranslate import config as _C
        import json as _j
        g = widget.geometry()  # WxH+X+Y
        import re as _re
        m = _re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", g)
        if not m:
            return
        w, h, x, y = map(int, m.groups())
        full = _C.load()
        full.setdefault("General", {})[key] = encode_placement(x, y, w,
                                                               h)
        with open(_C.DEFAULT_PATH, "w", encoding="utf-8") as f:
            _j.dump(full, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
