# UI fidelity: the Dictionary window's service strip (2026-10-21)

> **Scope:** the Dictionary window (native DLG 184, capture
> `docs/review/native_screens/2132.png`) and specifically the **service
> strip** along its bottom edge — the one part of that window the port
> did not have at all.
>
> **No checklist row state changed by this document.** G9 part (b) stays
> `UNKNOWN` and needs a human reviewer and a human-written waiver; this
> document records what was measured, not a Gate promotion.

---

## 1. What native's strip is, measured

Native's Dictionary window ends with a band of one cell per dictionary
service. Reading the capture:

| Measured | Value | How |
|---|---|---|
| Cells | **11** | one per dictionary service, in native's order |
| Icon size | **16 × 16** | the payload's `.ico` groups are all 16×16 |
| Cell pitch | **42 px** | the icons sit at x = 7, 49, 91, 133, 175, 217, 259, 301, 343, 385, 427 |
| Label | **first letter + an ellipsis** | cell 0 is the letter "G" at columns 8–12 followed by three dots at 15, 16, 17; cell 10 is "O" at columns 8–14 and dots at 17, 19, 21 |

The order, read off the labels and the icons:

```
G…  W…  B…  W…  M…  I…  R…  U…  A…  y…  O…
Google  WordRef  Babylon  Wiki  Multi  ImTr  Rev  Urban  ABBYY  youdao  Oxford
```

which is the port's own `_dorder` default (`[10, 19, 20, 14, 17, 18, 22,
24, 25, 26, 29]`) — so the port already had the right ORDER and was
missing the rendering.

---

## 2. The icons: where they came from

The installer payload carries **18** `.ico` groups (`\x00\x00\x01\x00`)
for **19** services. Ten of the eighteen are native's dictionary-strip
icons and nine are its translation-strip icons, with `Babylon` and
`youdao` shared between the two strips.

They were identified **by pixels**, not by eye. `tools/_scratch/
match_all_icons.py` template-matches every recovered icon (the payload's
18 *and* the EXE's 24 `RT_ICON` groups) against every position of
native's strip, on 4×4 block averages so that the capture's
antialiasing does not swamp the comparison:

| native cell | icon | score |
|---|---|---|
| 1 Google Search | `icon_015` | 659.8 |
| 2 WordReference | `icon_037` | 837.4 |
| 3 Babylon Dictionary | `icon_008` | 280.5 |
| 5 Multitran | `icon_023` | 226.8 |
| 6 ImTranslator | `icon_019` | 593.6 |
| 7 Reverso | `icon_031` | 297.4 |
| 8 Urban Dictionary | `icon_033` | **0.0** |
| 9 ABBYY Lingvo Live | `icon_006` | **0.0** |
| 10 youdao | `icon_041` | 742.5 |
| 11 Oxford Learner | `icon_027` | 642.5 |

Two of the matches are **exact** (score 0.0): the icon and the pixels
native draws are the same bytes.

### The eleventh cell: Wikipedia

Cell 4 is Wikipedia, and **it has no `.ico` at all** — neither in the
payload's 18 nor in the EXE's 24 `RT_ICON` groups. What native draws is
a 16×16 **white tile with a black serif W**, read off the capture at
x = 134…148, y = 309…324:

```
309  |+++++++++++++++|
310  |               |
313  |##* *##+ ##++##|
314  |*#*  ##+.** .#*|
315  |+##. *#*+#  .# |
316  | ##+ +##**  ** |
317  | *#*  *##  .** |
318  |  ##+ +##  +#  |
319  |  *#* +##* **  |
320  |   ##.*### *.  |
321  |   *##*+##**   |
322  |   *##* *##+   |
323  |    ##+  ##    |
324  |    *+   +*    |
```

The bitmap behind it is not in the artifact, so it is **re-drawn from
those measurements** by `tools/_scratch/make_wikipedia_tile.py`: the four
strokes and the three top bars, drawn at twice the size and averaged
down so the stems carry the same soft edges the upscaled capture shows.
The result measures 46 near-black pixels against native's 49.

The eleven icons are bundled under `qtranslate/assets/dict_icons/` with
`manifest.json` recording the provenance of each one.

### A real mis-assignment this turned up

The port's **youdao** slot was drawing **Urban Dictionary's** orange
`ud` logo, because the manifest assigned `youdao` to `icon_033` — which
is Urban's. Native's `y` is `icon_041`. The translation strip had the
same defect and is now fixed too
(`qtranslate/assets/service_icons/manifest.json`).

---

## 3. Three real defects the render exposed

The strip was written first and drew **empty boxes**. Rendering the
window and measuring it found three separate causes:

1. **Every icon drew as an empty box.** The `PhotoImage`s were held in a
   local list inside the builder. When the builder returned, the list
   went out of scope, Tk freed the images, and a button whose image was
   freed draws nothing at all. The images are now held **on the
   window** (`w._dict_icon_images`).

2. **The zoom row had no size.** It was packed *after* the result pane,
   which is packed with `expand=True` and therefore takes the whole
   cavity. The row measured 1 × 1 and was never visible. The pack order
   is now the layout: the strip, then the zoom row, then the result
   pane.

3. **The magnifier, the history clock and the `:` menu were invisible.**
   Same cause, other end of the row: they were packed after the search
   field, which is also `expand=True`, so all three measured 1 × 1.
   They are now packed from the right edge before the field.

`tests/regress_dict_window_fidelity.py` (108 assertions) pins all
three: it opens the real window and reads the real widget geometry, the
real Tk image names and the real label text.

---

## 4. What is still different

| | Native | Port |
|---|---|---|
| Left service list | none — the strip *is* the selector | a `Dictionaries` listbox (`Dictionary.ShowServicesPane`) |
| Zoom row | none | `A-` / `A+` / `Dictionaries…` |
| Result pane | a vertical scrollbar | no scrollbar |
| Width | 476 px | 553 px (the template's width, not the captured instance's) |

The left list and the zoom row are **port features**, not native
mistakes: the port needs a multi-select to query several dictionaries
at once, and `DictionaryZoom` scales the result font. They are recorded
rather than removed. The strip was added *alongside* the list, so the
port now has both — clicking a strip cell selects that service in the
list and runs the lookup.

---

## 5. Evidence

| What | Where |
|---|---|
| native's capture | `docs/review/native_screens/2132.png` |
| the port's capture | `docs/review/ui_fidelity_2026-10-21/surfaces/dict.png` |
| the two side by side | `docs/review/ui_fidelity_2026-10-21/surfaces/cmp_dict.png` |
| the bundled icons | `qtranslate/assets/dict_icons/` (+ `manifest.json`) |
| the pixel matcher | `tools/_scratch/match_all_icons.py` |
| the Wikipedia tile | `tools/_scratch/make_wikipedia_tile.py` |
| the behaviour test | `tests/regress_dict_window_fidelity.py` |
| the strip zoomed 4× | `tools/_scratch/zoom_dict_strip.py` |
