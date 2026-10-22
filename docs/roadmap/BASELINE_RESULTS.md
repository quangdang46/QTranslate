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
dialog's `(1, 26)`, the Hotkeys page's `(1, 24)`.

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
| main | 2131 | 0.0107 | 0.0513 |
| dict | 2132 | 0.0028 | 0.0591 |
| hist | 2133 | 0.0046 | 0.0536 |
| kbd | 2134 | 0.0010 | 0.0197 |
| advanced | 2140 | 0.0065 | 0.0488 |
| appearance | 2138 | 0.0045 | 0.0239 |
| exceptions | 2139 | 0.0009 | 0.0091 |
| hotkeys | 2126 | 0.0047 | 0.0296 |
| internet | 2135 | 0.0039 | 0.0581 |
| languages | 2137 | 0.0018 | 0.0490 |
| services | 2136 | 0.0009 | 0.0132 |
| updates | 2141 | 0.0022 | 0.0109 |
| **mean** | | **0.0037** | 0.0355 |

All twelve screens are now in the table. The Hotkeys capture (2126) is
the window's bounding rect, so the OS's drop shadow on the left (seven
near-black columns that are not the app's pixels) is excluded from the
measure.

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
| the History and Keyboard windows written | - | - | the table grows to twelve screens: the History render is given the capture's one Google entry, so that screen compares the drawing, not the data |
| every page corrected on the ink profile | - | - | `tools/inkalign.py` compares the ink in each column and row, which ClearType cannot fool; the offsets it printed were applied -- the combo's left padding (5 to 7), the checkbox indicator (12 to 11), the drop-down arrow (11 to 12), the group box title's baseline (4 to 5px below the frame's top line), the provider strip's 56px buttons, the main window's tool row, the Hotkeys page's scrollbars and its 481px list, the Internet page's rows |
| the artwork recovered from the native | - | - | the parts that are artwork, not font: the Languages page's checkboxes are the theme's own 12x13 sprite (`check_blue.png`), the Appearance page's four buttons are the native's pictograms with the theme's shadow (`ap_icon1..4.png`), the History window's service icon is the real one; the native's pointer is NOT reproduced |
| the twelve screens, measured now | **0.0037** | 0.0355 | the mean over all twelve screens, History and Keyboard included |

The rgb number fell from 0.1703 to 0.0611: **64% of the difference is
gone**. The ink number, which ignores the fringes, is 0.0144: **92% of
the difference is gone** on the measure that counts.

That was the ten-screen table. The twelve-screen table reads 0.0037
against the old 0.0198: **81% of what was left is gone too**. The rgb
number reads 0.0355 against the old 0.0914. The measure did not change
between the two tables; the pixels did.

## 4. What the residual difference is

The remaining ink difference is not layout. It is:

1. **The ClearType sub-pixel phase.** Two renderings of the same glyph
   in the same place still put a little more ink on one subpixel than
   the other, and the ink sum moves by a level or two per pixel. This
   shows up as a thin outline around every glyph.
2. **The icon edges.** The recovered icons are palette images flattened
   onto the window face; the alpha is recovered from the flattened
   colour, and the edge pixels land a level or two off.
3. **The last pixel of the window borders.** Each side carries four
   or eight differing pixels along its whole length (the bottom row
   eight on every screen), the border antialiased a level or two
   differently.
4. **The native's own mouse pointer, which is in all twelve captures.**
   It is a 9x16 white arrow with a black outline, caught wherever it
   happened to be when the screenshot was taken: inside the client
   area on nine screens (the main window's at client (123, 3), the
   Hotkeys page's at (72, 51)), in the title bar on three (dict, and
   languages at client (152, -4), where the origin crop already
   removes it). The render has no pointer. It accounts for about a
   twentieth of the residual: without it the mean would read 0.0035
   against 0.0037. It is left in the measure rather than masked out,
   because the difference is real: the pointer is in the captures and
   not in the renders.

The layout itself -- the rectangles, the borders, the colours, the
positions of every control -- is measurable and is verified by
`tools/ui_measure.py`, by the ink-profile tool `tools/inkalign.py`
(which compares the sum of the ink per row and column, so ClearType
cannot fool it), and by the diff images in
`docs/review/ui_compare/`.

## 5. The Tk port, for comparison

The Tk front end is still the app that runs, and its renders (in
`docs/review/ui_parity/`) were put through the same ink measure on
2026-10-22. It reads **0.0403** mean ink over the same twelve screens
(main 0.0403, advanced 0.0387, languages 0.0417, dict 0.0179, hist
0.0137, kbd 0.1102), against the Qt front end's 0.0037. The old "0.51"
figure was the plain RGB difference, the fringe-counting measure; on
the ink measure the Tk port's problem is not the font but the layout
(the keyboard reads 0.1102, a full tenth of its pixels). That gap is
the reason the PySide6 port exists.
