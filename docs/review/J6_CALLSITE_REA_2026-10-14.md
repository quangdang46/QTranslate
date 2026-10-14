# J6 FLAC call site — re-decompiled from the restored artifact (REA 6.4.0)

> Supports row J6 (`VERIFIED` / `not-started` — the remaining gap is a
> **dependency**, not a missing step). No row state changes. This measures
> the J6 call site again, now that the artifact is restored, and confirms the
> note's structural claims instead of trusting them.

## Method

`rea decompile QTranslate.6.10.0.exe 0x445716 --provider ghidra`
against `docs/review/artifacts/QTranslate.6.10.0.exe`
(md5 `a7c1278d831b9dd8261b55b82eaaffc0`). Full output, 772 characters.

```c
void __thiscall FUN_00445716(void *this,int *param_1)
{
  uint uVar1;
  int iVar2;
  void *local_8;

  iVar2 = 0;
  local_8 = this;
  if (*(char *)((int)this + 0x14) == '\0') {
    FUN_00466509(*(void **)((int)this + 0x10));
    *(undefined1 *)((int)this + 0x14) = 1;
  }
  uVar1 = (uint)param_1[1] >> 1;
  local_8 = (void *)FUN_004b43f5(-(uint)((int)((ulonglong)uVar1 * 4 >> 0x20) != 0) |
                                 (uint)((ulonglong)uVar1 * 4));
  if (uVar1 != 0) {
    do {
      *(int *)((int)local_8 + iVar2 * 4) = (int)*(short *)(*param_1 + iVar2 * 2);
      iVar2 = iVar2 + 1;
    } while (iVar2 < (int)uVar1);
  }
  FUN_00467437(*(byte **)((int)this + 0x10),(int *)&local_8,uVar1);
  FID_conflict__free(local_8);
  return;
}
```

## What each line confirms against J6's note

| Line in the decompile | J6's note | Measured |
|---|---|---|
| `if (*(char *)(this + 0x14) == '\0')` then init, `*(undefined1 *)(this+0x14) = 1` | "init once behind a flag" | confirmed — a one-shot byte guard at `+0x14`, not a `param_3[5]` field |
| `FUN_00466509(*(void **)((int)this + 0x10))` | init `FUN_00466509` | confirmed |
| `uVar1 = (uint)param_1[1] >> 1` | "int16→int32 widening" | confirmed — frame byte count halved to a sample count |
| `short` read into a `FUN_004b43f5` 4-byte-per-sample allocation | "short read into a 4-byte-per-sample allocation, freed per frame" | confirmed — `iVar2*4` store, `iVar2*2` load, `FID_conflict__free` right after |
| `FUN_00467437(this+0x10, &local_8, uVar1)` | encode `FUN_00467437` | confirmed |

So the J6 structural claims reproduce exactly: one-time init guard at
`this+0x14`, PCM widening per frame, block-wise encode call, per-frame free.

One notation difference worth recording: J6's note says the init flag is
behind "`param_3[5]`". In this re-decompile the callable takes two parameters
(`this`, `param_1` = the frame record) and the flag is `this+0x14`. The `<< -> >>` semantic ("init once") is identical; the field address is stated
differently. This is a parameter-naming artifact of the earlier
`DecompileNamed.java` pass, not a contradiction — and it does not affect the
row, whose claims are about the widening/encode/free sequence.

## What this does NOT establish

- No new finding for the `not-started` port state. Python's stdlib still has
  no FLAC path and `requirements.txt` adds none, so "porting the encoder"
  means vendoring libFLAC 1.2.1 (statically linked, verified by the note's
  byte evidence) or reimplementing partitioned-rice coding **plus** the
  block chunking `FUN_00467437` does. That is a product decision, unchanged.
