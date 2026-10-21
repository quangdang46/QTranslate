"""Montage of the NINE unnamed payload icons, zoomed, with an index band."""
import importlib.util, json
from pathlib import Path
ROOT = Path("/Users/tranquangdang21/Projects/QTranslate")
spec = importlib.util.spec_from_file_location("g9", ROOT/"tools"/"g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(g9)
ICONS = ROOT/"docs/review/rea/service_icons"
named = set()
for mf in ("service_icons", "ui_icons"):
    d = json.loads((ROOT/"qtranslate"/"assets"/mf/"manifest.json").read_text())
    for v in d["icons"].values(): named.add(v["recovered_from"])
files = sorted(p for p in ICONS.glob("icon_*.png"))
unnamed = files  # ALL of them
print("unnamed:", [p.name for p in unnamed])
Z, GAP = 8, 4
W = 9*(16*Z+GAP)+GAP
H = 2*(16*Z+GAP*2)+GAP
canvas = bytearray(b"\x40"*(W*H*3))
for k, p in enumerate(unnamed):
    w,h,rgb = g9.png_decode(p)
    x0 = GAP + (k % 9)*(16*Z+GAP)
    ybase = GAP + (k // 9)*(16*Z+GAP*2)
    for j in range(16):
        for i in range(16):
            o = (j*w+i)*3
            r,g,b = rgb[o], rgb[o+1], rgb[o+2]
            for dy in range(Z):
                for dx in range(Z):
                    x = x0+i*Z+dx; y = ybase+j*Z+dy
                    if x<W and y<H:
                        q = (y*W+x)*3
                        canvas[q:q+3] = bytes((r,g,b))
    # index band: alternating black/white blocks, 3 per icon position
    for n in range(3):
        v = 255 if (k+n) % 2 == 0 else 0
        for dy in range(GAP):
            for dx in range(16*Z):
                x = x0+dx; y = GAP+16*Z+GAP+dy
                if x<W and y<H:
                    q=(y*W+x)*3; canvas[q:q+3]=bytes((v,v,v))
out = ICONS/"_all18.png"
out.write_bytes(g9.png_encode(W,H,bytes(canvas)))
print("wrote", out, W, H)
for k,p in enumerate(unnamed): print("  col", k, p.name)
