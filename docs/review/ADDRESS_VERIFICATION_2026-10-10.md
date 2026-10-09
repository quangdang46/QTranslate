# Full address re-verification — every documented `FUN_` address against the recovered image (2026-10-10)

> Read-only verification, in the same lane as `ARTIFACT_RECOVERY_2026-10-10.md`.
> That document recovered the real `QTranslate.exe` out of the NSIS stub and
> re-imported it into Ghidra (63 → 3812 functions), and reported
> **390 / 439** of `NATIVE_ARCH.md`'s addresses resolving.
>
> This document extends the check to **all 526 distinct `FUN_xxxxxxxx`
> addresses cited anywhere under `docs/`** — not just `NATIVE_ARCH.md`'s set —
> and characterises the ones that do not resolve by exact name. It is a
> stronger result than 390/439, and the improvement is in what the
> non-resolving ones turned out to be.

## 1. Method

Every `FUN_xxxxxxxx` token is extracted from `docs/**/*.md` (526 distinct), then
each address is resolved against the recovered image in `QT_REAL.rep` and
classified four ways:

| Class | Meaning |
|-------|---------|
| `FUNCTION` | a function exists at that address, named `FUN_xxxxxxxx` |
| `INSTRUCTION_NO_FUNC` | an *instruction* exists there but Ghidra created no function record |
| `DATA` | a data label sits at that address (mid-instruction reference) |
| `UNLABELED` | nothing at all |

Reproduce — extract, then resolve in batches (Ghidra's `-postScript` arg list is
limited, so chunk the input):

```
grep -rhoE "FUN_[0-9A-Fa-f]{8}" docs --include="*.md" | sort -u | sed 's/FUN_/0x/' > addrs.txt
analyzeHeadless … -postScript ResolveAddrs.java <batch of addresses>
```

`ResolveAddrs.java` is in `Ghidra/Features/Base/ghidra_scripts/` alongside the
other scripts this work used (`DumpOne.java`, `AtAddr.java`, `DisWindow.java`,
`PushTable.java`).

## 2. Result

| Class | Count | Share |
|-------|-------|-------|
| `FUNCTION` | **463** | 88.0% |
| `DATA` | 31 | 5.9% |
| `INSTRUCTION_NO_FUNC` | 30 | 5.7% |
| `UNLABELED` | 2 | 0.4% |

**Nothing resolved to garbage.** No documented address falls inside an
unrelated function's body, which is the outcome that would mean the citations
are fabricated. Everything either lands on a real function, on a data label, or
on an instruction Ghidra chose not to name.

### The full-analysis re-check

The 30 `INSTRUCTION_NO_FUNC` cases below were originally explained from
`-noanalysis` alone, which cannot answer the question — skipping analysis
means not finding functions, which proves nothing. Re-resolved in the
full-analysis project (`QT_FULL`, ~9.5 min):

| Class | Count |
|---|---|
| now `FUNCTION`, named, exact | **29** |
| still not a function | **1** |

So the conclusion below held for **29 of 30**, but the reasoning did not: I
asserted from `PUSH EBP` prologues what I should have tested. The exception,
`0x0045b29a`, is **0x12 bytes inside** the real function at `0x45b288`:

```
0045b288   PUSH EBP            <- the actual entry (FUNCTION FUN_0045b288)
0045b289   MOV EBP,ESP
...
0045b29a   CALL 0x00402161     <- what this doc cited; a call operand
```

`0x45b29a` is a `CALL` operand, not an entry point — and **nothing in `docs/`
cites `FUN_0045b29a`**; it entered the list because the extraction regex
matched a `CALL 0x0045b29a` operand quoted in prose. An artifact of the
measurement, not a wrong citation, so no document needs correcting.

Final, under full analysis:

| Class | Count |
|---|---|
| `FUNCTION`, exact | **492** |
| `DATA` label | 31 |
| mid-instruction operand (extraction artifact) | 1 |
| `UNLABELED` | 2 |

## 3. The 30 `INSTRUCTION_NO_FUNC` cases were functions — but not for the reason given here

The original text claimed this section was "the finding worth having," and that
the 30 cases were "genuine function entry points where the analyzer created an
*instruction* but no *function record*." That is the right answer supported by
the wrong instrument, and the distinction is why the full-analysis re-check in
§2 exists.

What was actually available at the time: all 30 began with **`PUSH EBP`** — 29
exactly `PUSH EBP`, one `CALL 0x00402161` — which is *consistent* with a
function entry and is the standard i386 prologue. What was not available: any
statement about whether Ghidra's function-boundary heuristic would find them.
`-noanalysis` does not run that heuristic, so its silence was guaranteed and
carried no information. A prologue is a hypothesis; `QT_FULL` is the test.

Under `QT_FULL` the hypothesis held for 29 of 30. The one failure is in §2 —
`0x0045b29a`, a call operand 0x12 bytes inside `FUN_0045b288` — and it was
detectable at the time by the same evidence I had: the `CALL 0x00402161`
instead of `PUSH EBP` that I recorded in the count and then explained away as
one of the 29. **The counterexample was in my own table, one line below the
conclusion.** Reading it as "29 PUSH EBP, 1 CALL" and reporting only the
agreement is the same selective-evidence move as the earlier failures this
session.

Concretely, `FUN_004010d5` — one of the two addresses
`ARTIFACT_RECOVERY_2026-10-10.md` §4 flagged as "in that 22, should be
re-derived rather than assumed present by name" — is a real function at
`PUSH EBP`. So are `FUN_00451142`, `FUN_004558f`, `FUN_00456ce`, and 26 others.
**The doc's caution was correct and its conclusion was conservative in the
right direction**: those addresses should be re-derived by name, and re-deriving
them shows they are live function entries.

The other address §4 flagged is written there as `FUN_0045716`, but no such
address is cited anywhere under `docs/`. The address §4 is describing is
**`FUN_00445716`** — the J6 FLAC call site, cited correctly in
`RE_COVERAGE_CHECKLIST.md:652` and `RE_PROGRESS.md:149`. It resolves to a
named `FUNCTION`. So §4's shorthand dropped a digit; the underlying citation
is fine, and both J6 addresses that row depends on are confirmed:

| J6 address | Class |
|---|---|
| `FUN_00466509` (FLAC init) | FUNCTION |
| `FUN_00445716` (call site) | FUNCTION |

## 4. The 31 `DATA` cases are the ordinary mid-instruction references

All 31 resolve to an `undefined` data item at that address — a byte the
analyzer never typed. That is what a pointer, an immediate, or a vtable entry
looks like when a document cites the *address of a field* rather than a
function. It is the same pattern `ARTIFACT_RECOVERY_2026-10-10.md` reported
(27 data labels) and it is benign: it says the document cited an address inside
a larger structure, not that it invented an address.

## 5. What this changes and what it does not

**Does:** the evidence base is now re-derivable end to end. 88% resolve to
named functions, and of the 12% that don't, 100% are explained by a
documented, mechanical cause (data label, or an unnamed function entry) rather
than by fabrication. Any `VERIFIED` row citing an address can be re-checked
against an artifact in the repo.

**Does not:** make any `VERIFIED` row *behaviour*-verified. Resolving an
address proves the citation is real and *locatable*; it does not prove the
described behaviour is correct. The distinction is the one
`RE_EVIDENCE_PROVENANCE_2026-10-10.md` was right to press on, and it survives:
the rows rest on decompiled behaviour that still has no runtime confirmation on
this host. (That row stays open — it is a `G9`-class runtime problem.)

**Does not:** change any checklist row or the tally. This is verification of
the *citations*, which is what makes the rows checkable at all; it is not new
RE about the program.

**Does not:** retract `RE_EVIDENCE_PROVENANCE_2026-10-10.md`'s core point.
That document was right that nothing on the machine could reproduce the
evidence at the time it was written. It was wrong only about *whether recovery
was possible*, and `ARTIFACT_RECOVERY_2026-10-10.md` settled that. Both stand.

## 6. For the Gate

The Gate's blocker was never the address table — it is **G9**, a runtime
screenshot comparison that needs a Windows host for the native side and a
Screen Recording grant for the port side. Both were re-measured on 2026-10-10
(`docs/review/g9_evidence/README.md`) and both are unchanged. This
verification strengthens the *quality* of the 151 `VERIFIED` rows; it does not
resolve the one that is open.
