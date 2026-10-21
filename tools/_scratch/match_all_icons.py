"""Match EVERY recovered icon (payload .ico + the EXE's RT_ICON) against
native's dictionary-service strip, cell by cell.

Native's Dictionary window (docs/review/native_screens/2132.png) draws one
cell per dictionary service along the bottom, each with the service's icon.
Eleven cells are visible. Ten of the icons are in the installer payload; the
eleventh (Wikipedia) is not, and this script establishes that by measuring
every candidate against every cell -- including the EXE's own RT_ICON
resources, which is where a text-drawn glyph would live.

    python3 -I tools/_scratch/match_all_icons.py
"""

from __future__ import annotations

import glob
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ex", ROOT / "tools" / "_scratch" / "extract_icons.py")
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)
spec2 = importlib.util.spec_from_file_location(
    "g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(g9)

DICT = ROOT / "docs/review/native_screens/2132.png"
PAYLOAD = ROOT / "docs/review/artifacts/nsis_payload_unpacked.bin"
B = 4


def blocks(rgb: bytes, w: int, x0: int, y0: int) -> list:
    out = []
    for bj in range(4):
        for bi in range(4):
            r = g = b = 0
            for j in range(bj * B, bj * B + B):
                for i in range(bi * B, bi * B + B):
                    o = ((y0 + j) * w + (x0 + i)) * 3
                    r += rgb[o]
                    g += rgb[o + 1]
                    b += rgb[o + 2]
            n = B * B
            out += [r / n, g / n, b / n]
    return out


def payload_icons():
    blob = PAYLOAD.read_bytes()
    out = []
    for index, body in ex.walk_chunks(blob):
        dec = ex.decode_ico(body)
        if not dec:
            continue
        _kind, w, h, rgb = dec
        if (w, h) == (16, 16):
            out.append(("payload:icon_%03d" % index, rgb))
    return out


def exe_icons():
    out = []
    for f in sorted(glob.glob(str(ROOT / "docs/review/rea/ui_icons/ui_*_16x16.png"))):
        w, h, rgb = g9.png_decode(Path(f))
        if (w, h) == (16, 16):
            out.append(("exe:" + Path(f).stem, rgb))
    return out


def main() -> int:
    W, H, px = g9.png_decode(DICT)
    # the icon band: the row with the most saturated pixels in the bottom 40
    best = (0, 0)
    for y in range(H - 40, H):
        n = 0
        for x in range(0, W, 2):
            o = (y * W + x) * 3
            r, g, b = px[o], px[o + 1], px[o + 2]
            if max(r, g, b) - min(r, g, b) > 60:
                n += 1
        if n > best[0]:
            best = (n, y)
    ytop = best[1] - 12
    print("dict strip %dx%d, icon band y=%d" % (W, H, ytop))

    icons = payload_icons() + exe_icons()
    print("candidates:", len(icons))

    # For every x, the best icon and its score.
    per_x = []
    for x0 in range(0, W - 15):
        bestsc = (1e18, "")
        for name, rgb in icons:
            sig = blocks(rgb, 16, 0, 0)
            for dy in (0, -1, 1, -2, 2):
                y0 = ytop + dy
                if y0 < 0 or y0 + 16 > H:
                    continue
                win = blocks(px, W, x0, y0)
                sc = sum(abs(a - c) for a, c in zip(sig, win))
                if sc < bestsc[0]:
                    bestsc = (sc, name)
        per_x.append((x0, bestsc[0], bestsc[1]))

    # report the local minima -- the icon positions
    mins = []
    for i, (x0, sc, nm) in enumerate(per_x):
        if sc < 1500:
            prev = per_x[i - 1][1] if i else 1e18
            nxt = per_x[i + 1][1] if i + 1 < len(per_x) else 1e18
            if sc <= prev and sc <= nxt:
                mins.append((x0, sc, nm))
    # collapse runs
    shown = []
    for x0, sc, nm in mins:
        if shown and x0 - shown[-1][0] < 6:
            if sc < shown[-1][1]:
                shown[-1] = (x0, sc, nm)
            continue
        shown.append((x0, sc, nm))
    for x0, sc, nm in shown:
        print("  x=%3d score=%8.1f  %s" % (x0, sc, nm))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
