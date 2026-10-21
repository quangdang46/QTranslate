"""Extract the native's UI icon groups from the EXE and identify the two the
main window overlays (the microphone and the headphone).

`rea inspect-pe-resources` reports the PE's RT_GROUP_ICON / RT_ICON tree with
the file range of every image. The RT_ICON payloads are plain DIBs (no .ico
wrapper), so they are decoded here the same way the installer payload's .ico
files were.

Each extracted 16x16 image is then matched against the pixels the native
main window draws in its source pane's bottom-right corner, so the
identification is by evidence rather than by eye alone.
"""

from __future__ import annotations

import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g9)

EXE = ROOT / "docs/review/artifacts/QTranslate.6.10.0.exe"
RES = ROOT / "docs/review/rea/pe_resources.json"
OUT = ROOT / "docs/review/rea/ui_icons"
NATIVE = ROOT / "docs/review/native_screens/2131.png"


def decode_dib(data: bytes):
    """Decode a PE RT_ICON DIB into (w, h, RGB)."""
    if len(data) < 40:
        return None
    (size, w, bi_height, planes, bpp, comp, imgsize, xppm, yppm,
     clrused, clrimp) = struct.unpack_from("<IiiHHIIiiII", data, 0)
    if size != 40:
        return None
    h = abs(bi_height) // 2 if bi_height > w else abs(bi_height)
    stride = ((w * bpp // 8) + 3) & ~3
    rows = abs(bi_height) // 2 if bi_height > w else h
    rgb = bytearray(w * h * 3)
    for row in range(h):
        src_row = rows - 1 - row if bi_height >= 0 else row
        base = 40 + src_row * stride
        for col in range(w):
            p = base + col * (bpp // 8)
            if p + 3 > len(data):
                continue
            b, g, r = data[p], data[p + 1], data[p + 2]
            a = data[p + 3] if bpp == 32 else 255
            if a < 255:
                alpha = a / 255.0
                r = int(r * alpha + 240 * (1 - alpha))
                g = int(g * alpha + 240 * (1 - alpha))
                b = int(b * alpha + 240 * (1 - alpha))
            o = (row * w + col) * 3
            rgb[o : o + 3] = bytes((r, g, b))
    return w, h, bytes(rgb)


def px(rgb, w, x, y):
    o = (y * w + x) * 3
    return rgb[o], rgb[o + 1], rgb[o + 2]


def ssd(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(0, len(a), 3))


def main() -> int:
    blob = EXE.read_bytes()
    data = json.loads(RES.read_text(encoding="utf-8"))
    groups = data["normalized_result"]["icon_groups"]
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    resources = data["normalized_result"]["resources"]
    images = []
    for gi, group in enumerate(groups):
        for ii, img in enumerate(group.get("images", [])):
            # The group's image entry points at the RT_ICON resource; the
            # payload's file range is on the resource, not on the group.
            cand = img.get("candidate_resource_indices") or []
            if not cand:
                continue
            res = resources[cand[0]]
            payload = res.get("payload") or {}
            loc = payload.get("location") or {}
            off = loc.get("offset")
            size = loc.get("bytes")
            if off is None or size is None:
                continue
            w = img["width"]
            h = img["height"]
            if w > 32:
                continue                      # the UI uses the 16px ones
            decoded = decode_dib(blob[off : off + size])
            if decoded is None:
                continue
            dw, dh, rgb = decoded
            if (dw, dh) != (w, h):
                continue
            name = f"ui_{gi:02d}_{ii}_{w}x{h}.png"
            (OUT / name).write_bytes(g9.png_encode(dw, dh, rgb))
            images.append({"file": name, "group": gi, "index": ii,
                           "w": dw, "h": dh, "offset": off,
                           "resource_id": img.get("resource_id")})

    print(f"extracted {len(images)} images")

    # Identify the two glyphs the native draws in the source pane's
    # bottom-right corner: a microphone and a headphone.
    nw, nh, nrgb = g9.png_decode(NATIVE)
    print("native:", nw, nh)
    # The glyphs sit in the pane's bottom-right; scan that corner for the
    # dark (non-white) pixel columns.
    region = (438, 178, 505, 208)
    x0, y0, x1, y1 = region
    dark_cols = []
    for x in range(x0, x1):
        hit = False
        for y in range(y0, y1):
            r, g, b = px(nrgb, nw, x, y)
            if r + g + b < 500:
                hit = True
                break
        if hit:
            dark_cols.append(x)
    if not dark_cols:
        print("no glyph pixels found in the corner region")
        return 1
    # split into groups
    groups_x = []
    start = prev = dark_cols[0]
    for x in dark_cols[1:]:
        if x - prev > 3:
            groups_x.append((start, prev))
            start = x
        prev = x
    groups_x.append((start, prev))
    print("glyph groups in the native corner:", groups_x)

    matches = []
    for gi, (gx0, gx1) in enumerate(groups_x):
        best = None
        for entry in images:
            if entry["w"] != 16:
                continue
            iw, ih, irgb = g9.png_decode(OUT / entry["file"])
            for dx in range(-3, 4):
                for dy in range(-6, 7):
                    sy = y0 + 8 + dy
                    sx = gx0 + dx
                    if sy < 0 or sy + 16 > nh or sx < 0 or sx + 16 > nw:
                        continue
                    patch = bytearray()
                    for y in range(16):
                        for x in range(16):
                            o = ((sy + y) * nw + (sx + x)) * 3
                            patch += nrgb[o : o + 3]
                    d = ssd(bytes(patch), irgb)
                    if best is None or d < best[0]:
                        best = (d, entry, sx, sy)
        d, entry, sx, sy = best
        matches.append({"glyph": gi, "x": [gx0, gx1], "file": entry["file"],
                        "group": entry["group"], "ssd": d})
        print(f"  glyph {gi} (x {gx0}..{gx1}) <- {entry['file']} "
              f"(group {entry['group']}) ssd={d}")
    (OUT / "_matches.json").write_text(json.dumps(
        {"images": images, "glyph_matches": matches}, indent=1) + "\n",
        encoding="utf-8")
    print("written", OUT / "_matches.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
