# Tally audit — the checklist's declared count is exact, measured two ways

> Read-only. Re-derives every count in `RE_COVERAGE_CHECKLIST.md`'s tally
> block from the table itself, after a counting error of my own made
> verifying the number non-optional.
>
> No row state changed. This is the check that the Gate line's denominator is
> the real denominator.

## Why this exists

Counting is where this session has been failing. I counted the E rows, got
18, asserted a paragraph about which ids "do not exist," and was wrong — the
real number was 20. So the obvious next question is whether **the tally block
itself** is right, and I measured it rather than assuming.

## Method, and the two parse traps that produce wrong answers here

A row is `| ... |` with ≥4 cells after masking `\|` — the checklist escapes
literal pipes inside cells as `caps TRANSLATE\|DETECT`. Splitting on `|` before
masking it shifts every cell after an escape and silently mislabels rows.

Both traps, with the row that triggers each:

| Trap | Wrong result | Row that triggers it |
|---|---|---|
| splitting on raw `\|` | reads the state cell as `DETECT`; drops `E4`, `E6` from a "cites Service.js" count | `E4` (line 385), `E6` (line 387) |
| `^([A-R])(\d+)\b` | misses `I4a`–`I4d`; group I reads **5 instead of 9** | `I4a`–`I4d` (lines 573–576) |

The second one is worth the table: it cost me 4 rows in group I and made the
declared tally look wrong when it was **exactly right**. The fix is
`^([A-R])(\d+[a-z]?)\b`.

## Result — the declared tally holds

**RE-state column**, parsed across all rows:

| State | Declared | Measured |
|---|---|---|
| `VERIFIED` | 151 | **151** |
| `INFERRED` | 0 | **0** |
| `UNKNOWN` | 1 | **1** |
| `UNRECOVERABLE` | 0 | **0** |
| **total** | **152** | **152** |

**Per-group counts** — every one matches, with no exceptions:

```
A9 B6 C10 D11 E22 F13 G9 H8 I9 J7 K4 L4 M23 N4 O4 P3 Q3 R3
```

The one `UNKNOWN` row is **G9** (line 481), split into (a) recovered native
window spec and (b) the runtime screenshot comparison that needs a Windows
host for the native side and a Screen Recording grant for the port side. Both
re-measured twice in `docs/review/g9_evidence/README.md` and both unchanged.
It is the only unresolved row, so the Gate stays `BLOCKED (1)`.

## The one row that needs the Gate line rewritten is not a counting error

This audit confirms the *count* is right, which sets up the separate finding
in `E_ROW_AFFECTED_COUNT_2026-10-10.md`: **20 of the 151 `VERIFIED` rows cite
an artifact this artifact cannot contain.** That is not a tally defect — every
one of those rows is present, counted, and labelled `VERIFIED`, exactly as the
table says. The claim is that the label is wrong for those 20, and the
destination is `VERIFIED → UNRECOVERABLE` with reason + impact, which keeps
them Gate-counting rather than Gate-blocking (rule text: lines 5–6 say
`INFERRED`/`UNKNOWN` block; line 59 says a waiver is only valid on those).

Two ways the Gate line can be written, and the difference matters:

- **Recount only** — "`BLOCKED (1)`" stays, with 20 rows quietly relabelled.
  The Gate looks unchanged and the reason those rows moved is invisible.
- **Structural** — "`BLOCKED (1)` — one runtime blocker, plus 20 rows whose
  native artifact is a runtime-loaded `Service.js` absent from
  `QTranslate.6.10.0.exe`." The Gate is blocked on one thing that needs a host
  and on 20 that no in-repo work can change.

The second is the honest line and it is the row owner's to write.

## Reproduce

```python
import re
raw = open("docs/RE_COVERAGE_CHECKLIST.md", encoding="utf-8").read().split("\n")
rows = []
for l in raw:
    if not l.startswith("|"):
        continue
    cells = [c.strip() for c in l.strip().strip("|").replace("\\|", "@P@").split("|")]
    if len(cells) < 4 or set(cells[0]) <= set("-: "):
        continue
    m = re.match(r"^([A-R])(\d+[a-z]?)\b", cells[0])   # the [a-z]? is required
    if m:
        rows.append((m.group(1), cells[2]))
assert len(rows) == 152
assert sum(1 for _, s in rows if s == "VERIFIED") == 151
assert sum(1 for _, s in rows if s == "UNKNOWN") == 1
```

Drop the `[a-z]?` and the assertion on 152 fails at 148 — which is what mine
did, and which read as "the tally is wrong" until I looked at the four rows
the regex was skipping.
