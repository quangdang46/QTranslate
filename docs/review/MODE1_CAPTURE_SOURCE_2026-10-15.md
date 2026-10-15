# Capture-source dispatcher `FUN_004052E4` — decompile re-read (2026-10-15)

> Read-only trace from the Ghidra database (QTranslate 6.10.0). Corrects a
> label carried in two docs; no row state changed. Not a port change.

## 1. What the dispatcher actually does

`FUN_004052E4(this, param_1)` switches on `*(this + 8)` — the **capture
source**, not the user-facing mouse-mode. Decompiled 2026-10-15:

```c
iVar1 = *(int *)((int)this + 8);
if (iVar1 == 1) {                       // reuse supplied text
    puVar3 = FUN_0041b872((CString*)((int)this + 0xc));   // trim
    FUN_00401ec9((void *)(param_1 + 4), puVar3);          // copy -> out
} else if (iVar1 == 2) {                // OLEACC mouse
    if (!FUN_004543c6((CString*)(param_1 + 4), '\x01'))
        FUN_00404901((BSTR)(param_1 + 4));
} else if (iVar1 == 3) {                // clipboard read
    FUN_0043beb2((int *)(param_1 + 4), 0);
}
```

So:

| `this+8` | Source | Native action |
|---|---|---|
| 1 | supplied buffer | copy `this+0xc` → out (no mouse, no clipboard) |
| 2 | OLEACC | `FUN_004543C6` modifier gate, else `FUN_00404901` (cursor text) |
| 3 | clipboard | `FUN_0043BEB2` (`GetClipboardData(CF_UNICODETEXT)`) |

## 2. Correction: `FUN_0041B872` is a trim helper, not the copy

Both `NATIVE_ARCH.md:173` and `RE_COVERAGE_CHECKLIST.md` C2 describe mode 1
as "reuse **last capture**" and imply `FUN_0041B872` performs the copy.
Decompile of `FUN_0041B872` shows it only **trims trailing whitespace**
(walk to the last `iswspace`, `FUN_0040335d` + `FUN_004033a6` shrink, then
`CStringT::TrimLeft`) — it is a string-hygiene helper called from ~35 sites,
not a capture mechanism.

The accurate reading: mode 1 **reuses a text buffer supplied in the task
struct** (`this+0xc`); `FUN_0041B872` merely trims it before the copy into
the output field (`FUN_00401EC9`).

## 3. The sibling `FUN_0040558F` is the FILL half of the pair

`FUN_0040558F(this, param_1)` shares the same `this+8` switch and the same
`this+0xc` buffer, but **writes** instead of reading (decompiled 2026-10-15):

```c
iVar1 = *(int *)((int)this + 8);
if (iVar1 == 0)      FUN_00401ec9((void *)((int)this + 0xc), (void *)(param_1 + 4)); // fill from task
else if (iVar1 == 1) FUN_0041b872((CString*)((int)this + 0xc));                       // trim
else if (iVar1 == 2) { if (!FUN_004543c6(...)) FUN_00404901(...); }                    // OLEACC
```

So the two are a **fill/read pair over one buffer**:

- `FUN_0040558F` (modes 0/1/2): mode 0 **copies the task-supplied text into
  `this+0xc`**, mode 1 trims it, mode 2 OLEACC-captures into it.
- `FUN_004052E4` (modes 1/2/3): mode 1 copies `this+0xc` **out** to the
  result, mode 2 OLEACC, mode 3 clipboard.

"Reuse supplied text" therefore means: `0040558F` put the caller's text into
the buffer, `004052E4` hands that same buffer back — the "supplied" text is
the one the task struct carried in, not a previous capture.

## 3b. `General.MouseMode` (the UI axis) is `DAT_005493F8`

`FUN_004183BD` (the WndProc the port's `mouse_capture.py` header cites)
switches on `DAT_005493F8`, not on `this+8`:

```c
if (DAT_005493F8 == 1 || DAT_005493F8 == 2)  TaskShowPopupWindow (read-aloud when == 2)
else if (DAT_005493F8 == 0)                  TaskShowIcons
```

So the port's `0/1/2` mouse-mode axis follows `DAT_005493F8` correctly; the
`FUN_004052E4`/`FUN_0040558F` `this+8` values are the **capture-source**
selector, a different field.

## 4. Why no port change (yet)

The port's mouse-mode axis (`DAT_005493F8`, the `0/1/2` the UI toggles) is
implemented correctly. The `this+8` capture-**source** selector is a separate
field the port does not model, because the port's click path always starts a
fresh capture and has no "task struct carried in supplied text" concept to
fill `this+0xc` from. Adding mode-1 source reuse needs that concept defined
first; guessing it would be inventing semantics the evidence frames but does
not pin. Recorded, not changed — same rule as the other label tensions
(`NATIVE_ARCH` is frozen; the checklist row keeps its state).

## 5. Consequence

- No RE row moves; no port behaviour changes.
- `NATIVE_ARCH.md` label tension recorded here (not edited — frozen).
- If a future slice models "reuse supplied text", this is the evidence to
  build on, and it must first define the port's supplied-text source.
