"""Draw native's Wikipedia dictionary icon: a white tile with a black W.

The installer payload carries 18 `.ico` files for 19 services. Ten of them
are native's dictionary-strip icons (matched pixel-for-pixel against
`docs/review/native_screens/2132.png`), and nine are its translation-strip
icons. Wikipedia -- the eleventh dictionary cell -- has no `.ico`: neither
the payload's 18 nor the EXE's 24 `RT_ICON` groups match the pixels native
draws in that cell (`tools/_scratch/match_all_icons.py`).

What native draws is a 16x16 **white tile with a black serif W**, read off
the capture at cell 4 (x=134..148, y=309..324). The bitmap behind it is
not in the artifact, so it is re-drawn here from the measured geometry:
four strokes plus the three top bars, on a white 16x16 tile.

The strokes are drawn at twice the size and averaged down, so the stems
come out with the soft edges native's own (upscaled) capture shows
instead of a hard-edged 2-pixel line.

    python3 -I tools/_scratch/make_wikipedia_tile.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g9)

OUT = ROOT / "qtranslate" / "assets" / "dict_icons" / "wikipedia.png"

SIZE = 16
SS = 2                      # supersampling factor
BIG = SIZE * SS
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# The W's skeleton, read off native's cell as a brightness map (the
# capture at 2132.png, x=134..148, y=309..324): it is a serif "W" -- the
# two outer strokes start on a bar at row 4, the middle peak rises to that
# same row, and the two inner vertices land on row 15. Coordinates here are
# tile-local, i.e. native's (x-134, y-309).
STROKES = (
    ((1, 4), (5, 15)),        # down-right
    ((5, 15), (6, 4)),        # up-right
    ((6, 4), (10, 15)),       # down-right
    ((10, 15), (13, 4)),      # up-right
)
SERIFS = (
    ((0, 4), (2, 4)),         # the left stem's top bar
    ((4, 4), (7, 4)),         # the middle peak's top bar
    ((13, 4), (14, 4)),       # the right stem's top bar
)


def plot(buf, x: int, y: int) -> None:
    """Set one pixel of the supersampled canvas."""
    if 0 <= x < BIG and 0 <= y < BIG:
        buf[(y * BIG + x) * 3 : (y * BIG + x) * 3 + 3] = bytes(BLACK)


def line(buf, a, b) -> None:
    """Plot a 1px line between two points, in supersampled coordinates."""
    (x0, y0), (x1, y1) = a, b
    steps = max(abs(x1 - x0), abs(y1 - y0))
    if steps == 0:
        plot(buf, x0, y0)
        return
    for i in range(steps + 1):
        x = round(x0 + (x1 - x0) * i / steps)
        y = round(y0 + (y1 - y0) * i / steps)
        plot(buf, x, y)
        # keep a diagonal connected
        if abs(x1 - x0) and abs(y1 - y0):
            plot(buf, x, y + (1 if y1 > y0 else -1))


def main() -> int:
    big = bytearray(bytes(WHITE) * (BIG * BIG))
    for a, b in STROKES + SERIFS:
        line(big, (a[0] * SS, a[1] * SS), (b[0] * SS, b[1] * SS))
    # Average each SS x SS block down to one pixel.
    out = bytearray(SIZE * SIZE * 3)
    for y in range(SIZE):
        for x in range(SIZE):
            r = g = b = 0
            for dy in range(SS):
                for dx in range(SS):
                    o = ((y * SS + dy) * BIG + (x * SS + dx)) * 3
                    r += big[o]
                    g += big[o + 1]
                    b += big[o + 2]
            n = SS * SS
            o = (y * SIZE + x) * 3
            out[o : o + 3] = bytes((r // n, g // n, b // n))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(g9.png_encode(SIZE, SIZE, bytes(out)))
    print("wrote", OUT, OUT.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
