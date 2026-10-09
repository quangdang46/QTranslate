# J6 — FLAC encode chain, decompiled from the recovered image (2026-10-10)

> Re-opened because the tooling changed. The first pass over J6 closed it from
> string/byte evidence plus the earlier session's decompile notes; **Ghidra is
> now running again on this host**, so the three functions in the chain were
> re-decompiled and the row is being rounded out with what they actually say.
>
> Launch recipe:
>
> ```sh
> JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
>   ~/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
>     ~/Projects QT_REAL -process "QTranslate.6.10.0.exe" -noanalysis \
>     -scriptPath tools/ghidra -postScript DecompileNamed.java FUN_...
> ```
>
> `JAVA_HOME` is required and non-obvious: `java_home` does not list keg-only
> Homebrew formulae, which is how this host's OpenJDK 21 was wrongly declared
> missing — see `GHIDRA_MCP_UNAVAILABLE_2026-10-10.md`. The script resolves by
> exact **name** rather than address, so a differently-labelled function reports
> `NOT FOUND` instead of silently decompiling the wrong one.

## 1. The chain, verified

`FUN_00445716` — the call site, reached from the speech loop:

```c
iVar3 = 0;
if ((char)param_3[5] == '\0') {          // encoder not yet initialized
  FUN_00466509(param_1, 0, (uint *)param_3[4]);   // init once
  *(undefined1 *)(param_3 + 5) = 1;      // and set the "initialized" byte
}
uVar2 = (uint)param_4[1] >> 1;           // frame length in samples
local_8 = (int *)FUN_004b43f5(uVar2 * 4); // int32 buffer, 4 bytes/sample
do {
  local_8[iVar3] = (int)*(short *)(*param_4 + iVar3 * 2);   // int16 -> int32
  iVar3 = iVar3 + 1;
} while (iVar3 < (int)uVar2);
FUN_00467437(piVar1, (int *)&local_8, (uint *)param_3[4], uVar2);  // encode
FID_conflict__free(local_8);
```

So the widening is exactly as the row said: **`short` → `int`, 2 bytes read
into a 4-byte-per-sample buffer**, freed after each frame. The init guard is a
single byte at `param_3 + 5`, so the encoder is created once per capture
session and this runs per PCM frame.

`FUN_00467437` — the per-buffer encode call. The shape that matters:

```c
uVar1 = *(uint *)(*param_3 + 0x18);      // channel count
uVar2 = *(uint *)(*param_3 + 0x24);      // block size
uVar4 = (uVar2 - *(int *)(uVar7 + 0x1b8c)) + 1;   // room left in the block
if (param_4 - uVar5 <= uVar4) uVar4 = param_4 - uVar5;   // clamp to the request
...
FUN_004c0200(channel_buf + offset, &samples[iVar8], uVar4 << 2);
```

This is **block-wise accumulation, not one-frame-per-call**: the encoder keeps
a partially-filled block (`+0x1b8c` is samples-so-far) and only flushes when
the block is full. `FUN_004c0200` is the de-interleave/copy into per-channel
buffers, once per channel. That is a detail the row's "per-buffer encode call
site" wording did not carry, and it matters for a faithful port: you cannot
just hand libFLAC one buffer per call.

## 2. The encoder init, and what its guards really are

`FUN_00466509` — FLAC encoder init. Decompiled in full; the guards that the
row previously summed up as "returns FLAC init-status codes 1..0xd" are more
specific than that:

| Check | Code | Meaning |
|---|---|---|
| `*piVar13 != 1` | `goto LAB_004670c7` (bail) | the pointed-to object must be in state 1 |
| `piVar13[6] == 0 \|\| 8 < piVar13[6]` | bail | **channels in 1..8** |
| `piVar13[4]` / `piVar13[5]` | zeroed | per-channel buffers reset |
| `0x1f < *(uint *)(uVar14 + 0x1c)` | `*(uVar14 + 0x10) = 0` | block size at most 0x20 |
| `0x14 < *(int *)(+0x1c) - 4U \|\| *(+0x20) == 0 \|\| 0x9fff6 < *(+0x20)` | bail | **sample rate in 0x15..0x9fff7** |
| `*(int *)(+0x24) == 0` | default `0x1000`, or `0x480` when `[+300]==0` | block size default |
| `*puVar1 < 5 \|\| 0xf < *puVar1` | bail | some parameter in 5..15 |
| `uVar14 != 0xc0, 0x240, 0x480, 0x900, 0x1200, 0x100` | bail | an allow-list of **six** sizes |
| `piVar13[7] != 0x20 \|\| piVar13[8] != 0x20` | bail | two fields exactly 32 |
| `(&DAT_0052db20)[iVar15]` walk over `piVar13[5]`, 4 of them | bail | a 4-byte magic compare |

That last one, in the tail:

```c
while (iVar15 = iVar15 + 1, iVar15 != 4) {
LAB_00466975:
  pcVar16 = pcVar17 + iVar15;
  pcVar17 = (char *)piVar13[5];
  if (*pcVar16 != (&DAT_0052db20)[iVar15]) goto LAB_004670c7;   // a 4-byte tag
}
LAB_00466990:
  if ((piVar13[7] != 0x20) || (piVar13[8] != 0x20)) goto LAB_004670c7;
```

`(&DAT_0052db20)[iVar15]` is a 4-entry comparison table — almost certainly the
`"fLaC"` magic the row already cites (`FUN_0046CBCE` writing `0x664C6143`),
checked here against whatever `piVar13[5]` points at. **Not re-verified as
`fLaC` by reading `DAT_0052db20`'s bytes**; asserted only as "a 4-byte
sequence compare against a table", which is what the decompile shows.

Two terminal states, both of which are *writes into the caller's struct*
rather than return values — which is consistent with the function being
`void`:

```c
LAB_00466e56:
  *(undefined4 *)*param_3 = 7;      // failure: state 7
...
  else {
    *(undefined4 *)*param_3 = 5;    // success: state 5
  }
```

So the "return codes 1..0xd" in the row's Note is **imprecise in a way worth
fixing**: `FUN_00466509` returns `void` and communicates through
`*(undefined4 *)*param_3`, taking `7` on the bail path and `5` on success.
The state machine values 1/5/7 are visible; the full `1..0xd` enumeration is
not reproducible from this decompile and should not be cited as though it were.

## 3. Effect on the row

`RE_COVERAGE_CHECKLIST.md` J6 — the RE axis stays `VERIFIED`; what changes is
precision:

- **init**: `void`, communicates via `*param_3` (state 5 ok / 7 bail), with a
  channels-in-1..8, a sample-rate bound of `0x15..0x9fff7`, a six-value size
  allow-list, and a 4-byte tag compare.
- **call site**: int16→int32 widening with a 4-byte-per-sample allocation, per
  frame, encoder created once behind a `param_3[5]` byte.
- **encode**: block-wise with per-channel de-interleave, not one-frame-per-call.
- **Port axis stays `not-started`, and now with a sharper reason.** Native
  links `reference libFLAC 1.2.1` statically. Porting means vendoring libFLAC
  or reimplementing partitioned-rice coding **plus** this chunking, which the
  libFLAC API does not do for you. Python's stdlib has no FLAC path and
  `requirements.txt` adds none, so it is a dependency decision, not RE work.
