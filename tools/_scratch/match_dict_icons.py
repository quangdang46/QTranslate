"""Match the un-named installer-payload icons against native's dictionary strip.

The installer payload carries 18 single-image ``.ico`` files. Nine of them
are the TRANSLATION services (already recovered and bundled under
``qtranslate/assets/service_icons/``). The other nine are unnamed. Native's
dictionary window (capture 2132) draws a strip of eleven dictionary-service
icons along the bottom, and the port has none of them.

This matches the nine unnamed icons against that strip by PIXELS -- the same
technique ``tools/_scratch/extract_icons.py`` used for the translation
services -- and reports, for each, where in the strip it belongs. The
service NAME then comes from the strip's own order, which is read off the
capture.

Writes nothing; it only reports.
"""

from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ex", ROOT / "tools" / "_scratch" / "extract_icons.py")
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

spec2 = importlib.util.spec_from_file_location(
    "g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(g9)

PAYLOAD = ROOT / "docs/review/artifacts/nsis_payload_unpacked.bin"
ICONS = ROOT / "docs/review/rea/service_icons"
NATIVE = ROOT / "docs/review/native_screens/2132.png"

# Native's dictionary strip, in the order the capture shows it. The
# labels are native's own truncated ones.
NATIVE_ORDER = [
    "Google Search", "WordReference", "Babylon Dictionary", "Wikipedia",
    "Multitran", "ImTranslator", "Reverso", "Urban Dictionary",
    "ABBYY Lingvo Live", "youdao", "Oxford Learner Dictionary",
]


def named_icons():
    """The payload icons that already have a name."""
    out = set()
    for mf in ("service_icons", "ui_icons"):
        p = ROOT / "qtranslate" / "assets" / mf / "manifest.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        for v in d["icons"].values():
            out.add(v["recovered_from"])
    return out


def main() -> int:
    blob = PAYLOAD.read_bytes()
    named = named_icons()
    icons = []
    # The payload carries no filenames (the chunks are anonymous), so the
    # icons are identified by their INDEX -- the same numbering
    # extract_icons.py used (icon_006.png, icon_008.png, ...).
    for index, body in ex.walk_chunks(blob):
        name = "icon_%03d.png" % index
        dec = ex.decode_ico(body)
        if not dec:
            continue
        kind, w, h, rgb = dec
        if (w, h) != (16, 16):
            continue
        icons.append((name, w, h, rgb))
    print("payload 16x16 icons:", len(icons))
    unnamed = [(n, w, h, rgb) for n, w, h, rgb in icons if n not in named]
    print("already named:", len(icons) - len(unnamed), " unnamed:", len(unnamed))

    W, H, px = g9.png_decode(NATIVE)
    print("native capture:", W, H)

    # The strip is the bottom band. Find the row band that carries the
    # most saturated (icon) pixels.
    best = (0, 0, 0)
    for y in range(H - 40, H):
        n = 0
        for x in range(0, W, 2):
            o = (y * W + x) * 3
            r, g, b = px[o], px[o + 1], px[o + 2]
            if max(r, g, b) - min(r, g, b) > 60:
                n += 1
        if n > best[0]:
            best = (n, y, y)
    y0 = best[1]
    print("icon row band starts at y =", y0)

    # Slide each unnamed icon over the band and score the best x by the
    # number of pixels that agree (ignoring the light background on
    # either side, which the icon is composited onto).
    results = []
    for name, w, h, rgb in unnamed:
        best_hit, bx, by = -1, 0, y0
        # The strip is the last row of the capture and is partly cut, so
        # the icon band is tried at a few offsets.
        for dy in (-4, -3, -2, -1, 0, 1):
            yy = y0 + dy
            if yy < 0 or yy + 16 > H:
                continue
            for x0 in range(0, W - 15):
                hit = 0
                for j in range(16):
                    for i in range(16):
                        ir, ig, ib = rgb[(j * 16 + i) * 3:(j * 16 + i) * 3 + 3]
                        if max(ir, ig, ib) - min(ir, ig, ib) < 24 and \
                                (ir + ig + ib) // 3 > 200:
                            continue      # icon background pixel
                        o = ((yy + j) * W + (x0 + i)) * 3
                        nr, ng, nb = px[o], px[o + 1], px[o + 2]
                        if abs(nr - ir) < 40 and abs(ng - ig) < 40 and \
                                abs(nb - ib) < 40:
                            hit += 1
                if hit > best_hit:
                    best_hit, bx, by = hit, x0, yy
        results.append((name, bx, best_hit, by))
        print("  %-16s best x=%3d y=%3d score=%3d"
              % (name, bx, by, best_hit))

    results.sort(key=lambda r: r[1])
    print("\nordered:")
    for k, (name, x, s, y) in enumerate(results):
        svc = NATIVE_ORDER[k] if k < len(NATIVE_ORDER) else "?"
        print("  %2d  x=%3d y=%3d  %-16s -> %s" % (k, x, y, name, svc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
