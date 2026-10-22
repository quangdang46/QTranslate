"""Where a page's remaining difference is, as a map.

The ink ratio says HOW MUCH is different; this says WHERE, cell by cell,
so the next fix is aimed at the biggest patch instead of the first thing
that catches the eye.

Usage:
    python -I tools/hotspots.py advanced
    python -I tools/hotspots.py advanced --cols 80
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageChops

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
RAMP = " .:-=+*#%@"


def ink(im):
    r, g, b = im.split()
    return ImageChops.add(ImageChops.add(r, g), b)


def report(screen, cols=64):
    ox, oy = ORIGIN.get(screen, DEFAULT_ORIGIN)
    nat = Image.open(os.path.join(NATIVE_DIR, NATIVE[screen])).convert("RGB")
    nat = nat.crop((ox, oy, nat.width, nat.height))
    qt_path = os.path.join(QT_DIR, screen + ".png")
    if not os.path.exists(qt_path):
        print("%s: no render" % screen)
        return
    qt = Image.open(qt_path).convert("RGB")
    w, h = min(nat.width, qt.width), min(nat.height, qt.height)
    nat, qt = nat.crop((0, 0, w, h)), qt.crop((0, 0, w, h))
    diff = ImageChops.difference(ink(nat), ink(qt))
    mask = diff.point(lambda v: 255 if v > 8 else 0)
    px = mask.load()
    rows = max(1, h // 16)
    grid = [[0] * cols for _ in range((h + rows - 1) // rows)]
    for y in range(h):
        for x in range(w):
            if px[x, y]:
                grid[y // rows][min(cols - 1, x * cols // w)] += 1
    print("=== %s  %dx%d  rows=%dpx" % (screen, w, h, rows))
    for r, line in enumerate(grid):
        text = "".join(RAMP[min(9, n * 10 // 40)] for n in line)
        if text.strip():
            print("y=%3d %s" % (r * rows, text))


def main():
    args = []
    cols = 64
    rest = sys.argv[1:]
    while rest:
        a = rest.pop(0)
        if a == "--cols":
            cols = int(rest.pop(0))
        elif not a.startswith("-"):
            args.append(a)
    for screen in args or sorted(NATIVE):
        report(screen, cols)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
