# Main window: the band structure, measured against native (2026-10-21)

> **Scope:** the second pass on the main window, after
> `UI_FIDELITY_MAIN_WINDOW_2026-10-21.md` fixed the service strip, the
> overlays, the help text and the clipped Translate button. This pass is
> about the window's **vertical structure** — how many bands it has, how
> tall each one is, and which of them native actually shows.
>
> **No checklist row state changed by this document.** G9 part (b) stays
> `UNKNOWN` and needs a human reviewer and a human-written waiver.

---

## 1. The measurement

Native's main window is `docs/review/native_screens/2131.png` — a genuine
capture of the real `QTranslate.exe`, not a mockup. That is worth stating,
because it is measurable: the service icons in that strip are **byte-identical**
to the `.ico` groups in the installer payload (the pixel match scores
exactly 0.0 for three of them), and no rendering of a specification could
reproduce another file's bytes.

`tools/_scratch/band_compare.py` measures the port's live widget tree and
native's pixels side by side. Native's bands, in client coordinates:

| # | native band | height |
|---|---|---|
| 1 | nav row (back/forward, the service link, the overflow) | 25 |
| 2 | gap | 4 |
| 3 | **SOURCE pane** | 151 |
| 4 | separator (1134) | 2 |
| 5 | tool row (language combo, swap, target, Translate) | 26 |
| 6 | gap | 4 |
| 7 | **RESULT pane** | 150 |
| 8 | separator (1135) | 2 |
| 9 | service icon strip | 27 |

**Seven bands.** The port now measures the same seven:

| # | port band | before | after | native |
|---|---|---|---|---|
| 1 | nav row | 28 | 28 | 25 |
| 2 | source pane | **170** | **153** | 151 |
| 3 | separator | 3 | 3 | 2 |
| 4 | tool row | 28 | 28 | 26 |
| 5 | **suggestion strip** | **17** | **absent** | absent |
| 6 | result pane | **129** | **146** | 150 |
| 7 | **third pane (1018)** | **16** | **absent** | collapsed to 0 |
| 8 | separator | — | 3 | 2 |
| 9 | service strip | 19 | 19 | 27 |

---

## 2. Native's third pane is COLLAPSED, not absent

DLG129 declares **three** `RichEdit50W` controls — 1000 (source, 66 DU),
1017 (result, 51 DU) and 1018 (a third, 27 DU) — and the port builds the
third one. But native's own capture shows the separator **1135** between
the result pane and the service strip and **no pane behind it**: the
result pane runs to y=362, the separator is at 362..364, and the service
strip starts at 364. The third pane has **zero height**.

So native's 1018 is a pane that is present in the template and collapsed
at run time — it appears when there is a back-translation to show and is
gone otherwise. The port showed it **always**, as a 16-pixel empty grey
band between the result pane and the separator.

Fixed: the third pane is packed only while it carries a back-translation,
and the separator stays (native shows it too).

## 3. Native has no permanent suggestion strip

The port had a `Label` under the tool row for Google's spelling
suggestions, packed unconditionally — 17 pixels of empty grey when there
was no suggestion. Native has no such band at all in its capture; the
suggestion is a transient, not a row. Fixed: the label is packed only
while it carries text.

## 4. The source pane's height is native's, not the Text's request

The port's source `Text` asked for **12 lines** (170 px here). Native's
source pane measures **151 px** in its capture and shows ten and a half
lines of the same help text — the same line pitch (14.6 px there, 14.2 px
here), so the port was showing **a line and a half more** of the help text
than native, and a result pane 21 px shorter for it.

Native's own value moves a little with the window height — 153 px at a
423 px window, 145 px at 409, 142 px at 402 — so the port now takes
native's value at the reference window size (`SRC_PANE_PX = 153`) and
stops propagating the `Text`'s request. The eleventh line is clipped
exactly as native's is.

## 5. Two more real defects, found on the way

**The pane toggles did nothing.** `Ctrl+F1`, `Ctrl+F2`, `Ctrl+F3` and
their menu items call `toggle_pane("ShowTopPane", "src")` and
`toggle_pane("ShowMiddlePane", "mid")`, which read
`self.app._panes["src"]` and `["mid"]`. But the builder **replaced** the
whole `_panes` dict at the end with `{"src": None, "mid": None, ...}`, so
both keys were `None` and every toggle returned early. The dict is now
updated, not replaced.

**The nav arrows were 47 pixels wide.** Native's back/forward buttons,
its `:` menu and its `New` button are `BS_ICON` buttons — the EXE's own
`RT_ICON` resources — not text. Drawn as text on macOS they came out 47
px wide (the fallback font's arrow glyph is that wide) where native's are
20. The four icons are now bundled (`back`, `forward`, `menu`, `new` in
`qtranslate/assets/ui_icons/`) and the buttons carry them.

**And the settings file was landing inside the package.** `config.py`
built its path as `os.path.join(os.environ.get("APPDATA", ""), "QTranslate",
"Options.json")`. Off Windows `APPDATA` is empty, so that join produced a
**relative** path — and on macOS, where the filesystem is case-insensitive,
`QTranslate/Options.json` resolved to `qtranslate/Options.json`, *inside
the package directory*. The path is now `platforms.app_data_dir()`:
`%APPDATA%\QTranslate` on Windows, `~/.config/QTranslate` everywhere else,
which is the convention `reliability.py` already used for its log.

And a third, found by testing the round trip on a fresh `HOME`: the
settings **directory was never created**. The app persists a setting
from ~38 places, each opening `DEFAULT_PATH` directly inside a `try`
that swallows the error — so on a fresh install every one of those
writes raised `FileNotFoundError` and the setting was silently lost.
`config.ensure_dir()` creates the directory (once for the default path,
and again inside `save()` for a path it is handed).

That had two consequences, both fixed here:

* `config.load()` and `config.save()` took `DEFAULT_PATH` as a **default
  argument**, which freezes the value when the function is *defined*. A
  caller that points `DEFAULT_PATH` somewhere else — the tests do, and so
  does the pane toggle — still read and wrote the original file. The path
  is now resolved at call time.
* `toggle_pane` had its read, its write and its packing inside one
  `try`. With no `Options.json` on the machine, `load()` raised, the
  `except` swallowed it, and **the pane never toggled at all**. Each of
  the three is now separately guarded: a missing settings file is not a
  reason to refuse to show the pane.

---

## 6. What is still different

- **The result pane is empty on boot** where native shows
  "No data returned (timeout while sending data)." That is **not** native
  translating on boot: native RESTORES the result pane from
  `Contents.EditTranslation` on boot
  (`D10_SPOTCHECK_Contents_2026-10-10.md` §4), and on the capture machine
  the saved value was the error message left by a timed-out translation.
  The port restores the same key — it had nothing to restore, because off
  Windows its settings file never persisted at all (see §5).
- **The service strip is 19 px** where native's is 27, and the port's
  window is 516 px wide against native's 516 — the same width, a
  different strip height.
- **The service strip is 19 px** where native's is 27 (the port's cells
  are 16 px icons with 8 pt labels; native's strip is taller).
- **The title bars differ**, because macOS draws different chrome.

---

## 7. Evidence

| What | Where |
|---|---|
| native's capture | `docs/review/native_screens/2131.png` |
| the port's capture | `docs/review/ui_fidelity_2026-10-21/surfaces/main.png` |
| the two side by side | `docs/review/ui_fidelity_2026-10-21/surfaces/cmp_main.png` |
| the band comparison | `tools/_scratch/band_compare.py` |
| the bundled icons | `qtranslate/assets/ui_icons/` (+ `manifest.json`) |
| the behaviour test | `tests/regress_main_window_fidelity.py` |
