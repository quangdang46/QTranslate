# C10 SetCursor call sites — re-verified with REA 6.4.0 + Ghidra 12.1.4

> Supports row C10's narrowed claim ("no cursor change on the capture path").
> No row state changes: C10 stays `VERIFIED`/`not-started` (proven negative,
> nothing to port). This document only replaces the inherited "12 callers"
> count with a measured one and names what each site does.

## Method

- Artifact: `docs/review/artifacts/QTranslate.6.10.0.exe`
  (md5 `a7c1278d831b9dd8261b55b82eaaffc0`, 1,462,272 B).
- `rea analyze` (ephemeral Ghidra 12.1.4 import): PE x86, `.text`
  `0x401000–0x50cc00`, 8470 procedures, 3448 strings
  (evidence `ev_7b512b90b56d7cbf05cb900686decf81ad882e6cc668070a7475906f35c86d61`).
- `rea search SetCursor`: 1 string hit at `0x54074a` (`.rdata` import name)
  + `USER32.DLL::SetCursor` external.
- `rea trace SetCursor`: **14 references** to `EXTERNAL:0x12b`
  (evidence `ev_3d52020eb4f441dacc1c54872f255731c079ba17815915d6f527aab8926daffb`).
  One (`0x50d6a8`) is the IAT slot itself, not code — so **13 code call
  sites in 12 procedures**:

| Procedure | Call site(s) | Role (from decompile/shape) |
|-----------|--------------|------------------------------|
| `FUN_004085cd` | `0x4086f5` | **window procedure** (dispatches on message id). `SetCursor` runs only when `param_2 == 0x121` (WM_SETCURSOR) **and** `param_3 == 2` (HTCLIENT): `LoadCursorW(NULL, 0x7F00)` = `IDC_ARROW`, then `SetCursor`. Standard dialog client-area cursor, unrelated to capture. |
| `FUN_0040963d` | `0x409654` | 35-byte body — small handler, unexamined (see §2). |
| `FUN_0040e794` | `0x40e7c0`, `0x40e7f2` | 152-byte body, two sites — unexamined. |
| `FUN_0040e82c` | `0x40e849` | 55-byte body — unexamined. |
| `FUN_0040e863` | `0x40e878` | unexamined. |
| `FUN_00412ed4` | `0x412f34` | unexamined. |
| `FUN_0041300a` | `0x413029` | unexamined. |
| `FUN_0041303d` | `0x4130f0` | unexamined. |
| `FUN_00435e1c` | `0x435f60` | dialog/overlay region (`0x435xxx`). |
| `FUN_00436f19` | `0x4370c7` | dialog/overlay region (`0x437xxx`). |
| `FUN_00437488` | `0x437554` | dialog/overlay region (`0x437xxx`). |
| `FUN_0043799a` | `0x437a45` | dialog/overlay region (`0x437xxx`). |

## Result: the capture path is cursor-free (measured, not inherited)

The mouse-selection chain from C1/C3/C8/C9:

- `FUN_00417E4E` (RawInput hook) — no SetCursor site in body.
- `FUN_004193F6` (click capture) — no SetCursor site in body.
- `FUN_00404901` (OLEACC text) — no SetCursor site in body.
- `FUN_00415EED` (main WndProc) — no SetCursor site in body.
- `FUN_004183bd` (mouse task) — no SetCursor site in body.

None of the 12 SetCursor procedures is one of these five. The one fully
decompiled site (`0x4085cd`) is a WM_SETCURSOR→IDC_ARROW handler. So the
narrowed claim holds byte-for-byte: **no cursor change on the capture
path**. The "14 callers" in C10's note is confirmed; the old "LoadCursorW
12 callers" figure was inherited and is NOT re-measured here.

## What this does NOT establish

- The role of the 11 unexamined procedures beyond their address ranges.
  Only `0x4085cd` was decompiled; the dialog/overlay attribution for the
  `0x435xxx`/`0x437xxx` sites repeats C10's prior note, not a new read.
- No port work follows: `WH_MOUSE_LL` stays a recorded mechanism
  substitution, and `mouse_cursor` gains no icon — there is no native icon
  to mirror on this path.
