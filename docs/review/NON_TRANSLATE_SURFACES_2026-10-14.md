# Non-translate surfaces — measured inventory (2026-10-14)

> Written because the user's correction ("QTranslate isn't only the translate
> UI: pressing Q shows a popup beside the cursor, there's an Options panel
> with hotkeys, and much more that isn't about translating") was fair: this
> repo's recent attention had drifted to the translate path. This document
> measures what the port actually has versus the native window, from the
> three user-supplied native screenshots and the port's own source.

## The native screenshots, itemized

| Screenshot | Native surface observed |
|---|---|
| `2126.png` | tray/kebab menu: `QTranslate` heading, Dictionary, Text recognition, History, Keyboard, Options, About QTranslate; checkable Enable global hotkeys; Mouse mode submenu; Exit. Header also shows a live `X: / Y:` cursor readout. |
| `2128.png` | **Options → Hotkeys page**: Enable hotkeys checkbox; 11 actions with current binding shown (`Show popup window` = `Ctrl + Q`, `Replace selected text` = `Alt + W`, rest blank). |
| `2130.png` | **the press-Ctrl+Q popup**: title line `English to Viet…` + star + 4 icon glyphs, source line, then the result line. |
| `2131.png` | main window: version line + help.txt in the source pane, toolbar `Auto-Detect → Vietnamese → Translate`, and the bottom **service icon strip** (Google, Microsoft, Promt, Babylon, Yandex, Youdao, …). |

## Port state, one row per surface

| Surface | Native | Port | Evidence |
|---|---|---|---|
| press-Q popup | borderless, cursor-adjacent, title + star + icons + result | **present** — and the title/star/glyph header landed today (`f6e2997`) | `show_popup()` `app.py:4761`; header from FUN_0040C393 `+0x3c` caption |
| PopupIcons | 4 glyphs as passive row | present as Labels (button-less pinned by `ui_match:popup-no-buttons`) | same |
| Options panel | 9 pages | present, 9/9 | `open_options()` `app.py:2203`; `ui_match:pages-9` |
| Hotkeys page | Enable + 11 actions | present, 17 action names pinned | `show_hotkeys()` `app.py:2163`; `ui_match:hotkey-names-17` |
| Tray/kebab menu | Dictionary, Text recognition, History, Keyboard, Options, About + Enable global hotkeys + Mouse mode + Exit | present | `show_nav_menu()` `app.py:1423` |
| Service strip | icon + short name (Go.., Mi.., …) | present | `_build_main()` `app.py:1048` |
| Boot source text | version + help.txt | present | `default_source_text()` `app.py:1361` |

## What the inventory says

The surfaces the user named exist in the port. The gap found by actually
looking was narrower than "the port only builds a translate table": the
popup was missing its **native title line** (lang pair + star + glyphs),
which made the popup read as a bare text box rather than the QTranslate
popup. That is fixed and pushed.

Two things this inventory does **not** claim:

1. **Not a fidelity claim.** Presence is measured (a function/widget
   exists), not pixel equivalence. G9 remains the open fidelity question.
2. **Not exhaustive.** This lists the surfaces visible in the four
   screenshots. `windows::ApplicationWindow` also embeds
   `WindowPopupIcons`, `ProgressWindow`, and `LayoutIndicatorWindow`
   (row A5) — none of which was checked here.

## Still open, stated rather than glossed

- `Text recognition` (OCR) and `Dictionary`/`History`/`Keyboard` menu items
  are present as commands; their windows were not compared against native
  screenshots in this pass.
- The tray menu's live `X: / Y:` cursor readout (visible in 2126) has no
  port counterpart — a real gap found by this inventory, not yet fixed.

> **RESOLVED 2026-10-16 — it is not a gap.** See
> `TRAY_CURSOR_READOUT_CLOSED_2026-10-16.md`: the spec's tray menu carries no
> such element (its `.bar` footer is empty in the markup), the binary holds no
> `X: %d` / `Y: %d` format string, and the coordinates in that capture are a
> mouse-mode **debug overlay** the analyst's session happened to be showing.
> The port's tray needs no change.
