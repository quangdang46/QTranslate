# D10 Spot-Verification Against the Recovered Binary — 2026-10-10

> Scope: three `Contents` option keys the recent commits touched, re-checked
> against the **real** `QTranslate.exe` recovered in
> `ARTIFACT_RECOVERY_2026-10-10.md`. This is the first D10 check that has been
> possible: until the artifact was recovered, "preserve 6.10 behavior" could
> only be inherited on trust.
>
> Method: `analyzeHeadless` (Ghidra 12.1.4) over
> `docs/review/artifacts/QTranslate.6.10.0.exe` in `QT_REAL.rep` — decompile by
> address, then read the referenced `.rdata` wide strings and their xrefs.
> Addresses are from `RE_COVERAGE_CHECKLIST.md` and confirmed present §4 of the
> recovery doc (390/439 resolve; these three are all in the resolving set).
>
> **Conclusion: the port's model is faithful on all three keys.** No code change
> was made by this pass, so no code needs re-testing.

## 1. The keys exist, and are symmetric loader/saver keys

A UTF-16LE search of the recovered image finds exactly one hit for
`EditTranslation`: `.rdata` @ `005235b0`. Exactly two references point at it:

| Referencing function | Offset | Type |
|----------------------|--------|------|
| `FUN_004561f0` | `+3010` → `00456db2` | DATA (options **saver**) |
| `FUN_0045869f` | `+2243` → `00458f62` | DATA (options **loader**) |

So the key is written as well as read — it round-trips through `Options.json`
rather than being a read-only input. That matters, because the port also writes
all three fields on exit, and a one-way native would make that wrong.

## 2. Loader (`FUN_0045869f`, 7294 B) — the three keys are distinct fields

Inside the `Contents` section branch, decompiled:

```c
FUN_00401f21(... &DAT_005235e4);            // "Contents" section header
FUN_004409c6(&cfg, &local_80);              //   section lookup
if (... != 0) {
    FUN_00401f21(... ); FUN_00440921(&cfg, in_ECX + 0x170);   // (unnamed key)
    FUN_00401f21(... L"EditSource");        FUN_00440984(&cfg, in_ECX + 0x174);
    FUN_00401f21(... L"EditTranslation");   FUN_00440984(&cfg, in_ECX + 0x178);
    FUN_00401f21(... L"EditBackTranslation"); FUN_00440984(&cfg, in_ECX + 0x17c);
}
```

Three adjacent, separately-loaded string fields at `+0x174` / `+0x178` /
`+0x17c`. `EditTranslation` and `EditBackTranslation` are therefore **real,
independently-stored native keys** — not aliases of one another and not
derived from `EditSource`.

## 3. Saver (`FUN_004561f0`, 9224 B) — writes back the same three

```
L"EditSource"          (line 294)
L"EditTranslation"     (line 299)
L"EditBackTranslation" (line 304)
```

Same order, same names, so the save path mirrors the load path.

## 4. What this says about the port

`qtranslate/app.py:805-818` restores the result pane on boot from
`Contents.EditTranslation`, appending the `--- back-translation ---` segment
when `Contents.EditBackTranslation` is non-empty; `app.py:1702-1708` writes
`EditSource` / `EditTranslation` / `EditBackTranslation` on exit, truncating
each to 5000 chars.

Against the binary:

| Port behavior | Binary evidence | Verdict |
|---------------|-----------------|---------|
| Three distinct keys | `+0x174` / `+0x178` / `+0x17c`, loaded separately | **matches** |
| `EditTranslation` and `EditBackTranslation` are separate strings | separate `FUN_00440984` calls, separate keys | **matches** |
| All three are persisted | both loader and saver reference `EditTranslation` | **matches** |
| Back-translation stored separately, re-attached on restore | field exists only to hold the second segment | **matches** |

**One thing this pass does NOT establish:** whether the native appends the
back-translation to the *result pane* on boot using a separator, versus writing
the two fields into two separate controls. The fields are separate in the
struct, so it is possible the native fills two distinct edit controls rather
than concatenating into one. The port's concatenation is a plausible reading but
is **not confirmed** by this check — the consumer of `+0x178` at window-init
time has not been located. Flagging it rather than claiming the restore is
proven.

### 4a. The port's separator text is not in the binary

`app.py:1707` and the restore path reconstruct the result pane as
`main + "\n\n--- back-translation ---\n" + back`. A UTF-16LE content search of
the recovered image finds **no** `back-translation` string and **no**
`--- back` string. The only `---`-wrapped literals in `.rdata` are
`"--- Default ---"` (a theme/style label, appearing four times around
`0x121a0c`–`0x121a4c`).

So the literal `--- back-translation ---` is **a port invention**, not a native
string. That is defensible as a UI affordance (the port has one combined pane
where the native may have two controls), but it must not be described as
faithful: if a future pass finds the native's real separator or two-control
layout, this text should change, and any test asserting it is testing our own
convention.

The consumer of `+0x178` was not located in this pass. An instruction scan for
`[reg + 0x178]` / `[reg + 0x17c]` across all 3812 functions returned **zero**
hits, which means the struct field is reached through a different addressing
form (a computed base, or the loader itself passes the field pointer onward) —
not that nothing reads it. Whoever takes the Options rows should decompile by
address rather than trusting which doc labels resolve: `FUN_0045716` and
`FUN_004010d5` do **not** resolve by name in the recovered image.

## 5. Reproduce

```
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
~/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
    ~/Projects QT_REAL -process QTranslate.6.10.0.exe -noanalysis \
    -postScript DecompOut.java 45869f /tmp/loader.c
```

`DecompOut.java`, `ReadStr.java`, `SearchBytes.java` and `XrefSearch.java` were
placed under `ghidra_12.1.4_PUBLIC/Ghidra/Features/Base/ghidra_scripts/` for
this session and **should be cleaned up** (they are outside the repo and not
part of it). Nothing in the repo was modified by this pass.
