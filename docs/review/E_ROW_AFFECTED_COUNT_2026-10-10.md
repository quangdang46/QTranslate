# The affected-row count is 20, not 15 — and E2/E3/E5/E7 are among them

> Read-only. Counts precisely which rows
> `PLUGIN_LOADER_FOUND_2026-10-10.md` rules out, and disagrees with that
> document's §4 on two specific rows. No row state changed; the checklist has
> a single writer and this is the measurement that writer needs.
>
> **Self-corrected: the first version of this document said 18.** The count
> was produced by a table parse that dropped two rows, and the error is in
> §1a below because the reason is worth having. 20 is the measured number.

## 1. The count

Extracted every `E` row that cites `Services/<Name>/Service.js` as its
native artifact. **Note when parsing: two rows (`E4`, `E6`) contain an
escaped pipe `\|` inside their artifact cell** — a `split('|')` that does not
first mask `\|` shifts their cells and silently drops or mislabels them.

**20 rows, all `VERIFIED`:**

```
E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, E13,
E14, E15, E16, E17, E18, E19, E20, E22
```

Only two E rows escape the count: **E1** (cites `Services/Common.js`, the
framework the loader provably loads first) and **E21** (cites
`FUN_0040FB54` + `FUN_0040FEC9`, decompiled against the recovered image).

The peer's loader document says **15**, and names them as "E1 (framework),
E4, E6, E9–E20 — and the E rows that cite `Services/Microsoft
Translator/Service.js` for the `/tlookupv3` block (E22)". Three problems with
that list, all checkable in one pass:

- **It is 16 items if you count its own enumeration**, not 15: E1, E4, E6,
  E9, E10, E11, E12, E13, E14, E15, E16, E17, E18, E19, E20, E22.
- **E1 does not belong in the set.** It cites `Common.js`, which the loader
  reads *before* the subdirectory loop — its artifact is the framework, and
  `FUN_0045d6a9` is the address-backed evidence for E1's own claim. Counting
  E1 as affected is the opposite of what the loader shows.
- **It excludes E2/E3/E5/E7**, on the grounds that those rows' endpoints are
  "compiled in."

E4 and E6, which it *does* have, are confirmed affected and their literals are
entirely absent from the image in either encoding:
`www2.deepl.com/jsonrpc`, `LMT_handle_jobs`, `papago.naver.com`,
`/apis/nsmt`, `buildAuthData`, `v1.6.5_956d74858f` — all ABSENT.

## 1a. The parse error in the first version, recorded

My first extraction used `^\| (E\d+...)` against raw lines and found 18, on
which basis I wrote that "E4 and E6 do not exist in the checklist." **They
exist, at lines 385 and 387, both `VERIFIED`.** The rows' artifact cells
contain `caps TRANSLATE\|DETECT` with a literal backslash-escape, so the
naive split read the state as `DETECT` and the count came out two short.

The tell was available in the same output: the parse also reported
"VERIFIED rows citing Service.js: 20" from a second, looser regex. Two
parsers, two numbers, one artifact — and I acted on the one that agreed with
the number I had just committed. The same selective-agreement failure the
session has been recording, in a new costume: **when two measurements
disagree, the disagreement is the finding, not a nuisance to resolve by
preferring the one you like.**

The corrected parse masks `\|` before splitting, and the counts now agree
across both methods: 20.

## 2. The exemption is wrong, and it is the part that matters

The loader document §4 states:

> What is **not** affected is E2/E3/E5/E7, whose endpoints are compiled in
> (`translate.google.`, `bing.com/*`, `translate.yandex.com`,
> `fanyi.baidu.com`).

That conflates the **host** with the **endpoint**. The four rows do not cite
hosts; they cite paths:

| Row | Cites | Present in image? |
|---|---|---|
| E2 | `Services/Google Translate/Service.js`: `/translate_a/single` | `translate.google.` **yes**; `/translate_a/single` **ABSENT** |
| E3 | `Services/Microsoft Translator/Service.js`: `bing.com/ttranslatev3` | **`0x1298a0`** |
| E5 | `Services/Yandex/Service.js`: `/api/v1/tr.json/translate`, `tts.voicetech.yandex.net` | `translate.yandex.com` **yes**; both paths **ABSENT** |
| E7 | `Services/Baidu/Service.js`: `/v2transapi`, `tts.baidu.com` | `fanyi.baidu.com` **yes**; both paths **ABSENT** |

So of the four "not affected" rows, **three have no endpoint literal in the
artifact at all**, and the fourth (E3) has exactly one. This is not a
disagreement about judgement; it is the host-vs-path rule from
`E_ROW_ENDPOINT_VERIFIABILITY_2026-10-10.md` §3, which the loader document's
§4 applies inconsistently by calling a host string an endpoint.

## 3. But the loader makes the distinction moot, which is the real conclusion

`FUN_0045d6a9` reads `Services/<Name>/Service.js` **from disk at runtime**,
compiles it, and calls `serviceHeader` into it. Every one of the 20 rows
asserts a URL shape, a parameter order, or a caps mask *for code that ships
in that file*. The file is not in `QTranslate.6.10.0.exe` and, by the loader's
own mechanism, **cannot be**.

So the per-row literal question I measured in
`E_ROW_ENDPOINT_VERIFIABILITY` is **subsumed**: whether the path happens to
be present in the image decides nothing, because presence in the image does
not mean the row's native client used it. E3's `bing.com/ttranslatev3` being
present at `0x1298a0` is a *native compiled client* — and E3 is also
`Services/Microsoft Translator/Service.js`, i.e. the row is claiming a
runtime-loaded plugin produced that request. Those two facts can only
coexist if the row conflates the compiled client with the plugin, which is
the exact thing §6 of my earlier document flagged as unproven.

**The honest state for all 20 is the same**, regardless of which hosts happen
to be in the binary: their cited artifact is a file the artifact cannot
contain.

## 4. What this changes

The number the Gate line needs is **20**, not 15, and the composition is
different from the peer's list. Specifically:

- The peer's list includes rows **that do not exist** (E4, E6) and excludes
  **four that do** (E2, E3, E5, E7).
- E2 is the row the whole port is built on. Its URL shape has never been
  image-verifiable, and the exemption asserted it was among the four that
  were safe. **That is the row where an incorrect "not affected" costs the
  most**, because it is the one every other E row was reasoned from.
- E22 (Bing `tlookupv3`) is affected and is in both lists, so that part is
  agreed.

**Direction of the reclassification**, settled from the checklist's own rule
text at lines 5–6 and 59: every in-scope row must be `VERIFIED`, or
`UNRECOVERABLE` **with reason + impact**. `INFERRED` and `UNKNOWN` block the
Gate, and a waiver is only valid on an `INFERRED`/`UNKNOWN` row. So moving
these rows `VERIFIED → INFERRED` would **block the Gate**, and the honest
destination is `VERIFIED → UNRECOVERABLE`, which keeps them Gate-counting.

The peer reached the same conclusion after reading the rule and reported that
they had initially had it inverted. Their correction is right; the count in
this document is the input it needs.

## 5. What this does not do

- Does not reclassify anything. Not my file, not my call.
- Does not claim these 20 rows are wrong. The peers measured the endpoints
  live and they respond correctly. The claim is narrow: **the row's stated
  native artifact is not obtainable from this artifact**, so the row's RE
  axis cannot be `VERIFIED` and its behaviour axis stands on live evidence.
- Does not extend to E21, which cites `FUN_0040FB54` + `FUN_0040FEC9` and is
  address-backed and decompile-verified against the recovered image. It is
  the one E row whose artifact *is* in the binary.
- Does not touch the C/D/F/G/H/I/J/K/L/M/N/O/P/Q/R groups.

## 6. Reproduce

```python
import re
txt = open("docs/RE_COVERAGE_CHECKLIST.md", encoding="utf-8").read()
rows = re.findall(r'^\| (E\d+[^|]*) \| ([^|]*) \| (\w+) \|', txt, re.M)
affected = [n.strip() for n, art, st in rows if "Service.js" in art]
print(len(affected), affected)

blob = open("docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()
for needle in ("/translate_a/single", "/api/v1/tr.json/translate",
               "/v2transapi", "bing.com/ttranslatev3", "/tlookupv3"):
    print(needle, "PRESENT@" + hex(blob.find(needle.encode("utf-16-le")))
          if blob.find(needle.encode("utf-16-le")) >= 0 else "ABSENT")
```
