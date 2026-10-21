# The port's main window is structurally wrong — 4 divergences from DLG129

> Found 2026-10-16 while reading DLG129's full control table for G9 part (a)
> (`tools/dlg_parse.py`). The user reported the UI "lệch, không đúng" despite
> the prototypes. This is the structural cause. **No code was changed in
> this document** — it is a finding, and §5 says what a fix would require.

## 1. Native DLG129, top to bottom

Parsed from the image (`cDlgItems=17`, all resolved). Positions in dialog
units, `runtime` order preserved:

| y | Controls | What it is |
|---|---|---|
| 0 | `1009` `:` (x=322) | help button, top-right corner |
| 4 | `1161` `SysLink "Info"` (x=39, cx=279) | the info/version strip |
| **16–82** | **`1000` RichEdit50W, cy=66** | **SOURCE pane** |
| 64–77 | `1029` `Fav`, `1030` `Speech`, `1027` `Play` | icon buttons **overlaid** inside the source pane's bottom-right |
| 82 | `1134` Static cy=2 | separator |
| 85–86 | `1021` `New`, `1022` `V`, `1001` ComboBox, `1015` `<>`, `1002` ComboBox, `1004` `Translate` | the control row |
| **101–152** | **`1017` RichEdit50W, cy=51** | **RESULT pane** |
| 134 | `1028` `Play` | listen button overlaid inside the **result** pane |
| 152 | `1135` Static cy=2 | separator |
| **154–181** | **`1018` RichEdit50W, cy=27** | **a THIRD pane** |

**Three text panes**, not two: `1000` (66 DU), `1017` (51), `1018` (27) —
144 of the template's 201, the rest being the control rows and separators.

### Which pane is source, which is result

The two `Play` buttons disambiguate it, because `Play` beside a pane means
"listen to *this* pane's text" and native has a distinct listen action for
each:

- `1027` at y=64 → inside pane **1000** (y 16–82)
- `1028` at y=134 → inside pane **1017** (y 101–152)

So **`1000` = source, `1017` = result**. `1018` is a third pane native's
spec does not name here; it is 27 DU tall (about one line), which is the
size of an auxiliary/status strip rather than a body pane.

## 2. The four divergences

| # | Native | Port | Consequence |
|---|---|---|---|
| **1** | **Three** text panes (`1000`/`1017`/`1018`) | **Two** (`self.src`, `self.out`). `self.src` is the 519-line `tk.Text`, `self.out` the 657-line one — there is no third. | A whole pane is missing. Everything that would live in `1018` has nowhere to go. |
| **2** | `1017` = result, `1000` = source | The code labels them the other way: `qtranslate/app.py:510` says *"source pane (id1017)"* and `:637` *"result pane (id1018)"*. | The port's two panes are (probably) `1000` and `1017` — the right panes — but the *ids it cites* are wrong, so the mapping it claims is off by one and every doc that copied it inherited the error. `win32app.py:4` and `:36` (`ID_OUT = 1018`) repeat it. |
| **3** | Icon buttons **overlay** the panes (`Fav`/`Speech`/`Play` sit *inside* 1000 at y=64; `Play` inside 1017 at y=134) — no side column | The port puts mic/listen in a **side frame** (`srcside.pack(side="right")`, `outside.pack(side="right")`), i.e. a dedicated column beside each pane, plus a hardcoded `tk.Frame(outside, height=120)` spacer | The buttons take horizontal space out of the pane instead of floating over it, so the panes are narrower than native's and the widget order reads differently. |
| **4** | Absolute placement — every control has explicit x/y/cx/cy | `_build_main` is **fluid** (`pack()` ×28, zero `place()`) | Native's controls are at fixed DU offsets; the port re-flows. With a saved placement of `530×430` (this machine) rather than the template's `595×376`, the port's fluid result and native's absolute layout diverge further. |

**Status 2026-10-21.** Divergences **1**, **2** and **3** are closed:

| # | Closed by | How |
|---|---|---|
| 1 | the third pane | `auxfrm` / `self.aux` (a 1-line RichEdit) is built, with its own separator. **Refined 2026-10-21** by `UI_FIDELITY_MAIN_WINDOW_BANDS_2026-10-21.md`: native's capture shows that pane **collapsed to zero height** when it is empty (the separator 1135 is there, the RichEdit is not), so the port now shows it only while it carries a back-translation — and the port's band structure matches native's: source, tool row, result, service strip |
| 2 | the pane ids | `app.py` and `win32app.py` now say `ID_SRC = 1000` / `ID_OUT = 1017`; the *old* wrong ids (`1000` = source was labelled 1017) are gone |
| 3 | the overlay | the mic/headphone/listen buttons are `place()`d **over** the panes at their native offsets, not given a side column |

**#4 (fluid vs absolute) is now MEASURED, and the two models agree.** The
port's bands are measured against native's
(`docs/review/UI_FIDELITY_MAIN_WINDOW_BANDS_2026-10-21.md` §1) and both
have the same **seven** bands in the same order:

| band | native | port (2026-10-21) |
|---|---|---|
| nav row | 25 | 21 |
| source pane | 151 | 153 |
| separator | 2 | 3 |
| tool row | 26 | 28 |
| result pane | 150 | 146 |
| separator | 2 | 3 |
| service strip | 27 | 19 |

**The two extra 16-17px bands and the source-pane height are closed
2026-10-21** by that document — native has no permanent suggestion band
and its third pane is collapsed, and the source pane now takes native's
measured 153px.

What is left is that native positions its controls by **absolute dialog
units** while the port re-flows, so the two agree at one window size
and drift at another: native's source pane measures 153 px at a 423 px
window, 145 px at 409 and 142 px at 402, while the port's is fixed at
153 px. That is a font-metric and layout-model question, not a mistake,
and it is the only part of #4 that is still open.

The main window's own body also moved on 2026-10-21: Phase 7 (6/6) extracted
it as `qtranslate.windows.MainWindow`, leaving thin delegators in `app.py`.
The split is verified behaviour-preserving: the widget geometry before and
after is **identical**, band for band.

## 3. Why it looks "lệch" rather than "incomplete"

The port is a plausible two-pane translator and every widget exists, so a
glance reads as "done". The visible wrongness comes from the combination:

- **One pane short**, so the vertical rhythm is one row off — the result
  pane sits where native's *second* row sits, and there is nothing below it.
- **The icon buttons in a side column** instead of overlaid, which changes
  where the eye expects mic/headphone/Fav and shrinks both panes.
- **Fluid layout against an absolute template**, so any window size other
  than the one the fluid layout happens to suit makes it drift.

The prototypes the user saw were `screens.py`'s reference renderers, which
are drawn against the HTML spec (`UI-FULL.html`), not against DLG129 — so
"prototype looks right, live app looks wrong" is exactly the expected
outcome of the live app not implementing the template.

## 4. Why nobody caught it

`ui_match` (103 checks) is the structural suite for this window, and it
passes. Its checks are about *the port's own* invariants — hotkey vk
values, pane restore, `_PAGES` ids, `TEMPLATE_GEOMETRY` — not about
*agreement with DLG129*. Nothing asserted "there are three panes" or
"`1000` is the source", because nothing had ever listed DLG129's controls
correctly: the 2026-10-10 walker misread the control id as 2 bytes, so its
own table was wrong in exactly the way that hid this (`1001` missing,
`1021`/`1022`/`1028` missing, ids implausible).

The honest statement is that **G9 part (a) being complete is what made this
findable** — and that a passing structural suite over a wrong table is
worth nothing.

## 5. What a fix requires (not done here)

This is a **UI fidelity change**, which is what the screenshot ban was
blocking, so it is recorded rather than attempted:

1. **Add the third pane** and decide what it holds. `1018` is unnamed in
   every doc here; the candidates from the port's own state are the
   back-translation segment (currently concatenated into `self.out` with a
   `--- back-translation ---` marker) or the suggestion line. That is a
   product question — which one, or neither — not a transcription.
2. **Correct the id mapping** in `app.py:510`/`:637`, `win32app.py:4`/`:36`,
   and `NATIVE_ARCH.md:75`. That part *is* mechanical and safe.
3. **Overlay the icon buttons** instead of side frames — a layout change
   with no verification signal available.
4. Keep `_build_main` fluid or move to absolute placement. Fluid is
   defensible (it adapts to the saved `530×430`); absolute matches native
   but breaks on a resized window. Needs a decision.

## 6. Reproduce

```
python -I tools/dlg_parse.py --id 129          # the full control table
python -I tests/regress_dlg129_spec.py         # pins the table (87 assertions)
```

The two `Play` positions that settle the source/result question are
asserted in §4 of that suite.
