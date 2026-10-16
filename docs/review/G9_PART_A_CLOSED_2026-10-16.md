# G9 part (a) — CLOSED: the native window spec is fully recovered

> Supersedes the open items in `G9_SPEC_NATIVE_WINDOW_2026-10-10.md` §5.
> Part **(a)** of the G9 row is now complete and re-derived. Part **(b)**
> (the runtime screenshot diff) is **NOT** — it stays `UNKNOWN`, the Gate
> stays `BLOCKED (1)`, and nothing in this document promotes either.

## 1. What was open, and what closed it

The 2026-10-10 spec left three items explicitly unresolved ("What I could
not pin, and will not guess"). A corrected walker, `tools/dlg_parse.py`,
resolves all three — not by guessing, but because the previous walker had
a **field-width bug**.

### The bug: control ids are 4 bytes

`DLGITEMTEMPLATEEX` is

```
helpID(4) exStyle(4) style(4) x(2) y(2) cx(2) cy(2)
id(4)          <-- 4 bytes, not 2
sz_Class       <-- 0xFFFF,ordinal  |  WCHAR[]
sz_Text        <-- WCHAR[]
creationDataLength(2) creationData
```

Reading `id` as 2 bytes shifts every subsequent field by 2, so after the
first control whose `sz_Class` is a length-prefixed name rather than an
atom, everything downstream is garbage. That is exactly where the old
walker's implausible ids came from (`1342275648` = `0x50010000`, a *style*
value read as an id).

### Resolution #1 — control id `1001` exists

The 2026-10-10 doc had to correct the checklist's claim that `1001` is the
source ComboBox, because its own walker saw `1002` and no `1001`. With the
id field read at the right width, **`1001` is there**: a `ComboBox` at
`x=43 y=86 cx=100 cy=120`. The checklist was right; the walker was wrong.

### Resolution #2 — the four "owner-draw" ids

They were never owner-draw. They are **`BS_ICON`** (`style & 0x40`) icon
buttons whose captions double as fallback labels:

| Id | Text | style | exStyle |
|----|------|-------|---------|
| `1021` | `New` | `0x50010040` | 0 |
| `1022` | `V` | `0x50018040` | 0 |
| `1029` | `Fav` | `0x50018040` | `0x20` |
| `1030` | `Speech` | `0x50019045` | `0x20` |
| `1027` | `Play` | `0x50018040` | `0x20` |
| `1028` | `Play` | `0x50018040` | `0x20` |

The old walker resolved the *classes* correctly but read the ids out of
the style word. There are **six** icon buttons, not four — `1021 New`
and `1022 V` were missing from the old table entirely.

### Resolution #3 — DLU→px is a range, and the range is the answer

`340×201` DU cannot be one number, because the conversion needs the actual
`GetTextMetrics` of the dialog's own font:

```
px_x = (du_x * tmAveCharWidth)            / 4
px_y = (du_y * (tmHeight + tmExternalLeading)) / 8
```

Candidates for what `MS Shell Dlg` 8pt maps to:

| metric | result |
|---|---|
| Tahoma 8pt @100% | **510 × 326** |
| Segoe UI 8pt @100% | **595 × 326** |
| MS Sans Serif 8pt | **595 × 376** |
| Tahoma 8pt @125% | 680 × 427 |
| Segoe UI 8pt @125% | 765 × 427 |

**No candidate reproduces `526×366`.** That number is a saved
`WINDOWPLACEMENT`, not a conversion of this template — which the 2026-10-10
doc already deduced and this now confirms arithmetically.

## 2. The corrected DLG129 table

Template: `cx=340 cy=201` DU, `cDlgItems=17`, `MS Shell Dlg` 8pt,
`style 0x80CF0048`, `exStyle 0x00040000 (WS_EX_CONTROLPARENT)`.

| Id | Class | Text | x | y | cx | cy |
|----|-------|------|---|---|----|----|
| 1000 | `RichEdit50W` | | 1 | 16 | 337 | 66 |
| 1017 | `RichEdit50W` | | 1 | 101 | 337 | 51 |
| 1018 | `RichEdit50W` | | 1 | 154 | 337 | 27 |
| 1009 | `Button` | `:` | 322 | 0 | 16 | 15 |
| 1021 | `Button` | `New` | 1 | 85 | 22 | 15 |
| 1022 | `Button` | `V` | 25 | 85 | 15 | 15 |
| 1001 | `ComboBox` | | 43 | 86 | 100 | 120 |
| 1015 | `Button` | `<>` | 146 | 85 | 19 | 15 |
| 1002 | `ComboBox` | | 168 | 86 | 118 | 120 |
| 1004 | `Button` | `Translate` | 288 | 85 | 50 | 15 |
| 1029 | `Button` | `Fav` | 280 | 64 | 15 | 13 |
| 1030 | `Button` | `Speech` | 295 | 64 | 15 | 13 |
| 1027 | `Button` | `Play` | 310 | 64 | 15 | 13 |
| 1028 | `Button` | `Play` | 310 | 134 | 15 | 13 |
| 1134 | `Static` | | 0 | 82 | 339 | 2 |
| 1135 | `Static` | | 0 | 152 | 339 | 2 |
| 1161 | `SysLink` | `Info` | 39 | 4 | 279 | 10 |

Differences from the 2026-10-10 table: **`1001` present** (was reported
absent), **`1021`/`1022`/`1028` added** (were missing), and the four
"owner-draw" ids reclassified as `BS_ICON` buttons with their real ids.

## 3. Corroboration — this is not a doc claim

The parse is cross-checked against `qtranslate/win32app.py`, whose id
constants were written **independently** from native:

```
ID_SRC=1017  ID_OUT=1018  ID_SRC_LANG=1001  ID_TGT_LANG=1002
ID_NEW=1021  ID_MENU=1022 ID_SWAP=1015      ID_GO=1004
ID_FAV=1029  ID_SPEECH=1030 ID_PLAY_SRC=1027 ID_PLAY_OUT=1028
ID_HELP=1009
```

All 13 agree with the parse. Two independent derivations landing on the
same 13 ids is what makes the table evidence rather than another claim —
the failure mode this project has already hit three times with stale
known-answer vectors.

`tests/regress_dlg129_spec.py` (87 assertions) pins the whole table, the
style/exStyle values, the DLU range, and the cross-check against the port.
It **skips (exit 0)** when the recovered exe is absent, since that blob is
intentionally uncommitted.

## 4. Also re-derived while doing it: all 19 dialogs

`tools/dlg_parse.py` parses the whole `RT_DIALOG` table, and the
control-count sanity check (every dialog ≥2 controls) is what proves the
parser stayed aligned across all of them:

| Id | Title | cx × cy DU | controls |
|----|-------|-----------|----------|
| 129 | `QTranslate` | 340 × 201 | 17 |
| 133 | `About` | 315 × 135 | 4 |
| 154 | `Options` | 429 × 223 | 5 |
| 162 | `Virtual keyboard` | 308 × 102 | 2 |
| 164 | `History` | 316 × 177 | 6 |
| 171–176, 179, 185, 205 | *(untitled — Options pages)* | 324 × 186 | 2–24 |
| 178 | `Exception` | 234 × 90 | 8 |
| 184 | `Dictionary` | 316 × 185 | 3 |
| 190 | `Languages` | 297 × 138 | 10 |
| 201 | *(untitled)* | 212 × 49 | 3 |
| 204 | `Info` | 287 × 143 | 2 |

The port's own `_place_aux` defaults now have something to be checked
against: `WindowHistoryPlacement "500x280"` vs the template's
`316 × 177` DU (≈ `474 × 221` px at Segoe UI 8pt) — the same
template-vs-placement question as DLG129, and still a Phase 7 decision.

## 5. What this does NOT do

- **It does not resolve G9.** Part (b) — a real native-vs-port pixel
  comparison, human-reviewed — is unchanged and still `UNKNOWN`.
- **It does not change the Gate.** Still `BLOCKED (1)`.
- **It does not need a screenshot.** Part (a) is read out of the image,
  which is why it could be finished while screenshots are banned.
- **It does not change runtime code.** No converter was touched.

## 6. Reproduce

```
python -I tools/dlg_parse.py                # all 19 dialogs
python -I tools/dlg_parse.py --id 129 --dlu # the DLG129 table + DLU range
python -I tools/regress...                   # via tests/regress_dlg129_spec.py
```

The artifact is `docs/review/artifacts/QTranslate.6.10.0.exe` (1,462,272 B,
sha256 `f35a3bc8…38227`), uncommitted by design — recovered per
`ARTIFACT_RECOVERY_2026-10-10.md` §7.
