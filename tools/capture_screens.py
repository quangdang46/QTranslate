"""Capture all 7 screens.py builders -> screenshots/screens/<name>.png.

The augmented screenshot workflow the user asked for: every real screen of
the ported UI, side-by-side checkable against UI-FULL.html and the native
screenshots. Each builder runs in the same interpreter so the captures are
cheap; windows hide off-screen before the grab.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else "screenshots/screens"


def main():
    import tkinter as tk
    from PIL import ImageGrab

    from qtranslate import screens as S

    os.makedirs(OUTDIR, exist_ok=True)
    names = list(S.SCREENS)
    print("screens:", " ".join(names))

    root = tk.Tk()
    root.withdraw()
    grabbed = 0
    for name in names:
        try:
            win = S.SCREENS[name](root)
        except Exception as e:
            print(name, "BUILD FAILED:", type(e).__name__, str(e)[:120])
            continue
        try:
            win.lift()
            win.attributes("-topmost", True)
            root.update_idletasks()
            root.update()
            import time
            time.sleep(0.5)
            root.update()
            x, y = win.winfo_rootx(), win.winfo_rooty()
            w, h = win.winfo_width(), win.winfo_height()
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            out = os.path.join(OUTDIR, name + ".png")
            img.save(out)
            print("saved", out, "(%dx%d)" % (w, h))
            grabbed += 1
        except Exception as e:
            print(name, "GRAB FAILED:", type(e).__name__, str(e)[:120])
        finally:
            try:
                win.destroy()
            except Exception:
                pass
    root.destroy()
    print("grabbed %d/%d" % (grabbed, len(names)))
    return 0 if grabbed == len(names) else 1


if __name__ == "__main__":
    raise SystemExit(main())
