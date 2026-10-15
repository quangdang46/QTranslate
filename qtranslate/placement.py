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
# standard dialog baseunit for that font (7x15 px): 340*7/4 = 595 wide,
# 201*15/4 = 753 tall. This is the FIRST-RUN fallback only: once native
# saves a placement blob, place_main restores the saved rect instead.
# (The old "526x366" fallback was a stale pixel constant from another
# machine's saved placement — see
# docs/review/G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md. It matched neither
# the template (~595x753) nor this machine's real blob (530x430).)
TEMPLATE_GEOMETRY = "595x753"


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


def place_aux(widget, key: str, default: str) -> None:
    """Restore aux-window geometry from General.<key> blob (native
    WindowOptions/History/Dictionary/KeyboardPlacement); save on
    close via WM_DELETE_WINDOW hook."""
    try:
        from qtranslate import config as _C
        rc = decode_placement(
            _C.load().get("General", {}).get(key, ""))
    except Exception:
        rc = None
    if rc:
        x, y, w, h, _ = rc
        try:
            widget.geometry(f"{w}x{h}+{x}+{y}")
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
