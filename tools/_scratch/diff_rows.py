import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("g9", "tools/g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(g9)
out = Path("docs/review/g9_evidence/out")
nw, nh, nrgb = g9.png_decode(out/"native.png")
pw, ph, prgb = g9.png_decode(out/"port.png")
def px(img, w, x, y):
    o=(y*w+x)*3; return tuple(img[o:o+3])
print("== bottom rows, sample x = 250 (middle) ==")
for y in range(392, nh):
    print(f"  y={y:3d} native={px(nrgb,nw,250,y)} port={px(prgb,pw,250,y)}")
print("== top rows, x=250 ==")
for y in range(0, 10):
    print(f"  y={y:3d} native={px(nrgb,nw,250,y)} port={px(prgb,pw,250,y)}")
print("== row 400 across x ==")
for x in range(0, nw, 40):
    print(f"  x={x:3d} native={px(nrgb,nw,x,400)} port={px(prgb,pw,x,400)}")
