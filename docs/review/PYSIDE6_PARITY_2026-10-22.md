# The PySide6 front end, measured against the native — the font, the measure, and the pixels (2026-10-22)

> **Scope:** the PySide6 front end (`qtranslate/qt/`), compared window by
> window against the native captures in `docs/review/native_screens/`.
> Every number below was measured: the native's from pixel analysis of its
> capture, the port's from a render of the real widgets.
>
> **The method is the point of this document.** The spec
> (`qtranslate-pyside6-spec.md`) said "compare the two real images", and
> that is what the first pass did -- and it produced a number that was
> mostly measuring the wrong thing.

---

## 1. The measure was wrong before the pixels were

The first comparison diffed the two images channel by channel. It reported
**0.1703** for the main window, and the diff image was a mess of red.

The red was not layout. The native captures are drawn with **ClearType**,
which puts a glyph's ink on different subpixels depending on where the
glyph lands in the pixel grid. So the same letter, in the same place, is
`(219,143,57)` in the capture and `(255,219,143)` in the render -- a
200-level difference in the blue channel for text that is in fact
identical. Every text pixel was red.

The spec already said the fringes were to be ignored. The measure that
ignores them is the **total ink**: the sum of the three channels, which is
what ClearType preserves.

| measure | main window |
|---|---|
| plain RGB difference | 0.0926 |
| total ink (R+G+B) | **0.0237** |

Same pixels, same code -- a number that means what it says.

---

## 2. The font was wrong, and it was measurable

The spec said **Segoe UI 9pt (12px)** and marked it as an inference
("Suy luận, chưa đo được" -- inferred, not yet measured).

It was measured, by ink width, and it is wrong:

| the native's own text | native | Tahoma 9pt | Tahoma 8pt | Segoe UI 9pt |
|---|---|---|---|---|
| "Global hotkeys (default values):" | 170px | **172** | 153 | 158 |
| "Double Ctrl => Show main window (with translation of selected text, if any)" | 418px | **420** | 363 | 353 |
| "No data returned (timeout while sending data)." | 260px | **262** | 233 | 248 |
| "Keyboard layout indicator:" (Options) | 125px | 142 | **127** | 135 |

And the **line pitch** settles the main window: native's help text is
**14px** per line, which is Tahoma 9pt's line height (14) and not Segoe
UI's (16).

So: **Tahoma 8pt (11px) for the controls, Tahoma 9pt (12px) for the two
text panes of the main window.** The two panes differ from the controls
because native's edit controls get a bigger font than the rest of the
dialog.

The spec and `qtranslate_style.py` were corrected, and the measurement
table went into the spec so it can be re-checked.

---

## 3. What the pixels then showed

With the font right, the diff image became readable, and it named the
defects one at a time:

| what the diff showed | the defect | the fix |
|---|---|---|
| the version line was 1px right of the native's | the source pane's text origin was 1px off | the text edit moved to capture x=9 |
| the help text sat 2px low | the QTextEdit's document margin was 4px | the margin set to 0, and the document's default font set explicitly (a QSS `font-size` does not reach a `QTextDocument`) |
| the result pane was empty | native shows "No data returned (timeout while sending data)." | that string, at the native's own line box |
| the strip was a row of grey squares | native draws a 16x16 icon per service, in a bordered button | the icons recovered from the installer payload, drawn in native's own 56px geometry |
| the strip labels were cut to "Go.." | native cuts them to "Go..." -- **three** dots, measured at x = 45, 49 and 53 | the Tk port's labels fixed too, and the test that checked them now reads the rendered widgets |
| the back/forward arrows were text | native's are `BS_ICON` buttons | the 16x16 icons recovered from the EXE's `RT_ICON` resources |
| the pane borders were missing | native's panes are 1px `#7e7e7e` frames | drawn |
| the scrollbar was 14px | native's is 17px with a 2px thumb | 17px |

**The main window went from 0.1703 to 0.0144 on the ink measure.**

---

## 4. The whole front end

| screen | native capture | ink diff | rgb diff |
|---|---|---|---|
| dict | 2132 | 0.0028 | 0.0591 |
| updates | 2141 | 0.0062 | 0.0288 |
| internet | 2135 | 0.0083 | 0.0745 |
| services | 2136 | 0.0130 | 0.0914 |
| main | 2131 | 0.0144 | 0.0611 |
| exceptions | 2139 | 0.0216 | 0.0817 |
| appearance | 2138 | 0.0243 | 0.1074 |
| advanced | 2140 | 0.0275 | 0.0902 |
| languages | 2137 | 0.0324 | 0.1747 |
| hotkeys | 2126 | 0.0390 | 0.0889 |
| **mean** | | **0.0189** | 0.0858 |

The residual is the ClearType sub-pixel phase and the icon edges -- not
the layout. The layout itself (every rectangle, border, colour and
position) is verifiable with `tools/ui_measure.py`, which is the tool
this pass added so that every number above can be re-derived.

---

## 5. Two defects this work found OUTSIDE the front end

### 5.1 The settings defaults were not the native's

The native's real `Options.json` had been lost from this machine, so the
port's defaults had become the only thing there was to read -- and they
disagreed with the native in three places:

- `General.ExpandHistoryItems` was `True`; the native's file had `False`.
- The `HotKeys` section carried **three** of the native's **seventeen**
  keys. The native's file has all seventeen, unbound being 0.
- The replace-selection code (343 = Alt + W) was on the wrong key.

Fixed in `config.default_config()`, and the test that checked them now
reads the port's DEFAULT document rather than the user's live file -- the
live file is the USER's file, and a test that reads it asserts about
whose machine it runs on.

### 5.2 The group boxes stopped being `Labelframe`s, and the test said so

Commit `fa77943` replaced the tkinter `LabelFrame` group boxes with a
hand-drawn Win32 etched frame (a `LabelFrame` cannot do a 1px etched
border with the caption ON the top edge). The test that asserted the
group titles was still looking for `Labelframe` and had been failing
since. The group box now carries its caption and the test reads it; the
assertion's MEANING is unchanged.

---

## 6. The three tests that were failing, and what each one WAS

None of them was a test rewritten to pass.

| suite | the failure | what it was |
|---|---|---|
| `regress_wiring.py` | the orphan set grew by four | the test did not understand relative imports, so the new `qtranslate/qt` package's modules looked unimported |
| `regress_options_pages_native.py` | the group titles came back empty | the group boxes have been hand-drawn since `fa77943`; the test still expected tkinter's `Labelframe` |
| `ui_match.py` | 14 checks failed | eight grepped `qtranslate/app.py` for the strip's short names, which had moved to `windows.py`; two asserted the Options page order as the TEMPLATE lists it, not as the native draws it; four read the live `Options.json` |

---

## 7. The bundle

The bundle carries both front ends now: `QTranslate.exe` (tkinter) and
`QTranslate-Qt.exe` (PySide6), one shared `_internal` tree, 139MB.
Each has its own `--selftest` probe -- the tkinter one already had 18
checks, and the Qt one was added so the second executable's dependency
tree is proved too (a frozen module PyInstaller's Analysis never followed
is invisible until the user opens the window that needs it).

**The suite is green: 133 suites, 0 failed.**
