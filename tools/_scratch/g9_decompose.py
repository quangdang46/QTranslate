"""Decompose the G9 native-vs-port pixel difference into its causes.

The acceptance-declared capture pair in `docs/review/g9_evidence/` was taken
with two *different* capture methods (native via `PrintWindow`, port via a
desktop crop) and two different window activation states. Those differences
land in the window frame and title bar, not in the application's own pixels, so
the raw whole-image ratio overstates the fidelity gap.

This script reports, for one pair of PNGs:
  * the raw whole-image diff ratio (what the harness reports),
  * the diff restricted to each band (title bar / frame / client area),
  * an aligned client-area ratio after cropping both sides to their window
    content rectangle.

It is a measurement helper, not a gate decision.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g9)


def load(path: Path):
    w, h, rgb = g9.png_decode(path)
    return w, h, rgb


def pixel(rgb, w, x, y):
    o = (y * w + x) * 3
    return rgb[o], rgb[o + 1], rgb[o + 2]


def diff_mask(nrgb, prgb, w, h, tol):
    """1 where the two images differ by more than ``tol`` on any channel."""
    mask = bytearray(w * h)
    for i in range(w * h):
        o = i * 3
        d = (abs(nrgb[o] - prgb[o])
             | abs(nrgb[o + 1] - prgb[o + 1])
             | abs(nrgb[o + 2] - prgb[o + 2]))
        # OR of the three deltas is not the max; compute the max explicitly.
        a = abs(nrgb[o] - prgb[o])
        b = abs(nrgb[o + 1] - prgb[o + 1])
        c = abs(nrgb[o + 2] - prgb[o + 2])
        m = a if a >= b else b
        if c > m:
            m = c
        mask[i] = 1 if m > tol else 0
    return mask


def ratio(mask, w, h, x0, y0, x1, y1):
    total = (x1 - x0) * (y1 - y0)
    if total <= 0:
        return 0.0, 0
    count = 0
    for y in range(y0, y1):
        row = y * w
        count += sum(mask[row + x0 : row + x1])
    return count / total, count


def find_title_bar(rgb, w, h):
    """Locate the title-bar band: the first row whose colour is near-uniform."""
    for y in range(0, min(60, h)):
        first = pixel(rgb, w, 0, y)
        uniform = all(pixel(rgb, w, x, y) == first for x in range(0, w, 17))
        if uniform and y > 0:
            return y
    return 0


def find_window_rect(rgb, w, h):
    """Leftmost/rightmost column that belong to the window, not the desktop.

    The desktop-crop side carries dark desktop pixels outside the window; the
    window's own title bar is a light, near-uniform band. Detect the first row
    that is uniform and use the columns of that band.
    """
    band = find_title_bar(rgb, w, h)
    if band <= 0:
        return 0, 0, w, h
    y = band
    left = 0
    while left < w and pixel(rgb, w, left, y) == pixel(rgb, w, 0, y):
        left += 1
    right = w - 1
    while right > left and pixel(rgb, w, right, y) == pixel(rgb, w, w - 1, y):
        right -= 1
    return left, 0, right + 1, h


def main() -> int:
    out = ROOT / "docs" / "review" / "g9_evidence" / "out"
    nw, nh, nrgb = load(out / "native.png")
    pw, ph, prgb = load(out / "port.png")
    if (nw, nh) != (pw, ph):
        print(f"geometry differs: native {nw}x{nh} port {pw}x{ph}")
        return 1
    tol = 8
    mask = diff_mask(nrgb, prgb, nw, nh, tol)

    nl, _, nr, _ = find_window_rect(nrgb, nw, nh)
    pl, _, pr, _ = find_window_rect(prgb, pw, ph)

    report = {
        "geometry": {"width": nw, "height": nh},
        "channel_tolerance": tol,
        "detected_window_rect": {
            "native": {"left": nl, "right": nr},
            "port": {"left": pl, "right": pr},
        },
        "bands": {},
    }

    whole_r, whole_n = ratio(mask, nw, nh, 0, 0, nw, nh)
    report["bands"]["whole_image"] = {"ratio": whole_r, "differing": whole_n,
                                      "pixels": nw * nh}

    for name, y0, y1 in (("title_bar", 0, 30), ("upper_content", 30, 60)):
        r, n = ratio(mask, nw, nh, 0, y0, nw, y1)
        report["bands"][name] = {"ratio": r, "differing": n, "pixels": nw * (y1 - y0)}

    bottom_r, bottom_n = ratio(mask, nw, nh, 0, nh - 12, nw, nh)
    report["bands"]["bottom_12_rows"] = {"ratio": bottom_r, "differing": bottom_n,
                                         "pixels": nw * 12}

    # Client area: below the title bar, inside both detected window rects.
    x0 = max(nl, pl)
    x1 = min(nr, pr)
    r, n = ratio(mask, nw, nh, x0, 30, x1, nh - 12)
    report["bands"]["client_area_aligned"] = {"ratio": r, "differing": n,
                                              "pixels": (x1 - x0) * (nh - 42)}

    # Content area excluding the bottom service strip is where the app's own
    # pixels live; report it separately so the strip's icon row is not
    # mistaken for text fidelity.
    r, n = ratio(mask, nw, nh, x0, 30, x1, nh - 30)
    report["bands"]["client_area_no_strip"] = {"ratio": r, "differing": n,
                                               "pixels": (x1 - x0) * (nh - 60)}

    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
