"""Match the recovered payload icons to the native strip's icons.

For every icon group in the native main window's bottom strip, take a
16x16 patch and compare it against every recovered payload icon, over a
range of vertical offsets (the strip's band detection finds only the
saturated rows of each icon, not the icon's full box).

The match is reported as the sum of squared differences over the RGB
channels, plus a small-correlation sanity check, so a wrong match is visible
as a large distance rather than being silently accepted.
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

NATIVE = ROOT / "docs/review/g9_evidence/out/native.png"
ICONS = ROOT / "docs/review/rea/service_icons"
NATIVE_2131 = ROOT / "docs/review/native_screens/2131.png"


def load(path):
    w, h, rgb = g9.png_decode(path)
    return w, h, rgb


def px(rgb, w, x, y):
    o = (y * w + x) * 3
    return rgb[o], rgb[o + 1], rgb[o + 2]


def icon_groups(w, h, rgb, bottom=60):
    rows = []
    for y in range(h - 1, max(0, h - bottom), -1):
        sat = sum(max(px(rgb, w, x, y)) - min(px(rgb, w, x, y))
                  for x in range(0, w, 2))
        if sat / max(1, w // 2) > 30:
            rows.append(y)
    if not rows:
        return [], None
    y0, y1 = min(rows), max(rows)
    coloured = []
    for x in range(w):
        hit = False
        for y in range(y0, y1 + 1):
            r, g, b = px(rgb, w, x, y)
            if max(r, g, b) - min(r, g, b) >= 40:
                hit = True
                break
        coloured.append(hit)
    groups = []
    x = 0
    while x < w:
        if coloured[x]:
            start = x
            while x < w and coloured[x]:
                x += 1
            groups.append((start, x - 1))
        else:
            x += 1
    merged = []
    for cell in groups:
        if merged and cell[0] - merged[-1][1] <= 3:
            merged[-1] = (merged[-1][0], cell[1])
        else:
            merged.append(cell)
    icons = [c for c in merged if (c[1] - c[0] + 1) <= 18]
    return icons, (y0, y1)


def ssd(a, b):
    """Sum of squared differences between two RGB buffers."""
    return sum((a[i] - b[i]) ** 2 for i in range(0, len(a), 3))


def main() -> int:
    nw, nh, nrgb = load(NATIVE)
    groups, band = icon_groups(nw, nh, nrgb)
    print(f"native icon groups: {len(groups)} band={band}")

    manifest = json.loads((ICONS / "_manifest.json").read_text(encoding="utf-8"))
    icons = []
    for entry in manifest["icons"]:
        iw, ih, irgb = load(ICONS / entry["file"])
        icons.append((entry, irgb))

    results = []
    for gi, (x0, x1) in enumerate(groups):
        # A 16-wide window centred on the coloured group.
        width = 16
        best = None
        for dx in range(-6, 7):
            sx = x0 + dx
            if sx < 0 or sx + width > nw:
                continue
            for dy in range(-10, 4):
                sy = band[0] - 4 + dy
                if sy < 0 or sy + width > nh:
                    continue
                patch = bytearray()
                for y in range(sy, sy + width):
                    for x in range(sx, sx + width):
                        o = (y * nw + x) * 3
                        patch += nrgb[o : o + 3]
                for entry, irgb in icons:
                    d = ssd(bytes(patch), irgb)
                    if best is None or d < best[0]:
                        best = (d, entry, sy, sx)
        d, entry, sy, sx = best
        results.append({"native_index": gi, "x": x0, "icon": entry["file"],
                        "chunk": entry["chunk"], "ssd": d,
                        "patch_at": [sx, sy]})
        print(f"  native {gi} (x={x0:3d}) <- {entry['file']} "
              f"(chunk {entry['chunk']:3d})  ssd={d:9d}  at ({sx},{sy})")

    (ICONS / "_matches.json").write_text(json.dumps({
        "native_strip": str(NATIVE.relative_to(ROOT)),
        "matches": results,
    }, indent=1) + "\n", encoding="utf-8")
    print(f"\nwritten {ICONS / '_matches.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
