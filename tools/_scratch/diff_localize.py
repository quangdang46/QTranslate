import sys, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("g9", "/Users/tranquangdang21/Projects/QTranslate/tools/g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(g9)

out = Path("/Users/tranquangdang21/Projects/QTranslate/docs/review/g9_evidence/out")
nw, nh, nrgb = g9.png_decode(out/"native.png")
pw, ph, prgb = g9.png_decode(out/"port.png")
print("native", nw, nh, "port", pw, ph)
tol = 8
mask = bytearray(nw*nh)
for i in range(nw*nh):
    o = i*3
    d = max(abs(nrgb[o]-prgb[o]), abs(nrgb[o+1]-prgb[o+1]), abs(nrgb[o+2]-prgb[o+2]))
    mask[i] = 1 if d > tol else 0
tot = sum(mask)
print("differing px:", tot, "ratio", tot/(nw*nh))

# row profile
print("\n-- rows with most diffs --")
rows = sorted(((sum(mask[y*nw:(y+1)*nw]), y) for y in range(nh)), reverse=True)[:25]
for c, y in rows: print(f"  y={y:4d} count={c:5d}")
print("\n-- column bands (diff count per 10px column band) --")
for x0 in range(0, nw, 10):
    c = sum(mask[y*nw+x0:y*nw+min(x0+10,nw)] for y in range(nh))
    bar = "#" * (c//20)
    print(f"  x={x0:4d}..{min(x0+9,nw-1):4d} count={c:5d} {bar}")

# classify: is a diff pixel inside a "frame" band?
def band(y, x):
    if y < 32: return "titlebar"
    if x < 4 or x >= nw-4 or y >= nh-4: return "edge"
    return "content"
from collections import Counter
c = Counter()
for y in range(nh):
    for x in range(nw):
        if mask[y*nw+x]:
            c[band(y,x)] += 1
print("\n-- by band --")
for k,v in c.most_common(): print(f"  {k}: {v}  ({100*v/tot:.1f}%)")
