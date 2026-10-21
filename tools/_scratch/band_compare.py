"""Compare the port's main-window band structure with native's, at one size.

Native's bands are measured from `docs/review/native_screens/2131.png` (the
real QTranslate main window, 516x423 including its 31px Windows title bar,
so the client area is 516x392).

The port is built at the SAME client size and its direct children of the
root are reported in vertical order, so the two structures can be compared
band for band instead of by eye.

No screenshot is taken: this host's Screen Recording permission is not
granted, and widget geometry does not need it.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import tkinter as tk  # noqa: E402
from qtranslate import app as A  # noqa: E402

# Native bands, measured from 2131.png (client coords, title bar removed).
NATIVE_BANDS = [
    ("nav row (back/forward + service link + overflow)", 0, 25),
    ("gap", 25, 29),
    ("SOURCE pane", 29, 180),
    ("separator", 180, 182),
    ("language/tool row (Auto-Detect | swap | target | Translate)", 182, 208),
    ("gap", 208, 212),
    ("RESULT pane", 212, 362),
    ("separator", 362, 364),
    ("service icon strip", 364, 391),
]


def main() -> int:
    width, height = 516, 392
    root = tk.Tk()
    app = A.App(root)
    # _place_main() restores native's saved/template placement, so the size
    # has to be forced AFTER the app is built.
    root.geometry(f"{width}x{height}")
    root.update_idletasks()
    root.update()
    root.deiconify()
    root.update_idletasks()
    root.update()

    print(f"port root: {root.winfo_width()}x{root.winfo_height()}")
    print()
    print("port bands (root's direct children, top to bottom):")
    children = []
    for child in root.winfo_children():
        try:
            info = child.pack_info()
        except tk.TclError:
            info = None
        if not info:
            continue
        children.append(child)
    rows = []
    for child in children:
        y = child.winfo_rooty() - root.winfo_rooty()
        rows.append((y, child))
    rows.sort(key=lambda r: r[0])
    for y, child in rows:
        h = child.winfo_height()
        cls = child.winfo_class()
        extra = ""
        if isinstance(child, tk.Frame):
            names = []
            for sub in child.winfo_children():
                names.append(sub.winfo_class())
            extra = " {" + ",".join(names[:4]) + "}"
        print(f"  y={y:4d}..{y + h:4d}  h={h:3d}  {cls}{extra}")
        prev = y + h
    print(f"  (root height {root.winfo_height()})")
    print()
    print("native bands (measured from 2131.png, client coords):")
    for name, y0, y1 in NATIVE_BANDS:
        print(f"  y={y0:4d}..{y1:4d}  h={y1 - y0:3d}  {name}")
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
