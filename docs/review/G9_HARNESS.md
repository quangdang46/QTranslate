# G9 Runtime Screenshot-Diff Harness

> **Scope:** test-only tooling authorized *separately* from the Gate. Building or
> running this harness **does not open the Gate**, does **not** resolve G9, and
> does **not** start Phase C. It exists to *measure* G9 visual fidelity, not to
> perform reverse engineering.
>
> **G9 gate remains `BLOCKED`** until genuine native-versus-port screenshots are
> captured and their comparison is independently reviewed and accepted.

## 1. What this is (and is not)

- **Is:** a reproducible harness that compares a *native* QTranslate 6.10.0
  screenshot against a *port* screenshot and emits a diff image + a
  machine-readable report, under documented tolerances.
- **Is not:** RE evidence, a Gate decision, an acceptance result by itself, or
  permission to change runtime code.
- **Never:** fabricates a baseline or reports `PASS` without an actual
  pixel comparison of two decoded images.

The single source of truth for RE coverage stays `RE_COVERAGE_CHECKLIST.md`.
This harness only produces the *runtime measurement* that G9 is currently
`UNKNOWN` for.

## 2. Files

| Path | Role |
|------|------|
| `tools/g9_screenshot_diff.py` | The harness (stdlib-only; no new dependencies). |
| `docs/review/G9_HARNESS.md` | This document — protocol, tolerances, semantics. |
| `docs/review/g9_samples/` | Synthetic fixture run: PASS/FAIL/BLOCKED reports + diff images. **Mechanics only.** |

No application runtime, schema, dependency, or production configuration is
touched. `docs/NATIVE_ARCH.md` is untouched.

## 3. Result semantics (exactly three outcomes)

| Result | Exit | Meaning |
|--------|------|---------|
| `PASS` | 0 | Both images decoded, geometry equal, protocol metadata (`ui_state`/`input`) equal, diff ratio ≤ tolerance. |
| `FAIL` | 1 | Evidence exists but comparison is negative: window geometries differ, **or** diff ratio > tolerance. |
| `BLOCKED` | 2 | Comparison could not run on usable evidence: a missing/unreadable input, an undecodable image, a failed capture, a protocol mismatch, wrong-side metadata, or **invalid provenance**. |

`BLOCKED` is a first-class outcome, not an error to work around. If the native
application cannot be run or captured, the harness reports `BLOCKED` with a
specific reason — it never substitutes a synthetic baseline.

Usage/mechanism errors (bad arguments, out-of-range tolerance) exit `3`.

### 3.1 Mechanics vs. acceptance evidence (provenance) — and its hard limit

Every capture carries a `capture_kind`:

- **`mechanics`** — fixtures used to test the harness. Result is tagged
  `evidence_kind: mechanics`, `g9_evidence: false`. **Never** G9 evidence.
- **`acceptance`** — the capturer *declares* this came from a real application
  run. If **both** sides are `acceptance`, pass every protocol check (§4), and
  the harness can verify:
  - `source` — non-empty, not an obviously synthetic string;
  - `sha256` — the 64-hex hash of the PNG, **re-computed from the file on disk**
    and compared to the value recorded in the metadata;

  the report is tagged `evidence_kind: acceptance-declared`,
  `g9_evidence: true`.

> **What this verification does NOT prove, and cannot prove:** `sha256`
> confirms only that the PNG bytes on disk are unchanged from whatever bytes
> were hashed when the metadata was written — it says nothing about *where
> those bytes came from*. `source` is a free-text claim with no independent
> check. **A self-built, entirely synthetic image can satisfy both checks** if
> whoever wrote the metadata computed a correct hash and wrote a
> plausible-looking `source` string — this harness has no way to detect that
> from inside itself (see `selftest` case 11, which demonstrates exactly this
> limitation and is itself labeled accordingly). Therefore
> `evidence_kind: acceptance-declared` / `g9_evidence: true` means **"file
> integrity and a declared source checked out, and all protocol checks agree"
> — not "a human has confirmed this came from the real native app and the real
> port."** A human must still open `native.png`, `port.png`, and `diff.png`
> and confirm the capture circumstances before treating a result as the actual
> G9 acceptance evidence. The report's `evidence_note` says this explicitly.

Any protocol failure (dimensions / `ui_state` / `input` / geometry) is checked
**before** provenance is evaluated, and `blocked()` always force-sets
`g9_evidence: false`. So **a `BLOCKED` report can never claim
`g9_evidence: true`.**

### 3.2 `g9_evidence` across outcomes (`BLOCKED` vs `FAIL`)

`g9_evidence` starts `False` and is only set `True` once dimensions,
`ui_state`, `input`, and geometry have all agreed **and** provenance has been
verified. Concretely:

| Outcome | `g9_evidence` | Why |
|---------|---------------|-----|
| `PASS` (equivalent, within tolerance) | `true` | verified eligibility, subject to human review (§3.1) |
| `FAIL` (diff ratio > tolerance) | `true` | captures *were* equivalent and provenance verified — a below-fidelity result is itself valid evidence a human should review |
| `FAIL` (geometry mismatch) | `false` | protocol not equivalent — this check runs before provenance |
| `BLOCKED` (any reason) | `false` | never eligible; `blocked()` force-sets it |

So `g9_evidence: true` means "eligible for human review", **not** "passed".
A `FAIL` with `g9_evidence: true` is a perfectly valid finding: it says the
two captures were taken under equivalent conditions with verified file
integrity, and the port's fidelity fell short. Only `BLOCKED` is excluded.
`selftest` case 14 captures the `BLOCKED` case directly: valid hashes/source but
a `ui_state` mismatch still yields `BLOCKED` + `g9_evidence: false`, never a
stale `True` left over from a provenance check that ran out of order.

## 4. Capture protocol

For a comparison to be *valid* both captures must be equivalent. The metadata
sidecar (`.json`) records this; `compare` **refuses** (`BLOCKED`) when they
disagree.

Required metadata fields per capture:

| Field | Meaning |
|-------|---------|
| `app` | `native` or `port` — **must be on the correct side** (checked: wrong side ⇒ `BLOCKED`) |
| `window_title` | The window captured |
| `width`, `height` | Pixel dimensions — must match the decoded image |
| `ui_state` | e.g. `main`, `popup`, `options`, `history` — **must match across sides** |
| `input` | The exact test input used — **must match across sides** |
| `capture_kind` | `mechanics` or `acceptance` (§3.1) |
| `source` | Provenance string (non-empty) |
| `sha256` | PNG content hash — **required** for `acceptance`, re-verified at compare |

Protocol rules:

1. **Same window size** — the two windows must be the same pixel dimensions.
   A mismatch is reported as `FAIL` (a real negative), with the pixel diff
   skipped; both originals are still saved.
2. **Same UI state** — same screen/mode (e.g. both on the main window, popup
   hidden/visible identically).
3. **Same input** — identical text/clipboard/hotkey context so content matches.
4. **Same DPI awareness** — capture the native window with the process DPI-aware
   so pixel sizes are physical, not scaled.

### 4.1 Capturing the native app (Windows)

```
python -I tools/g9_screenshot_diff.py capture \
    --app native --title "QTranslate" \
    --ui-state main --input "hello world" \
    --capture-kind acceptance --source "QTranslate.exe 6.10.0, Win11 26200" \
    --out docs/review/g9_evidence/native.png
```

Uses `PrintWindow` (PW_RENDERFULLCONTENT). Its `BOOL` return is checked: if it
returns 0, or if the bitmap is all-black (window refuses full-content render),
the tool reports `BLOCKED` — it never saves a black image. `--capture-kind
acceptance` requires `--source` and stamps the PNG's `sha256` into the sidecar.

### 4.2 Capturing the port

Same command with `--app port` and the port's window title. The port must be
brought to the identical `ui_state` and given the identical `input` first.
Record the same `--input` string on both sides.

> If there is **no runnable native environment** on this machine, stop here and
> report `BLOCKED` in the completion report. Do not create proxy baselines.

## 5. Comparing

```
python -I tools/g9_screenshot_diff.py compare \
    --native      docs/review/g9_evidence/native.png \
    --port        docs/review/g9_evidence/port.png \
    --native-meta docs/review/g9_evidence/native.json \
    --port-meta   docs/review/g9_evidence/port.json \
    --channel-tolerance 8 --max-diff-ratio 0.01 \
    --out docs/review/g9_evidence/out
```

Outputs into `--out`:

- `native.png`, `port.png` — preserved originals (evidence).
- `diff.png` — differing pixels marked red on the native image.
- `report.json` — machine-readable report.
- `report.md` — human-readable report.

### 5.1 Tolerance (configurable, documented)

| Flag | Default | Meaning |
|------|---------|---------|
| `--channel-tolerance` | `4` | Per-channel absolute delta (0..255) considered "different". Anti-aliasing/font hinting usually needs 4–8. |
| `--max-diff-ratio` | `0.005` | Max fraction of pixels that may differ for `PASS`. |

A pixel counts as differing when **any** channel delta exceeds
`--channel-tolerance`. `--channel-tolerance` is validated to `0..255` and
`--max-diff-ratio` to `0.0..1.0`; out-of-range values are a usage error (exit 3),
never a `PASS`. The comparison uses the *native* image as the base for the diff
image. Alpha is dropped (screenshots are treated as opaque RGB) — a documented
approximation.

> **What `PASS` means.** `PASS` is a *quantitative threshold result* under the
> configured tolerance — it does **not** by itself mean the UI is functionally
> equivalent. Two images can pass while a small button or region still differs
> materially. Always review the `diff.png` and the important UI regions before
> treating a `PASS` as fidelity. The default `0.5%` / channel `4` values are a
> *starting configuration*, not a validated fidelity threshold.

## 6. Self-test vs. G9 acceptance — the critical distinction

- **Harness self-test** (`selftest`, `make-sample`): fixtures that verify the
  *mechanics* — identical→PASS, within-tolerance→PASS, beyond→FAIL, missing
  input→BLOCKED, protocol mismatch→BLOCKED, geometry mismatch→FAIL,
  wrong-side metadata→BLOCKED, out-of-range tolerance→usage error,
  acceptance-declared→PASS+G9-eligible, acceptance hash mismatch→BLOCKED,
  corrupt PNG→BLOCKED, protocol mismatch with valid hash→BLOCKED+`g9_evidence`
  false, diff-ratio FAIL→`g9_evidence` true. Every such report is tagged
  **`evidence_kind: mechanics`** /
  `g9_evidence: false` and carries a banner. **These are NOT native-versus-port
  fidelity evidence and must never be cited as a G9 result.**
- **G9 acceptance result**: a `compare` run over `capture` output where **both**
  sides are `capture_kind: acceptance`, pass every protocol check, and pass the
  file-integrity + declared-source check (`evidence_kind: acceptance-declared`,
  `g9_evidence: true`). As explained in §3.1, this is **not itself** proof the
  images are real — it is the point at which a **human reviewer** takes over:
  only after that reviewer opens `native.png`/`port.png`/`diff.png`, confirms
  they recognize the actual native app and port UI, and accepts the capture
  circumstances, does the result become an actual G9 acceptance finding.

## 7. Reproduce the sample

```
python -I tools/g9_screenshot_diff.py selftest
python -I tools/g9_screenshot_diff.py make-sample --out docs/review/g9_samples
```

Expected: `selftest` → `PASS (15/15)` exit 0; `make-sample` prints
`PASS=0 FAIL=1 BLOCKED=2 (ok)` and writes the three reports under
`docs/review/g9_samples/`.

## 8. Closing condition for this step

The harness step is complete when the harness is reviewed and its **mechanics**
self-tests pass. G9 itself is **not** concluded until real captures from **both**
native and port exist and their comparison can be independently re-checked.
Until then G9 stays `UNKNOWN` and the Gate stays `BLOCKED`.
