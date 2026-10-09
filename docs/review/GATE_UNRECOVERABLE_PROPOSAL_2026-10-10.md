# Gate line proposal: 15 JS-service rows are `UNRECOVERABLE`, not `VERIFIED`

> A **proposal**, not an edit. The rows' RE state belongs to whoever owns them,
> and the Gate line is the number the project's honesty rests on, so this
> document exists to make the change reviewable rather than to make it.
>
> No row or tally was changed by this document.

## 1. Why the rows' current state does not describe them

`PLUGIN_LOADER_FOUND_2026-10-10.md` settles that `FUN_0045d6a9` builds
`<config>/Services`, bails when it is absent, loads `Common.js` first, then
enumerates subdirectories and loads each `<name>/Service.js` — and
`FUN_0045d160` registers it through `services::Script::vftable`. The service
plugins are therefore **files on disk**, not bytes in `QTranslate.6.10.0.exe`.

The checklist's own state definitions (lines 15-20):

| State | Meaning | Counts for Gate? |
|---|---|---|
| `VERIFIED` | Proven by a concrete artifact: Ghidra address **+** decompile, **JS source**, asset bytes, or a behavioral test | yes |
| `INFERRED` | Reasoned from a pointer, not directly proven | **no → blocks** |
| `UNRECOVERABLE` | The native artifact genuinely cannot be obtained. **Reason and impact required** | **yes, with reason+impact** |

A `Service.js` row can no longer claim `VERIFIED` on the *endpoint shape*: the JS
source is not in this artifact, its asset bytes are not in this artifact, and a
live probe never tested the native client's shape. That is the `INFERRED`
meaning. But `INFERRED` is the wrong label for a *structural* impossibility,
and — see §2 — it is the more damaging one.

## 2. Why `INFERRED` is the worse of the two accurate labels

This is the part worth stating explicitly, because the intuitive reading is the
opposite. Per line 5-6 and line 20:

> `UNRECOVERABLE` **counts toward** the Gate. `INFERRED` and `UNKNOWN` **block**
> the Gate, and waivers exist only for `INFERRED`/`UNKNOWN` rows.

So reclassifying `VERIFIED → INFERRED` would take 15 currently Gate-counting
rows and make them Gate-**blocking**, requiring 15 human waivers to clear. The
accurate structural claim is `VERIFIED → UNRECOVERABLE`, which keeps them
Gate-counting *and* says plainly that no in-repo work can verify them.

`INFERRED` says "we did not check." `UNRECOVERABLE` says "this artifact cannot
check it." The second is both true and cheaper, which is an unusual alignment.

I got this backwards in a message to qtranslate-ed before reading the rule, and
am recording the error here rather than only in the correction: I claimed
`UNRECOVERABLE` rows "may not be waivable at all" and therefore "cannot be made
Gate-clean." The rule states the reverse — waiving a `VERIFIED`/`UNRECOVERABLE`
row is an *error*, because those rows already count. The failure mode was
asserting a rule from the phrase "valid only on `INFERRED`/`UNKNOWN`" without
checking which side of the Gate each state sits on.

## 3. The rows, and the exact reason/impact each needs

Affected (endpoint shape not in the artifact): **E1, E4, E6, E9, E10, E11, E12,
E13, E14, E15, E16, E17, E18, E19, E20**, plus the E22 dictionary block that
cites `Services/Microsoft Translator/Service.js`. E3 is **mixed** — its
translate host is compiled in, its dictionary block is a service file.

Not affected: E2/E3/E5/E7 (compiled-in host strings), and every C/D/F/G/I/J row
citing a `FUN_` address.

Reason (identical for all, from the loader):

> `Services/*/Service.js` is loaded at runtime from the app's own directory by
> `FUN_0045d6a9`, so no service endpoint exists in
> `docs/review/artifacts/QTranslate.6.10.0.exe` to verify against.

Impact (differs per row, so it must be written per row, not once):

> the endpoint and parameter *shape* of this service is unverifiable from the
> recovered artifact; the *behaviour* remains live-tested and is recorded in the
> Port column.

## 4. What I would put in the Gate line

Current:

```
**Gate status: BLOCKED** — 1 rows still `INFERRED`/`UNKNOWN` without a valid waiver.
```

Proposed — the unresolved count is unchanged, and the second clause is additive
rather than replaced:

```
**Gate status: BLOCKED** — 1 row still `INFERRED`/`UNKNOWN` without a valid waiver
(G9). Separately, 16 E-group rows are `UNRECOVERABLE` from the recovered artifact
with reason+impact recorded: their `Services/*/Service.js` plugins are
runtime-loaded files (`PLUGIN_LOADER_FOUND_2026-10-10.md`), so no service endpoint
exists in the binary. These count toward the Gate per line 20 — they are not
waivable, and no in-repo work can verify them. Reading the tally as "151 verified
native behaviours" without this clause overstates it.
```

The last sentence is the reason to write the clause at all: the tally is a
*derived* number (`tools/coverage_tally.py`, `--selftest` passing), and a derived
number cannot carry a caveat about what it is derived *from*.

## 5. What I could not settle

- **Whether a row owner would read `UNRECOVERABLE` as a downgrade** where it is
  in fact the accurate label. That is a judgement about the artifact's readers,
  not about the binary, and it is the only reason I framed this as a proposal.
- **Whether `E1 Common.js` should be treated as recoverable.** The string
  `Common.js` is in the image and the framework is loaded by the same loader, so
  the loader's *protocol* is readable — but `Common.js`'s source is a file, same
  as `Service.js`. E1's row text cites the file, so it has the same problem;
  the row's "ported 1:1 → `common.py`" claim is a port claim and unaffected.
- **Whether the 16 should be listed individually** in the Gate line or referred
  to by count with the reason given once. I proposed the latter; a reader
  auditing one row will still find the reason on the row.
