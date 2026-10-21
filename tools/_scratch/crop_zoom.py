"""Crop a region of a PNG and upscale it, for reading small glyphs."""
import importlib.util, sys
spec = importlib.util.spec_from_file_location(
    "g9", "/Users/tranquangdang21/Projects/QTranslate/tools/g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(g9)
src, x, y, w, h, scale, out = sys.argv[1], *map(int, sys.argv[2:6]), int(sys.argv[6]), sys.argv[7]
from pathlib import Path as _P
W, H, px = g9.png_decode(_P(src))
print("src", W, H)
rows = []
for j in range(h):
    row = bytearray()
    for i in range(w):
        o = ((y + j) * W + (x + i)) * 3
        row += px[o:o+3] * scale
    rows.append(bytes(row))
big = b"".join(rows)
canvas = bytearray()
for j in range(h):
    for _ in range(scale):
        canvas += big[j*w*scale*3:(j+1)*w*scale*3]
open(out, "wb").write(g9.png_encode(w*scale, h*scale, bytes(canvas)))
print("wrote", out, w*scale, h*scale)
