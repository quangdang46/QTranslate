"""Render each port window and diff it against the native capture.

The native screenshots in ``docs/review/native_screens/`` are the SOURCE OF
TRUTH for the port's look. Reading the code and reasoning about it is not
evidence -- a port can have every widget on the right row and still be
the wrong colour, the wrong pitch, or one pixel off. So this tool does
the only thing that settles it:

  1. build the port's real window (the same classes the app uses),
  2. screenshot it, at the native capture's own size,
  3. diff it against the native PNG and report where the pixels differ.

Each screen is a separate subprocess-free step, so one failure does not
stop the sweep.

The comparison is reported as a diff image plus a per-band breakdown, so
a reviewer can see WHICH part of the window is off rather than only how
much of it is.

Usage:
    python -I tools/ui_parity.py --list
    python -I tools/ui_parity.py --screen options_advanced
    python -I tools/ui_parity.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

NATIVE_DIR = os.path.join(ROOT, "docs", "review", "native_screens")
OUT_DIR = os.path.join(ROOT, "docs", "review", "ui_parity")


# --- the screens: (port builder, native capture, native size) --------------
# The native size is the PNG's own size, measured from the file, so it is
# the capture that decides, not a number written down here.
SCREENS = {
    "main": ("main", "2131.png"),
    "popup": ("popup", "2130.png"),
    "options_hotkeys": ("options:Hotkeys", "2126.png"),
    "options_internet": ("options:Internet", "2135.png"),
    "options_services": ("options:Services", "2136.png"),
    "options_languages": ("options:Languages", "2137.png"),
    "options_appearance": ("options:Appearance", "2138.png"),
    "options_exceptions": ("options:Exceptions", "2139.png"),
    "options_advanced": ("options:Advanced", "2140.png"),
    "options_updates": ("options:Updates", "2141.png"),
    "dict": ("dict", "2132.png"),
    "history": ("hist", "2133.png"),
    "keyboard": ("kbd", "2134.png"),
}


def _client_origin(im):
    """The first row of the window's CLIENT area.

    The window frame -- the title bar and the border -- is drawn by the
    OS, and its height is not the app's business: native's Options
    window has a 26-pixel title bar and the port's has 31, because the
    native is a Win32 dialog and the port is a themed Tk toplevel.

    Comparing the two WHOLE windows therefore measures the OS decoration
    as much as the UI. So the comparison crops both images to their own
    client area, and every coordinate the app lays out is a CLIENT
    coordinate -- which is what Tk's `place`/`pack` use.
    """
    from PIL import Image
    px = im.convert("RGB").load()
    W, H = im.size
    for y in range(H):
        c = px[min(W - 1, 300), y]
        if c == (240, 240, 240) or c == (255, 255, 255):
            return y
    return 0


def _native_size(name: str):
    """The native capture's CLIENT size."""
    from PIL import Image
    p = os.path.join(NATIVE_DIR, name)
    with Image.open(p) as im:
        im = im.convert("RGB")
        oy = _client_origin(im)
        return (im.width, im.height - oy)


def _build(spec: str):
    """Build the port's window for a screen spec.

    Returns (tk_root, toplevel, app). The caller screenshots the
    toplevel. The app is returned because it must be KEPT ALIVE: it owns
    the widgets' behaviour, and a garbage-collected App takes its
    command variables with it, which changes what the window renders.
    """
    import tkinter as tk

    # The app reads sys.argv[1..3] as service / target language / theme
    # (qtranslate/cli.py, row A9), so this tool's OWN flags would set the
    # window's target language -- `--screen main` made the port's combo
    # read "main" instead of "Vietnamese", and the comparison then
    # measured the tool's arguments rather than the UI. The app's argv
    # is therefore neutralised BEFORE the app module is imported, because
    # the values are read at import time.
    _saved_argv = list(sys.argv)
    sys.argv = [sys.argv[0]]
    try:
        from qtranslate import app as A
        root = tk.Tk()
        root.withdraw()
        app = A.App(root)
    finally:
        sys.argv = _saved_argv
    root.update_idletasks()
    root.update()

    if spec == "main":
        win = root
    elif spec == "popup":
        from qtranslate import windows as W
        win = W.PopupHost.open("English to Vietnamese", "người_record")
    elif spec.startswith("options:"):
        page = spec.split(":", 1)[1]
        from qtranslate.windows import OptionsDialog
        dlg = OptionsDialog(root, app)
        win = dlg.open()
        # The page list is a Listbox. Selecting an item and firing
        # `<<ListboxSelect>>` is what the user's click does, so the
        # capture shows the same page native's capture shows.
        for child in win.winfo_children():
            if child.winfo_class() == "Listbox":
                pages = ["Basics", "Hotkeys", "Internet", "Services",
                         "Languages", "Appearance", "Exceptions", "Advanced",
                         "Updates"]
                if page in pages:
                    idx = pages.index(page)
                    child.selection_clear(0, "end")
                    child.selection_set(idx)
                    child.activate(idx)
                    child.event_generate("<<ListboxSelect>>")
                break
        root.update_idletasks()
        root.update()
    elif spec == "dict":
        win = app.open_dict_window()
        if win is None:
            from qtranslate.windows import DictionaryView
            win = DictionaryView(root, app).open()
    elif spec == "hist":
        app.history = [("google", "hello", "xin chào")]
        win = app.open_history_window()
    elif spec == "kbd":
        from qtranslate.windows import MainWindow
        win = MainWindow(app).open_keyboard()
    else:
        raise SystemExit("unknown screen spec %r" % spec)
    root.update_idletasks()
    root.update()
    return root, win, app


def _screenshot(win, path: str, native_size=None):
    """Screenshot a Tk toplevel from the DESKTOP.

    ``PrintWindow`` returns an all-black bitmap for a Tk window on
    Windows -- Tk draws with GDI in a way PrintWindow's
    ``PW_RENDERFULLCONTENT`` mode does not capture. The native captures
    were taken as desktop grabs, so this does the same: the window is
    shown, and the pixels under its rectangle are read from the screen.

    The window is first resized so its TOTAL size (client area plus the
    OS frame) equals the native capture's size. Comparing two windows of
    different sizes measures the size difference, not the layout: every
    control past the width difference lands on a different pixel, and
    the diff says nothing about where the port's controls actually are.
    The frame's own thickness is measured from the window itself, so the
    client area is set to (native - frame).
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    win.deiconify()
    win.lift()
    win.update_idletasks()
    win.update()

    hwnd = int(win.frame(), 16)

    def _visible_rect():
        """The window's VISIBLE bounds.

        ``GetWindowRect`` includes the invisible resize margin Windows 11
        puts around a window (about 7px on each side), so a grab taken
        from it is shifted and catches whatever is beside the window.
        ``DWMWA_EXTENDED_FRAME_BOUNDS`` is the rectangle the user
        actually sees -- the same one a screenshot tool copies.
        """
        r = wintypes.RECT()
        try:
            dwm = ctypes.windll.dwmapi
            ok = dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r),
                                           ctypes.sizeof(r))
            if ok == 0 and r.right > r.left and r.bottom > r.top:
                return r
        except Exception:
            pass
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        return r

    def _chrome():
        """(left border, title bar, right border, bottom border).

        Measured from the window itself: the visible rectangle against
        the client area's own position and size. The title bar's height
        depends on the system's title bar and the display's scaling, so
        it is measured, never assumed.
        """
        v = _visible_rect()
        cx, cy = win.winfo_rootx(), win.winfo_rooty()
        cw, ch = win.winfo_width(), win.winfo_height()
        return (max(0, cx - v.left), max(0, cy - v.top),
                max(0, v.right - (cx + cw)), max(0, v.bottom - (cy + ch)))

    if native_size:
        # Size the CLIENT area to the native capture's CLIENT area. The
        # two windows have different title bars (native's is a Win32
        # dialog, the port's a themed toplevel), so sizing the whole
        # window to the same total would leave the port's client area
        # five pixels shorter -- and the diff would then measure the
        # title bar instead of the UI.
        # `native_size` is the native's CLIENT size. The port's client
        # is set to exactly that, and the grab is then cropped to the
        # client, so the two images are the same size regardless of how
        # thick each window's own border is.
        win.geometry("%dx%d" % (max(200, native_size[0]),
                                max(120, native_size[1])))
        win.update_idletasks()
        win.update()

    # Park the window at the top-left of the primary monitor and keep it
    # on top. A screen grab reads whatever is VISIBLE, so a window that
    # is behind the browser (or half off-screen) contributes the
    # browser's pixels to the comparison.
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass
    win.geometry("+%d+%d" % (0, 0))
    win.lift()
    try:
        win.focus_force()
    except Exception:
        pass
    win.update_idletasks()
    win.update()

    # Let the compositor settle: a grab taken in the same tick as the
    # resize can catch a half-painted window.
    import time
    for _ in range(3):
        win.update_idletasks()
        win.update()
        time.sleep(0.15)

    v = _visible_rect()
    w, h = v.right - v.left, v.bottom - v.top
    if w <= 0 or h <= 0:
        raise RuntimeError("window has no area")

    import os as _os
    _dbg = _os.environ.get("UI_PARITY_DEBUG")
    if _dbg:
        print("[dbg] grab bbox", v.left, v.top, v.right, v.bottom,
              "file", path, "exists", _os.path.exists(path))
    from PIL import ImageGrab
    im = ImageGrab.grab(bbox=(v.left, v.top, v.right, v.bottom))
    im = im.convert("RGB")
    im.save(path)
    try:
        win.attributes("-topmost", False)
    except Exception:
        pass
    return im.size


def _client_origin(im):
    """The first row of the window's CLIENT area.

    The window frame -- the title bar and the border -- is drawn by the
    OS, and its height is not the app's business: native's Options
    window has a 26-pixel title bar and the port's has 31, because the
    native is a Win32 dialog and the port is a themed Tk toplevel.

    Comparing the two WHOLE windows therefore measures the OS decoration
    as much as the UI. So the comparison crops both images to their own
    client area, and every coordinate the app lays out is a CLIENT
    coordinate -- which is what Tk's `place`/`pack` use.
    """
    from PIL import Image
    px = im.convert("RGB").load()
    W, H = im.size
    for y in range(H):
        c = px[min(W - 1, 300), y]
        # the dialog's face colour: the first row that is the plain
        # window background rather than the title bar's band
        if c == (240, 240, 240) or c == (255, 255, 255):
            return y
    return 0


def _diff(native_path: str, port_path: str, out_path: str, tol: int = 8):
    from PIL import Image, ImageChops

    na = Image.open(native_path).convert("RGB")
    pa = Image.open(port_path).convert("RGB")
    # crop both to their client areas, so the OS's title bar is not
    # counted as a UI difference
    ny = _client_origin(na)
    py = _client_origin(pa)
    a = na.crop((0, ny, na.width, na.height))
    b = pa.crop((0, py, pa.width, pa.height))
    # The client areas are the same size by construction, but the port's
    # window may have a thicker border, so the grab is trimmed to the
    # smaller of the two before the diff.
    # the client areas must be the same size for the diff to mean
    # anything
    if a.size != b.size:
        a = a.crop((0, 0, min(a.width, b.width), min(a.height, b.height)))
        b = b.crop((0, 0, min(a.width, b.width), min(a.height, b.height)))
    size = a.size

    diff = ImageChops.difference(a, b).convert("L")
    mask = diff.point(lambda v: 255 if v > tol else 0)
    total = size[0] * size[1]
    differing = sum(mask.histogram()[255:])
    out = Image.new("RGB", size, (255, 255, 255))
    out.paste((255, 0, 0), (0, 0), mask)
    out.save(out_path)

    # Per-band breakdown: 10 horizontal bands, so a reviewer sees WHICH
    # part of the window is off.
    bands = []
    bh = max(1, size[1] // 10)
    for i in range(10):
        y0 = i * bh
        y1 = size[1] if i == 9 else (i + 1) * bh
        m = mask.crop((0, y0, size[0], y1))
        n = sum(m.histogram()[255:])
        bands.append({"y0": y0, "y1": y1, "differing": n,
                      "ratio": round(n / max(1, size[0] * (y1 - y0)), 4)})
    return {
        "native": os.path.basename(native_path),
        "port": os.path.basename(port_path),
        "native_size": list(na.size),
        "port_size": list(pa.size),
        "native_client_origin_y": ny,
        "port_client_origin_y": py,
        "compared_client_size": list(size),
        "differing_pixels": differing,
        "total_pixels": total,
        "diff_ratio": round(differing / max(1, total), 5),
        "bands": bands,
    }


def run_screen(name: str, keep: bool = True):
    spec, native_name = SCREENS[name]
    native_path = os.path.join(NATIVE_DIR, native_name)
    os.makedirs(OUT_DIR, exist_ok=True)
    port_path = os.path.join(OUT_DIR, name + "_port.png")
    diff_path = os.path.join(OUT_DIR, name + "_diff.png")

    root = None
    try:
        root, win, app = _build(spec)
        native_size = _native_size(native_name)
        size = _screenshot(win, port_path, native_size=native_size)
    except Exception as exc:
        print("ERROR %-20s %r" % (name, exc))
        return {"screen": name, "error": repr(exc)}
    finally:
        try:
            if root is not None:
                root.destroy()
        except Exception:
            pass

    info = _diff(native_path, port_path, diff_path)
    info["screen"] = name
    print("%-20s native=%-12s port=%-12s diff=%.4f  worst_band=%s"
          % (name, "%dx%d" % tuple(info["native_size"]),
             "%dx%d" % tuple(info["port_size"]), info["diff_ratio"],
             max(info["bands"], key=lambda b: b["ratio"])["y0"]))
    with open(os.path.join(OUT_DIR, name + ".json"), "w",
              encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for k, (spec, nat) in SCREENS.items():
            print("%-20s %-18s %s" % (k, spec, nat))
        return 0
    if args.screen:
        run_screen(args.screen)
        return 0
    if args.all:
        results = []
        for k in SCREENS:
            results.append(run_screen(k))
        ok = [r for r in results if "error" not in r]
        if ok:
            print("\n%d screens compared; mean diff ratio %.4f"
                  % (len(ok), sum(r["diff_ratio"] for r in ok) / len(ok)))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
