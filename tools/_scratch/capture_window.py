"""Capture the port's own window with Quartz, bypassing `screencapture`.

`screencapture` exits 1 with "could not create image from display" on this
host: macOS Screen Recording is not granted to the process. The harness's
own capture path is Windows-only anyway.

`CGWindowListCreateImage` on a window *belonging to this process* is a
different code path from the display-wide one, so it may still work. This
script builds the port's main window, finds its `CGWindowID` through
`CGWindowListCopyWindowInfo`, and asks for that one window's pixels.

It reports plainly whether the capture worked; it never substitutes a
synthetic image for a failed capture.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import Quartz  # noqa: E402
from Quartz import CoreGraphics as CG  # noqa: E402


def display_scale():
    """Backing-store scale factor of the main display (2 on Retina)."""
    main = Quartz.CGMainDisplayID()
    bounds = Quartz.CGDisplayBounds(main)
    wide = Quartz.CGDisplayPixelsWide(main)
    if bounds.size.width <= 0:
        return 1
    return wide / bounds.size.width


def window_ids_for_pid(pid):
    options = CG.kCGWindowListOptionOnScreenOnly | CG.kCGWindowListExcludeDesktopElements
    info = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    out = []
    for entry in info or ():
        if entry.get("kCGWindowOwnerPID") != pid:
            continue
        wid = entry.get("kCGWindowNumber")
        name = entry.get("kCGWindowName") or ""
        bounds = entry.get("kCGWindowBounds") or {}
        out.append((wid, name, bounds))
    return out


def capture(wid, path, rect=None):
    rect = rect if rect is not None else CG.CGRectInfinite
    # The option constants are not exposed by every pyobjc build; use the
    # numeric values from CGWindowImageOption.
    #   kCGWindowImageOptionDefault = 0
    #   kCGWindowImageOptionBoundsIgnoreFraming = 1
    # CGWindowListCreateImage(rect, listOption, windowID, imageOption)
    #   kCGWindowListOptionIncludingWindow = 1 << 3 = 8
    #   kCGWindowImageOptionBoundsIgnoreFraming = 1
    list_option = getattr(CG, "kCGWindowListOptionIncludingWindow", 8)
    option = getattr(CG, "kCGWindowImageOptionBoundsIgnoreFraming", 1)
    image = CG.CGWindowListCreateImage(rect, list_option, wid, option)
    if image is None:
        return False, "CGWindowListCreateImage returned None (Screen Recording not granted)"
    width = CG.CGImageGetWidth(image)
    height = CG.CGImageGetHeight(image)
    provider = CG.CGImageGetDataProvider(image)
    data = Quartz.CGDataProviderCopyData(provider)
    # NSData -> bytes, without depending on a particular CoreFoundation shim.
    try:
        buf = bytes(data.bytes())
    except Exception:
        from CoreFoundation import CFDataGetBytePtr, CFDataGetLength
        raw = CFDataGetBytePtr(data)
        buf = bytes(raw[:CFDataGetLength(data)])
    # The data provider's row stride is NOT necessarily width*4 (it is padded),
    # and reading it as width*4 shears the image.
    stride = CG.CGImageGetBytesPerRow(image)
    bpp = stride // width if width else 4
    rgb = bytearray(width * height * 3)
    for y in range(height):
        row = buf[y * stride : (y + 1) * stride]
        for x in range(width):
            o = (y * width + x) * 3
            s = x * bpp
            rgb[o] = row[s]
            rgb[o + 1] = row[s + 1]
            rgb[o + 2] = row[s + 2]
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "g9", os.path.join(ROOT, "tools", "g9_screenshot_diff.py"))
    g9 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g9)
    with open(path, "wb") as fh:
        fh.write(g9.png_encode(width, height, bytes(rgb)))
    return True, f"{width}x{height}"


def crop_window(rgb, width, height, bounds, scale):
    """Crop the captured display down to the window's own rectangle.

    `CGWindowListCreateImage` with an infinite rect returns the whole
    display here, so the window's rectangle (in points) is scaled and cut
    out of it. Returns (w, h, rgb).
    """
    x = int(bounds["X"] * scale)
    y = int(bounds["Y"] * scale)
    w = int(bounds["Width"] * scale)
    h = int(bounds["Height"] * scale)
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    out = bytearray(w * h * 3)
    for row in range(h):
        s = ((y + row) * width + x) * 3
        out[row * w * 3 : (row + 1) * w * 3] = rgb[s : s + w * 3]
    return w, h, bytes(out)


def main() -> int:
    import tkinter as tk
    from qtranslate import app as A

    width, height = 516, 392
    root = tk.Tk()
    app = A.App(root)
    root.geometry(f"{width}x{height}+40+60")
    root.update_idletasks()
    root.update()
    root.deiconify()
    root.lift()
    root.focus_force()
    root.update_idletasks()
    root.update()

    pid = os.getpid()
    cands = window_ids_for_pid(pid)
    print("our windows:", cands)
    out = sys.argv[1] if len(sys.argv) > 1 else "tools/_scratch/port_window.png"
    for wid, name, bounds in cands:
        print("  bounds:", dict(bounds) if bounds else None)
        # Ask Quartz for the window's own rectangle rather than the whole
        # desktop; the global coordinate space is in logical points.
        wrect = None
        if bounds:
            wrect = CG.CGRectMake(bounds["X"], bounds["Y"],
                                   bounds["Width"], bounds["Height"])
        ok, info = capture(wid, out, wrect)
        print(f"  window {wid} {name!r} {bounds.get('Width')}x"
              f"{bounds.get('Height')} -> {'OK' if ok else 'FAILED'}: {info}")
        if ok:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "g9", os.path.join(ROOT, "tools", "g9_screenshot_diff.py"))
            g9 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(g9)
            w, h, rgb = g9.png_decode(Path(out))
            print("  capture", w, "x", h)
            cw, ch, crgb = w, h, rgb
            with open(out, "wb") as fh:
                fh.write(g9.png_encode(cw, ch, crgb))
            print(f"wrote {out} ({cw}x{ch})")
            root.destroy()
            return 0
    root.destroy()
    print("no window captured")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
