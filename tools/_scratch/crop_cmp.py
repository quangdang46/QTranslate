import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("g9", "tools/g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(g9)

def crop_scale(rgb, w, h, x0, y0, cw, ch, scale):
    ow, oh = cw*scale, ch*scale
    out = bytearray(ow*oh*3)
    for y in range(oh):
        sy = y0 + y//scale
        for x in range(ow):
            sx = x0 + x//scale
            o = (y*ow+x)*3; s = (sy*w+sx)*3
            out[o:o+3] = rgb[s:s+3]
    return ow, oh, bytes(out)

def stack(rows):
    # rows: list of (label, w, h, rgb)
    W = max(r[1] for r in rows)
    H = sum(r[2] for r in rows)
    out = bytearray(W*H*3)
    for i in range(W*H*3): out[i] = 255
    y0 = 0
    for (_l, w, h, rgb) in rows:
        for y in range(h):
            o = ((y0+y)*W)*3; s = y*w*3
            out[o:o+w*3] = rgb[s:s+w*3]
        y0 += h
    return W, H, bytes(out)

out = Path("docs/review/g9_evidence/out")
nw, nh, nrgb = g9.png_decode(out/"native.png")
pw, ph, prgb = g9.png_decode(out/"port.png")

x0,y0,cw,ch,scale = (int(a) for a in sys.argv[1:6])
rows = [("native",)+crop_scale(nrgb,nw,nh,x0,y0,cw,ch,scale),
        ("port",)+crop_scale(prgb,pw,ph,x0,y0,cw,ch,scale)]
# diff
W,H = rows[0][1], rows[0][2]
d = bytearray(W*H*3)
for i in range(W*H):
    a = rows[0][3][i*3:i*3+3]; b = rows[1][3][i*3:i*3+3]
    dv = max(abs(a[j]-b[j]) for j in range(3))
    if dv > 8:
        d[i*3:i*3+3] = bytes((255,0,0))
    else:
        v = (a[0]//3 + b[0]//3)//2
        d[i*3:i*3+3] = bytes((v,v,v))
rows.append(("diff",W,H,bytes(d)))
W,H,rgb = stack(rows)
p = Path("tools/_scratch/crop_cmp.png")
p.write_bytes(g9.png_encode(W,H,rgb))
print("wrote", p, W, H)
