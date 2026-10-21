"""Match the installer-payload icons against native's service strips, by pixels.

The installer payload carries 18 single-image ``.ico`` files with no
filenames. Nine were already identified (the TRANSLATION services) by
matching them against native's main-window strip; the other nine were
un-named, and this matches them against native's DICTIONARY strip
(capture 2132).

The match is done on 4x4 BLOCK AVERAGES rather than raw pixels: the
native capture is antialiased and scaled, the payload icons are hard
edges, so a per-pixel comparison scores badly even on a correct match.
Block averages are what survive both.

Reports; writes nothing.
"""

from __future__ import annotations

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

PAYLOAD = ROOT / "docs/review/artifacts/nsis_payload_unpacked.bin"
MAIN = ROOT / "docs/review/native_screens/2131.png"
DICT = ROOT / "docs/review/native_screens/2132.png"

B = 4          # block size -> 4x4 blocks over a 16x16 icon


def blocks(rgb: bytes, w: int, x0: int, y0: int) -> list:
    """4x4 block averages of a 16x16 region, as a flat RGB list."""
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


def named_icons() -> set:
    out = set()
    for mf in ("service_icons", "ui_icons"):
        d = json.loads((ROOT / "qtranslate" / "assets" / mf /
                        "manifest.json").read_text(encoding="utf-8"))
        for v in d["icons"].values():
            out.add(v["recovered_from"])
    return out


def load_payload():
    blob = PAYLOAD.read_bytes()
    out = []
    for index, body in ex.walk_chunks(blob):
        dec = ex.decode_ico(body)
        if not dec:
            continue
        _kind, w, h, rgb = dec
        if (w, h) == (16, 16):
            out.append(("icon_%03d.png" % index, rgb))
    return out


def match(icon_rgb, strip_rgb, W, H, y_top):
    """Best (score, x) for the icon over the strip's icon row."""
    sig = blocks(icon_rgb, 16, 0, 0)
    best = (1e18, 0)
    for x0 in range(0, W - 15):
        for dy in (0, -1, 1, -2, 2, -3, 3):
            y0 = y_top + dy
            if y0 < 0 or y0 + 16 > H:
                continue
            win = blocks(strip_rgb, W, x0, y0)
            score = sum(abs(a - c) for a, c in zip(sig, win))
            if score < best[0]:
                best = (score, x0)
    return best


def main() -> int:
    named = named_icons()
    icons = load_payload()
    unnamed = [(n, r) for n, r in icons if n not in named]
    print("payload icons:", len(icons), " already named:", len(icons) -
          len(unnamed))

    for label, path in (("MAIN strip", MAIN), ("DICT strip", DICT)):
        W, H, px = g9.png_decode(path)
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
        print("\n=== %s (%dx%d) icon band y=%d" % (label, W, H, ytop))
        rows = []
        for n, r in unnamed:
            s, x = match(r, px, W, H, ytop)
            rows.append((n, x, s))
        rows.sort(key=lambda t: t[1])
        for n, x, s in rows:
            print("    x=%3d  %-14s score=%8.1f" % (x, n, s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
