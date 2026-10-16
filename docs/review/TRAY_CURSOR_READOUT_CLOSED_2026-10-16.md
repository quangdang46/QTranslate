# The tray menu's `X: / Y:` readout is NOT a native feature — closed 2026-10-16

> Resolves the open item recorded in
> `NON_TRANSLATE_SURFACES_2026-10-14.md`: *"The tray menu's live `X: / Y:`
> cursor readout (visible in 2126) has no port counterpart — a real gap found
> by this inventory, not yet fixed."*
>
> **It is not a gap.** Three independent sources agree, and the port was right
> all along. No code change was made, which is the point of checking before
> fixing.

## 1. The screenshot shows a debug overlay, not the menu

`screenshots/screens/tray.png` (the reference capture) shows the menu's
**header area** with `X: 490` and `Y: 440` to the right of the `QTranslate`
title. A cursor coordinate in a *static context menu* has no function — a
right-click menu is modal, the cursor is on it, and the value could only be
read once before the menu closes.

That is the signature of a **mouse-mode debug overlay**: the app's mouse-mode
feature tracks the cursor (`FUN_004193F6` reads `GetCursorPos` and feeds
`FUN_00404901`'s OLEACC text-under-cursor path — checklist C10/J/K rows), and
a build with a debug HUD would paint the live position. The capture happens
to show it because the analyst's window class was captured with the overlay
still on.

## 2. The spec's tray menu has no such element

`ui-html-port-need-strict-follow/UI-FULL.html` §Tray menu lists exactly the
items the port renders:

```
QTranslate (bold)  Dictionary  Text recognition  History  Keyboard
Options  About QTranslate — sep — ✓Enable global hotkeys  Mouse mode ›
— sep — Exit
```

The one extra element in the spec is `#tray .bar` (`left:0; top:240px;
width:367px; height:55px; background:#e4effa`) — a **footer band**, and it is
**empty in the markup** (`<div class="bar"></div>`, no children, no text).
It is the reference capture's window chrome, not a readout. The port's tray
matches the spec item-for-item, including that band's absence.

## 3. The binary has no readout format string

A rendered coordinate needs a format string. Searching the recovered image
for the obvious shapes finds none belonging to this feature:

| Searched | Hits |
|---|---|
| `X: %d`, `Y: %d` | 0 |
| `%d / %d` | 0 |
| `X: ` (wide) | 1 — `…led function: %s\n\n0x%08X: %s`, an error formatter |
| `X: ` (ascii) | 1 — inside libFLAC's `bitwriter:` debug output |

`GetCursorPos` **is** imported and used (C10's mouse-mode chain), which is
why the coordinates existed in the process — but nothing formats them for
display in the tray menu.

## Consequence

* `qtranslate/app.py`'s tray (`_tray_menu`, the `Menu(MenuItem(...))` block,
  with the `QTranslate / Dictionary / Text recognition / History / Keyboard /
  Options / About QTranslate` order already matching native's screenshot)
  needs **no change**.
* The `NON_TRANSLATE_SURFACES_2026-10-14.md` note is corrected: what looked
  like a missing feature was an artifact of the capture environment.
* The lesson is the one this project keeps re-deriving: a screenshot is
  evidence of *a* screen, not of the intended UI. The spec plus the binary
  are what decide.
