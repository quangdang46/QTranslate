"""Zoom native's dictionary-window service strip.

`docs/review/native_screens/2132.png` is native's own capture of the
Dictionary window (DLG184). Its bottom strip holds one cell per dictionary
service -- a small round badge plus a short name label. The cells are ~26 px
wide, so the badges are read at 4x nearest-neighbour here rather than by eye
at 1x.

    python3 -I tools/_scratch/zoom_dict_strip.py <src.png> <out.png> [scale]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import g9_screenshot_diff as g9  # noqa: E402


def crop_scale(w: int, h: int, rgb: bytes, x0: int, y0: int, x1: int, y1: int,
               scale: int) -> tuple[int, int, bytes]:
    """Crop [x0,x1) x [y0,y1) and blow it up by ``scale`` (nearest)."""
    cw, ch = x1 - x0, y1 - y0
    out = bytearray(cw * scale * ch * scale * 3)
    for y in range(ch * scale):
        sy = y0 + y // scale
        for x in range(cw * scale):
            sx = x0 + x // scale
            so = (sy * w + sx) * 3
            do = (y * cw * scale + x) * 3
            out[do : do + 3] = rgb[so : so + 3]
    return cw * scale, ch * scale, bytes(out)


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1
               else "docs/review/native_screens/2132.png")
    dst = Path(sys.argv[2] if len(sys.argv) > 2
               else "tools/_scratch/dict_strip_zoom.png")
    scale = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    w, h, rgb = g9.png_decode(src)
    print("source %dx%d" % (w, h))
    # The strip is the last band of the window; find it as the rows that
    # carry the strip's own light-grey background.
    top = max(0, h - 30)
    cw, ch, out = crop_scale(w, h, rgb, 0, top, w, h, scale)
    dst.write_bytes(g9.png_encode(cw, ch, out))
    print("wrote %s (%dx%d) from rows %d..%d" % (dst, cw, ch, top, h))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
