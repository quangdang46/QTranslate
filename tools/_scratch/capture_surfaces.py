"""Capture the port's own windows and compare them with the native screens.

`screencapture` cannot be used on this host (macOS Screen Recording is not
granted), but `CGWindowListCreateImage` on a window belonging to *this
process* works. So the port's windows are captured for real and compared
with the native captures in `docs/review/native_screens/`.

Two things this harness has to get right, both learned the hard way:

* **A page that raises leaves the window's pixels stale.** The Options
  page bodies are rebuilt by destroying the body frame's children. If the
  page function raises halfway through, the body is left half-built and
  the window server keeps the *previous* page's pixels -- so a capture
  shows a page that is not the one the widget tree holds. Every page
  switch is therefore checked for an exception (via
  `report_callback_exception`) before its pixels are trusted.
* **The capture returns the last COMPOSITED frame.** The page switch has
  to be given time to reach the screen, and the window has to be
  frontmost, before the pixels are read.

Each pair is written as a side-by-side PNG so a reviewer can see them.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import Quartz  # noqa: E402
from Quartz import CoreGraphics as CG  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g9)

OUT = ROOT / "docs" / "review" / "ui_fidelity_2026-10-21" / "surfaces"
NATIVE = ROOT / "docs" / "review" / "native_screens"

# The native Options pages, read off the nav stacks in the native
# captures (see docs/review/UI_FIDELITY_OPTIONS_2026-10-21.md §1).
NATIVE_OPTIONS = {
    "Internet": "2135.png",
    "Services": "2136.png",
    "Languages": "2137.png",
    "Appearance": "2138.png",
    "Exceptions": "2139.png",
    "Advanced": "2140.png",
    "Updates": "2141.png",
}


def window_ids(pid):
    options = (CG.kCGWindowListOptionOnScreenOnly
               | CG.kCGWindowListExcludeDesktopElements)
    info = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    out = []
    for entry in info or ():
        if entry.get("kCGWindowOwnerPID") != pid:
            continue
        bounds = entry.get("kCGWindowBounds") or {}
        out.append((entry.get("kCGWindowNumber"),
                    entry.get("kCGWindowName") or "",
                    bounds.get("X", 0), bounds.get("Y", 0),
                    bounds.get("Width", 0), bounds.get("Height", 0)))
    return out


def capture(wid, path, bounds=None):
    # The window's OWN rectangle: with an infinite rect this call returns
    # the whole display, not the window.
    if bounds:
        rect = CG.CGRectMake(bounds[0], bounds[1], bounds[2], bounds[3])
    else:
        rect = CG.CGRectInfinite
    list_option = getattr(CG, "kCGWindowListOptionIncludingWindow", 8)
    option = getattr(CG, "kCGWindowImageOptionBoundsIgnoreFraming", 1)
    image = CG.CGWindowListCreateImage(rect, list_option, wid, option)
    if image is None:
        return None
    width = CG.CGImageGetWidth(image)
    height = CG.CGImageGetHeight(image)
    stride = CG.CGImageGetBytesPerRow(image)
    bpp = stride // width if width else 4
    data = Quartz.CGDataProviderCopyData(CG.CGImageGetDataProvider(image))
    try:
        buf = bytes(data.bytes())
    except Exception:
        from CoreFoundation import CFDataGetBytePtr, CFDataGetLength
        raw = CFDataGetBytePtr(data)
        buf = bytes(raw[:CFDataGetLength(data)])
    # The CGImage is 32-bit **BGRA**, not RGBA: read as RGB, blue and red
    # come out swapped. Measured on this host: a canvas filled #0000ff
    # captured as f60e00 and one filled #ff0000 as 142eee, while #00ff00
    # stayed green -- a red/blue swap plus the display profile's own
    # small shift. Every port screenshot taken before this fix had its
    # red and blue exchanged, so the port's blue controls (checkbox
    # grid, listbox selection) looked orange next to the native's.
    rgb = bytearray(width * height * 3)
    for y in range(height):
        row = buf[y * stride : (y + 1) * stride]
        for x in range(width):
            o = (y * width + x) * 3
            s = x * bpp
            rgb[o] = row[s + 2]
            rgb[o + 1] = row[s + 1]
            rgb[o + 2] = row[s]
    path.write_bytes(g9.png_encode(width, height, bytes(rgb)))
    return width, height


def find_window(pid, title_sub, skip=None):
    """The first window whose name contains `title_sub`.

    `skip` is a set of window ids to ignore: the main window is also
    called "QTranslate", and the borderless popup shares that name, so
    the popup search has to exclude the main window.
    """
    skip = skip or set()
    for wid, name, x, y, w, h in window_ids(pid):
        if wid in skip:
            continue
        if title_sub.lower() in name.lower():
            return wid, name, (x, y, w, h)
    return None, None, None


def find_unnamed(pid, skip=None):
    """The borderless popup: an overrideredirect window has NO name, so
    it cannot be found by title."""
    skip = skip or set()
    for wid, name, x, y, w, h in window_ids(pid):
        if wid in skip or name:
            continue
        return wid, name, (x, y, w, h)
    return None, None, None


def side_by_side(native_path, port_path, out_path):
    nw, nh, n = g9.png_decode(native_path)
    pw, ph, p = g9.png_decode(port_path)
    W = nw + pw + 8
    H = max(nh, ph)
    canvas = bytearray(b"\xcc" * (W * H * 3))
    for y in range(nh):
        o = (y * W) * 3
        canvas[o : o + nw * 3] = n[y * nw * 3 : (y + 1) * nw * 3]
    for y in range(ph):
        o = (y * W + nw + 8) * 3
        canvas[o : o + pw * 3] = p[y * pw * 3 : (y + 1) * pw * 3]
    out_path.write_bytes(g9.png_encode(W, H, bytes(canvas)))
    return nw, nh, pw, ph


def main() -> int:
    import tkinter as tk
    from qtranslate import app as A

    OUT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = A.App(root)
    root.update_idletasks()
    root.update()

    pid = os.getpid()
    report = []
    errors = []
    _MAIN_IDS = set()

    # Tk swallows callback exceptions and prints them to stderr. Capture
    # them instead, so a page that dies is reported as a page that died
    # rather than as a capture of the previous page's stale pixels.
    def _exc(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb)))
    root.report_callback_exception = _exc

    # --- the main window ---------------------------------------------------
    root.deiconify()
    root.lift()
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()

    wid, name, bounds = find_window(pid, "QTranslate")
    if wid is not None:
        _MAIN_IDS.add(wid)
        p = OUT / "main.png"
        capture(wid, p, bounds)
        report.append({"surface": "main", "port": p.name})
        print("  captured", p.name, bounds)

    # The Options window and its nine pages.
    try:
        app.open_options()
    except Exception as exc:
        print("open_options failed:", exc)
    root.update_idletasks()
    root.update()
    time.sleep(0.3)
    root.update()

    wid, name, bounds = find_window(pid, "Options")
    print("options window:", wid, name, bounds)

    if wid is not None:
        opts = None
        for w in root.winfo_children():
            if w.winfo_class() == "Toplevel":
                opts = w
        lb = None
        for child in opts.winfo_children():
            if child.winfo_class() == "Listbox":
                lb = child
        # The page body is the LARGEST frame: the button row
        # (OK/Cancel/Apply) is also a frame, and it is created first,
        # so "the first frame" is no longer the body.
        body = None
        for child in opts.winfo_children():
            if child.winfo_class() != "Frame" or child is lb:
                continue
            if body is None or (child.winfo_width() * child.winfo_height() >
                                body.winfo_width() * body.winfo_height()):
                body = child
        pages = [lb.get(i) for i in range(lb.size())]
        print("pages:", pages)
        for i, page in enumerate(pages):
            errors.clear()
            # `selection_set` ADDS to the selection on this listbox, so the
            # cursor stayed on row 0 and the page never changed; clear it
            # first. A synthetic click at a guessed y lands on the wrong
            # row, so the selection is set directly.
            lb.selection_clear(0, "end")
            lb.selection_set(i)
            lb.event_generate("<<ListboxSelect>>")
            root.update_idletasks()
            root.update()
            # The Quartz capture returns the LAST COMPOSITED frame, so the
            # page switch has to be given time to reach the screen.
            opts.lift()
            opts.update_idletasks()
            opts.update()
            time.sleep(0.45)
            opts.update()
            n_kids = len(body.winfo_children()) if body else -1
            _first = ""
            if body and body.winfo_children():
                try:
                    _first = str(body.winfo_children()[0].cget("text"))[:40]
                except Exception:
                    _first = body.winfo_children()[0].winfo_class()
            if errors:
                print(f"    page {page!r}: RAISED")
                for e in errors:
                    print("      " + e.strip().splitlines()[-1])
                report.append({"surface": f"options:{page}", "error":
                               errors[0].strip().splitlines()[-1]})
                continue
            print(f"    page {page!r}: cursor={lb.curselection()} "
                  f"kids={n_kids} first={_first!r}")
            wid2, name2, b2 = find_window(pid, "Options")
            if wid2 is None:
                continue
            safe = "".join(ch if ch.isalnum() else "_" for ch in page)
            p = OUT / f"options_{safe}.png"
            capture(wid2, p, b2)
            report.append({"surface": f"options:{page}", "port": p.name})
            print("  captured", p.name)

            native = NATIVE_OPTIONS.get(page)
            if native and (NATIVE / native).exists():
                side_by_side(NATIVE / native, p, OUT / f"cmp_{safe}.png")

    # --- the other surfaces ------------------------------------------------
    # native: 2130 popup, 2133 keyboard, 2134 history, 2131 main.
    def _open_history():
        app.history.append(("google", "person_record", "nguồi_record", True))
        app.open_history_window()

    for surface, opener, title in (
            # the source language is passed RESOLVED, as the app's own
            # call sites do (`res.source_language_code or src`), so the
            # caption reads "English to Viet..." like native's
            ("popup", lambda: A.show_popup("English to Vietnamese",
                                          "người_record", "google", "vi",
                                          "en"), "QTranslate"),
            ("keyboard", app.open_keyboard, "keyboard"),
            # native's capture has one entry (a favourite "person_record"
            # and its child "nguồi_record"), so the port needs one too
            # for the trees to be comparable
            ("history", _open_history, "History"),
            ("dict", app.open_dict_window, "Dictionary")):
        try:
            opener()
        except Exception as exc:
            print("  %s: could not open (%s)" % (surface, exc))
            continue
        root.update_idletasks()
        root.update()
        time.sleep(0.4)
        root.update()
        if title == "QTranslate":
            _w, _n, _b = find_unnamed(pid, skip=_MAIN_IDS)
        else:
            _w, _n, _b = find_window(pid, title, skip=_MAIN_IDS)
        if _w is None:
            print("  %s: no window titled %r" % (surface, title))
            continue
        _p = OUT / ("%s.png" % surface)
        capture(_w, _p, _b)
        report.append({"surface": surface, "port": _p.name})
        print("  captured", _p.name, _b)

    # side-by-sides for the surfaces native captured
    # native: 2130 popup, 2131 main, 2132 dictionary, 2133 HISTORY,
    # 2134 KEYBOARD. (2133 and 2134 were swapped until 2026-10-21: the
    # History window is 476x320 and the virtual keyboard is 464x198.)
    for surface, native in (("main", "2131.png"), ("popup", "2130.png"),
                            ("keyboard", "2134.png"), ("history", "2133.png"),
                            ("dict", "2132.png")):
        _pp = OUT / ("%s.png" % surface)
        _nn = NATIVE / native
        if _pp.exists() and _nn.exists():
            side_by_side(_nn, _pp, OUT / ("cmp_%s.png" % surface))
            print("  compared %s with %s" % (surface, native))

    json.dump(report, open(OUT / "_captured.json", "w"), indent=1)
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
