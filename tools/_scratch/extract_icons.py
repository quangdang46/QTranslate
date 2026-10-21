"""Recover the service icons from the installer payload and name them.

The NSIS payload carries 18 single-image `.ico` files, each a 16x16 icon —
the service icons the native main window shows in its bottom strip. The
payload has no filenames, so the icons are identified by their *pixels*: each
is decoded to RGBA, reduced to a dominant-colour signature, and matched
against the native strip's own pixels (the strip in
`docs/review/g9_evidence/out/native.png`, a PrintWindow capture of the real
QTranslate.exe).

Writes PNGs into a new, empty directory.
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

PAYLOAD = ROOT / "docs/review/artifacts/nsis_payload_unpacked.bin"
OUT = ROOT / "docs/review/rea/service_icons"
NATIVE = ROOT / "docs/review/g9_evidence/out/native.png"


def walk_chunks(blob: bytes):
    off = 0
    index = 0
    while off < len(blob):
        (length,) = struct.unpack_from("<I", blob, off)
        off += 4
        yield index, blob[off : off + length]
        off += length
        index += 1


def decode_ico(body: bytes):
    """Decode a single-image ICO to (width, height, RGBA bytes)."""
    if body[:4] != b"\x00\x00\x01\x00":
        return None
    count = struct.unpack_from("<H", body, 4)[0]
    if count != 1:
        return None
    (w, h, _cc, _res, _planes, bpp, size, offset) = struct.unpack_from(
        "<BBBBHHII", body, 6)
    w = w or 256
    h = h or 256
    data = body[offset : offset + size]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ("png", w, h, data)
    # DIB: BITMAPINFOHEADER + XOR bitmap + AND mask
    hdr = struct.unpack_from("<IiiHHIIiiII", data, 0)
    bi_height = hdr[3]
    xor_off = 40
    stride = ((w * bpp // 8) + 3) & ~3
    rows = abs(bi_height) // 2 if bi_height > w else h
    rgba = bytearray(w * h * 4)
    for row in range(h):
        src_row = rows - 1 - row if bi_height >= 0 else row
        base = xor_off + src_row * stride
        for col in range(w):
            p = base + col * (bpp // 8)
            if p + 3 > len(data):
                continue
            b, g, r = data[p], data[p + 1], data[p + 2]
            a = data[p + 3] if bpp == 32 else 255
            o = (row * w + col) * 4
            rgba[o : o + 4] = bytes((r, g, b, a))
    # The harness's PNG encoder is RGB-only, so composite the icon onto the
    # light background the native draws it on (the strip's background is a
    # light grey) instead of dropping alpha and leaving black holes.
    rgb = bytearray(w * h * 3)
    for i in range(w * h):
        r, g, b, a = rgba[i * 4 : i * 4 + 4]
        if a == 255:
            rgb[i * 3 : i * 3 + 3] = bytes((r, g, b))
        else:
            alpha = a / 255.0
            rgb[i * 3 : i * 3 + 3] = bytes((
                int(r * alpha + 240 * (1 - alpha)),
                int(g * alpha + 240 * (1 - alpha)),
                int(b * alpha + 240 * (1 - alpha)),
            ))
    return ("dib", w, h, bytes(rgb))


def signature(rgb: bytes, w: int, h: int) -> dict:
    """Dominant colour of the icon, ignoring the composited background."""
    counts: dict[tuple[int, int, int], int] = {}
    for i in range(0, w * h * 3, 3):
        r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
        if max(r, g, b) - min(r, g, b) < 24 and (r + g + b) // 3 > 200:
            continue          # background
        key = (r // 32, g // 32, b // 32)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return {"dominant": None, "colours": 0}
    best = max(counts.items(), key=lambda kv: kv[1])
    total = sum(counts.values())
    return {
        "dominant": [best[0][0] * 32 + 16, best[0][1] * 32 + 16,
                     best[0][2] * 32 + 16],
        "share": round(best[1] / total, 3),
        "colours": len(counts),
        "top": [[list(k), v] for k, v in
                sorted(counts.items(), key=lambda kv: -kv[1])[:4]],
    }


def main() -> int:
    blob = PAYLOAD.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    icons = []
    for index, body in walk_chunks(blob):
        decoded = decode_ico(body)
        if decoded is None:
            continue
        kind, w, h, payload = decoded
        if kind == "dib":
            rgba = payload
            png = g9.png_encode(w, h, rgba)
        else:
            rgba = None
            png = payload
        name = f"icon_{index:03d}.png"
        (OUT / name).write_bytes(png)
        entry = {"chunk": index, "file": name, "kind": kind,
                 "width": w, "height": h}
        if rgba is not None:
            entry["signature"] = signature(rgba, w, h)
        icons.append(entry)

    (OUT / "_manifest.json").write_text(json.dumps({
        "source_payload": str(PAYLOAD.relative_to(ROOT)),
        "icons": icons,
    }, indent=1) + "\n", encoding="utf-8")

    print(f"extracted {len(icons)} icons into {OUT}")
    for entry in icons:
        sig = entry.get("signature", {})
        dom = sig.get("dominant")
        print(f"  {entry['file']}  {entry['width']}x{entry['height']}  "
              f"dominant={dom}  share={sig.get('share')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
