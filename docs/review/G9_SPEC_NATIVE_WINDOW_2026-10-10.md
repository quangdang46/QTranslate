# G9 part (a) — Native window spec measured from the recovered binary

> Complements `G9_RESULT_2026-10-09.md`, which records G9's **part (b)** — the
> runtime screenshot diff — as **BLOCKED**. This document covers **part (a)** of
> the G9 row: the native window specification. Part (a) *is* an RE question,
> and it is now answerable because the real binary was recovered
> (`ARTIFACT_RECOVERY_2026-10-10.md`).
>
> **This does not resolve G9.** G9 stays `UNKNOWN` and the Gate stays
> `BLOCKED (1)`. A correct spec is necessary for fidelity, not sufficient for
> it, and no screenshot comparison exists.

## 1. Method

`RT_DIALOG` (resource type 5) parsed straight out of the recovered image's
`.rsrc` (raw `0x146000`, size `0x13600`) with a stdlib `struct` walker — the PE
resource directory → type `DIALOG` → per-id subtrees → `IMAGE_DATA_DIRECTORY` →
RVA→file-offset → `DLGTEMPLATEEX`.

19 dialogs are present. Titles parse as clean UTF-16, which is the check that
the walker is aligned (`QTranslate`, `About`, `Options`, `History`,
`Dictionary`, `Info`, `Languages`, `Virtual keyboard`, `Exception`).

## 2. DLG129 — the main window

| Field | Value |
|-------|-------|
| Dialog id / title | `129` / **`QTranslate`** |
| Resource RVA / size | `0x15a220` / 784 bytes |
| `style` | `0x80cf0048` |
| `exStyle` | `0x00040000` = **`WS_EX_CONTROLPARENT`** |
| geometry | **`cx=340`, `cy=201`** (dialog units) |
| `cDlgItems` | **17** |
| font | **`MS Shell Dlg`, 8pt** (`DS_SETFONT`) |
| `WS_` flags set | `POPUP`, `SYSMENU`, `CAPTION`, `DLGFRAME`, `BORDER`, `SETFONT` |

Control geometry (dialog units, from the template):

| Id | Class | Text | x | y | cx | cy |
|----|-------|------|---|---|----|----|
| 1000 | `RichEdit50W` | — | 1 | 16 | 337 | 66 |
| 1017 | `RichEdit50W` | — | 1 | 101 | 337 | 51 |
| 1018 | `RichEdit50W` | — | 1 | 154 | 337 | 27 |
| 1009 | `Button` | `:` | 322 | 0 | 16 | 15 |
| 1015 | `Button` | `<>` | 146 | 85 | 19 | 15 |
| 1002 | `ComboBox` | — | 168 | 86 | 118 | 120 |
| 1004 | `Button` | `Translate` | 288 | 85 | 50 | 15 |
| 1029 | `Button` | `Fav` | 280 | 64 | 15 | 13 |
| 1134 | `Static` | — | 0 | 82 | 339 | 2 |
| 1135 | `Static` | — | 0 | 152 | 339 | 2 |
| 1161 | `SysLink` | `Info` | 39 | 4 | 279 | 10 |

**13 of 17 controls parsed with unambiguous field alignment.** The remaining 4
(the owner-draw icon buttons and their statics) hold `BS_OWNERDRAW` controls
whose class/text atoms my walker resolves but whose *ids* it does not pin
cleanly — see §5.

### What this confirms vs the checklist's claim

| Checklist (G9 row) claim | Measured | Verdict |
|--------------------------|----------|---------|
| DLG129 geometry `526×366` | **`340×201`** | **WRONG** — see §3 |
| control ids `1017/1018/1001/1002/1004…` | `1000/1017/1018/1002/1004` present; **`1001` is NOT in DLG129** | partly wrong |
| RichEdit50W | 3× `RichEdit50W` | correct |
| Tahoma 9 | **`MS Shell Dlg` 8pt** | **WRONG** — see §4 |

## 3. `526×366` is not the template geometry

The G9 row claims `DLG129 geometry 526×366`. The template says `340×201` dialog
units. Both numbers can be true — 340×201 DU converts to a larger pixel box at
some DPI — but **the row states them as the same quantity and they are not the
same units**. At 96 DPI with `MS Shell Dlg`→Tahoma metrics, 340×201 DU is
roughly `340 × 201` px only if the dialog base unit is 1:1, which it is not for
an 8pt font (DLU→px is ~1.5:1 horizontally, ~1.6:1 vertically, giving roughly
`510 × 320` px, not `526 × 366`).

So `526×366` looks like a **runtime-measured pixel window size** (possibly with
a non-default DPI or a scaled font), not the template size. Stating it as
"DLG129 geometry" conflates the two. The honest statement is:
*template `340×201` DU at `MS Shell Dlg` 8pt; runtime pixel size depends on the
machine's DPI and was never measured on a machine that could run it.*

The port's README claims its window is `526×366` (matching the wrong number),
so **the port may be sizing to a runtime artifact rather than the template.**

## 4. The font is `MS Shell Dlg` 8pt, not Tahoma 9

The template's `DS_SETFONT` font is `MS Shell Dlg` at **8pt**. `Tahoma` does
not appear in DLG129. The checklist's "Tahoma 9" is therefore **not from this
dialog** — it may come from a child control's own font, from a `.rsrc`
string, or from a different dialog. (The app's own `app.py` docstring also
claims `Tahoma` — inherited from the same unchecked claim.)

`Tahoma` and `Segoe UI` do each appear **once** in the image, but both sit
inside Windows **font-substitution tables**, not a dialog template: `Segoe UI`
is adjacent to the control class names (`Edit20W`, `msctls_hotkey32`,
`SysLink`) and both flank `Arial Unicode MS` / `Lucida Sans Unicode` /
`Arial Unicode MS`. `MS Shell Dlg` appears **20 times**, which is what a
per-dialog `DS_SETFONT` font looks like.

This is a real fidelity difference: `MS Shell Dlg` maps to the system UI font
(`Segoe UI` on Vista+, `Tahoma` on XP), so on a modern Windows box the native
UI is `Segoe UI 8pt`, and **`Tahoma 9` is a materially different look** —
larger, heavier, different metrics.

## 5. What I could not pin, and will not guess

- **The 4 remaining DLG129 controls.** My walker cleanly resolves 13; for the
  owner-draw buttons (`Fav`/`Speech`/`Play`) it finds the right classes and
  strings but produces implausible ids (`1342275648` etc.), so the ids for
  those are **unknown**, not recorded. Guessing them would put wrong ids in a
  doc that other work cites as RE evidence.
- **Control id 1001** — the checklist names it as the source ComboBox. The
  template has `1002` as a ComboBox and no `1001`. Either `1001` is created at
  runtime, or the doc conflated `1002` with `1001`. Not settled here.
- **Theme colors** — the G9 row claims "theme colours" recovered. I did not
  re-derive them in this pass.
- **DLU→px conversion** — needs the exact font metrics of `MS Shell Dlg` on a
  Windows host, which cannot be measured here.

## 6. Consequence for G9 and for the port

1. **G9 remains `UNKNOWN`, Gate remains `BLOCKED (1)`.** Part (a) is now partly
   measured, but (b) — the actual comparison — is still BLOCKED and cannot be
   produced on this machine.
2. **The checklist's G9 row needs three corrections** (geometry units, font,
   control id 1001). Per the split, `RE_COVERAGE_CHECKLIST.md` is single-writer
   by **qtranslate-8e**; I have not edited it. Send the row the corrections.
3. **The port's `526×366` window sizing should be re-examined** against
   `340×201` DU. That is a Phase 7 (UI fidelity) item, not Phase 1.

## 7. Reproduce

```
python3 - <<'PY'
import struct
blob = open("QTranslate_extracted.exe","rb").read()
RS, RL = 0x146000, 0x13600
rsrc = blob[RS:RS+RL]
u16 = lambda o: struct.unpack_from('<H', rsrc, o)[0]
u32 = lambda o: struct.unpack_from('<I', rsrc, o)[0]
def walk(off):
    n = u16(off+12) + u16(off+14)
    return [(u32(off+16+k*8) & 0x7fffffff,
             bool(u32(off+16+k*8+4) & 0x80000000),
             u32(off+16+k*8+4) & 0x7fffffff) for k in range(n)]
def data_of(sub):
    i, is_dir, off = walk(sub)[0]
    if is_dir: _, _, off = walk(off)[0]
    return u32(off), u32(off+4)          # (rva, size)
sub = [s for (i,_,s) in walk(0x180) if i == 129][0]   # DIALOG type @0x180
rva, size = data_of(sub)
off = 0x146000 + (rva - 0x14b000)         # rva -> file offset in .rsrc
buf = blob[off:off+size]
exstyle, style = struct.unpack_from('<II', buf, 8)
cdit = struct.unpack_from('<H', buf, 16)[0]
cx, cy = struct.unpack_from('<hh', buf, 22)
print(cx, cy, hex(style), hex(exstyle), cdit)   # 340 201 0x80cf0048 0x40000 17
PY
```
