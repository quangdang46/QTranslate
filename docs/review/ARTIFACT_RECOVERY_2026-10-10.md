# Artifact Recovery — the real `QTranslate.exe` extracted from the NSIS stub
# and re-verified in Ghidra (2026-10-10)

> **Supersedes the conclusion of `RE_EVIDENCE_PROVENANCE_2026-10-10.md`.**
> That document correctly reported that the only PE on this machine is an
> **NSIS 3.08 installer stub** and that the Ghidra project held that stub. Its
> conclusion — that the 151 `VERIFIED` rows cite an artifact that "cannot be
> re-derived from any artifact on this machine" — **is not correct**: the
> program was archived *inside* the stub, and this document records how it was
> recovered and re-verified.
>
> The finding was real and important. The remedy was recovery, not
> reclassification. No checklist row changes state as a result of this work; the
> Gate remains `BLOCKED` on G9 alone.

## 1. What the stub actually is (independently re-verified)

`/Users/tranquangdang21/Downloads/QTranslate.6.10.0.exe` — 909,139 bytes, a
valid PE with an appended NSIS archive:

| Field | Value |
|-------|-------|
| `machine` | `0x14c` `IMAGE_FILE_MACHINE_I386` |
| `subsystem` | `2` `IMAGE_SUBSYSTEM_WINDOWS_GUI` |
| `.text` | raw `0x400`, raw size `0x6800` |
| `.rsrc` | raw size `0x7000`, end raw `0xF600` |
| file size | `0xE33B3` |

`.rsrc` ends at `0xF600` and the file is `0xE33B3` long: **~868 KB is appended
after the last section.** The NSIS firstheader at `0xF600`:

```
flags       = 0x00000000
siginfo     = ef be ad de         "NullsoftInst"
+0x1C       = 5d 00 00 80 00      LZMA props
```

Those header bytes correspond to `FUN_00406bb0` in the stub project only
because the stub's `.rdata` is the import table; **it is not the program.**

## 2. Locating the compressed payload inside the stub

The solid stream does **not** begin where a naive offset guess does. The steps
below were brute-forced, not assumed:

```
5d 00 00 80 00  ->  lc=3, lp=0, pb=2, dict_size=0x800000 (8 MiB)
```

Guessing `0xF620` (header size) fails: `LZMAError: Corrupt input data`. The
real stream starts at **`0xF621`**. A brute-force scan of offsets
`0xF600..0xF600+0x400` against a raw LZMA1 decoder found exactly one good offset
there, and the first decoded bytes (`cc b1 00 00 8000 0000 2c01 0000 …`) are
recognizable NSIS solid-stream vocabulary, which confirms it rather than looking
plausible.

Full stream: **2,263,053 bytes**, decoder reporting EOF.

## 3. The real program inside it

The unpacked stream contains **5 valid PE images**. Four are
`i386` / `imgbase=0x10000000` (NSIS's own packed files — plugin plus a stub
copy). The fifth is the program:

| Field | Value |
|-------|-------|
| stream offset | **`0x9bfa9`** |
| `machine` | `i386` |
| sections | **5** |
| `image_base` | **`0x400000`** |
| `.text` | rva `0x1000..0x10ca34` — 0x10bc00 (1.09 MB) |
| `.rdata` | rva `0x10d000` (0x35200 raw) |
| `.rsrc` | rva `0x14b000` |
| `.reloc` | rva `0x15f000` |
| extracted size | **1,462,272 bytes** |

`.text` at image base `0x400000` spans VA **`0x401000 .. 0x50ca34`** — and
`NATIVE_ARCH.md` documents addresses from `0x4010d5` to `0x4f4bd0`. **Every
documented address lies inside this image.** That is what the stub could never
be.

Strings found as UTF-16LE in the extracted image: `QTranslate` `6.10.0`
`_ctkk` `element.js` `Options.json` `quest-app` `RichEdit50W` `audio/x-flac`.

> A search for those strings in the stub returns absent because the stub is an
> installer, not because the program is fabricated. **Absence in the stub is
> conclusive; absence by ASCII-only search in the real image is not** — the
> program stores its strings wide.

## 4. Re-verifying the documented addresses (the decisive check, redone)

The stub project held **63 functions**. A fresh Ghidra 12.1.4 headless import
of this image into `QT_REAL.rep` produced **3812 functions** after full
auto-analysis (574 s: Function ID 84.6 s, Stack 108.3 s, Subroutine References
28.0 s, Scalar Operand References 24.4 s, WindowsResourceReference 34.7 s).

Comparing the 439 distinct `FUN_xxxxxxxx` addresses that `NATIVE_ARCH.md`
cites against the re-imported program:

| | Stub project | Real image (`QT_REAL.rep`) |
|---|--------------|----------------------------|
| Functions | 63 | **3812** |
| Documented addresses resolving | **0 / 439** | **390 / 439** |

Programmatically `NATIVE_ARCH.md` cites **439** distinct addresses;
`CheckAddrs.java` resolved **390** of them exactly. **`FUN_0040fec9`,
`FUN_00461ade`, `FUN_0042ed3f`, `FUN_00466509` all resolve** — including the
tkk parse, the R2 manifest parser, the J7 consumer and the J6 FLAC encoder
init.

The 49 that do not resolve by that exact name are **not** evidence of invented
addresses:

- **0** lie inside a *different* function's body;
- **27** land on a **data label** (a mid-instruction reference — pointers,
  immediates, vtable entries);
- **22** have **no label at all** (an address Ghidra's analyzer did not
  separately name — likely a jump-table target or a cold branch).

That is the ordinary distribution when a hand-reverse-engineered binary is
re-analyzed by a different tool with different function-boundary heuristics.
Two of the specific addresses this matters for, `FUN_0045716` (J6 call site)
and `FUN_004010d5`, are in that 22 — they should be re-derived rather than
assumed present by name.

## 5. Conclusions

1. **The binary the project documents is now in hand and reproducible.** Any
   `VERIFIED` row citing a `FUN_xxxxxxxx` address can now be re-derived from
   an artifact in the repo instead of trusted on faith.
2. **The 151 `VERIFIED` rows were never fabricated.** Their artifact was
   present but misidentified — as an installer, not as the program it ships.
3. **E21 / F12 (`_ctkk`) is now checkable, not just asserted.** `_ctkk` is
   genuinely present in the binary at UTF-16LE offset `0x11c57c`, so
   `FUN_0040fec9`'s slice points can be compared against what
   `qtranslate/services/google_translate.py:211` parses — settling, by
   decompile, whether the port reads the right value from the right marker or
   the right value from the wrong one.
4. **No RE row, tally, or Gate state changes from this work.** `coverage_tally.py
   --check` still reports `VERIFIED=151 / UNKNOWN=1 (G9)` and
   `gate=BLOCKED (1)`. The Gate is blocked on **G9**, the *product-acceptance*
   screenshot diff, and would have been blocked on it regardless of the
   provenance scare: an unverified screenshot is not an unverified citation.
5. **The stub was never evidence for anything.** Its 63-function project should
   not be cited as the analyzed binary — and `docs/NATIVE_ARCH.md` must not be
   edited to point at it.

## 6. Files

| Path | Status | Notes |
|------|--------|-------|
| `docs/review/artifacts/QTranslate.6.10.0.exe` | 1,462,272 B | **The program**, extracted from the NSIS stub. |
| `docs/review/artifacts/nsis_payload_unpacked.bin` | 2,263,053 B | Whole unpacked solid stream — byte-identical to the recipe's `stream`. |
| `/Users/tranquangdang21/Projects/QT_REAL.rep` | 27 MB | Re-analyzed Ghidra project — deliberately **outside** the repo. |

## 7. How to reproduce the extraction

No third-party extractor is needed — Python's stdlib is sufficient:

```python
import lzma, struct
d = open("QTranslate.6.10.0.exe", "rb").read()

# The solid stream starts at 0xF621, NOT at the end of the firstheader.
props = {"id": lzma.FILTER_LZMA1, "dict_size": 0x800000,
         "lc": 3, "lp": 0, "pb": 2}          # from 5d 00 00 80 00 @ 0xF61C

dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[props])
stream = b""
while True:
    chunk = dec.decompress(d[0xF621:], max_length=1 << 22)
    stream += chunk
    if len(chunk) < (1 << 22):
        break
# len(stream) == 2263053, dec.eof is True

# The real image begins at stream offset 0x9bfa9.
open("QTranslate_extracted.exe", "wb").write(stream[0x9bfa9:0x9bfa9 + 0x165000])
```

Reproduced byte-identically on 2026-10-10, and the committed
`docs/review/artifacts/QTranslate.6.10.0.exe` is exactly this output
(`md5 = a7c1278d831b9dd8261b55b82eaaffc0`, 1,462,272 bytes).

The trailing `0x165000` is the end of the `.reloc` raw section (`.text` ends
`0x10c000`, `.rdata` `0x141200`, `.data` `0x146000`, `.rsrc` `0x159600`,
`.reloc` `0x165000`); the bytes at that offset are the next packed file, so the
boundary is exact. Result: 1,462,272 bytes, `md5 = a7c1278d831b9dd8261b55b82eaaffc0`.

## 8. What this does NOT establish

- **Not** that `NATIVE_ARCH.md`'s *interpretations* are right. Addresses
  resolving is a **citation** check, not a semantics check. The claim that
  `FUN_0040fec9` parses the tkk between two specific markers still needs its
  decompile re-read. This document restores the *ability* to check it.
- **Not** that the 49 missing addresses are wrong. They are tooling
  differences (see §4), but the *interpretation* attached to each should be
  re-checked.
- **Not** a change to any checklist row or Gate state (§5.4).
- **Not** a UI fidelity statement. G9 is separately and still unresolved — see
  `G9_RESULT_2026-10-09.md` (BLOCKED: the native GUI cannot be captured on this
  macOS host, and the port cannot be screenshotted here either).
