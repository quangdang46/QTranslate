"""Report the OPTIONS dialog's geometry, native vs port, side by side.

The pixel diff says HOW MUCH is different; this says WHERE. It extracts
the same set of measurable features from both images -- the nav list's
frame, the page body's edges, the group boxes, the combo boxes, the
button row and the text rows -- and prints them next to each other, so a
divergence is a number to fix rather than a shape to squint at.

Every feature is measured the same way in both images, so the two
columns are directly comparable.

Usage:
    python -I tools/ui_geometry.py [screen ...]
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

NATIVE_DIR = os.path.join(ROOT, "docs", "review", "native_screens")
PARITY_DIR = os.path.join(ROOT, "docs", "review", "ui_parity")

# screen -> (native capture, port capture)
SCREENS = {
    "options_advanced": ("2140.png", "options_advanced_port.png"),
    "options_updates": ("2141.png", "options_updates_port.png"),
    "options_appearance": ("2138.png", "options_appearance_port.png"),
    "options_exceptions": ("2139.png", "options_exceptions_port.png"),
    "options_services": ("2136.png", "options_services_port.png"),
    "options_languages": ("2137.png", "options_languages_port.png"),
    "options_internet": ("2135.png", "options_internet_port.png"),
    "options_hotkeys": ("2126.png", "options_hotkeys_port.png"),
    "main": ("2131.png", "main_port.png"),
    "dict": ("2132.png", "dict_port.png"),
    "history": ("2133.png", "history_port.png"),
    "keyboard": ("2134.png", "keyboard_port.png"),
}


def _is_line(c):
    r, g, b = c
    return abs(r - g) < 14 and abs(g - b) < 14 and r < 190


def _client_origin(im):
    """The first row of the window's CLIENT area (the OS title bar is
    above it and is not the app's UI)."""
    px = im.convert("RGB").load()
    W, H = im.size
    for y in range(H):
        c = px[min(W - 1, 300), y]
        if c == (240, 240, 240) or c == (255, 255, 255):
            return y
    return 0


def features(path):
    """The measurable features of one image, in CLIENT coordinates."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    oy = _client_origin(im)
    im = im.crop((0, oy, im.width, im.height))
    W, H = im.size
    px = im.load()

    def dark_col(x, y0, y1, thr=190):
        return sum(1 for y in range(y0, y1) if _is_line(px[x, y]))

    def dark_row(y, x0, x1, thr=190):
        return sum(1 for x in range(x0, x1) if _is_line(px[x, y]))

    out = {"size": (W, H), "client_origin_y": oy}

    # Vertical edges: a column that is a line over most of the window.
    out["vlines"] = [x for x in range(W)
                      if dark_col(x, 20, H - 20) > (H - 40) * 0.65]
    # Horizontal edges: a row that is a line across most of the width.
    out["hlines"] = [y for y in range(H)
                     if dark_row(y, 140, W) > (W - 140) * 0.55]

    # Text rows: contiguous bands with dark pixels in the label column.
    bands = []
    for y in range(H):
        n = sum(1 for x in range(156, 300) if sum(px[x, y]) < 500)
        if n:
            bands.append(y)
    groups = []
    for y in bands:
        if groups and y - groups[-1][-1] <= 2:
            groups[-1].append(y)
        else:
            groups.append([y])
    out["text_rows"] = [(g[0], g[-1]) for g in groups]

    # Combo boxes: a row through a combo shows the sunken border as a
    # pair of dark columns with the face colour between them.
    combos = []
    for y in range(30, H - 30):
        run = []
        x = 140
        while x < W:
            if _is_line(px[x, y]):
                run.append(x)
            x += 1
        if len(run) >= 2:
            a, b = run[0], run[-1]
            if b - a > 60 and a > 300:
                combos.append((y, a, b))
    # keep one per contiguous band of rows
    uniq = []
    for c in combos:
        if not uniq or c[0] - uniq[-1][0] > 4:
            uniq.append(c)
    out["combos"] = uniq[:8]
    return out


def report(screen):
    nat_name, port_name = SCREENS[screen]
    nat_p = os.path.join(NATIVE_DIR, nat_name)
    port_p = os.path.join(PARITY_DIR, port_name)
    if not os.path.exists(port_p):
        print("%-22s NO PORT CAPTURE -- run tools/ui_parity.py --all" % screen)
        return
    n = features(nat_p)
    p = features(port_p)
    print("=== %s" % screen)
    print("  size   native=%-10s port=%-10s %s" % (
        "%dx%d" % n["size"], "%dx%d" % p["size"],
        "OK" if n["size"] == p["size"] else "** SIZE MISMATCH **"))
    for key, label in (("vlines", "v-lines"), ("hlines", "h-lines"),
                       ("text_rows", "text rows")):
        nv, pv = n[key], p[key]
        same = nv == pv
        print("  %-10s native: %s" % (label, nv if len(str(nv)) < 150
                                       else str(nv)[:150]))
        print("  %-10s port  : %s%s" % (
            "", pv if len(str(pv)) < 150 else str(pv)[:150],
            "" if same else "   ** DIFFERS **"))
    print("  combos    native: %s" % (n["combos"],))
    print("  combos    port  : %s" % (p["combos"],))


def main():
    screens = sys.argv[1:] or sorted(SCREENS)
    for s in screens:
        if s in SCREENS:
            report(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
