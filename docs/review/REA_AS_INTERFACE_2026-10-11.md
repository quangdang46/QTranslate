# REA accepted as the interface; Ghidra remains the engine

> Tooling decision, recorded so the provenance lines in `docs/review/` stay
> true and so nobody later reads "measured with REA" as "measured by
> something other than Ghidra".
>
> **No row state changed by this document.** Nothing here re-measures a
> behaviour; it changes how the same engine is driven.

## 1. The question, and what REA turned out to be

The peer asked whether the RE work should move from hand-written Ghidra
headless scripts to <https://github.com/morluto/rea>. I checked REA's own
documentation rather than inferring, and then ran it against this target.

REA is a **CLI + MCP wrapper with an investigation workflow**. For native
binaries its own README says the requirement is "Hopper, Ghidra or IDA", and
`docs/installation.md` says the Ghidra provider is **bring-your-own**:

> REA's Ghidra provider ... supports ... the exact official Ghidra
> release and a 64-bit full JDK 21.

So on this host — no Hopper, no IDA, Ghidra 12.1.4 already installed — **REA
is Ghidra at the engine and a better interface on top.** It drives the same
`support/analyzeHeadless` with a packaged Java bridge.

Verified on this host, not assumed. `rea doctor --provider ghidra --json`:

| Check | Result |
|---|---|
| node | 26.3.0 ok |
| ghidra-installation | `ghidra_12.1.4_PUBLIC/Ghidra/application.properties` ok |
| ghidra-version | 12.1.4 ok |
| ghidra-headless | `support/analyzeHeadless` ok |
| ghidra-native_decompiler | macOS arm64 decompiler present, matches host |
| ghidra-java | JDK 21.0.12.1, 64-bit, full JDK with `javac` |

`environment_healthy` is false only for the two engines we do not have
(Hopper, IDA registration) — both informational.

The target is **i386 PE**, machine `0x014c`, optional-header magic `0x10b`
(PE32), 5 sections. REA reports `architecture: x86` and Ghidra handles it. The
Windows-only Ghidra P0 path is documented as x86-64 and is not our path; we
are on the main provider from macOS.

## 2. The cross-check that justifies adopting it

Adopting an interface because it is convenient would be the wrong reason. The
reason is that it reads the **same database**. `PLUGIN_LOADER_FOUND_2026-10-10.md`
recorded the plugin loader `FUN_0045d6a9` from a Ghidra decompile; REA returns
the same function with the same shapes:

```c
FUN_0045b1cf(L"Services", &local_c);          // <config dir>/Services
DVar3 = GetFileAttributesW(local_c);
if (DVar3 == 0xffffffff) { uVar5 = 0; }        // no Services dir -> bail
else {
  FUN_00401f21(&local_14, L"Common.js");       // framework first
  FUN_0045b9d9(&local_18, &local_14);
  FUN_0043df32(pWVar8, &DAT_005492ac);         // read + compile it
  ...
```

`L"Services"`, `L"Common.js"` before the subdirectory loop, and `FUN_0043df32`
as the compiler — the three load-bearing facts of the loader doc, reproduced
through an interface we had never used before, on the same artifact. The same
cross-check on `FUN_004253cc` (the dictionary card builder) returned the card
format string, `L"Service.ico"`, `L"Services"`, and the `Service.js`-icon
derivation.

Two independent interfaces, one artifact, same result. That is the finding
that makes the switch safe; REA's own output is not it.

## 3. What is not changed, stated so it is not misread

| Unchanged | Why |
|---|---|
| the analysis engine | Ghidra 12.1.4, same install, same auto-analysis |
| every address | `FUN_0045d6a9` is `0x0045d6a9` in both |
| every measured number in `docs/review/` | the reproduce blocks read the exe bytes directly in Python and do not go through either interface |
| the RE-state column's meaning | `VERIFIED` still means artifact + decompile / JS source / asset bytes / behavioural test |

**Changed:** how a human-shaped query reaches the engine. The
script-compile-failure class disappears — it was a real cost, not a
hypothetical one: the peer's `FrameMap`, `FmtArgs`, `EspTrack`, `Vars`,
`UpToAddr`, `SlotResolve`, `StackMap`, `Varargs` and `E.php` scripts all failed
to compile, and only `UpTo.java` and `FindRefs.java` survived.

**The one lesson that survives the switch:** `skipping <path>` +
`ClassNotFoundException` in a headless log means the script did not compile,
and the real `error:` lines are ~15 lines above. That is not a REA fact — it is
a Ghidra fact, and the new interface does not remove the need to know it,
because Ghidra's headless log is still what we read when something fails.

## 4. Cost, measured rather than guessed

REA re-imports and re-analyzes the target on each invocation — there is no
persistent session across CLI calls. The 0x004253cc and 0x0045d6a9 decompiles
each took roughly two minutes end-to-end, so **per-call cost is a full
analysis**, where the old `QT_FULL` project kept one analysis and served many
scripts against it.

That is a real regression for queries that revisit a known function, and it is
why the standing practice stays: **if a document already records a function's
decompile and the reproduce block is self-contained, do not re-derive it
through a new interface to confirm it.** REA's `--snapshot` flag exists for
this; whether to keep snapshots on disk is a separate question (§5).

## 5. Snapshots and Evidence JSON: kept out of the repo

Decision, matching the peer's own lean and my reasoning from the evidence
chain:

**REA's Evidence JSON is not committed.** Reasons:

1. **It is a second artifact format to keep honest.** Our reproduce blocks are
   self-contained Python that reads `QTranslate.6.10.0.exe` and prints the
   bytes a claim rests on. A signed Evidence envelope is only as good as the
   schema version that produced it, and a stale one is indistinguishable from
   a current one to a reader.
2. **It would imply an authority the docs do not claim.** `authority:
   shipped-artifact` and a `digest` read as more load-bearing than a
   reproducibility note, and `PROJECT_VISION.md` §7 is explicit that no axis may
   borrow credibility from another.
3. **The digest already does the useful part.** Every result carries the
   SHA-256 of the exe; when a document needs to pin which bytes it measured,
   naming the digest is enough. `docs/review/artifacts/` keeps the exe and the
   unpacked NSIS payload, both of which are the thing being measured — not
   one tool's rendering of it.

## 6. Verified limitation: `instructions` returns the whole function, not a window

I asked `rea instructions <exe> 0x425583` — an address in the middle of
`FUN_004253cc`, well past its entry — and measured what came back:

```
n instructions: 257
first: 0x4253cc: PUSH EBP
last:  0x425757: RET 0x4
```

It returns **the entire containing function from its entry**, not a window
starting at the address given. The `--procedure` help text says "Procedure
name or address", and that is what it does: an address is *resolved to a
procedure*, then that procedure's instructions are listed. The `address`
argument is a procedure selector, not an offset.

This matters because it is exactly the query the old hand-written script
existed to answer. In `DICT_CARD_HEADER_SLOTS_RESOLVED_2026-10-10.md` the
finding turned on a 44-byte window around `0x004255a2`:

```
0x42558d: PUSH dword ptr [ESP + 0x30]
0x425591: PUSH dword ptr [ESP + 0x20]
0x42559c: PUSH 0x51e8f0
0x4255a2: CALL 0x004023f1
0x4255af: ADD ESP, 0x2c
```

Those five instructions **are** in the 257 REA returned — so REA does answer
the question, and I re-read them through REA to confirm. What it does not do
is answer it *cheaply*: the answer arrives inside a whole-function dump that
must be paged or filtered. `--filter-output` and `--token-limit` are the right
tools, and `rea instructions` is documented as the fast path because it skips
the decompiler — but the window it returns is the function's, not the caller's.

**Practical rule, recorded so nobody re-derives it:** use `rea instructions`
when you want a function's instruction list. Use the JSON output with
`--filter-output raw_result.value.instructions` when you want to inspect one
region, and expect to locate your address within the returned range rather
than have it be the start. `address-to-file-offset` remains the right tool for
the VA→file-offset conversion that §4's hand work did.

This does not weaken §2's cross-check: the loader and card findings were
reproduced exactly. It means REA replaces *some* of the script work and
re-frames the rest — the compile-failure class is gone, and the remaining cost
is output volume rather than script errors.

## 7. Provenance line, updated

Documents that say "from a full-analysis Ghidra run (`QT_FULL`)" stay as they
are — that is what was used at the time. **New** RE verification states the
interface alongside the engine, so a reader does not have to guess whether a
finding came from Ghidra, from REA, or from a method that predates both:

> Read-only verification from the recovered image
> (`docs/review/artifacts/QTranslate.6.10.0.exe`, SHA-256
> `f35a3bc8e09e217130ff97efe85ba02bd86573b2e0796b003526604454338227`),
> decompiled with **Ghidra 12.1.4 headless, via REA 6.4.0**.

The digest is included because it is the one piece of REA's output that is
worth copying into the docs: it pins the exact artifact.

## 8. Answering the peer's two other questions, since they were asked

**Q3 (snapshots):** out of the repo, as above. Use them locally, do not
commit them.

**The I-row second class:** measured independently and it holds. Exactly five
rows cite `Plugins/*.js` — I3, I4a, I4b, I4c, I4d — and that file class is in
neither the image nor the repo (no `*.js` filename anywhere in the exe; no
committed `*.js`). I1/I2/I5/I6 are `FUN_`-address-backed and O2 cites
`lang.json`, so they are outside the class. The count is 5, not the ~30 a
loose substring count gives, and the difference is the whole point of reading
the rows rather than matching a pattern.

That is **not** the same class as the 20 `Service.js` rows, and it must not be
merged into that proposal: the `Services/*` loader is *found and readable*
(`FUN_0045d6a9`), which is why those rows are `UNRECOVERABLE`-in-principle
with a definite reason, whereas the `Plugins/History/*.js` rows have no
loader located at all. Same destination label, different and weaker reason.
Recording that distinction is the honest part.

No row state changed by this document; the reclassification remains the row
owner's decision.
