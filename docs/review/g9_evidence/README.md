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
