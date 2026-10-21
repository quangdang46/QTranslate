"""Identify every native icon the main window draws, by pixel evidence.

Scans a region of the native main-window screenshot for glyph-shaped groups
of non-background pixels, and matches each group against the 16x16 images
extracted from the EXE's RT_ICON resources (`rea inspect-pe-resources`).

The match is a sum of squared differences over RGB, minimised over a small
offset window; a good match is near zero, a wrong one is not.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g9)

NATIVE = ROOT / "docs/review/native_screens/2131.png"
UI_ICONS = ROOT / "docs/review/rea/ui_icons"

# Regions are chosen to avoid the combobox borders and the window frame,
# which are wide and would swamp the glyph groups.
REGIONS = [
    ("tool row left (new | kebab)", 0, 212, 62, 242),
    ("tool row swap button", 218, 212, 254, 242),
    ("source pane bottom-right", 435, 175, 505, 210),
    ("result pane bottom-right", 435, 385, 505, 415),
]


def px(rgb, w, x, y):
    o = (y * w + x) * 3
    return rgb[o], rgb[o + 1], rgb[o + 2]


def ssd(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(0, len(a), 3))


def groups_in_region(nw, nrgb, x0, y0, x1, y1):
    """Column groups that contain a non-background pixel."""
    dark = []
    for x in range(x0, x1):
        hit = False
        for y in range(y0, y1):
            r, g, b = px(nrgb, nw, x, y)
            if r + g + b < 620:
                hit = True
                break
        dark.append(hit)
    out = []
    x = 0
    while x < len(dark):
        if dark[x]:
            start = x
            while x < len(dark) and dark[x]:
                x += 1
            out.append((x0 + start, x0 + x - 1))
        else:
            x += 1
    merged = []
    for g in out:
        if merged and g[0] - merged[-1][1] <= 4:
            merged[-1] = (merged[-1][0], g[1])
        else:
            merged.append(g)
    return merged


def main() -> int:
    nw, nh, nrgb = g9.png_decode(NATIVE)
    icons = []
    for entry in json.loads((UI_ICONS / "_matches.json").read_text())["images"]:
        if entry["w"] != 16:
            continue
        iw, ih, irgb = g9.png_decode(UI_ICONS / entry["file"])
        icons.append((entry, irgb))
    print(f"{len(icons)} candidate 16x16 icons")

    results = []
    for label, x0, y0, x1, y1 in REGIONS:
        print()
        print(f"--- {label} (y {y0}..{y1}) ---")
        for gx0, gx1 in groups_in_region(nw, nrgb, x0, y0, x1, y1):
            best = None
            for entry, irgb in icons:
                for dx in range(-4, 5):
                    for dy in range(-14, 15):
                        sx = gx0 + dx
                        sy = y0 + 6 + dy
                        if sy < 0 or sy + 16 > nh or sx < 0 or sx + 16 > nw:
                            continue
                        patch = bytearray()
                        for y in range(16):
                            row = (sy + y) * nw
                            for x in range(16):
                                o = (row + sx + x) * 3
                                patch += nrgb[o : o + 3]
                        d = ssd(bytes(patch), irgb)
                        if best is None or d < best[0]:
                            best = (d, entry, sx, sy)
            if best is None:
                print(f"  x {gx0:3d}..{gx1:3d} (w={gx1 - gx0 + 1:2d}) <- "
                      f"(no candidate fit)")
                continue
            d, entry, sx, sy = best
            print(f"  x {gx0:3d}..{gx1:3d} (w={gx1 - gx0 + 1:2d}) <- "
                  f"{entry['file']:24s} group={entry['group']:2d} ssd={d}")
            results.append({"region": label, "x": [gx0, gx1],
                            "file": entry["file"], "group": entry["group"],
                            "ssd": d})
    (UI_ICONS / "_window_matches.json").write_text(json.dumps(
        results, indent=1) + "\n", encoding="utf-8")
    print("\nwritten", UI_ICONS / "_window_matches.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
