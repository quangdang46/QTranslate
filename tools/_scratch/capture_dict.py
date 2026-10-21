"""Capture the port's Dictionary window and measure its bottom band.

Native's Dictionary window (docs/review/native_screens/2132.png) ends with
a strip of the dictionary services. The port had none of it; the strip is
being rebuilt from the recovered payload icons, and this script checks the
thing that is easy to get wrong -- a `PhotoImage` that is created and then
garbage-collected renders as nothing, and a widget packed after an
`expand=True` sibling gets no space at all.

    python3 -I tools/_scratch/capture_dict.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "cap", ROOT / "tools" / "_scratch" / "capture_surfaces.py")
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

OUT = ROOT / "docs" / "review" / "ui_fidelity_2026-10-21" / "surfaces"


def walk(w, depth=0, out=None):
    out = out if out is not None else []
    for c in w.winfo_children():
        try:
            out.append((depth, c.winfo_class(), c.winfo_x(), c.winfo_y(),
                        c.winfo_width(), c.winfo_height()))
        except Exception:
            continue
        walk(c, depth + 1, out)
    return out


def main() -> int:
    import tkinter as tk
    from qtranslate import app as A

    OUT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = A.App(root)
    root.update_idletasks()
    root.update()
    root.deiconify()
    root.lift()
    root.update()
    time.sleep(0.3)
    root.update()

    errors = []

    def _exc(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb)))

    root.report_callback_exception = _exc

    app.open_dict_window()
    root.update_idletasks()
    root.update()
    time.sleep(0.5)
    root.update()

    if errors:
        print("EXCEPTIONS:")
        for e in errors:
            print("  " + e.strip().splitlines()[-1])

    # Find the dictionary toplevel.
    dlg = None
    for w in root.winfo_children():
        if w.winfo_class() == "Toplevel":
            dlg = w
    print("dialog:", dlg, dlg.winfo_geometry() if dlg else None)
    if dlg is not None:
        print("  screen y:", dlg.winfo_rooty(), "h:", dlg.winfo_height())
        for depth, cls, x, y, w, h in walk(dlg):
            if depth <= 2:
                print("   %s%s @%d,%d %dx%d" % ("  " * depth, cls, x, y, w, h))

    # Check the PhotoImages that back the strip.
    icons_dir = ROOT / "qtranslate" / "assets" / "dict_icons"
    for f in sorted(icons_dir.glob("*.png")):
        print("  asset", f.name, f.stat().st_size, "bytes")

    pid = os.getpid()
    wid, name, bounds = cap.find_window(pid, "Dictionary")
    print("window:", wid, name, bounds)
    if wid is not None:
        p = OUT / "dict.png"
        cap.capture(wid, p, bounds)
        print("captured", p, p.stat().st_size)

    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
