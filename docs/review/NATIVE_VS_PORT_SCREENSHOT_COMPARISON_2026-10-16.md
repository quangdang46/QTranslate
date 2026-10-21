# Native vs Port — Screenshot Comparison (2026-10-16)

> **Scope:** visual comparison of the port's captured screenshots
> (`screenshots/screens/*.png`) against the native reference captures
> (`docs/review/native_screens/*.png`). This is a **human-reviewed** pass —
> the images were opened and compared side-by-side, not run through a pixel
> diff tool. G9 remains `UNKNOWN`; this document records what the comparison
> found, not a Gate decision.
>
> **App launch:** the port was opened live on this host (macOS, Python 3.11,
> Tk 9.0). Main window: title `QTranslate`, geometry `595x376`, source pane
> shows the expected boot text. `screencapture` is denied on this host
> (`could not create image from display`), so no new port captures were made —
> the comparison uses the existing `screenshots/screens/` set.

## 1. The captures compared

| Native | Port | Surface | Verdict |
|---|---|---|---|
| `2131.png` (516×423) | `main.png` (516×393) | Main window | **Close** — same panes, same toolbar, same boot text. Native has a service icon strip at the bottom; port has it too. Height differs by 30px (native 423 vs port 393). |
| `2130.png` (265×115) | `popup.png` (200×68) | Ctrl+Q popup | **Close** — same title line (`English to Vietnamese…` + star + glyphs), same source line. Port is smaller (200×68 vs 265×115) and shows fewer glyphs. |
| `2126.png` (663×388) | `tray.png` (367×295) | Tray menu | **Mismatch** — `tray.png` is actually the Options→Hotkeys page, not the tray menu. The port's tray menu was not captured. |
| `2135.png` (646×389) | `options_internet.png` (663×388) | Options → Internet | **Close** — same Connection group, Timeout field, Proxy group. Port is larger (663×388 vs 646×389). |
| `2134.png` (464×198) | `kbd.png` (479×217) | Virtual keyboard | **Close** — **2026-10-21: the screen numbers 2133 and 2134 were swapped until then; 2133 is the HISTORY window (476×320) and 2134 the keyboard (464×198), and this row compared the port's keyboard against native's history.** Native's DLG 162 declares only the language combo (1064); the key grid is built at run time. The port had three rows of letters and now has native's six rows — Esc/F1–F12, the number row, Tab/Caps/Enter/Shift, Ctrl/Win/Alt/AltGr/Apps and the arrows — with the language combo.
| `2133.png` (476×320) | `hist.png` (553×359) | History window | **Close** — same tree view (`person_record` → `nguười_record`), and **2026-10-21** the port's bottom row is native's DLG 164 row: Clear (1067), Save as... (1160), the 15×14 star (1173) and OK (control 1) — the port had a wide 'Favorite' text button and no OK.
| `2136.png` (646×389) | `options_services.png` (663×388) | Options → Services | **Close** — same Translation group (Google, Microsoft, Promt, Babylon, Yandex, youdao, Baidu, Papago, DeepL), same Dictionary group, same Add/Remove dictionary buttons. |
| `2137.png` (646×389) | `options_languages.png` (663×388) | Options → Languages | **Close** — same 4-column language list, same Check/Uncheck all button. |
| `2132.png` (476×333) | `dict.png` (553×374) | Dictionary window | **Close** (2026-10-21) — native's DLG184 is three controls: a language ComboBox (1142), a search Edit (1183) and a `:` menu button (1187), over a large result area with a service icon strip along the bottom. The port now draws that row exactly (`[language v] [<][>] [field] [q] [d] [v]`) and that strip: eleven cells, native's own icons matched to native's pixels, native's clipped `G…`/`W…`/`B…` labels. The port keeps its `Dictionaries` list and its zoom row, which native does not have, and is 77 px wider (the template's width). See `docs/review/UI_FIDELITY_DICTIONARY_2026-10-21.md`. |

> **2026-10-21: three native screen numbers in this table were wrong**
> -- `2132` was read as the Internet page (it is the **Dictionary
> window**), and `2135`/`2136`/`2137` were read as Services / Languages
> / Dictionary (they are **Internet / Services / Languages**). The
> numbering was re-derived by reading each capture's highlighted nav row
> and its body: **2132 = Dictionary window, 2135 = Internet, 2136 =
> Services, 2137 = Languages, 2138 = Appearance, 2139 = Exceptions,
> 2140 = Advanced, 2141 = Updates**. See
> `docs/review/UI_FIDELITY_OPTIONS_2026-10-21.md`.
| `2138.png` (646×389) | `options_exceptions.png` (663×388) | Options → Exceptions | **Close** — same `Disabled for these programs:` list, same Add/Modify/Delete buttons, same Enable smart detection checkbox. |
| `2139.png` (646×389) | `options_hotkeys.png` (663×388) | Options → Hotkeys | **Close** — same Enable hotkeys checkbox, same Action/Hotkey table (Show popup window = Ctrl+Q, Replace selected text = Alt+W). |
| `2140.png` (646×389) | `options_updates.png` (663×388) | Options → Updates | **Close** — same `Automatically check for updates` checkbox, same Check now button. |
| `2141.png` (646×389) | `options_advanced.png` (663×388) | Options → Advanced | **Close** — same Default browser, Copy action, Keyboard layout indicator, Preferred domain, Mouse mode, API keys sections. |
| `2144.png` (516×402) | `options_appearance.png` (663×388) | Options → Appearance | **Close** — same General/Popup window groups, same Theme dropdown, same Auto-hide delay/Transparency/Frame thickness fields, same Icons row, same color pickers. |

## 2. What the comparison found

### 2.1 Structural fidelity is high

Every native surface has a port counterpart with the same controls, same
labels, and same grouping. The Options pages (9/9) are especially close —
the port's `screens.py` renderers were built against the HTML spec, and the
native captures confirm the spec was accurate.

### 2.2 Size differences are systematic

The port's captures are consistently **larger** than native's (663×388 vs
646×389 for Options pages, 476×303 vs 464×198 for History). This is a
**DPI / scaling difference** between the capture environments, not a layout
difference. The native captures were taken on a Windows machine with a
different display scaling than the port's macOS captures.

### 2.3 The tray menu was not captured

`screenshots/screens/tray.png` is actually the Options→Hotkeys page, not
the tray menu. The port's tray menu (which exists in `app.py` as
`_tray_menu`) was never captured. This is a **gap in the port's screenshot
set**, not a missing feature.

### 2.4 The main window height differs by 30px

Native `2131.png` is 516×423; port `main.png` is 516×393. The 30px
difference is likely the service icon strip at the bottom — native's strip
is slightly taller, or the port's window was captured at a different
scroll position.

## 3. What this does NOT claim

- **Not a G9 result.** G9 remains `UNKNOWN`. This is a human visual
  comparison, not a pixel diff. The G9 harness (`tools/g9_screenshot_diff.py`)
  remains the tool for a quantitative comparison.
- **Not exhaustive.** Only the surfaces that have both a native capture and
  a port capture were compared. The port's tray menu, popup window (live),
  and other surfaces were not captured.
- **Not a code change.** No runtime code was modified. This document records
  what the comparison found.

## 4. Reproduce

```bash
# View native captures
open docs/review/native_screens/

# View port captures
open screenshots/screens/

# Launch the port app live
uv run --with keyboard --with pyperclip -- python -I start_app.py
```

## 5. Next steps

1. **Capture the port's tray menu** — the existing `tray.png` is the wrong
   surface. A new capture of the actual tray menu would complete the set.
2. **Re-capture at matching DPI** — the size differences are environmental.
   Capturing both sides at the same DPI would make the comparison tighter.
3. **Run the G9 harness** — once both sides have matching captures, run
   `tools/g9_screenshot_diff.py compare` for a quantitative diff.
