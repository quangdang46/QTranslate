"""Font resolution — the pure part of `_pane_font` (row G Fonts).

Native: the main window uses the dialog font (`MS Shell Dlg`, which the
port approximates as Tahoma); `General.FontName`/`TextSize` override it.
The port's `_pane_font` reads the same two keys with a Tahoma/9 fallback
and a minimum-size clamp. This module factors that resolution out so the
fallback table is testable without Tk — `app._pane_font` keeps the same
contract and should stay in sync.
"""
from __future__ import annotations

DEFAULT_NAME = "Tahoma"  # approximates the native MS Shell Dlg
DEFAULT_SIZE = 9
MIN_SIZE = 6  # the clamp app._pane_font applies via max(6, size)

# macOS has no Tahoma; map to the closest system font. Windows keeps the
# native approximation. (Row G: "mac mapping".)
MAC_FALLBACK = "Helvetica"


def resolve_font(cfg_general=None, platform="win32", size_delta=0):
    """``(name, size)`` from a General section dict.

    Empty/missing FontName → the platform default; TextSize parses as
    int, falling back to 9 on garbage; the delta is added first and the
    result is clamped at MIN_SIZE (matching the old inline expression
    ``max(6, size + delta)``).
    """
    g = cfg_general or {}
    name = (g.get("FontName", "") or "").strip()
    if not name:
        name = MAC_FALLBACK if platform == "darwin" else DEFAULT_NAME
    try:
        size = int(g.get("TextSize", DEFAULT_SIZE))
    except Exception:
        size = DEFAULT_SIZE
    return name, max(MIN_SIZE, size + size_delta)
