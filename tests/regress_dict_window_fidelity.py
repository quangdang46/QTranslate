"""Regression: the Dictionary window's service strip, asserted on the live widgets.

Native's Dictionary window (`docs/review/native_screens/2132.png`, DLG 184)
ends with a strip of the dictionary services -- one cell per service, each
with the service's own icon and its name clipped to the cell's width. The
measured facts this pins:

* **Eleven cells**, in native's order: Google Search, WordReference,
  Babylon Dictionary, Wikipedia, Multitran, ImTranslator, Reverso, Urban
  Dictionary, ABBYY Lingvo Live, youdao, Oxford Learner Dictionary. The
  icons sit at x = 7, 49, 91, ... in the capture, so the cells are
  **42 pixels** apart, and each icon is **16x16**.
* **The label is the first letter of the name plus an ellipsis.** Read as
  a brightness map, cell 0 is the letter "G" at columns 8-12 followed by
  three dots at 15, 16 and 17 -- "G..." -- and cell 10 is the letter "O"
  at columns 8-14 followed by dots at 17, 19 and 21.
* **Wikipedia's icon is a white 16x16 tile with a black serif W.** The
  installer payload carries 18 `.ico` files for 19 services and the EXE's
  own RT_ICON resources do not carry it either, so the tile is re-drawn
  from native's own pixels.

Three real defects were found by rendering the port's window and measuring
it against those numbers:

1. **Every icon drew as an empty box.** The `PhotoImage`s were held in a
   local list that went out of scope when the builder returned; Tk frees
   an image when the last Python reference to it goes, and a button whose
   image was freed draws nothing at all.
2. **The zoom row had no size.** It was packed *after* the result pane,
   which is packed with `expand=True` and therefore takes the whole
   cavity -- the row measured 1x1 and was never visible.
3. **The magnifier, the clock and the ':' menu were invisible.** They were
   packed after the search field, which is also `expand=True`, so all
   three measured 1x1.

Every assertion here calls the real code and reads the real widget
geometry; none of them greps source text.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


# --- the bundled assets ------------------------------------------------------
ASSETS = os.path.join(ROOT, "qtranslate", "assets")
DICT_ICONS = os.path.join(ASSETS, "dict_icons")

# Native's eleven cells, in native's order (2132.png, icons at x=7+42k).
NATIVE_ORDER = ("google-search", "wordreference", "babylon", "wikipedia",
                "multitran", "imtranslator", "reverso", "urban", "lingvo",
                "youdao", "oxford")

ck("the dictionary icons are bundled", os.path.isdir(DICT_ICONS), DICT_ICONS)
for stem in NATIVE_ORDER:
    path = os.path.join(DICT_ICONS, stem + ".png")
    ck(f"{stem}: the dictionary icon is bundled", os.path.isfile(path), path)

# The manifest has to agree with what is on disk.
try:
    import json
    with open(os.path.join(DICT_ICONS, "manifest.json"),
              encoding="utf-8") as fh:
        man = json.load(fh)
    ck("the manifest lists eleven dictionary icons",
       len(man.get("icons", {})) == 11, str(len(man.get("icons", {}))))
    ck("the manifest's size is native's 16x16",
       man.get("size") == [16, 16], repr(man.get("size")))
except Exception as exc:
    ck("the dictionary icon manifest loads", False, repr(exc))

# Wikipedia's tile: a white square with a black W in it.
try:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "g9", os.path.join(ROOT, "tools", "g9_screenshot_diff.py"))
    g9 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g9)
    from pathlib import Path
    w, h, rgb = g9.png_decode(Path(os.path.join(DICT_ICONS,
                                                "wikipedia.png")))
    ck("the Wikipedia tile is 16x16", (w, h) == (16, 16), f"{w}x{h}")
    dark = sum(1 for i in range(w * h)
               if sum(rgb[i * 3:i * 3 + 3]) / 3 < 128)
    white = sum(1 for i in range(w * h)
                if sum(rgb[i * 3:i * 3 + 3]) / 3 > 235)
    ck("the Wikipedia tile is mostly white", white > 110, str(white))
    # Native's own capture is upscaled, so its near-black count (49) is a
    # lower bound on the bitmap's; the re-drawn tile measures 46.
    ck("the Wikipedia tile draws a dark W", 30 < dark < 70, str(dark))
except Exception as exc:
    ck("the Wikipedia tile decodes", False, repr(exc))

# --- the live window ---------------------------------------------------------
import tkinter as tk  # noqa: E402
from qtranslate import app as A  # noqa: E402

root = tk.Tk()
root.withdraw()
app = A.App(root)
root.update_idletasks()
root.update()

win = app.open_dict_window()
root.update_idletasks()
root.update()
ck("the dictionary window opens", win is not None)


def walk(w, out=None):
    out = out if out is not None else []
    for c in w.winfo_children():
        out.append(c)
        walk(c, out)
    return out


allw = walk(win)

# The service strip: a frame holding one cell per service.
strip = None
for f in allw:
    if f.winfo_class() == "Frame":
        kids = f.winfo_children()
        if kids and all(k.winfo_class() == "Frame" for k in kids) and len(kids) >= 9:
            strip = f
            break
ck("the service strip exists", strip is not None)
if strip is not None:
    cells = strip.winfo_children()
    ck("the strip has native's eleven cells", len(cells) == 11, str(len(cells)))
    # Each cell: an IMAGE button and the clipped label.
    for i, cell in enumerate(cells):
        btns = [k for k in cell.winfo_children()
                if k.winfo_class() == "Button"]
        cvs = [k for k in cell.winfo_children() if k.winfo_class() == "Canvas"]
        ck(f"cell {i}: holds one button", len(btns) == 1, str(len(btns)))
        ck(f"cell {i}: holds the label canvas", len(cvs) == 1, str(len(cvs)))
        if btns:
            img = str(btns[0].cget("image"))
            ck(f"cell {i}: the button carries an IMAGE, not a text fallback",
               img not in ("", "none"), img[:40])
            ck(f"cell {i}: the image is still alive in Tk",
               img in win.tk.call("image", "names"),
               "Tk freed the PhotoImage -- the button draws an empty box")
            ck(f"cell {i}: the button is pixel-sized",
               btns[0].winfo_reqwidth() <= 24,
               str(btns[0].winfo_reqwidth()))
        if cvs:
            items = cvs[0].find_all()
            texts = [cvs[0].itemcget(i, "text") for i in items
                     if cvs[0].type(i) == "text"]
            ck(f"cell {i}: the label is the first letter plus an ellipsis",
               len(texts) == 1 and len(texts[0]) == 4
               and texts[0].endswith("..."), repr(texts))
            ck(f"cell {i}: the label canvas is a fixed width (it clips)",
               cvs[0].winfo_reqwidth() <= 26,
               str(cvs[0].winfo_reqwidth()))

    # The cells are 42 pixels apart, like native's.
    if len(cells) >= 2:
        xs = [c.winfo_rootx() for c in cells]
        pitches = [b - a for a, b in zip(xs, xs[1:])]
        ck("the cells are native's 42 pixels apart",
           all(p == 42 for p in pitches), str(pitches))

    # The strip sits on the BOTTOM edge of the window.
    ck("the strip is on the bottom edge of the window",
       abs((strip.winfo_rooty() + strip.winfo_height())
           - (win.winfo_rooty() + win.winfo_height())) <= 4,
       f"strip bottom {strip.winfo_rooty() + strip.winfo_height()}, "
       f"window bottom {win.winfo_rooty() + win.winfo_height()}")

# The images are held on the window, so they survive the builder's return.
ck("the window holds the PhotoImages",
   len(getattr(win, "_dict_icon_images", []) or []) == 11,
   str(len(getattr(win, "_dict_icon_images", []) or [])))

# The result pane's scrollbar: native's dictionary window has one (the
# capture 2132 shows its up and down arrows at the right edge).
_sbar = getattr(win, "_dict_scroll", None)
ck("the dictionary result pane has a scrollbar", _sbar is not None)
if _sbar is not None:
    ck("the scrollbar scrolls the result pane",
       _sbar.cget("command") != "", repr(_sbar.cget("command")))

# The zoom row: it must have a size. It used to be packed after the
# result pane and measured 1x1.
zoom = [f for f in allw
        if f.winfo_class() == "Frame"
        and any(k.winfo_class() == "Button"
                and str(k.cget("text")) in ("A-", "A+")
                for k in f.winfo_children())]
ck("the zoom row exists", bool(zoom))
if zoom:
    ck("the zoom row is VISIBLE (it used to measure 1x1)",
       zoom[0].winfo_height() > 4, str(zoom[0].winfo_height()))

# The top row: the magnifier, the clock and the ':' menu.
for glyph, what in (("⌕", "the magnifier"), ("⌗", "the history clock"),
                    ("⋮", "the ':' menu")):
    btns = [b for b in allw
            if b.winfo_class() == "Button" and str(b.cget("text")) == glyph]
    ck(f"{what} exists", bool(btns))
    if btns:
        ck(f"{what} is VISIBLE (it used to measure 1x1)",
           btns[0].winfo_width() > 4 and btns[0].winfo_height() > 4,
           f"{btns[0].winfo_width()}x{btns[0].winfo_height()}")

root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_window_fidelity: all checks ok (%d assertions)" % n[0])
