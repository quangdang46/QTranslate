# UI fidelity: the non-Options surfaces (2026-10-21)

> The companion to `UI_FIDELITY_OPTIONS_2026-10-21.md`. That one covers
> the Options window; this covers the five other windows the native
> captured, and it is the **re-capture** of the surfaces that
> `qt-fj5` lists as outstanding ("a re-capture of the other 12 native
> surfaces under a matched protocol").

## 1. The capture, and the bug that made it wrong

The port's own windows are captured on this host with
`CGWindowListCreateImage` (a window belonging to *this* process does
not need macOS Screen Recording permission) and placed beside the
native captures.

**The first capture harness was wrong.** The `CGImage` is 32-bit
**BGRA** and the harness read the bytes as RGB, so red and blue came
out swapped. Measured on this host:

| drawn | captured |
|---|---|
| `#0000ff` | `f60e00` |
| `#ff0000` | `142eee` |
| `#00ff00` | `3cfa5a` (unchanged) |

So every port screenshot taken before the fix had its red and blue
exchanged -- the port's blue checkbox grid and blue listbox selection
came out orange next to the native's, and the *only* way that was
visible was the Options page, where the port's blue squares sat next
to the native's blue squares. **Every earlier claim of a colour
difference between the port and the native was an artifact of the
harness** and does not survive it.

The harness also has to work around two macOS facts: an
`overrideredirect` window (the popup) has **no title**, so it cannot
be found by name; and the window list holds the main window and the
popup under the same name, so the main window has to be excluded when
looking for the popup.

## 2. The surfaces

| Native | Port | Surface | Verdict |
|---|---|---|---|
| `2131.png` (516×423) | `main.png` (595×404) | Main window | **Close** -- same panes, same toolbar, same boot text, same service strip with the same truncated labels, the mic/headphone overlay in the same corner. The port is 79px wider (it uses the template's width rather than the captured instance's). |
| `2130.png` (265×115) | `popup.png` (265×79) | Ctrl+Q popup | **Close** -- same caption row, the same ★, the same four glyphs, the same result line. **Fixed 2026-10-21**: the port drew a fixed 60-column text area (616px wide) where native sizes the popup to its content and truncates the caption to fit ("English to Viet…"), and it had no close button. The port's fourth glyph was a refresh arrow; native's is the romanization mark "b" over "a". |
| `2132.png` (476×333) | `dict.png` (553×374) | Dictionary window | **Close on the row, open on the strip** -- native's DLG184 is three controls: a language ComboBox (1142), a search Edit (1183) and a `:` menu button (1187), and the capture shows the row it builds around them: `[language v] [<][>] [field] [q] [d] [v]`. The port drew a `Word:` field + `Exact` + `Look up` instead; it now draws native's row, the arrows walking the `DictionaryHistory.json` the port already writes and the magnifier running the lookup. **The strip is closed 2026-10-21**: native's eleven-cell service strip is drawn from the recovered payload icons, matched to native's own pixels, and the Wikipedia cell -- which has no `.ico` in the artifact at all -- is re-drawn from native's capture. The match that was inconclusive before is now conclusive because it is a template match over every candidate icon and every strip position rather than a best guess; two of the eleven match native's pixels EXACTLY. See `UI_FIDELITY_DICTIONARY_2026-10-21.md`. |
| `2133.png` (476×320) | `keyboard.png` (539×219) | Virtual keyboard | **Close** -- same key layout, same language dropdown. The port is 63px wider (the template's 539px against the captured instance's 476px). |
| `2134.png` (464×198) | `history.png` (553×359) | History window | **Close** -- same tree, same buttons. The port is 89px wider and 161px taller (the template's 553×331 against the captured instance's 464×198). |
| `2126.png` (663×388) | -- | Tray menu | **Not capturable** -- the tray menu is a Tk menu, not a window, so a window capture cannot see it. The native's is a bitmap. |

The three aux windows (keyboard, history, dictionary) were previously
opened at **arbitrary** sizes -- the keyboard's default was even raw
dialog units used as pixels (308x102). They now take their size from
the native's own dialog templates (`placement.template_geometry`).

## 3. What the re-capture does and does not settle

It settles the **port side** of every native surface: the port is now
rendered, captured and compared under one protocol, and the
comparisons are in `docs/review/ui_fidelity_2026-10-21/surfaces/`.

It does **not** settle G9 part (b), and it does not close `qt-fj5`:

* G9 part (b) requires a **human** to open `native.png` / `port.png` /
  `diff.png` and confirm the capture circumstances. A screenshot ban
  forbids exactly that, and no agent may self-assign the waiver the
  row needs.
* The **native** captures are the operator's; they were taken under
  their own protocol, and the two sides still differ in capture method
  and focus (see `G9_DIFF_DECOMPOSITION_2026-10-21.md`). The
  decomposition already shows that the 5.3508% whole-image difference
  is 97.5% window frame and 0.2087% client area.

What this document adds is the **re-capture of the other surfaces**
that `qt-fj5` listed as outstanding, done under one protocol on the
port side, with the differences *classified* rather than asserted away.
The remaining human steps are unchanged: the review, the waiver token,
and a matched re-capture of the native side.

## 4. Reproducing

```bash
~/.local/bin/python3.11 tools/_scratch/capture_surfaces.py
# -> docs/review/ui_fidelity_2026-10-21/surfaces/cmp_*.png
```

The harness writes `_captured.json` (what was captured) and prints
the window id, name and bounds it captured, so a reviewer can check
the capture circumstances without re-deriving them.
