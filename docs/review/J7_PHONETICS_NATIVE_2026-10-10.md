# J7 read-phonetically — native behavior recovered from the binary

> Read-only RE note. Companion to `G9_RESULT_2026-10-09.md`,
> `ARTIFACT_RECOVERY_2026-10-10.md` and `G9_SPEC_NATIVE_WINDOW_2026-10-10.md`.
> This settles J7 on the **RE axis** and records the port implementation
> against it.
>
> Nothing here edits `RE_COVERAGE_CHECKLIST.md` (single-writer: **qtranslate-8e**).
> §6 records that `common.py` is shared, Phase 5 scope.
>
> **§4 carries a correction to its own first draft** — the surprising part of
> this file is that the port already had the data and was throwing it away.

## 1. The consumer, decompiled

`FUN_0042ed3f` — 348 bytes, resolves by name in `QT_REAL.rep`:

```c
uVar1 = FUN_00403897();                       // gate 1
if ((char)uVar1 == '\0') {
    FUN_00408924(param_1 + 3, param_1[4]);    // set the primary result (entry[3])
    uVar1 = FUN_00403897();
    if ((((char)uVar1 == '\0') && (*(int *)(param_1[5] + -0xc) != 0))
        && (DAT_00549414 != '\0')) {
        FUN_00401f21((uint *)&DAT_0052284c);          // separator
        FUN_004089fe((int *)&param_2, 0);
        piVar2 = (int *)FUN_00451d23(&param_2, 0xba); // string resource 186
        FUN_004089fe(piVar2, bVar5);
        FUN_004033d1();
        FUN_00408924(param_1 + 5, 0);                 // append entry[5]
    }
}
```

## 2. The three gates, each verified

| Gate | Code | Verified how |
|------|------|--------------|
| 1 | `FUN_00403897() == 0` | decompiled: 20 bytes, `CString::Find(L"<Error>")`, returns `1 - (found != 0)`. So the append needs **`<Error>` absent** from the result. |
| 2 | `*(int *)(param_1[5] + -0xc) != 0` | a `CString` length read — `entry[5]` (phonetics) non-empty. |
| 3 | `DAT_00549414 != 0` | the `General.ReadPhonetically` flag (per the checklist's own trace). |

**Gate 1's meaning is easy to get backwards, so recording it explicitly:** the
check is *not* "the result is empty". `<Error>` is a **marker the orchestrator
writes into the result when a provider fails**, so the condition means
**"the translation succeeded"**. Phonetics are an *annotation on a good result*,
not a substitute for a failed one.

Literals, read from the image by content search (not by address mapping, which
misleads — see `ARTIFACT_RECOVERY_2026-10-10.md` §4). These are **file offsets
into the recovered image**; §4c re-verifies all three against the bytes:

| Literal | Location | Role |
|---------|----------|------|
| `"\r\r"` | UTF-16LE `0x12184c` | separator before the phonetics |
| `<Error>` | UTF-16LE `0x121af0` | gate 1's marker, in `.rdata` next to `Service.ico` |
| `"Romanization: "` | UTF-16LE `0x158c00`, `.rsrc` STRINGTABLE block 12, id **186** | the fixed prefix |

## 3. Native's output, precisely

```
if entry[5] non-empty AND ReadPhonetically AND "<Error>" not in result:
    result += "\r\r" + "Romanization: " + entry[5]
```

Appended **after** the primary result is set at `entry[3]` — strictly an
addition, never a replacement.

## 4. The phonetics source — **corrected 2026-10-10**

> **This section supersedes its own first version.** The draft here said the
> port had "no phonetics channel at all" and that the feature was blocked on a
> response-model field before any append could be written. That was half
> right: the *channel* was indeed missing. The stronger claim ("no provider
> produces a phonetics field") was **false**, and the live endpoint disproves
> it. Recording the correction rather than deleting it, because the wrong
> version is the more plausible-sounding one.

**Google has produced a phonetics field all along.** `translate()`
(`qtranslate/services/google_translate.py:285-287`) requests
`&dt=bd&dt=t&dt=ld&dt=rm`, and `_translate_response` has read a 4th return
value from the response since the first 1:1 port (commit `3d9da8d`).
`translate()` then threw it away:

```python
b, _, _, _ = _translate_response(obj, sl, tl)   # the g was parsed, then dropped
```

So the "missing piece" was not a provider — it was **one unsubscribe**.

**And there was a second, real bug in reading it.** The parser took the
romanization from `e[2]`; the live payload carries it at `e[3]`:

```
GET /translate_a/single?client=gtx&sl=zh-CN&tl=en&dt=t&dt=rm&q=你好

[[["Hello",  "你好",      null, null,       10],
  [null,     null,       null, "Nǐ hǎo",  ]]     # <- the romanization
                       ^^ e[2] is null; e[3] holds it
```

Verified 2026-10-10 against the live endpoint for zh-CN/ko/ja/ru
(`Nǐ hǎo`, `annyeonghaseyo`, `Kon'nichiwa`, `Privet`), and isolated by `dt`:

| request | segments |
|---|---|
| `dt=t&dt=rm` | `["Hello","你好",null,null,10]` + `[null,null,null,"Nǐ hǎo"]` |
| `dt=rm` alone | exactly one: `[null,null,null,"Nǐ hǎo"]` |
| `dt=t` alone | `["Hello","你好",null,null,10]` only — no romanization |

So `dt=rm` alone reproduces the payload, `e[2]` is always `null` there, and
the fix is `g = e[3]`. Because `translate()` discarded `g`, the wrong slot
read cost nothing until the append was wired — which is exactly why it
survived. `tests/regress_google_romanization.py` now pins index 3 and
re-fetches the four languages under `--live`.

**The response-model gap is still real** — it just is not a blocker.
`ResponseData` (`qtranslate/common.py:62`) has five fields and none is
phonetics, and the `_t_*` adapters return a bare `str`, so the romanization
reaches the render path via module state
(`google_translate.set_romanization` / `get_romanization`) instead of a field.
That is a documented stopgap for what `ARCHITECTURE.md` §3.1's
`TranslationRequest`/`Result` value object exists to replace. It is recorded
here so the stopgap is not mistaken for the design.

## 4b. Per-provider: only Google fills it

`dt=rm` (romanization) is a Google-specific `dt` value. The other providers'
requests do not ask for one and their responses have nothing equivalent, so
they produce no phonetics — which matches native, whose `entry[5]` is likewise
filled by whichever `Services/*/Service.js` the active service runs. J7's
append therefore appears for Google translations and silently does not for
the rest, exactly as it does natively.

## 4c. The string id re-verified from the resource table, not just the call

The two of us cite `RT_STRING` id **186** (`0xBA`) for `"Romanization: "`,
each taking it from the decompiled call `FUN_00451d23(&s, 0xba)`. Reading that
off a decompile is not the same as confirming it in the resource table, so I
walked `RT_STRING` by hand — and it disagreed, giving id **202** (`0xCA`),
block 12 slot 10.

Resolved by decompiling the loader instead of counting bytes:

- `FUN_00451d23(param_1, param_2)` → `FUN_0045242d(param_2)` →
  `FUN_0040218a(param_2)` → `FUN_004027ef`, whose call is:

  ```c
  FindResourceW(hModule, (LPCWSTR)((param_2 >> 4) + 1), (LPCWSTR)6);
  ```

  `6` is `RT_STRING`; the resource name is `(id >> 4) + 1`, i.e. the
  STRINGTABLE block index of a 16-string block.

  The PE import table confirms this is the resource path and not something
  else: `FindResourceW` at `0x13ed64`, `LoadResource` at `0x13ed42`,
  `LockResource` at `0x13ed32`, `SizeofResource` at `0x13ed20`, and **no
  `LoadStringA`/`LoadStringW` at all** — the table is read by hand.

For id 186, block = `0xba >> 4` = 11, so nameId = 12. My walk had been
labelling each type-6 leaf's `nameId` as the block index directly, when a
leaf's nameId is `block + 1`. Reading leaf nameId 12 with that corrected base:

```
nameId 12 -> block 11 -> ids 176..191
  slot  9  id  185  'Update failed'
  slot 10  id  186  'Romanization: '     <-- what PUSH 0xba fetches
```

So the id in this document and in `phonetics.py` is right, and the
disagreement was my walker's off-by-one. Cross-checked against a second id
this repo already depends on: id **190**, which the same helper fetches for
the translate-failure message cited in `RELIABILITY_WIRING_AUDIT_2026-10-10.md`
§2, resolves under the same leaf to
`'No data returned (timeout while sending data).'` — the exact string 190.
Two independent ids agreeing is what settles the indexing.

**Re-confirmed independently 2026-10-10 by a third walker** (qtranslate-8e's,
`tools/rtstring_check.py` — kept so the table can be re-derived rather than
trusted). Two bugs had to be fixed to get it working, and both are worth
recording because each silently produced *plausible* output:

1. **Resource `OffsetToData` is an RVA, and `.rsrc` is loaded at RVA
   `0x14b000` from file `0x146000`** — so the conversion is
   `ROOT + (RVA - 0x14b000)`, not `ROOT + RVA` (which walks off the end of
   the file).
2. **Each `RT_STRING` leaf has exactly ONE sub-entry** — the unnamed
   `IMAGE_RESOURCE_DATA_ENTRY` for the whole 16-string block, not 16
   per-string entries. Walking it as 16 yielded 3 strings from ids 160..192
   and nothing at the ids of interest, i.e. a *quietly wrong* table.

The walker's output:

```
parsed ids 160..207 (48 strings)
  id 185  -> 'Update failed'
  id 186  -> 'Romanization: '
  id 190  -> 'No data returned (timeout while sending data).'
  id 202  -> 'Remove from favorites'
```

Id 186 and id 190 both resolve exactly, from three levels: the decompiled
`PUSH 0xba`, the corrected resource-table walk, and the port's own string 190.

The three literals are also **file offsets into the recovered image**, not
image VAs (my §2 table said "UTF-16LE 0x…" without saying which, which
invited the reading that they were VAs):

| Literal | File offset | First bytes |
|---------|-------------|-------------|
| `"\r\r"` | `0x12184c` | `0d 00 0d 00 00 00` |
| `<Error>` | `0x121af0` | `3c 00 45 00 72 00 72 00` |
| `"Romanization: "` | `0x158c00` | `52 00 6f 00 6d 00 61 00` |

The append target is pinned in the disassembly too — `ESI` is set to
`&entry[5]` by `ADD ESI,0x14` at `0x0042edf9`, and pushed as-is into the same
`FUN_004089fe` string-append used for the separator and the label:

```
0042ee58   PUSH EDI              ; EDI = 0
0042ee59   PUSH ESI              ; the phonetics itself
0042ee5c   CALL 0x004089fe       ; CString::operator+=
```

## 4d. What I could not confirm myself

Both of my live spot-checks of the `dt=rm` payload returned **HTTP 429**, so
the `e[3]` slot and the four-language evidence in §4 are **qtranslate-8e's**
measurements, not mine. The static half I did confirm directly against
`git show HEAD:qtranslate/services/google_translate.py`: `g = ""` (169),
`g = e[2] or ""` (177), `return b, sl, tl, g` (189), and the discarding
`b, _, _, _ = ...` (281). If the slot ever changes upstream, §4 needs are-fetch rather than an inference from this host.

## 5. The "no-op for TTS" docstring is a correct premise, wrong conclusion

`app.py:1244-1245` says:

```python
# ReadPhonetically (menu Id 1/50): kept as flag; Google
# TTS has no phonetic mode (documented, no-op for TTS).
```

The premise is right — Google TTS has no phonetic mode. The conclusion is not:
native's consumer is the **result pane**, not TTS. As written the comment
implies the port matches native, when in fact the saved flag is inert.

## 6. What this does and does not establish

- **Does:** the exact native behavior (gates, separator, prefix, append point),
  from a decompile plus three string reads on an artifact that is on disk.
- **Does:** establish that the port's phonetics source is Google's `dt=rm`,
  with the live payload shape measured and the parse-slot bug pinned.
- **Does:** record that the append is implemented as of 2026-10-10
  (`qtranslate/phonetics.py` + `app.py:do_translate`), so J7's port state is
  now `ported` — Python exists, behavior not proven equivalent.
- **Does not:** verify *which provider* fills native's `entry[5]``. The native
  reads it from the JS service's response handling, and no
  `Services/*/Service.js` source is present on this machine to check
  per-provider. §4b infers "Google only" from the `dt` values, which is a
  property of the **port's** requests, not a claim about native.
- **Does not:** include a live API check of the `dt=rm` payload shape. Both of
  my attempts returned **HTTP 429** (§4d), so §4's slot and four-language
  evidence is qtranslate-8e's, not mine. The half I did confirm directly is
  the pre-edit code path, against `git show HEAD:…google_translate.py`.
- **Does not:** prove equivalence on any platform. The suites pin the gates and
  the parse against recorded/live payloads; nothing here was compared against
  a running native binary (impossible on this host —
  `G9_RESULT_2026-10-09.md`).
- **Does not:** touch `common.py`. The romanization passes through module state
  as a stopgap; moving it onto `ResponseData` is Phase 5, and is the honest
  reason the current wiring is not a claim of 1:1 fidelity.

## 7. The whole consumer re-decompiled from the live image (2026-10-10, later)

Ghidra is running again on this host, so the consumer was re-decompiled
directly rather than read from the earlier session's notes. The full body,
with the J7 branch intact:

```c
void FUN_0042ed3f(int *param_1, int *param_2)
{
  DAT_0054916c = DAT_0054916c + 1;
  FUN_0042efda((int)param_1);
  FUN_00408b83();
  FUN_00408b83();
  if ((param_1 == (int *)0x0) || (*param_1 == 0)) {
    FUN_00408b83();
    SetFocus(*(HWND *)(in_ECX + 0x9c));
    uVar4 = FUN_0042e991();
    FUN_00433a4b((int)uVar4, (int)((ulonglong)uVar4 >> 0x20), (int *)(in_ECX + 100));
  }
  else {
    if ((char)param_2 != '\0') {
      FUN_00408924(param_1 + 1, param_1[2]);        // <-- slots 1/2
    }
    uVar1 = FUN_00403897();
    if ((char)uVar1 == '\0') {
      FUN_00408924(param_1 + 3, param_1[4]);        // the primary result
      uVar1 = FUN_00403897();
      if ((((char)uVar1 == '\0') && (*(int *)(param_1[5] + -0xc) != 0))
          && (DAT_00549414 != '\0')) {
        FUN_00401f21((uint *)&DAT_0052284c);
        FUN_004089fe((int *)&param_2, 0);
        FUN_004033d1();
        piVar2 = (int *)FUN_00451d23(&param_2, 0xba);
        FUN_004089fe(piVar2, bVar5);
        FUN_004033d1();
        FUN_004089fe(param_1 + 5, 0);
      }
    }
    else { /* the <Error> path: rebuild and re-set entry[3] */ }
  }
  DAT_0054916c = DAT_0054916c + -1;
}
```

Every claim this doc made about J7 survives: gate 1 (`FUN_00403897`),
gate 2 (`param_1[5] + -0xc` length), gate 3 (`DAT_00549414`), the
separator (`DAT_0052284c`), the `0xba` resource fetch, and the append of
`param_1 + 5`.

**Two things this adds that nobody had:**

1. **`FUN_00403897` is verbatim what the row says**, decompiled standalone:
   ```c
   uVar1 = FUN_00401fc2((ushort *)L"<Error>");
   return CONCAT31((int3)(-uVar1 >> 8), '\x01' - (uVar1 != 0));
   ```
   So gate 1 is `<Error>` absent, confirmed from the function itself rather
   than from the return convention at the call site.
2. **The slots-1/2 call is gated on `(char)param_2 != '\0'`** — a flag in
   *param_2*, the same struct that later receives the appended string. So
   `FUN_00408924(entry[1], entry[2])` is **conditional display state**, set
   only when that flag is set, and it runs *before* the result is written.
   That is a stronger statement than "formatter state" and it is the last word
   on `CORE_RESULT_SHAPE`'s question: slots 1/2 are not a language pair, and
   the flag gating them is the reason — it is a "did the caller supply
   formatting?" switch, not a payload.

**`FUN_00408924` itself is not a language setter** (retraction confirmed by
reading it): `iVar4 = 1; if (param_2 - 2U < 0x4a) iVar4 = param_2;` is a
clamp, `*(int *)(in_ECX + 0x28) = iVar4` stores it at a fixed field, and the
rest walks a COM vtable (`+0x20`, `+0x48`, `+0x54`, `+8`) on an object from
`FUN_004088a9`, with an `Ordinal_6()` call. The `{5, 0x1a, 0x2a, 0x38, 0x3b}`
special-case that made the first reading look settled is **part coincidence,
which is worse than none**: 5 and 26 are both real `config.py` service ids
(`microsoft`, `youdao`), while 42, 56 and 59 are not service ids at all. Two
hits out of five is exactly the pattern that should prompt suspicion instead
of satisfaction, and did not at the time.
