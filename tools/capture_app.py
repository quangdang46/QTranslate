"""Capture a screenshot of the port app's main window -> screenshots/app.png.

Committed alongside changes so the repo always shows the current UI. Also
usable as the port side of the G9 screenshot-diff harness.

Run: python -I tools/capture_app.py [out.png]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = sys.argv[1] if len(sys.argv) > 1 else "screenshots/app.png"


def main():
    import tkinter as tk
    from qtranslate import app as A

    root = tk.Tk()
    A._MAIN_APP = None
    inst = A.App(root)
    A._MAIN_APP = inst
    root.lift()
    root.attributes("-topmost", True)
    root.update_idletasks()
    root.update()
    # give Tk + the window manager time to paint and raise the window,
    # or ImageGrab can capture whatever was on top at call time.
    import time
    time.sleep(1)
    root.update()

    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        img.save(OUT)
        print(f"saved {OUT} ({w}x{h})")
    except Exception as e:
        print(f"BLOCKED: screenshot failed: {e}")
        return 2
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
