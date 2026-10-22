"""Report the text rows of a native capture and of a render, side by side.

The pixel diff says HOW MUCH is different; this says WHERE. For each
window it lists the horizontal bands that carry text -- the bands of
rows with ink in the label column -- in the native capture and in the
render, so a page's coordinates can be corrected in one pass instead of
one row at a time.

Usage:
    python -I tools/rows.py advanced
    python -I tools/rows.py advanced --x 155 300
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


def bands(im, x0, x1, thr=600, need=2, gap=3):
    """The rows that carry text, as (first, last) pairs."""
    px = im.load()
    W, H = im.size
    rows = []
    for y in range(H):
        n = 0
        for x in range(max(0, x0), min(W, x1)):
            if sum(px[x, y]) < thr:
                n += 1
                if n >= need:
                    break
        if n >= need:
            rows.append(y)
    out = []
    for y in rows:
        if out and y - out[-1][-1] <= gap:
            out[-1][-1] = y
        else:
            out.append([y, y])
    return out


def ink_x(im, y0, y1, x0, x1, thr=600):
    """The first and last column with ink between two rows."""
    px = im.load()
    W = im.size[0]
    cols = [x for x in range(max(0, x0), min(W, x1))
            if any(sum(px[x, y]) < thr for y in range(y0, min(y1, im.size[1])))]
    return (min(cols), max(cols)) if cols else (None, None)


def report(screen, x0, x1):
    ox, oy = ORIGIN.get(screen, DEFAULT_ORIGIN)
    nat = Image.open(os.path.join(NATIVE_DIR, NATIVE[screen])).convert("RGB")
    nat = nat.crop((ox, oy, nat.width, nat.height))
    qt_path = os.path.join(QT_DIR, screen + ".png")
    if not os.path.exists(qt_path):
        print("%s: no render" % screen)
        return
    qt = Image.open(qt_path).convert("RGB")
    nb = bands(nat, x0, x1)
    qb = bands(qt, x0, x1)
    print("=== %s  (x %d..%d)" % (screen, x0, x1))
    print("%-28s %s" % ("native", "render"))
    for i in range(max(len(nb), len(qb))):
        n = "%3d..%-3d" % (nb[i][0], nb[i][1]) if i < len(nb) else " " * 8
        q = "%3d..%-3d" % (qb[i][0], qb[i][1]) if i < len(qb) else ""
        dy = dx = ""
        if i < len(nb) and i < len(qb):
            dy = "  dy=%+d" % (qb[i][0] - nb[i][0])
            n0, _ = ink_x(nat, nb[i][0], nb[i][1] + 1, x0, x1)
            q0, _ = ink_x(qt, qb[i][0], qb[i][1] + 1, x0, x1)
            if n0 is not None and q0 is not None:
                dx = " dx=%+d" % (q0 - n0)
        print("  %-10s %-10s%s%s" % (n, q, dy, dx))


def main():
    args = []
    x0, x1 = 155, 300
    rest = sys.argv[1:]
    while rest:
        a = rest.pop(0)
        if a == "--x":
            x0, x1 = int(rest.pop(0)), int(rest.pop(0))
        elif not a.startswith("-"):
            args.append(a)
    for screen in args or sorted(NATIVE):
        report(screen, x0, x1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
