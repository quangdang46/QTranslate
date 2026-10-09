# G9 evidence (native vs port screenshots)

This directory holds the **real** captures for a G9 comparison. It is currently
**empty / BLOCKED**: no native-vs-port capture pair has been produced yet, so
no G9 acceptance result exists.

Do not place synthetic fixtures here — those live in `docs/review/g9_samples/`
and are mechanics-only. Everything written here must come from `capture` on a
genuine native window and a genuine port window under identical protocol (see
`docs/review/G9_HARNESS.md` §4).

Expected layout after a real run:

```
docs/review/g9_evidence/
  native.png   native.json
  port.png     port.json
  out/         report.json  report.md  diff.png  native.png  port.png
```

Status: **BLOCKED — awaiting a runnable native + port capture pair.**
Non-synthetic PASS/FAIL may only be recorded once such a pair exists.

## Attempt 2026-10-09 — BLOCKED (both sides, different reasons)

Recorded in full in `docs/review/G9_RESULT_2026-10-09.md`. Two independent
blocks, neither invented around:

- **Native:** `QTranslate.6.10.0.exe` is `IMAGE_FILE_MACHINE_I386` (32-bit
  x86, GUI subsystem). This host is `arm64` Darwin 25.4.0 with no `wine` /
  `wine64`. It cannot execute here at all.
- **Port:** tkinter constructs fine, but Screen Recording is not granted —
  `screencapture` and PIL's `ImageGrab` both fail with
  `could not create image from display` / `…from rect` (exit 1, no file).
  That is a human permission grant away, not a code defect.

**No proxy baseline was created and this directory received no files.**

## Attempt 2026-10-10 — BLOCKED again (both sides re-checked, unchanged)

Re-verified rather than assumed, because G9 is the last open row and a
block that has "probably" changed is exactly the kind worth re-testing:

- **Native:** still `PE32 executable (GUI) Intel 80386`, and still no
  `wine`/`wine64` on `PATH`. Unchanged — the binary cannot execute on
  `arm64` Darwin 25.4.0.
- **Port:** the display itself is *reachable* — under Python 3.11 (which has
  `_tkinter`; the Homebrew 3.14 build does not) `Tk()` succeeds and reports
  `2560x1440`. So the port can render. Capture still cannot: `screencapture -x`
  exits 1 with `could not create image from display` and produces no file.
  Same human permission grant as 2026-10-09.

The distinction matters for how this row reads: the port-side block is not
"no GUI" but "GUI renders, capture is denied". Nothing about that is a code
defect, and it does not become evidence of anything by being retried.

**This directory still received no files.** The G9 row stays `UNKNOWN` and
the Gate stays `BLOCKED (1)`.
