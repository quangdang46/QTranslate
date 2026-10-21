import importlib.util, json
from pathlib import Path
ROOT = Path("/Users/tranquangdang21/Projects/QTranslate")
spec = importlib.util.spec_from_file_location("g9", ROOT/"tools/g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(g9)
ICONS = ROOT/"docs/review/rea/service_icons"
NATIVE = ROOT/"docs/review/g9_evidence/out/native.png"
ZOOM = 8
def load(p):
    w,h,rgb = g9.png_decode(p); return w,h,rgb
def px(rgb,w,x,y):
    o=(y*w+x)*3; return rgb[o],rgb[o+1],rgb[o+2]
nw,nh,nrgb = load(NATIVE)
m = json.loads((ICONS/"_matches.json").read_text())
def scale(img,w,h):
    out=bytearray(w*ZOOM*h*ZOOM*3)
    for y in range(h*ZOOM):
        for x in range(w*ZOOM):
            o=(y*w*ZOOM+x)*3; s=((y//ZOOM)*w+(x//ZOOM))*3
            out[o:o+3]=img[s:s+3]
    return bytes(out)
pairs = m["matches"]
tile=16*ZOOM
W=len(pairs)*(tile*2+6)+6
H=tile+12
canvas=bytearray(b"\x30"*(W*H*3))
for i,pm in enumerate(pairs):
    sx,sy = pm["patch_at"]
    patch=bytearray()
    for y in range(sy,sy+16):
        for x in range(sx,sx+16):
            o=(y*nw+x)*3; patch+=nrgb[o:o+3]
    iw,ih,irgb = load(ICONS/pm["icon"])
    for j,(img,w,h) in enumerate(((bytes(patch),16,16),(irgb,iw,ih))):
        srgb=scale(img,w,h); ox=6+i*(tile*2+6)+j*tile
        for y in range(min(tile,h*ZOOM)):
            o=((6+y)*W+ox)*3
            canvas[o:o+min(tile,w*ZOOM)*3]=srgb[y*w*ZOOM*3:(y+1)*w*ZOOM*3]
out = ICONS/"_pairs.png"
out.write_bytes(g9.png_encode(W,H,bytes(canvas)))
print("pairs montage", out, W, H)
for i,pm in enumerate(pairs):
    print(f"  pair {i}: native <- {pm['icon']} (chunk {pm['chunk']}) ssd={pm['ssd']}")
