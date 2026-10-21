"""Match the recovered payload icons to the services, using the native strip.

`docs/review/g9_evidence/out/native.png` is a PrintWindow capture of the real
QTranslate.exe, so its bottom strip is native's own rendering of the service
icons. The strip is split into cells by its icon gaps, each cell's dominant
colour is measured, and the recovered payload icons are matched to the cells
by colour distance.

Writes a montage PNG so the match can be checked by eye as well as by
arithmetic.
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
OUT = ROOT / "docs/review/rea/service_icons"


def load(path):
    w, h, rgb = g9.png_decode(path)
    return w, h, rgb


def px(rgb, w, x, y):
    o = (y * w + x) * 3
    return rgb[o], rgb[o + 1], rgb[o + 2]


def strip_band(w, h, rgb):
    """Rows at the bottom that contain saturated (coloured) pixels."""
    rows = []
    # The strip is the LAST coloured band in the window; search only the
    # bottom region so the source pane's coloured text is not picked up.
    for y in range(h - 1, max(0, h - 60), -1):
        sat = 0
        for x in range(0, w, 2):
            r, g, b = px(rgb, w, x, y)
            sat += max(r, g, b) - min(r, g, b)
        if sat / max(1, w // 2) > 30:
            rows.append(y)
    if not rows:
        return None
    return (min(rows), max(rows))


def cell_dominant(rgb, w, x0, x1, y0, y1):
    counts: dict[tuple[int, int, int], int] = {}
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            r, g, b = px(rgb, w, x, y)
            if max(r, g, b) - min(r, g, b) < 40:
                continue
            key = (r // 32, g // 32, b // 32)
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None, 0
    best = max(counts.items(), key=lambda kv: kv[1])
    total = sum(counts.values())
    return [best[0][0] * 32 + 16, best[0][1] * 32 + 16, best[0][2] * 32 + 16], \
        round(best[1] / total, 3)


def split_cells(w, rgb, y0, y1):
    """Split the strip into cells by the columns with no coloured pixel."""
    coloured = []
    for x in range(w):
        hit = False
        for y in range(y0, y1 + 1):
            r, g, b = px(rgb, w, x, y)
            if max(r, g, b) - min(r, g, b) >= 40:
                hit = True
                break
        coloured.append(hit)
    cells = []
    x = 0
    while x < w:
        if coloured[x]:
            start = x
            while x < w and coloured[x]:
                x += 1
            cells.append((start, x - 1))
        else:
            x += 1
    # merge cells separated by a tiny gap (an icon's own two-tone parts)
    merged = []
    for cell in cells:
        if merged and cell[0] - merged[-1][1] <= 3:
            merged[-1] = (merged[-1][0], cell[1])
        else:
            merged.append(cell)
    return merged


def distance(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def main() -> int:
    nw, nh, nrgb = load(NATIVE)
    band = strip_band(nw, nh, nrgb)
    print(f"native strip band: rows {band[0]}..{band[1]}")
    cells = split_cells(nw, nrgb, band[0], band[1])
    print(f"native strip cells: {len(cells)}")
    native_cells = []
    for i, (x0, x1) in enumerate(cells):
        dom, share = cell_dominant(nrgb, nw, x0, x1, band[0], band[1])
        native_cells.append({"index": i, "x0": x0, "x1": x1,
                              "dominant": dom, "share": share})
        print(f"  cell {i}: x {x0:3d}..{x1:3d}  dominant={dom} share={share}")

    manifest = json.loads((ICONS / "_manifest.json").read_text(encoding="utf-8"))
    icons = manifest["icons"]

    # Greedy best match by colour distance.
    remaining = list(range(len(icons)))
    matches = []
    for cell in native_cells:
        best = None
        for idx in remaining:
            sig = icons[idx].get("signature") or {}
            dom = sig.get("dominant")
            if dom is None or cell["dominant"] is None:
                continue
            d = distance(dom, cell["dominant"])
            if best is None or d < best[0]:
                best = (d, idx)
        if best:
            remaining.remove(best[1])
            matches.append({"cell": cell["index"],
                            "icon": icons[best[1]]["file"],
                            "chunk": icons[best[1]]["chunk"],
                            "distance": round(best[0], 1)})
            print(f"  cell {cell['index']} <- {icons[best[1]]['file']} "
                  f"(chunk {icons[best[1]]['chunk']}, dist {best[0]:.1f})")
    unmatched = [icons[i]["file"] for i in remaining]
    if unmatched:
        print(f"  unmatched icons: {unmatched}")

    (ICONS / "_matches.json").write_text(json.dumps({
        "native_strip": {"file": str(NATIVE.relative_to(ROOT)),
                         "band": band, "cells": native_cells},
        "matches": matches,
        "unmatched_icons": unmatched,
    }, indent=1) + "\n", encoding="utf-8")

    # Montage: native strip cells on top, the recovered icons below.
    zoom = 4
    def scale(img, w, h):
        out = bytearray(w * zoom * h * zoom * 3)
        for y in range(h * zoom):
            for x in range(w * zoom):
                o = (y * w * zoom + x) * 3
                s = ((y // zoom) * w + (x // zoom)) * 3
                out[o : o + 3] = img[s : s + 3]
        return bytes(out)

    def scale_tuple(img, w, h):
        return w * zoom, h * zoom, scale(img, w, h)

    strip_crop = bytearray()
    cw = max(c[1] - c[0] + 1 for c in cells)
    for y in range(band[0], band[1] + 1):
        row = bytearray()
        for x in range(0, nw):
            o = (y * nw + x) * 3
            row += nrgb[o : o + 3]
        strip_crop += row
    mw, mh = nw, band[1] - band[0] + 1
    parts = [("strip", mw, mh, bytes(strip_crop))]
    for entry in icons:
        iw, ih, irgb = load(ICONS / entry["file"])
        parts.append((entry["file"], iw, ih, irgb))
    W = max(p[1] for p in parts) * zoom
    H = sum(p[2] for p in parts) * zoom
    canvas = bytearray(b"\xff" * (W * H * 3))
    y0 = 0
    for _l, w, h, rgb in parts:
        sw, sh, srgb = scale_tuple(rgb, w, h)
        for y in range(sh):
            o = ((y0 + y) * W) * 3
            canvas[o : o + sw * 3] = srgb[: sw * 3]
        y0 += sh
    out = OUT / "_montage.png"
    out.write_bytes(g9.png_encode(W, H, bytes(canvas)))
    print(f"\nmontage: {out} ({W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
