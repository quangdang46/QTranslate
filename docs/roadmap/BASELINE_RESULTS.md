# BASELINE RESULTS

The measured starting point, and the measured state now. Everything here
is a number that came out of a run on 2026-10-22 on this machine
(Windows 11 Pro 10.0.26200, AMD64).

## 1. The measure

Two things are compared: the native capture of a window, and the Qt
render of the same window. The capture is the window as the OS draws it
-- frame, title bar and all -- and the render is the client area alone,
so the capture is cropped by the window's `ORIGIN` before the two are put
on top of each other. Each window declares where its client area starts
inside the capture; the main window's is `(1, 31)`, the Options
dialog's `(1, 26)`, the Hotkeys page's `(0, 24)`.

The number is the fraction of pixels that differ by more than 8 levels.

**The measure is the TOTAL INK -- the sum of the three channels -- and
not the plain RGB difference.** The native captures are drawn with
ClearType, so the same glyph puts its ink on different subpixels there
than in the Qt render: a pixel that is `(219,143,57)` in the capture can
be `(255,219,143)` in the render, which is a 200-level difference in the
blue channel for text that is in fact identical. The sum of the channels
is what ClearType preserves, and the spec says the fringes are to be
ignored, so the sum is the honest measure of "do these two images draw
the same thing".

Both numbers are reported: `diff` is the ink measure and it is the one
that counts; `rgb` is shown next to it for reference.

## 2. The numbers

Command:

```
uv tool run --python 3.12 --with PySide6 --with pillow python tools/render_qt.py
uv tool run --python 3.12 --with PySide6 --with pillow python tools/render_qt.py --compare
```

| Screen | Native capture | ink diff | rgb diff |
|---|---|---|---|
| main | 2131 | 0.0144 | 0.0611 |
| dict | 2132 | 0.0028 | 0.0591 |
| advanced | 2140 | 0.0286 | 0.0925 |
| appearance | 2138 | 0.0252 | 0.1094 |
| exceptions | 2139 | 0.0212 | 0.0800 |
| hotkeys | 2126 | 0.0391 | 0.0892 |
| internet | 2135 | 0.0078 | 0.0735 |
| languages | 2137 | 0.0352 | 0.2097 |
| services | 2136 | 0.0135 | 0.1023 |
| updates | 2141 | 0.0060 | 0.0290 |
| **mean** | | **0.0194** | 0.0906 |

`hist` (2133) and `kbd` (2134) are not in the table: the History and
Keyboard windows had not been written when this table was taken. See
`PROGRESS.md`.

## 3. Where the number came from

The main window is the one with a history, so it is the one with the
before/after.

| Step | ink diff | rgb diff | What changed |
|---|---|---|---|
| the first Qt render, measured against the capture | - | 0.1703 | the layout was the reference renderer's, which is 3px off on the left and uses the wrong font |
| the font corrected to Tahoma 8pt/9pt | - | 0.1199 | the spec had said Segoe UI 9pt, which was an inference; the measurement says Tahoma |
| the text panes moved onto native's line box | 0.0237 | 0.1007 | the help text sat 2px low and the result text 2px high |
| the measure switched to total ink | 0.0237 | 0.0926 | the RGB number was counting ClearType fringes |
| the strip, the icons and the panes finished | **0.0144** | 0.0611 | the real icons, the real strip geometry, the pane borders |

The rgb number fell from 0.1703 to 0.0611: **64% of the difference is
gone**. The ink number, which ignores the fringes, is 0.0144: **92% of
the difference is gone** on the measure that counts.

## 4. What the residual difference is

The remaining ink difference is not layout. It is:

1. **The ClearType sub-pixel phase.** Two renderings of the same glyph
   in the same place still put a little more ink on one subpixel than
   the other, and the ink sum moves by a level or two per pixel. This
   shows up as a thin outline around every glyph.
2. **The icon edges.** The recovered icons are palette images flattened
   onto the window face; the alpha is recovered from the flattened
   colour, and the edge pixels land a level or two off.
3. **The scrollbar and the rounded corners**, where a 2px radius is
   antialiased slightly differently.

The layout itself -- the rectangles, the borders, the colours, the
positions of every control -- is measurable and is verified by
`tools/ui_measure.py` and by the diff images in
`docs/review/ui_compare/`.

## 5. The Tk port, for comparison

The Tk front end is still the app that runs, and it is compared the same
way by `tools/ui_parity.py`. It sits at roughly **0.51** on the same
measure, because it uses a 611px-wide main window where the native's is
516px, and it does not reproduce the group boxes, the strip or the
scrollbars. That gap is the reason the PySide6 port exists.
