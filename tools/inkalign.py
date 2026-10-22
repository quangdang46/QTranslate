"""Where a render's ink sits, measured against the native's.

The pixel diff says HOW MUCH is different. This says WHERE, and by how
much, in a way that is not fooled by ClearType: it compares the SUM of
the ink in each column (or row) rather than the pixels themselves, so a
glyph that is one pixel to the left shows up as a shifted profile even
when the individual pixels differ in colour.

For every region it prints the offset (dx, dy) that best aligns the
render with the native, and how much of the region's ink matches at
that offset. A region that is already aligned prints 0/0 and a high
match; a region that is off prints the offset and a low one.

Usage:
    python -I tools/inkalign.py advanced
    python -I tools/inkalign.py advanced --region 150 260 44 64
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image

NATIVE_DIR = os.path.join(ROOT, "docs", "review", "native_screens")
QT_DIR = os.path.join(ROOT, "docs", "review", "ui_qt")

NATIVE = {
    "main": "2131.png", "dict": "2132.png", "hist": "2133.png",
    "kbd": "2134.png", "hotkeys": "2126.png", "internet": "2135.png",
    "services": "2136.png", "languages": "2137.png",
    "appearance": "2138.png", "exceptions": "2139.png",
    "advanced": "2140.png", "updates": "2141.png",
}
ORIGIN = {"main": (1, 31), "dict": (1, 31), "hist": (1, 31), "kbd": (1, 31),
          "hotkeys": (1, 24)}
DEFAULT_ORIGIN = (1, 26)

# The regions of the pages that carry text: (name, x0, x1, y0, y1) in
# the CLIENT's coordinates, which is what the render uses.
REGIONS = {
    "advanced": [
        ("title", 152, 240, 0, 16),
        ("browser", 155, 250, 20, 40),
        ("copy", 155, 250, 45, 65),
        ("kbd", 155, 300, 68, 90),
        ("domain", 155, 250, 93, 115),
        ("combo1", 460, 545, 18, 42),
        ("combo2", 460, 545, 43, 67),
        ("combo3", 460, 545, 68, 92),
        ("combo4", 460, 545, 93, 117),
        ("chk1 text", 175, 300, 118, 138),
        ("chk2 text", 175, 400, 140, 162),
        ("chk3 text", 175, 300, 163, 185),
        ("mouse1 text", 175, 400, 231, 253),
        ("mouse2 text", 175, 400, 254, 276),
        ("ocr label", 155, 250, 300, 325),
        ("ocr field", 380, 640, 300, 325),
        ("link", 155, 350, 328, 345),
    ],
    "appearance": [
        ("title", 152, 240, 0, 16),
        ("style text", 175, 300, 18, 40),
        ("theme label", 155, 200, 42, 62),
        ("theme combo", 460, 545, 38, 62),
        ("auto size", 175, 300, 86, 106),
        ("auto pos", 175, 300, 108, 128),
        ("activate", 175, 300, 130, 152),
        ("pin", 175, 300, 152, 176),
        ("hide label", 155, 240, 176, 198),
        ("hide combo", 460, 500, 176, 198),
        ("seconds", 518, 570, 176, 198),
        ("transp label", 155, 270, 199, 222),
        ("frame label", 155, 240, 224, 246),
        ("icons label", 155, 200, 250, 270),
        ("bg label", 155, 250, 276, 298),
        ("text color", 310, 375, 276, 298),
        ("frame color", 475, 545, 276, 298),
    ],
    "main": [
        ("title", 55, 115, 0, 20),
        ("version", 5, 200, 25, 45),
        ("hotkeys 1", 5, 200, 55, 75),
        ("hotkeys 2", 5, 200, 72, 92),
        ("hotkeys 3", 5, 200, 89, 109),
        ("hotkeys 4", 5, 200, 106, 126),
        ("hotkeys 5", 5, 200, 123, 143),
        ("main w 1", 5, 200, 143, 163),
        ("main w 2", 5, 200, 160, 180),
        ("mic", 450, 470, 185, 210),
        ("headphone", 470, 500, 185, 210),
        ("combo src", 60, 200, 185, 210),
        ("swap", 220, 250, 185, 210),
        ("combo tgt", 255, 450, 185, 210),
        ("translate", 440, 514, 185, 210),
        ("strip", 0, 514, 355, 391),
    ],
    "hist": [
        ("star", 4, 24, 28, 50),
        ("source", 24, 120, 28, 50),
        ("service icon", 20, 46, 46, 70),
        ("result", 44, 130, 46, 70),
        ("field", 4, 120, 30, 58),
        ("clear btn", 0, 80, 250, 288),
        ("save btn", 80, 200, 250, 288),
        ("star btn", 195, 225, 250, 288),
        ("ok btn", 395, 474, 250, 288),
    ],
    "internet": [
        ("title", 152, 240, 0, 16),
        ("label 1", 155, 300, 20, 40),
        ("label 2", 155, 300, 44, 64),
        ("label 3", 155, 300, 66, 86),
        ("label 4", 155, 300, 88, 108),
        ("edit 1", 380, 640, 20, 40),
        ("edit 2", 380, 640, 44, 64),
        ("edit 3", 380, 640, 66, 86),
        ("edit 4", 380, 640, 88, 108),
    ],
}


def load(screen):
    ox, oy = ORIGIN.get(screen, DEFAULT_ORIGIN)
    nat = Image.open(os.path.join(NATIVE_DIR, NATIVE[screen])).convert("RGB")
    nat = nat.crop((ox, oy, nat.width, nat.height))
    qt = Image.open(os.path.join(QT_DIR, screen + ".png")).convert("RGB")
    return nat, qt


def profile(im, x0, x1, y0, y1, axis="col"):
    """The ink sum per column (axis='col') or per row ('row')."""
    px = im.load()
    W, H = im.size
    if axis == "col":
        return [sum(sum(px[x, y]) for y in range(y0, min(y1, H)))
                for x in range(x0, min(x1, W))]
    return [sum(sum(px[x, y]) for x in range(x0, min(x1, W)))
            for y in range(y0, min(y1, H))]


def best_offset(a, b, rng=4):
    """The offset of b that best matches a, and the match ratio."""
    best = (0, 0.0)
    for d in range(-rng, rng + 1):
        if d >= 0:
            aa, bb = a[d:], b[:len(b) - d] if d else b
        else:
            aa, bb = a[:len(a) + d], b[-d:]
        if not aa or not bb:
            continue
        n = min(len(aa), len(bb))
        diff = sum(abs(aa[i] - bb[i]) for i in range(n))
        total = sum(aa[:n]) or 1
        ratio = 1.0 - diff / total
        if ratio > best[1]:
            best = (d, ratio)
    return best


def report(screen, regions):
    nat, qt = load(screen)
    print("=== %s" % screen)
    for name, x0, x1, y0, y1 in regions:
        dx, rx = best_offset(profile(nat, x0, x1, y0, y1),
                             profile(qt, x0, x1, y0, y1))
        dy, ry = best_offset(profile(nat, x0, x1, y0, y1, "row"),
                             profile(qt, x0, x1, y0, y1, "row"))
        flag = "" if (dx == 0 and dy == 0) else "   <-- off"
        print("  %-10s dx=%+d (%4.0f%%)  dy=%+d (%4.0f%%)%s"
              % (name, dx, rx * 100, dy, ry * 100, flag))


def main():
    args = sys.argv[1:]
    region = None
    screens = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--region":
            region = tuple(int(v) for v in args[i + 1:i + 5])
            i += 5
            continue
        screens.append(a)
        i += 1
    for screen in screens or sorted(REGIONS):
        regions = REGIONS.get(screen)
        if region:
            regions = [("region",) + region]
        if not regions:
            print("%s: no regions" % screen)
            continue
        report(screen, regions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
