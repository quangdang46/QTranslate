# UI fidelity: the Options window (2026-10-21)

> The user asked for a check of the port's UI against the native
> screenshots in `docs/review/native_screens/`: *"hiện tại UI lệch, xấu,
> không giống như các ảnh UI gốc"*. This is the Options window -- the
> one surface where the port and the native had **diverged in
> structure**, not just in pixels.

## 1. Method

The port's own windows are rendered on this host and captured with
`CGWindowListCreateImage` (a window belonging to *this* process does not
need macOS Screen Recording permission), then placed side by side with
the native captures. The harness is
`tools/_scratch/capture_surfaces.py`; the output is
`docs/review/ui_fidelity_2026-10-21/surfaces/`.

**The harness had a bug that made every comparison wrong.** The
`CGImage` is 32-bit **BGRA**, and the capture read the bytes as RGB, so
red and blue came out swapped. Measured on this host: a canvas filled
`#0000ff` captured as `f60e00`, one filled `#ff0000` as `142eee`, and
`#00ff00` stayed green. Every port screenshot taken before the fix had
its red and blue exchanged -- the port's blue checkbox grid and blue
listbox selection looked orange next to the native's. **Any earlier
claim of a colour difference between the port and the native was an
artifact of this**, and none of those claims survive.

The comparison is also *structural* first and *pixel* second: the
native's control inventory comes from the recovered image's dialog
templates (`tools/dlg_parse.py`), which is exact, where the screenshot
is only as good as the camera.

## 2. Native's Options window is nine dialogs

`DLG154` is the shell: a nav list (`1078`) and OK / Cancel / Apply
(`1` / `2` / `1049`), with the buttons in a full-width strip along the
**bottom**, right-aligned. Behind it sit **nine** page dialogs, one
per nav entry, and the mapping is fixed by the templates:

| Nav entry | DLG | Controls | Native's title |
|---|---|---|---|
| Basics | 171 | 19 | three group boxes: General / Auto-detect languages / History |
| Hotkeys | 179 | 2 | 'Enable hot keys' + the action list |
| Internet | 172 | 10 | Connection / Proxy |
| Services | 173 | 5 | ONE list (Translation + Dictionary) + 'Add dictionary...' / 'Remove dictionary' |
| **Languages** | **174** | **2** | **the language checklist + 'Check / Uncheck all'** |
| Appearance | 175 | 24 | General / Popup window |
| Exceptions | 176 | 6 | a MODE combo + ONE list + Add / Modify / Delete |
| Advanced | 185 | 19 | Advanced / Mouse mode / API keys |
| Updates | 205 | 4 | 'Automatically check for updates' + changelog + 'Check now' + 'Install' |

`DLG190` ("Languages") is a **separate top-level dialog** -- the
language-pair manager (from/to combos, the `<>` swap, Add / Remove /
Remove All / Up / Down). It is *not* the Options "Languages" page.

### 2.1 Two documents had this wrong, and are corrected here

* `docs/NATIVE_ARCH.md` called 173 the "Offline dicts" page and 174 the
  "Services check" page. Both are the *pages* the templates are: 173
  **is** the Services page (its visible controls are the dictionary
  add/remove), and 174 **is** the Languages page.
* `docs/review/SERVICES_PAGE_PARITY_2026-10-15.md` credited the
  'Check / Uncheck all' button to DLG174 *on the Services page*. It is
  on the Languages page.
* `docs/review/NATIVE_VS_PORT_SCREENSHOT_COMPARISON_2026-10-16.md`
  read the native captures off by one from 2135 on (it had 2135 =
  Services, 2136 = Languages, 2137 = Dictionary). The captures say
  2135 = Internet, 2136 = Services, 2137 = Languages, 2138 =
  Appearance, 2139 = Exceptions, 2140 = Advanced, 2141 = Updates; the
  mapping was re-derived by reading the highlighted nav row and the
  body of each capture.

## 3. What was wrong, and what was done

### 3.1 The English language pack was never loaded (root cause)

`_pack()` skipped the pack when the language was `English` -- the
comment claimed "English = built-in strings". It does not: the pack
holds the **runtime** strings native draws, while the hardcoded
fallbacks in the code are the **design-time** strings from the dialog
*template*, and the two differ:

| Control | Template | Runtime (the pack) |
|---|---|---|
| DLG175 `1159` | `Always activate` | `Activate when opened` |
| DLG175 `1145` | `Transparency (0-90):` | `Transparency (0 - 90):` |
| DLG185 `1151` | `Open links with:` | `Default browser:` |
| DLG185 `1157` | `Google domain:` | `Preferred domain:` |

So **every label in the English UI was the template's text**, in every
page, and the mismatch was invisible in the source because the
fallbacks read plausibly. The pack now loads for English like any other
language.

### 3.2 The Services page drew two EMPTY lists

The lists were filled from `ServicesOrder` / `DictionariesOrder` alone,
and those keys are absent until the user reorders something -- so on a
fresh config **both lists were empty**. They now fall back to the
canonical order (the same nine translation services and the dictionary
services the native capture shows), and the page is native's shape: one
list with the two group headers, the service icons, and 'Add
dictionary...' / 'Remove dictionary'.

### 3.3 The Languages page was a page native does not have

The port's "Languages" page showed "Default languages" with Translate
from / to, Dictionary, Virtual keyboard, Always detect, Smart
detection, Language pairs and a Disabled-languages list. **None of that
is native's Languages page.** It is now DLG174: native's own checklist
of 72 languages in four columns, with 'Check / Uncheck all'. The
per-slot defaults moved to `LANG_DEFAULTS` in `app.py` (where their
four consumers live) and the pair editor is native's separate DLG190.

### 3.4 The group boxes were bold Labels

Every Win32 group box -- 1046 / 1063 / 1064 (Basics), 1049 / 1048
(Internet), 1076 / 1124 (Appearance), 1146 / 1186 / 1158 (Advanced) --
was drawn as a caption with no frame. They are `LabelFrame`s now, and
the controls sit inside them, as native's template puts them.

### 3.5 ComboBoxes were Entries, and the Advanced page duplicated labels

Native's Advanced page has four **ComboBoxes**; the port had ten text
entries, two of them writing the *same* config key under two captions
("Preferred domain:" and "Google domain:" both wrote
`PreferredDomain`). The page also overflowed its window, pushing the
Apply button off the bottom edge. The page is now three group boxes
with the four native combos, and the Advanced/Appearance/Internet pages
fall back to the documented native defaults
(`config.DEFAULT_ADVANCED` / `DEFAULT_APPEARANCE`) for a key a fresh
config does not carry -- so "Enable auto size", "Enable auto position",
"Pin when dragging" and "Auto-hide delay 5" read as native reads them.

### 3.6 The Exceptions mode combo showed a raw Python list

The pack stores a combo's ITEMS as `[[index, text], ...]`, and `_Cw`
stringified the list into the widget. `_Cw` now returns the raw value
for a list, and the page resolves the two modes.

### 3.7 The Exceptions page's entry fields were inline

Native's Exceptions page (DLG176) has three buttons -- Add, Modify,
Delete -- and they open **DLG178**, a separate "Exception" dialog with
a Program name field plus a `...` browse button (1109), a Window class
name field plus its own `...` (1110), and OK / Cancel. The port drew
the two fields inline under the table, so the page had a row of inputs
native does not have. They are now that dialog. Its Program name
`...` opens a file chooser (native's 1112 is a ComboBoxEx32 over the
running programs and the port has no window enumerator), and the Window
class name `...` lists the classes already configured.

### 3.8 Smaller ones

* The Internet page's Timeout is native's **seconds** combo over a
  millisecond config value (native shows 10, the config holds 10000).
* The Options button row is a full-width bottom strip, right-aligned,
  in native's order (OK, Cancel, Apply). It used to be packed after
  the body, so the body had already taken the width and the row was
  pushed off the right-hand edge of the window.
* The nav list is 168px wide (native's 96 DU), not 128.
* The Appearance "Icons:" row is four icon buttons (a document, a
  headphone, two sheets, "b" over "a"), not four labelled checkboxes,
  and the colour fields are swatches, not text entries.

## 4. What still differs

| | Native | Port | Why |
|---|---|---|---|
| Widget chrome | Win32 | macOS Aqua | the platform |
| Checkbox colour | blue | blue (drawn on a canvas) | the Languages checklist is drawn, so it can be blue |
| Popup | 265x115, header truncated with "…" | wider, header not truncated | the popup sizes itself to its header |
| Transparency field | `15` | `217` | the *value* differs (different Options.json), the field is the same |
| Dictionary window (DLG184) | a language combo + a search field + a `:` menu button over a large result area, with a service icon strip along the bottom | the same row now (language combo, history arrows, magnifier, clock, ':' menu) but no bottom icon strip | the dictionary services' own icons are not in the recovered asset set; `docs/review/UI_FIDELITY_SURFACES_2026-10-21.md` |
| Popup | 265x115, header truncated with "…" | wider, header not truncated | the popup sizes itself to its header |
| Tray menu | 2126.png | not captured | the tray menu is a Tk menu, not a window, so the window capture cannot see it |
| Options window | 646x389 (a resized instance) | 751x417 (the template) | the template is the default size |

## 5. Reproducing

```bash
~/.local/bin/python3.11 tools/_scratch/capture_surfaces.py
# -> docs/review/ui_fidelity_2026-10-21/surfaces/cmp_*.png
~/.local/bin/python3.11 tests/regress_options_pages_native.py
```

The regression suite for this work is
`tests/regress_options_pages_native.py` (53 assertions, on the live
widget tree). It pins the pack resolving, the nav order, all nine
pages' native structure, the checklist's 72 languages, the Services
lists being non-empty, the group boxes, and the four native
ComboBoxes.
