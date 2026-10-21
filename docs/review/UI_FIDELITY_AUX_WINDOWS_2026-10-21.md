# UI fidelity: the virtual keyboard and the history window (2026-10-21)

> **Scope:** the two remaining aux windows — the **virtual keyboard**
> (native DLG 162) and the **History window** (native DLG 164) — and a
> correction to the review itself: two native screen numbers had been
> swapped.
>
> **No checklist row state changed by this document.**

---

## 1. 2133 and 2134 were swapped

`docs/review/native_screens/` holds thirteen captures of the real
`QTranslate.exe`. Two of them were attributed to the wrong windows:

| capture | size | what it is | what the review said |
|---|---|---|---|
| `2133.png` | 476×320 | the **History** window | the virtual keyboard |
| `2134.png` | 464×198 | the **virtual keyboard** | the History window |

The evidence is in the pixels: `2133.png` has the History window's
title, its `✕` in the tree's corner, its `person_record → nguồi_record`
tree and its `Clear / Save as... / ★ / OK` row; `2134.png` has the key
grid and the language combo.

That is not a cosmetic mistake — it meant the side-by-side comparisons
showed the port's keyboard next to native's *history window*, and the
port's history next to native's *keyboard*, and both were read as
"Close". The capture script and the three review documents that carried
the mapping are corrected.

## 2. The virtual keyboard had three rows of letters

Native's **DLG 162** declares only two controls — the language combo
(1064) and a small static (1155). The **key grid is built at run
time**, so the layout had to be read off native's own capture
(`2134.png`):

```
Esc | F1 F2 F3 F4 | F5 F6 F7 F8 | F9 F10 F11 F12
` 1 2 3 4 5 6 7 8 9 0 - = | BkSp
Tab | q w e r t y u i o p [ ] \
Caps | a s d f g h j k l ; ' | Enter
Shift | z x v b n m , . / | Shift
Ctrl Win Alt | (space) | AltGr Apps ^ v < >
[English ▾]
```

The port had `qwertyuiop / asdfghjkl / zxcvbnm` and a space bar. No
digits, no capitals, no punctuation — and nothing to type a URL with.
It now has native's six rows and the language combo.

**The keys are labels, not buttons.** A Tk button carries a platform
minimum width — 48 pixels for a two-character key on macOS, where
native's is 29 — so native's fifteen-key row could not have fitted.
A label sizes to its text and its padding is in pixels, so the widths
below are native's own; the widest row is 464 pixels, which is native's
window width.

**The window sizes itself to the grid**, like native's: the capture is
464×198 where DLG 162's template converts to 539×191. A *saved*
placement still wins — `placement.place_aux` now returns the placement
it applied so the keyboard can tell the two cases apart.

## 3. The history window's bottom row was missing two controls

Native's **DLG 164** declares six controls:

| id | class | text | x | y | cx | cy |
|----|-------|------|---|---|----|---|
| 1 | `Button(DEFPUSHBUTTON)` | `OK` | 264 | 161 | 50 | 14 |
| 1170 | `Edit` | | 1 | 2 | 313 | 14 |
| 1163 | `SysTreeView32` | | 1 | 18 | 313 | 141 |
| 1067 | `Button(PUSHBUTTON)` | `Clear` | 1 | 161 | 50 | 14 |
| 1160 | `Button(PUSHBUTTON)` | `Save as...` | 54 | 161 | 74 | 14 |
| 1173 | `Button(RADIO)` | | 130 | 161 | 15 | 14 |

The port's bottom row was `Favorite / Clear / Save as...` — a wide
**text** button where native has a **15×14 star**, and no `OK` at all.
It is now `Clear / Save as... / ★ / OK`, with the star carried by the
EXE's own `RT_ICON` group (the yellow star, `ui_21`) and showing the
selection's own favourite state, as native's does.

The tree itself is still different: native's `SysTreeView32` shows a
single indented column with the star in front of the text, while the
port's `ttk.Treeview` has three headed columns (Translation, ★,
Service). That is recorded, not changed — the port's columns carry the
service name, which native's does not show.

## 4. Evidence

| What | Where |
|---|---|
| native's keyboard | `docs/review/native_screens/2134.png` |
| native's history | `docs/review/native_screens/2133.png` |
| the port's captures | `docs/review/ui_fidelity_2026-10-21/surfaces/` |
| the side-by-sides | `docs/review/ui_fidelity_2026-10-21/surfaces/cmp_keyboard.png`, `cmp_history.png` |
| the behaviour test | `tests/regress_aux_windows_fidelity.py` (76 assertions) |
| the bundled star icons | `qtranslate/assets/ui_icons/` (+ `manifest.json`) |
