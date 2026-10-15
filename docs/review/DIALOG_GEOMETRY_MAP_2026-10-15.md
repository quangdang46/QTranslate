# Native dialog inventory + geometry map (2026-10-15)

> Static parse of all 19 `RT_DIALOG` templates from the recovered image's
> `.rsrc` (raw `0x146000`), using the same walker + RVA rule as
> `G9_SPEC_NATIVE_WINDOW_2026-10-10.md` (`off = 0x146000 + (rva -
> 0x14b000)`; `DLGITEMTEMPLATEEX` = 28-byte fixed part). No screenshot, no
> window opened. No row state changed.

## 1. Full inventory (id → title → DU → controls)

| Id | Title | DU (cx×cy) | ≈px @7×15 | cdit | Notes |
|---|---|---|---|---|---|
| 129 | QTranslate | 340×201 | 595×753 | 17 | main window |
| 133 | About | 315×135 | 551×506 | 4 | |
| 154 | Options | 429×223 | 751×835 | 5 | shell: OK/Cancel/Apply + SysTabControl32 (id 1078) |
| 162 | Virtual keyboard | 308×102 | 539×382 | 2 | |
| 164 | History | 316×177 | 553×663 | 6 | SysTreeView32 + Clear + Save as... |
| 171 | *(page)* | 324×198 | 567×742 | 19 | Options page |
| 172 | *(page)* | 324×186 | 567×697 | 10 | Options page |
| 173 | *(page)* | 324×186 | 567×697 | 5 | Options page |
| 174 | *(page)* | 324×186 | 567×697 | 2 | Options page |
| 175 | *(page)* | 324×186 | 567×697 | 24 | Options page |
| 176 | *(page)* | 324×186 | 567×697 | 6 | Options page |
| 178 | Exception | 234×90 | 409×337 | 8 | crash reporter |
| 179 | *(page)* | 324×186 | 567×697 | 2 | Options page |
| 184 | Dictionary | 316×185 | 553×693 | 3 | |
| 185 | *(page)* | 324×202 | 567×757 | 19 | Options page |
| 190 | Languages | 297×138 | 519×517 | 10 | |
| 201 | *(none)* | 212×49 | 371×183 | 3 | likely popup/progress |
| 204 | Info | 287×143 | 501×536 | 2 | |
| 205 | *(page)* | 324×186 | 567×697 | 4 | Options page |

The 9 untitled dialogs are exactly the 9 `windows::Page<id>` RTTI ids
(171–176, 179, 185, 205) from checklist M2 — untitled because they are
child pages hosted in the Options tab control, not top-level windows.

## 2. Measured tension: port Options size vs native pages

- Native Options shell: 429×223 DU ≈ **751×835 px**.
- Native page inside it: 324×186 DU ≈ **567×697 px**.
- Port `screens.py`: `OPTS_W, OPTS_H = 663, 388` — the shell is
  **smaller than the native shell in both axes**, and the native *page*
  (567×697) is **taller than the entire port window** (388).

So the port's Options reference layout cannot fit the native control
geometry at 1:1 scale — it is a re-layout, not a measurement. That is
fine for a reference sheet (which is what `screens.py` documents
itself as), but no fidelity claim can be built on it, and any future
G9 Options capture must use the native shell+page sizes above as the
expected geometry, not 663×388.

## 3. Cross-dialog patterns (same-day parse, style-bits method)

- **DLG190 (Languages)** reuses the 1001/1002 combo pair
  (`0x50210103` = CBS_DROPDOWNLIST) plus the `<>` swap button (1015),
  Add / Remove / Remove All / Up buttons, and a 243×119 list (1089) —
  the language-pair manager. The pair ids are stable across dialogs.
- **DLG178 (Exception)** = OK/Cancel + ComboBoxEx32 (1112, app picker)
  + "..." browse button (1110) + "Program name:" label — the crash
  reporter, matching Q1–Q3's `Exceptions.json` flow.
- **DLG164 (History)** = OK + tree (1163) + Clear (1067) + Save as...
  (1160), confirming the I4 save-as flow's dialog home.
- Small dialogs (184/201/204/133/162) show the same first-control
  misalignment seen in DLG129 before the header-struct fix
  (`id=2097260` garbage head) — the walker needs the per-dialog font
  block accounted for, not a new method. Ids/geometry past the head
  are still readable; not worth a parser rewrite for furniture dialogs.

## 4. Control-id notes (parser-correct, class atoms unresolved)

The walker reads class/text as string-or-atom; predeclared-class atoms
(Button/Static/Edit…) come back as `ord#N`, so the class column is not
yet human-readable. What IS pinned: control **ids, counts, and
rects**. DLG154: ids 1 (OK), 2 (Cancel), 1049 (Apply), 1078 (tab).
DLG164: ids 1 (OK), 1163 (tree), 1067 (Clear), 1160 (Save as...).
Full atom→class resolution is a follow-up that needs the atom table,
not more screenshots.

## 4. CLOSED 2026-10-15: id 1001 IS in DLG129

The G9 row carried the open question "Id `1001` is **not** in DLG129 —
unsettled whether runtime-created or conflated with 1002". Re-parse with
the correct `DLGTEMPLATEEX` header struct (`<HHIIIHhhhh`: ver=1,
sig=ffff, style=0x80cf0048, cdit=17, 340×201 — the earlier walker read
`style` at the wrong offset, though cx/cy/cdit happened to be right)
gives a clean 17-control stream, and control #06 is **id 1001 @(43,86)
100×120**, symmetric with id 1002 @(168,86) 118×120. Both are the
source/target language ComboBoxes (class atom unresolved, position and
size match the pair). The question is closed: 1001 is a static template
control, not runtime-created. (Parser lesson: always unpack the header
by struct, never by hardcoded offsets — the earlier run misaligned the
first two controls' class/text for exactly this reason.)

**Follow-up closed the same day:** the pair's class field is `(none)`
(template relies on the dialog proc's default class), but the style
word settles the type — 1001/1002 carry `WS_CHILD|WS_VISIBLE` with
combo-type bits `0x3` = **CBS_DROPDOWNLIST** (drop-down *list*, no manual
typing), vs the RichEdit panes (`0x…1144`, multiline + `RichEdit50W`
class string). So both language selectors are confirmed read-only
combo boxes by style bits alone, matching native behavior (pick from
the list, no free text). No atom table needed after all.
