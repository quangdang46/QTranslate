# G9 screenshot-diff report

- tool: `g9_screenshot_diff` v1
- timestamp: 2026-10-09T14:54:34
- **result: `PASS`** — diff_ratio 0.000000 <= 0.005 (tol 4/channel)
- evidence kind: **mechanics**
- eligible as G9 acceptance evidence: **False**

> mechanics capture(s) present — mechanics result, NOT G9 acceptance evidence

> **PASS caveat:** PASS is a quantitative threshold result under the configured tolerance. It does NOT by itself mean the UI is functionally equivalent: two images can pass while a small button or region still differs. Review the diff image and key UI regions.

> ⚠️ MECHANICS capture — this exercises the harness mechanics only.
> It is **NOT** native-versus-port fidelity evidence and must not be
> cited as a G9 result.

## Tolerance
- per-channel absolute tolerance: 4
- max diff ratio allowed: 0.005

## native
- path: `docs\review\g9_samples\pass_native.png`
- meta: `{"app": "native", "window_title": "native-synth", "width": 64, "height": 48, "ui_state": "main", "input": "none", "capture_kind": "mechanics", "source": "synthetic fixture (harness mechanics only)"}`

## port
- path: `docs\review\g9_samples\pass_port.png`
- meta: `{"app": "port", "window_title": "port-synth", "width": 64, "height": 48, "ui_state": "main", "input": "none", "capture_kind": "mechanics", "source": "synthetic fixture (harness mechanics only)"}`

## Geometry
- native: 64x48
- port:   64x48
- match: True

## Metrics
- total pixels: 3072
- differing pixels: 0 (ratio 0.0)
- max channel delta: 0
- mean channel delta: 0.0

## Artifacts

- native_png: `docs\review\g9_samples\pass_out\native.png`
- port_png: `docs\review\g9_samples\pass_out\port.png`
- diff_png: `docs\review\g9_samples\pass_out\diff.png`
