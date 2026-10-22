"""Compare a rendered UI against the native capture, pixel by pixel.

Two kinds of comparison live here:

  * ``--qt`` compares the PySide6 REFERENCE render (``qtranslate_ui.py``)
    against the native capture. The reference renders the CLIENT area, so
    the native capture is cropped with the same ORIGIN offset the
    reference declares.
  * ``--port`` compares the Tkinter port's own window against the same
    native capture, using the same client-area convention.

Both write a diff image next to the report so the divergence can be
looked at, not just counted.

Usage:
    python -I tools/ui_compare.py --qt
    python -I tools/ui_compare.py --port
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

NATIVE_DIR = os.path.join(ROOT, "docs", "review", "native_screens")
QT_DIR = os.path.join(ROOT, "docs", "review", "ui_reference")
OUT_DIR = os.path.join(ROOT, "docs", "review", "ui_compare")

# The reference's own ORIGIN table (qtranslate_ui.py): where the client
# area starts inside the native capture.
ORIGIN = {
    "main": (1, 31), "dict": (1, 31), "hist": (1, 31), "kbd": (1, 31),
    "hotkeys": (0, 24),
    "internet": (1, 26), "services": (1, 26), "languages": (1, 26),
    "appearance": (1, 26), "exceptions": (1, 26), "advanced": (1, 26),
    "updates": (1, 26),
}

# screen -> (native capture, reference/port render filename)
SCREENS = {
    "main": ("2131.png", "main.png"),
    "dict": ("2132.png", "dict.png"),
    "hist": ("2133.png", "hist.png"),
    "kbd": ("2134.png", "kbd.png"),
    "hotkeys": ("2126.png", "hotkeys.png"),
    "internet": ("2135.png", "internet.png"),
    "services": ("2136.png", "services.png"),
    "languages": ("2137.png", "languages.png"),
    "appearance": ("2138.png", "appearance.png"),
    "exceptions": ("2139.png", "exceptions.png"),
    "advanced": ("2140.png", "advanced.png"),
    "updates": ("2141.png", "updates.png"),
}


def compare(native_path, other_path, out_path, tol=8):
    from PIL import Image, ImageChops
    nat = Image.open(native_path).convert("RGB")
    oth = Image.open(other_path).convert("RGB")
    ox, oy = ORIGIN.get(os.path.basename(other_path)[:-4], (1, 31))
    nat = nat.crop((ox, oy, nat.width, nat.height))
    size = (min(nat.width, oth.width), min(nat.height, oth.height))
    nat = nat.crop((0, 0, size[0], size[1]))
    oth = oth.crop((0, 0, size[0], size[1]))
    diff = ImageChops.difference(nat, oth).convert("L")
    mask = diff.point(lambda v: 255 if v > tol else 0)
    total = size[0] * size[1]
    n = sum(mask.histogram()[255:])
    out = Image.new("RGB", size, (255, 255, 255))
    out.paste((255, 0, 0), (0, 0), mask)
    out.save(out_path)
    return {
        "native_size": list(nat.size), "other_size": list(oth.size),
        "differing_pixels": n, "total_pixels": total,
        "diff_ratio": round(n / max(1, total), 5),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qt", action="store_true",
                    help="compare the PySide6 reference render")
    ap.add_argument("--port", action="store_true",
                    help="compare the Tkinter port's windows")
    ap.add_argument("--screen")
    args = ap.parse_args()

    if args.qt:
        src = QT_DIR
    elif args.port:
        src = os.path.join(ROOT, "docs", "review", "ui_parity")
    else:
        ap.print_help()
        return 1
    if not os.path.isdir(src):
        print("no render directory: %s" % src)
        return 2
    os.makedirs(OUT_DIR, exist_ok=True)

    screens = [args.screen] if args.screen else sorted(SCREENS)
    ratios = []
    for name in screens:
        if name not in SCREENS:
            continue
        nat_name, other_name = SCREENS[name]
        other = os.path.join(src, other_name)
        if not os.path.exists(other):
            print("%-12s no render" % name)
            continue
        info = compare(os.path.join(NATIVE_DIR, nat_name), other,
                       os.path.join(OUT_DIR, name + "_diff.png"))
        ratios.append((name, info["diff_ratio"]))
        print("%-12s native=%-10s other=%-10s diff=%.4f"
              % (name, "%dx%d" % tuple(info["native_size"]),
                 "%dx%d" % tuple(info["other_size"]), info["diff_ratio"]))
    if ratios:
        print("\nmean diff ratio: %.4f over %d screens"
              % (sum(r for _, r in ratios) / len(ratios), len(ratios)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
