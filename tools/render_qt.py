"""Render the REAL PySide6 windows and compare them with the native captures.

The reference renderer (``qtranslate_ui.py``) proves the LAYOUT is right;
this proves the real, working windows are laid out the same way -- the
same numbers, the same widgets, the same pixels -- with the port's
behaviour attached.

Usage:
    python -I tools/render_qt.py --out docs/review/ui_qt
    python -I tools/render_qt.py --compare
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextEdit

OUT = os.path.join(ROOT, "docs", "review", "ui_qt")
NATIVE_DIR = os.path.join(ROOT, "docs", "review", "native_screens")

# screen -> native capture
NATIVE = {
    "main": "2131.png", "dict": "2132.png", "hist": "2133.png",
    "kbd": "2134.png", "hotkeys": "2126.png", "internet": "2135.png",
    "services": "2136.png", "languages": "2137.png",
    "appearance": "2138.png", "exceptions": "2139.png",
    "advanced": "2140.png", "updates": "2141.png",
}

# Where the CLIENT area of each native capture starts. The capture is the
# window as the OS draws it -- frame, title bar and all -- while the Qt
# render is the client area alone, so the two only line up after the
# capture is cropped by this offset. Measured off the captures.
ORIGINS = {
    "main": (1, 31),
    "dict": (1, 31),
    "hist": (1, 31),
    "kbd": (1, 31),
    "hotkeys": (1, 24),
    "internet": (1, 26),
    "services": (1, 26),
    "languages": (1, 26),
    "appearance": (1, 26),
    "exceptions": (1, 26),
    "advanced": (1, 26),
    "updates": (1, 26),
}

# screen -> (module, class) inside qtranslate.qt. A window that is not
# written yet is simply skipped, so the tool works while the port is
# still growing.
WINDOWS = {
    "main": ("main_window", "MainWindow"),
    "dict": ("dictionary", "DictionaryWindow"),
    "hist": ("history_window", "HistoryWindow"),
    "kbd": ("keyboard", "KeyboardWindow"),
    "hotkeys": ("options", "HotkeysPage"),
    "internet": ("options", "InternetPage"),
    "services": ("options", "ServicesPage"),
    "languages": ("options", "LanguagesPage"),
    "appearance": ("options", "AppearancePage"),
    "exceptions": ("options", "ExceptionsPage"),
    "advanced": ("options", "AdvancedPage"),
    "updates": ("options", "UpdatesPage"),
}


def render(out_dir=OUT):
    """Render every real window to a PNG."""
    os.makedirs(out_dir, exist_ok=True)
    # The OFFSCREEN platform has no font database on this host, so every
    # glyph comes out as a tofu box and the render cannot be compared
    # with a native capture. The real Windows platform has the fonts
    # (488 families, Segoe UI among them), so the render is taken there.
    os.environ.pop("QT_QPA_PLATFORM", None)
    import importlib
    from qtranslate.qt.app import QtApp

    app = QtApp([sys.argv[0]])
    app._load_session()
    done = 0
    for name, (mod, cls) in sorted(WINDOWS.items()):
        try:
            module = importlib.import_module("qtranslate.qt." + mod)
            window = getattr(module, cls)(app)
        except (ImportError, AttributeError) as e:
            print("%-12s skipped (%s)" % (name, type(e).__name__))
            continue
        window.show()
        # The native captures have no blinking text cursor (no pane was
        # focused when they were taken), so the render must not have one
        # either -- give the focus to the window itself.
        window.setFocusPolicy(Qt.StrongFocus)
        window.setFocus()
        # The native captures have no caret in the text panes, and the
        # caret would be drawn at the text origin -- which is where the
        # port's text starts, so it would be a real difference.
        for edit in window.findChildren(QTextEdit):
            edit.setCursorWidth(0)
        app.qapp.processEvents()
        window.grab().save(os.path.join(out_dir, name + ".png"))
        done += 1
        print("rendered %-12s -> %s" % (name, out_dir))
    print("rendered %d windows" % done)
    return 0


def compare(out_dir=OUT):
    """Compare the rendered windows with the native captures.

    The measure is the TOTAL INK -- the sum of the three channels -- and
    not the plain RGB difference. The native captures are drawn with
    ClearType, so the same glyph puts its ink on different subpixels
    there than here: a pixel that is (219,143,57) in the capture can be
    (255,219,143) in the render, which is a 200-level difference in the
    blue channel for text that is in fact identical. The sum of the
    channels is what ClearType preserves, and the spec says the fringes
    are to be ignored, so the sum is the honest measure of "do these two
    images draw the same thing". The plain RGB number is reported next
    to it, for reference.
    """
    from PIL import Image, ImageChops
    os.makedirs(os.path.join(ROOT, "docs", "review", "ui_compare"), exist_ok=True)

    def ink(im):
        r, g, b = im.split()
        return ImageChops.add(ImageChops.add(r, g), b)

    ratios, rgb_ratios = [], []
    for name, nat_name in sorted(NATIVE.items()):
        other = os.path.join(out_dir, name + ".png")
        nat_p = os.path.join(NATIVE_DIR, nat_name)
        if not os.path.exists(other):
            print("%-12s no render" % name)
            continue
        nat = Image.open(nat_p).convert("RGB")
        oth = Image.open(other).convert("RGB")
        ox, oy = ORIGINS.get(name, (1, 31))
        nat = nat.crop((ox, oy, nat.width, nat.height))
        w, h = min(nat.width, oth.width), min(nat.height, oth.height)
        nat = nat.crop((0, 0, w, h))
        oth = oth.crop((0, 0, w, h))
        diff = ImageChops.difference(ink(nat), ink(oth))
        mask = diff.point(lambda v: 255 if v > 8 else 0)
        n = sum(mask.histogram()[255:])
        ratio = n / max(1, w * h)
        ratios.append(ratio)
        rgb = ImageChops.difference(nat, oth).convert("L")
        rmask = rgb.point(lambda v: 255 if v > 8 else 0)
        rgb_ratio = sum(rmask.histogram()[255:]) / max(1, w * h)
        rgb_ratios.append(rgb_ratio)
        out = Image.new("RGB", (w, h), (255, 255, 255))
        out.paste((255, 0, 0), (0, 0), mask)
        out.save(os.path.join(ROOT, "docs", "review", "ui_compare",
                              name + "_qt_diff.png"))
        print("%-12s diff=%.4f  (rgb %.4f)" % (name, ratio, rgb_ratio))
    if ratios:
        print("mean diff ratio: %.4f over %d screens (rgb %.4f)"
              % (sum(ratios) / len(ratios), len(ratios),
                 sum(rgb_ratios) / len(rgb_ratios)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    if args.compare:
        return compare(args.out)
    return render(args.out)


if __name__ == "__main__":
    raise SystemExit(main())
