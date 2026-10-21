# Main-window fidelity against the native screens — three real defects fixed (2026-10-21)

> **Scope:** the main window only, compared against
> `docs/review/native_screens/2131.png` (the real QTranslate 6.10.0 main
> window). Every number below is measured, not estimated: the native's bands
> come from pixel analysis of its screenshot, the port's come from the live
> Tk widget geometry and from a Quartz capture of the port's own window.
>
> **No checklist row state changed by this document** except G9's note, which
> now records what was measured.

---

## 1. How this was found, and why the earlier review missed it

`FULL_FEATURE_UI_STATUS_2026-10-17.md` §3 compared the 13 native captures
against the port's screenshot set and called the main window "**Close** —
same panes, toolbar, boot text. Native has service icon strip; port has it
too."

That last clause was **wrong**. The port's macOS screenshots have no service
icon strip at all, and its "Google" link renders in a different colour with
a different font. The earlier comparison was a *visual* one between two
images of different size, on a host where the port could not be captured at
all (`screencapture` is denied here).

Two things changed on 2026-10-21 and made the check possible:

1. **`screencapture` is not the only capture path.** `CGWindowListCreateImage`
   on a window belonging to *this process* works without the Screen
   Recording grant that `screencapture` needs. The port's own window can
   therefore be captured on this host — and it can be captured **at the
   native's exact size**.
2. **The native's own assets were recovered**, so the port can draw what
   native draws instead of approximating it.

---

## 2. The three defects

### 2.1 The service strip was 2334 pixels wide inside a 587-pixel window

**Root cause — a Tk unit trap.** Tk reads a button's `width`/`height` as
**characters** for a text button and as **pixels** for an image button. The
strip's buttons were created as:

```python
b = tk.Button(cell, width=22, height=22, borderwidth=0, ...)
```

and the image was only ever loaded from
`C:/Program Files (x86)/QTranslate/Services/<Name>/Service.ico`. Off
Windows that path does not exist, so the button fell back to **text** — and
`width=22` became 22 *characters*.

Measured on the live widget tree, before the fix:

| | before | after |
|---|---|---|
| one strip button | **230 × 16 px** | 18 × 16 px |
| the strip's required width | **2334 px** | **426 px** |
| the window's width | 587 px | 587 px |
| services visible | **3 of 9** | **9 of 9** |

Six of the nine services were pushed off the end of the window entirely —
which is why the macOS screenshot showed no strip at all: three oversized
buttons covered the whole row and the rest were clipped.

### 2.2 The Translate button was cut off

The tool row was packed left to right, so on a 516-pixel window it
overflowed.

| element | native x | port x (before) | port x (after) |
|---|---|---|---|
| page icon | 4–13 | 8–64 (with the kebab) | 8–64 |
| kebab | 22–34 | — | — |
| Auto-Detect combo | 67–216 | 139–262 | 139–253 |
| swap | 223–249 | 264–280 | 264–280 |
| target combo | 256–432 | 356–479 | 302–425 |
| **Translate** | **438–510** | **481–497 (clipped)** | **413–493** |

The row is now **gridded** with the two combobox columns carrying the
weight, so the Translate button is always fully visible and the comboboxes
share whatever is left.

### 2.3 The main window opened with a three-line stub instead of native's help

`default_source_text()` read
`C:/Program Files (x86)/QTranslate/Locales/English/help.txt`. Off Windows
that file does not exist, and the fallback was three lines:

```
Double Ctrl => Show main window
Ctrl+Q => Translate selected text
Ctrl+E => Listen to selected text
```

Native opens with the **whole** help file — Global hotkeys, Main window
hotkeys, three mouse modes, and the Actions list. The port's own docstring
already said so ("it shows the whole help.txt … not just 4 lines"), which
made the stub a known divergence nobody could fix, because the file was
never in the repository.

---

## 3. The recovery: native's own assets, out of the installer and the EXE

### 3.1 The service strip icons (18 in the payload, 9 needed)

The NSIS payload carries **18 single-image `.ico` files**, each a 16×16
icon — the service icons. The payload has no filenames, so they were
identified by *pixels*: each was decoded to RGB and matched against the
native's own strip in `docs/review/g9_evidence/out/native.png` (a
`PrintWindow` capture of the real `QTranslate.exe`).

Nine matched **exactly** (`ssd = 0` for three of them, the rest within
anti-aliasing distance), and the pairing was confirmed visually in
`docs/review/rea/service_icons/_pairs.png` — native icon beside recovered
icon, nine pairs.

| native strip position | label | service | payload chunk |
|---|---|---|---|
| 1 | `Go..` | google | 17 |
| 2 | `Mi..` | microsoft | 21 |
| 3 | `Pr..` | promt | 29 |
| 4 | `Ba..` | babylon | 8 |
| 5 | `Ya..` | yandex | 39 |
| 6 | `yo..` | youdao | 33 |
| 7 | `Ba..` | baidu | 11 |
| 8 | `Pa..` | naver | 25 |
| 9 | `DeepL` | deepl | 13 |

They are committed at `qtranslate/assets/service_icons/` and are loaded on
every platform — the port no longer depends on a Windows install existing.

### 3.2 The microphone and the headphone (from the EXE's RT_ICON resources)

`rea inspect-pe-resources` reports the native EXE's resource tree: **24 icon
groups**, of which group 0 is the application icon. Two of them are the
glyphs the native overlays on the source and result panes:

| native glyph | native pixels | recovered |
|---|---|---|
| microphone | x 453–464, bottom-right of the source pane | `ui_23` (ssd 35560) |
| headphone | x 474–487, bottom-right of the source pane | `ui_08` (ssd 38931) |
| headphone | bottom-right of the **result** pane | the same `ui_08` |

The port had the text `Mic` and a **music note** (U+266B) there. The
music note was not a font-substitution artefact — it was simply a different
symbol. The native's own icons are committed at
`qtranslate/assets/ui_icons/` and are now what the port draws.

The application icon (group 0) matches the native window's title-bar icon
**exactly** (`ssd = 144` over 768 channel bytes) and is bundled as
`qtranslate/assets/app_icon/QTranslate.ico`, so the built executable now
ships native's own icon instead of none.

### 3.3 The 35 UI locale packs (from the payload)

The payload carries all 35 `Locales/<dir>/lang.json` and 35
`Locales/<dir>/help.txt` files — the census already proved them
SHA-256-identical to the installed ones, but the port could not reach them
because `locale.LOCALES_DIR` was the Windows install path.

They are now bundled at `qtranslate/assets/locales/`, with the directories
named the way the native's installed tree names them (`Bulgarian`,
`Vietnamese`, `Portuguese (Europian)` — native's own spelling), so the
bundled tree is a drop-in for the installed one.

**The `help.txt` files needed a pairing the payload does not carry.** The
payload interleaves the two streams — the `lang.json` at chunk 44 is
Arabic's, the `help.txt` at chunk 45 is *also* Arabic's, but chunk 66
(German's `lang.json`) is followed by chunk 67 (the **Greek** help). The
pairing was recovered by vocabulary: a pack's `lang.json` holds the locale's
translated UI strings and its `help.txt` holds the same locale's translated
hotkey descriptions, so scoring word overlap identifies the partner. The
median margin between the best and second-best pack is **0.32**; five
locales whose margin fell below the threshold (German, Italian, Dutch,
Romanian, Slovak) ship with `lang.json` only, and their `help.txt` is
recorded as unpaired in `qtranslate/assets/locales/_manifest.json` rather
than guessed.

**English is identified by content, not by score.** The payload holds *two*
English copies: chunk 57 (1,989 B — three mouse modes, an `F11` entry, and
the full Actions list) and chunk 91 (1,706 B — two mouse modes, "the
program's icon"). Chunk 57 is 6.10.0's; chunk 91 is a stale copy.

### 3.4 A native defect found on the way

**Native's Bulgarian `lang.json` is not valid JSON.** It carries a double
comma (`[184, "Напред (Alt+Right Arrow)"],,`) — a hand-editing slip that no
trailing-comma stripper fixes. The port's `locale._read_pack` already
collapses comma runs for exactly this reason, and
`docs/review/RELIABILITY_WIRING_AUDIT_2026-10-10.md`'s sibling note
records the same finding for Mongolian. This is a **native** defect, not a
port one; the port is deliberately more tolerant than the artifact it
mirrors.

---

## 4. The result

`docs/review/ui_fidelity_2026-10-21/native_vs_port.png` — native on top,
the port below, both at the same width:

| surface | native | port (before) | port (after) |
|---|---|---|---|
| service strip | 9 icons + labels | **absent** (3 giant buttons, 6 off-screen) | 9 icons + labels, native's own bitmaps |
| source pane help text | full help file | 3-line stub | full help file |
| source pane overlay | microphone + headphone | text `Mic` + **music note** | native's microphone + headphone |
| result pane overlay | headphone | music note | native's headphone |
| tool row | Translate at the right edge | **Translate clipped** | Translate fully visible |
| Auto-Detect combo | 150 px, label complete | clipped to `Auto-Detec` | complete |

`port_main_macos.png` is the port's window after the fixes;
`port_main_before_overlay_fix.png` is the same window before §2.2 and §2.3.

**Still open, and deliberately not claimed as fixed:**

- ~~The port's source pane is 170 px where native's is 151 px, and the
  port carries two bands native's capture does not show (a 17 px
  suggestion strip and a 16 px third pane).~~ **Closed 2026-10-21** by
  `UI_FIDELITY_MAIN_WINDOW_BANDS_2026-10-21.md`: native's capture shows
  the third pane (1018) COLLAPSED to zero height and no suggestion band
  at all, so both are now shown only when they have content, and the
  source pane takes native's 153 px.
- ~~The port's result pane is empty on boot where native shows
  "No data returned (timeout while sending data.)"~~ **Closed 2026-10-21**:
  that is native RESTORING `Contents.EditTranslation` on boot (its saved
  value was the message left by a timed-out translation), not a
  translation on boot. The port restores the same key; it had nothing to
  restore because off Windows its settings file never persisted.
- The port's window is 512 px wide where the native capture is 516 px, and
  the title bars are different because macOS draws different chrome.
- ~~The port has no vertical scrollbar on the source pane.~~ **Closed
  2026-10-21**: the pane grows a scrollbar when the content overflows,
  as native's RichEdit does.

---

## 5. Reproduce

```bash
# the port's own window, captured with Quartz (no Screen Recording needed)
~/.local/bin/python3.11 tools/_scratch/capture_window.py /tmp/port.png

# the regression that pins all of it
~/.local/bin/python3.11 -I tests/regress_main_window_fidelity.py
#   -> regress_main_window_fidelity: all checks ok (43 assertions)

# the band-by-band geometry comparison
~/.local/bin/python3.11 tools/_scratch/band_compare.py
```

The capture helper lives under `tools/_scratch/` because it is a
measurement aid, not part of the product; the regression test is the
committed, runnable part.

---

## 6. What this changes elsewhere

- `docs/RE_COVERAGE_CHECKLIST.md`'s G9 row: the note now records that the
  **client area** of the main window matches at **0.21 %** (0.026 % excluding
  the caption), that the 5.35 % whole-image difference was window frame, and
  that the main window's *content* was separately wrong off Windows in three
  ways, now fixed.
- `docs/review/G9_DIFF_DECOMPOSITION_2026-10-21.md` §4: the harness change
  that stops a frame artifact being reported as a fidelity failure.
- `docs/review/FULL_FEATURE_UI_STATUS_2026-10-17.md` §3: its claim that
  "port has [the service icon strip] too" was wrong on this platform and is
  corrected by this document.
