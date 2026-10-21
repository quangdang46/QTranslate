"""Measure the port's main-window layout from the live Tk widgets.

Builds the real `qtranslate.app.App` and reports each surface's geometry
(`winfo_x/y/width/height`), so the port can be compared with native's
measured layout (see `tools/_scratch/measure_native_ui.py`) as numbers
rather than as an impression.

No screenshot is involved: this host's Screen Recording permission is not
granted, so `screencapture` cannot be used. Widget geometry does not need it.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import tkinter as tk  # noqa: E402
from qtranslate import app as A  # noqa: E402


def geo(widget):
    try:
        widget.update_idletasks()
    except Exception:
        pass
    return (widget.winfo_x(), widget.winfo_y(),
            widget.winfo_width(), widget.winfo_height())


def report(label, widget):
    if widget is None:
        print(f"  {label:24s} MISSING")
        return None
    x, y, w, h = geo(widget)
    print(f"  {label:24s} x={x:4d} y={y:4d} w={w:4d} h={h:4d}")
    return (x, y, w, h)


def main() -> int:
    root = tk.Tk()
    root.withdraw()
    app = A.App(root)
    root.update_idletasks()
    root.update()

    print("port main window root:",
          f"{root.winfo_width()}x{root.winfo_height()}")
    print()
    print("named surfaces:")
    panes = getattr(app, "_panes", {}) or {}
    for name in ("src", "mid", "bar", "svc"):
        report(name, panes.get(name))
    report("src text widget", getattr(app, "src", None))
    report("out text widget", getattr(app, "out", None))
    report("tgt combobox", getattr(app, "tgt", None))
    report("src_lang combobox", getattr(app, "src_lang", None))
    print()
    print("service strip buttons:")
    for name, btn in (getattr(app, "svc_btns", {}) or {}).items():
        report(name, btn)
    print()
    print("other named widgets on the app:")
    for attr in sorted(dir(app)):
        if attr.startswith("_"):
            continue
        obj = getattr(app, attr, None)
        if isinstance(obj, tk.Widget):
            report(attr, obj)
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
