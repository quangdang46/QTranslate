"""Measure the native main window's layout from its screenshot.

Reads `docs/review/native_screens/2131.png` (the native QTranslate 6.10.0 main
window) and reports the geometry of the surfaces the port has to reproduce:

  * the toolbar row (back/forward arrows + the service link)
  * the source text pane
  * the source pane's bottom-right icon buttons
  * the language/tool row (Auto-Detect | swap | target | Translate)
  * the result text pane
  * the service icon strip at the very bottom, and each cell's x extent

The measurement is by pixel, not by eye: a horizontal separator is a row whose
pixels are all the same colour across the pane width, and the icon strip is
the band of coloured (non-grey) pixels at the bottom.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g9)


def load(path):
    w, h, rgb = g9.png_decode(path)
    return w, h, rgb


def px(rgb, w, x, y):
    o = (y * w + x) * 3
    return rgb[o], rgb[o + 1], rgb[o + 2]


def row_profile(w, h, rgb, x0=0, x1=None):
    """Per row: (unique_colour_count, mean_luma, max_saturation)."""
    if x1 is None:
        x1 = w
    prof = []
    for y in range(h):
        seen = set()
        luma = 0
        sat = 0
        for x in range(x0, x1):
            r, g, b = px(rgb, w, x, y)
            seen.add((r, g, b))
            luma += (r + g + b) // 3
            sat += max(r, g, b) - min(r, g, b)
        n = max(1, x1 - x0)
        prof.append((len(seen), luma // n, sat // n))
    return prof


def find_separators(prof, h, max_unique=3):
    """Rows that are nearly uniform across the width -- separators/borders."""
    out = []
    for y, (uniq, luma, sat) in enumerate(prof):
        if uniq <= max_unique and sat <= 8:
            out.append((y, luma))
    return out


def coloured_bands(w, h, rgb, min_sat=40):
    """Bands whose rows contain saturated (coloured) pixels."""
    bands = []
    start = None
    for y in range(h):
        sat = 0
        for x in range(0, w, 2):
            r, g, b = px(rgb, w, x, y)
            sat += max(r, g, b) - min(r, g, b)
        if sat / max(1, w // 2) > min_sat:
            if start is None:
                start = y
        else:
            if start is not None:
                bands.append((start, y - 1))
                start = None
    if start is not None:
        bands.append((start, h - 1))
    return bands


def main() -> int:
    src = ROOT / "docs" / "review" / "native_screens" / "2131.png"
    w, h, rgb = load(src)
    print(f"native main window: {w}x{h}  ({src.name})")
    prof = row_profile(w, h, rgb)
    seps = find_separators(prof, h)
    print()
    print("uniform (separator) rows, grouped:")
    runs = []
    for y, luma in seps:
        if runs and y == runs[-1][1] + 1:
            runs[-1][1] = y
        else:
            runs.append([y, y, luma])
    for a, b, luma in runs:
        print(f"  y {a:3d}..{b:3d}  (h={b - a + 1:3d})  luma={luma}")
    print()
    print("coloured (icon) bands:")
    for a, b in coloured_bands(w, h, rgb):
        print(f"  y {a:3d}..{b:3d}")
    print()
    print("row profile (every row: unique colours / mean luma / mean saturation):")
    for y in range(0, h):
        uniq, luma, sat = prof[y]
        marker = ""
        if uniq <= 3 and sat <= 8:
            marker = "  <- uniform"
        elif sat > 20:
            marker = "  <- coloured"
        print(f"  y={y:3d}  uniq={uniq:4d} luma={luma:3d} sat={sat:3d}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
