"""Measure a native capture: where its client area starts, what is in it.

The PySide6 port is built by comparing the two real images -- the native
capture and the Qt render -- so the numbers have to come off the pixels,
not off a guess. This tool prints the things that have to be measured:

  --origin        the first client row and the client's own left column
  --rows          each row's longest run of one colour: the rules, the
                  panes and the bands of the window
  --text X0 Y0 X1 Y1   the text bands inside a rectangle, with their
                  exact ink boxes
  --dump X0 Y0 X1 Y1   an ASCII dump of a rectangle, one character per
                  pixel: '#' dark, '+' mid, '.' light, ' ' background
  --runs X0 Y0 X1 Y1   the horizontal runs of one colour in a row band

Usage:
    python -I tools/ui_measure.py 2132 --rows
    python -I tools/ui_measure.py 2132 --dump 0 30 120 60
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIVE_DIR = os.path.join(ROOT, "docs", "review", "native_screens")


def load(name):
    from PIL import Image
    path = os.path.join(NATIVE_DIR, name if name.endswith(".png") else name + ".png")
    return Image.open(path).convert("RGB")


def client_origin(im):
    """Where the client's area starts: the first row that is window face
    or paper, and the first such column."""
    px = im.load()
    W, H = im.size
    oy = None
    for y in range(H):
        c = px[min(W - 1, 300), y]
        if c in ((240, 240, 240), (255, 255, 255)):
            oy = y
            break
    ox = 0
    for x in range(W):
        c = px[x, oy if oy is not None else 0]
        if c in ((240, 240, 240), (255, 255, 255)):
            ox = x
            break
    return ox, oy


def _sym(c):
    v = sum(c) // 3
    if v < 80:
        return "#"
    if v < 170:
        return "+"
    if v < 245:
        return "."
    return " "


def dump(im, x0, y0, x1, y1):
    px = im.load()
    print("     " + "".join(str((x // 10) % 10) for x in range(x0, x1)))
    print("     " + "".join(str(x % 10) for x in range(x0, x1)))
    for y in range(y0, y1):
        print("%4d %s" % (y, "".join(_sym(px[x, y]) for x in range(x0, x1))))


def rows(im):
    """Each row's longest run of a single colour: the rules and panes."""
    from collections import Counter
    px = im.load()
    W, H = im.size
    for y in range(H):
        row = [px[x, y] for x in range(W)]
        best, cur, bc, bs = 1, 1, row[0], 0
        for i in range(1, W):
            if row[i] == row[i - 1]:
                cur += 1
            else:
                if cur > best:
                    best, bc, bs = cur, row[i - 1], i - cur
                cur = 1
        if cur > best:
            best, bc, bs = cur, row[-1], W - cur
        top = Counter(row).most_common(1)[0]
        if best >= 30 or y % 4 == 0:
            print("y=%3d run=%3d @%3d %s  most=%s x%d"
                  % (y, best, bs, bc, top[0], top[1]))


def text(im, x0, y0, x1, y1, thr=520, need=2):
    """The text bands inside a rectangle, with their exact ink boxes."""
    px = im.load()
    out = []
    for y in range(y0, y1):
        xs = [x for x in range(x0, x1) if sum(px[x, y]) < thr]
        if len(xs) >= need:
            out.append((y, min(xs), max(xs)))
    groups = []
    for r in out:
        if groups and r[0] - groups[-1][-1][0] <= 3:
            groups[-1].append(r)
        else:
            groups.append([r])
    for g in groups:
        print("  y=%3d..%3d  x=%3d..%3d  w=%3d"
              % (g[0][0], g[-1][0], min(t[1] for t in g), max(t[2] for t in g),
                 max(t[2] for t in g) - min(t[1] for t in g) + 1))


def runs(im, x0, y0, x1, y1, colour, tol=30):
    """The horizontal runs of one colour in a band of rows."""
    px = im.load()
    out = []
    for y in range(y0, y1):
        s = None
        for x in range(x0, x1):
            c = px[x, y]
            hit = (abs(c[0] - colour[0]) <= tol and abs(c[1] - colour[1]) <= tol
                   and abs(c[2] - colour[2]) <= tol)
            if hit and s is None:
                s = x
            elif not hit and s is not None:
                if x - s >= 2:
                    out.append((y, s, x - 1))
                s = None
        if s is not None and x1 - s >= 2:
            out.append((y, s, x1 - 1))
    for r in out:
        print("  y=%3d x=%3d..%3d" % r)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    im = load(args[0])
    print("%s  %dx%d  client origin=%s" % (args[0], im.width, im.height,
                                           client_origin(im)))
    i = 1
    while i < len(args):
        opt = args[i]
        i += 1
        if opt == "--origin":
            print("client origin:", client_origin(im))
        elif opt == "--rows":
            rows(im)
        elif opt == "--text":
            box = [int(v) for v in args[i:i + 4]]
            i += 4
            text(im, *box)
        elif opt == "--dump":
            box = [int(v) for v in args[i:i + 4]]
            i += 4
            dump(im, *box)
        elif opt == "--runs":
            box = [int(v) for v in args[i:i + 4]]
            i += 4
            col = [int(v) for v in args[i:i + 3]] if len(args) > i + 2 else (126, 126, 126)
            i += 3 if len(args) > i + 2 else 0
            runs(im, *box, col)
        else:
            print("unknown option", opt)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
