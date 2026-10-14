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
    jobs = [(n, None) for n in S.SCREENS]
    jobs += [("options_" + p.lower(), p) for p in S.OPTION_PAGES]
    print("screens:", " ".join(n for n, _ in jobs))

    root = tk.Tk()
    root.withdraw()
    grabbed = 0
    for name, arg in jobs:
        try:
            win = (S.SCREENS[name](root) if arg is None
                   else S.options_window(root, page=arg))
        except Exception as e:
            print(name, "BUILD FAILED:", type(e).__name__, str(e)[:120])
            continue
        try:
            import time
            win.lift()
            win.attributes("-topmost", True)
            root.update()
            # poll until the window is really mapped at a stable position:
            # grabbing too early yields rootx/rooty=0 (the window is still
            # unmapped) and the capture then lands on whatever is behind.
            prev = None
            for _ in range(60):
                root.update()
                time.sleep(0.05)
                cur = (win.winfo_rootx(), win.winfo_rooty(),
                       win.winfo_width(), win.winfo_height())
                if cur == prev and cur[2] > 0 and cur[3] > 0:
                    break
                prev = cur
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
    print("grabbed %d/%d" % (grabbed, len(jobs)))
    return 0 if grabbed == len(jobs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
