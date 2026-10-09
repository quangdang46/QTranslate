# RE Evidence Provenance Audit — 2026-10-10

> **SUPERSEDED IN PART — read §0 first.** The original conclusion of this audit was
> that the Gate's evidence base could not be re-derived. That turned out to be
> wrong, and this document now records both the false alarm and its resolution,
> because the resolution changes how the citations should be described from here on.
> **Gate state is unchanged: BLOCKED (1), on G9 only** (per
> `FINAL_RE_AUDIT_2026-10-09.md` §13.2). No checklist row was relabelled and no
> waiver was assigned by this audit.

## 0. Correction (added 2026-10-10, after the original write-up)

**Original claim, now withdrawn:** that 151 `VERIFIED` rows rest on citations to
an artifact "not present and not re-derivable on this machine".

**What actually happened:** the only file on disk was an **NSIS installer stub**
(the findings in §1–§4 stand and are still correct about *that file*). The real
program was **inside** it. `QTranslate.6.10.0.exe` in Downloads is an unmodified
NSIS 3.08 wrapper whose appended payload is a solid **LZMA1** stream containing
the genuine 1,462,272-byte PE. It has been extracted and verified:

| Property | Value |
|----------|-------|
| PE / machine | `PE32` / `0x14c` (i386) |
| ImageBase | `0x400000` |
| `.text` | VA `0x401000 .. 0x50cc00` |
| sections | `.text .rdata .data .rsrc .reloc` |
| sha256 | `f35a3bc8e09e217130ff97efe85ba02bd86573b2e0796b003526604454338227` |

Extraction (independently reproduced from the raw stub, byte-identical result):

1. PE-header parse locates the last section raw end at `0xF600`; the NSIS
   firstheader `NullsoftInst` sits at `0xF608`.
2. Firstheader: `length_of_header = 45516`, `length_of_all_following_data =
   867763` (== `filesize − 0xF600`, self-consistent), LZMA props
   `5d 00 00 80 00` (lc=3, lp=0, pb=2, 8 MiB dict).
3. The solid LZMA1 stream begins at **`0xF621`** (not `0xF620` — this is the
   reason a naive decode fails). Decompressed: **2,263,053 bytes**, clean EOF.
4. The genuine PE starts at stream offset `0x9bfa9`.

**Effect on the documented citations.** `docs/NATIVE_ARCH.md` cites **439**
distinct `FUN_xxxxxxxx` addresses. Against this binary **all 439 lie inside
`.text` (0x401000..0x50cc00)**. In a fresh Ghidra 12.1.4 headless import
(3812 functions, ~9.5 min auto-analysis) **390 resolve by exact name**; the
remaining 49 are label differences (27 land on mid-instruction data labels, 22
have no label) rather than invented addresses.

So the honest state is: **the citations are reproducible from an artifact that is
now on disk** — `docs/review/artifacts/QTranslate.6.10.0.exe` (see §5).

**Two things this audit should not be read as having done.** It did not
re-verify the 151 rows — it re-verified only E21/F12/R2 (§6), which are the ones
that gate our port. And it did not turn the Gate green; G9's `UNKNOWN` is a real
runtime-measurement gap and is unaffected either way.

## 0a. Original text (superseded, kept for the record)

> Finding class: the Gate's evidence base cannot be re-verified from any
> artifact on this machine. This is written before any code is changed, and it
> does not relabel any checklist row. It records what I actually measured, so a
> human can decide what to do about it.

## 1. What triggered this

`docs/review/FINAL_RE_AUDIT_2026-10-09.md` §5 cites, as the new evidence for
several closures, specific functions and addresses in the native binary
(`FUN_0040FEC9` for E21/F12 tkk, `FUN_00461ADE` for R2, `FUN_0042ED3F` for J7,
`FUN_00466509` for J6). I set out to verify E21's tkk parse marker against the
binary rather than against the port's own regex (see §5 for why that matters).

## 2. What the available artifact actually is

The only PE on this machine:

```
/Users/tranquangdang21/Downloads/QTranslate.6.10.0.exe   (909,139 bytes)
```

An independent PE header parse (my own struct parser, not a doc claim):

| Field | Value |
|-------|-------|
| `machine` | `0x14c` IMAGE_FILE_MACHINE_I386 |
| sections | 5 |
| `.text` | vaddr `0x1000`, raw `0x400`, **raw size `0x6800`** |
| `.rdata` | raw size `0x1400` |
| `.rsrc` | raw size `0x7000`, ends raw `0xF600` |
| file size | `0xE33B3` (909,139) |

`.rsrc` ends at raw offset `0xF600`; the file is `0xE33B3`. **~868 KB is
appended after the last section.** At `0xF608` sits the NSIS signature:

```
00 00 00 00 ef be ad de "NullsoftInst"
```

That `deadbeef` prefix plus `NullsoftInst` is the **NSIS firstheader** magic. The
program's own embedded manifest (read from Ghidra, address `00456b20`) confirms
it in its own words:

> `assemblyIdentity ... name="Nullsoft.NSIS.exehead" .../description> Nullsoft
> Install System v3.08`

**Conclusion: the only PE available is an unmodified NSIS 3.08 *installer stub*,
not the QTranslate program.**

## 3. What the Ghidra project contains

The only Ghidra project on this machine is `/Users/tranquangdang21/Projects/QTranslate.rep`
(verified: sole `.prp` names the program `QTranslate.6.10.0.exe`, and the sole
entry in `idata/~index.dat`).

Its imported symbols and strings are, exhaustively:

- imports: `ADVAPI32.dll`, `SHELL32.dll`, `ole32.dll`, `COMCTL32.dll`,
  `GDI32.dll`, `USER32.dll`, `KERNEL32.dll` — **7 DLLs, all Win32 shell/user/gdi**
- **every string in the program** is either an imported API name, a DLL name, or
  the NSIS manifest quoted above. There is nothing else (`list_strings`, all 2000
- offset 0).
- `list_classes` returns exactly those 7 DLL names. No RTTI classes.
- segments: `Headers .text .rdata .data .ndata .rsrc tdb`
- **63 functions total**, last body ending at `00407601`.

The largest disassembled function, `FUN_00406bb0`, is a textbook **LZMA/lzma-sdk
range decoder** (probability-shifted `>> 5`, `<< 11` bit model, `0x1000000`
normalization) — i.e. the stub's decompressor, not application logic.

Absent from the entire program: `QTranslate`, `quest-app`, `element.js`,
`_ctkk`, `RichEdit`, `IActiveScript`, `JScript`, `Services/`, `Options.json`,
`BASS_`, `bass.dll`. Searched by bytes; all ABSENT.

## 4. The decisive check: documented addresses vs the loaded program

`docs/NATIVE_ARCH.md` cites **439 distinct** `FUN_xxxxxxxx` addresses
(min `0x4010d5`, max `0x4f4bd0`). Compared against the Ghidra project:

| | |
|---|---|
| Documented function addresses | 439 |
| Present as a function in the project | **0** |
| Lying above the project's last function body (`00407601`) | **365 (83%)** |

Not one documented address resolves. `FUN_0040FEC9`, `FUN_00461ADE`,
`FUN_0042ED3F` — all return *"Function not found"* / *"No function found at
address"*.

## 5. Why this matters specifically for the E21 tkk claim flagged by qtranslate-ed

`qtranslate/services/google_translate.py:211` parses:

```python
m = re.search(r"_ctkk\s*=\s*'([^']+)'", js)
```

and the comment asserts `element.js contains: var _ctkk='409484.2968434358';`.

I set out to check that marker against `FUN_0040FEC9`. **I could not — the
function does not exist in the available artifact.** So the port's marker is
unverifiable either way, and two possibilities are both live:

- the marker is right and matches the binary's slice points, or
- the port parses the right *value* from a marker the binary never uses, and a
  regex unit test plus a "parse closed" checklist note would both pass anyway.

**This is exactly the class of claim the evidence vocabulary is supposed to
prevent, and right now it cannot be settled.** The checklist marks E21 `VERIFIED`
citing `FUN_0040FEC9`, and `qtranslate-ed` independently flagged the port label
as stale. Both concerns are now the same, larger concern.

## 6. What I am NOT claiming

Two readings remain open and I cannot separate them from available artifacts:

- **(a) the real `QTranslate.exe` exists and was analysed somewhere**, and
  `NATIVE_ARCH.md`'s addresses are genuine but reference a binary that has since
  been replaced on disk by the NSIS stub;
- **(b) the addresses were never backed by that binary at all.

The NSIS payload could still contain a compressed `QTranslate.exe` (NSIS
compresses solidly — LZMA or zlib — so plaintext bytes are not findable, which
is why my byte searches for `MZ` at a second offset, `PK\03\04`, and the program
strings all came back absent). I have **no** extractor available (`7z`, `unar`,
`cabextract`, `wine` are all absent; `bsdtar` reports "Unrecognized archive
format"). So I cannot rule (a) in or out.

**Either way the consequence for this project is identical:** the 151 `VERIFIED`
rows rest on citations to an artifact that is not present, and no one on this
machine can re-derive them.

## 7. Consequences for the Gate and for Phase C

`FINAL_RE_AUDIT_2026-10-09.md` reads `BLOCKED (1)` — blocked *only* on G9. That
framing is not supportable: the Gate's real state is that its evidence base is
**unreproducible**, which is a strictly bigger problem than an unmeasured pixel
diff, and one that no runtime harness can address.

`IMPLEMENTATION_PLAN.md` Phase 0 requires "a baseline snapshot of current test
results is recorded (re-run, not copied from README)" — that baseline is
obtainable and is worth doing. But Phases 1–8 repeatedly justify decisions with
"preserve 6.10 behavior per `COMPATIBILITY_MATRIX.md`" (D10). D10 is the decision
most damaged by this finding: if we cannot read the binary, we cannot check
"preserve 6.10 behavior" against it, and the matrix's native-behavior rows are
inherited on trust.

**This is a checkpoint for the user, not a blocker I should resolve alone.**
The honest options are: obtain the real `QTranslate.exe` (and re-analyse it),
extract it from the NSIS payload (needs a tool I don't have), or explicitly
reclassify the evidence axis to reflect that native behavior is asserted, not
locally verified — and let Phase C proceed only on decisions that don't secretly
depend on unverified native behavior.
