"""Build an identification montage: native strip icons vs recovered icons.

Row 1: the nine ICONS cut out of the native main window's bottom strip
       (a PrintWindow capture of the real QTranslate.exe).
Rows below: the eighteen 16x16 icons recovered from the installer payload,
       in chunk order.

Zoomed so the shapes are legible; the recovered icons carry an index label
band underneath (rendered as alternating black/white blocks in a known order,
since no font is available here).
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
ZOOM = 8
GAP = 4


def load(path):
    w, h, rgb = g9.png_decode(path)
    return w, h, rgb


def px(rgb, w, x, y):
    o = (y * w + x) * 3
    return rgb[o], rgb[o + 1], rgb[o + 2]


def native_icon_cells(w, h, rgb):
    """The icon-sized coloured groups in the bottom strip."""
    rows = []
    for y in range(h - 1, max(0, h - 60), -1):
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
    # The strip alternates icon / label; the icons are the narrow groups.
    icons = [c for c in merged if (c[1] - c[0] + 1) <= 18]
    return icons, (y0, y1)


def crop(rgb, w, h, x0, y0, cw, ch):
    out = bytearray()
    for y in range(y0, y0 + ch):
        for x in range(x0, x0 + cw):
            o = (y * w + x) * 3
            out += rgb[o : o + 3]
    return bytes(out)


def scale(img, w, h):
    out = bytearray(w * ZOOM * h * ZOOM * 3)
    for y in range(h * ZOOM):
        for x in range(w * ZOOM):
            o = (y * w * ZOOM + x) * 3
            s = ((y // ZOOM) * w + (x // ZOOM)) * 3
            out[o : o + 3] = img[s : s + 3]
    return bytes(out)


def main() -> int:
    nw, nh, nrgb = load(NATIVE)
    cells, band = native_icon_cells(nw, nh, nrgb)
    print(f"native icon cells ({len(cells)}): {cells}  band={band}")

    manifest = json.loads((ICONS / "_manifest.json").read_text(encoding="utf-8"))
    icons = manifest["icons"]

    tile = 16 * ZOOM
    # Row 1: native icons; rows 2..: recovered icons, 9 per row.
    cols = 9
    rows_total = 1 + (len(icons) + cols - 1) // cols
    W = cols * (tile + GAP) + GAP
    H = rows_total * (tile + GAP) + GAP
    canvas = bytearray(b"\x40" * (W * H * 3))

    def put(img, w, h, col, row):
        sw, sh, srgb = w * ZOOM, h * ZOOM, scale(img, w, h)
        ox = GAP + col * (tile + GAP)
        oy = GAP + row * (tile + GAP)
        for y in range(min(sh, tile)):
            o = ((oy + y) * W + ox) * 3
            canvas[o : o + sw * 3] = srgb[y * sw * 3 : (y + 1) * sw * 3]

    for i, (x0, x1) in enumerate(cells):
        pad = max(0, (16 - (x1 - x0 + 1)) // 2)
        patch = crop(nrgb, nw, nh, x0 - pad, band[0], 16, 16)
        put(patch, 16, 16, i, 0)

    for i, entry in enumerate(icons):
        iw, ih, irgb = load(ICONS / entry["file"])
        put(irgb, iw, ih, i % cols, 1 + i // cols)

    out = ICONS / "_montage.png"
    out.write_bytes(g9.png_encode(W, H, bytes(canvas)))
    print(f"montage {out} ({W}x{H})")
    print("row 1 = native strip icons, left to right")
    for i, entry in enumerate(icons):
        print(f"  row {1 + i // cols} col {i % cols} = {entry['file']} "
              f"(chunk {entry['chunk']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
