# G9 screenshot-diff report

- tool: `g9_screenshot_diff` v1
- timestamp: 2026-10-09T14:54:34
- **result: `FAIL`** — diff_ratio 0.032552 > 0.005 (tol 4/channel)
- evidence kind: **mechanics**
- eligible as G9 acceptance evidence: **False**

> mechanics capture(s) present — mechanics result, NOT G9 acceptance evidence

> ⚠️ MECHANICS capture — this exercises the harness mechanics only.
> It is **NOT** native-versus-port fidelity evidence and must not be
> cited as a G9 result.

## Tolerance
- per-channel absolute tolerance: 4
- max diff ratio allowed: 0.005

## native
- path: `docs\review\g9_samples\fail_native.png`
- meta: `{"app": "native", "window_title": "native-synth", "width": 64, "height": 48, "ui_state": "main", "input": "none", "capture_kind": "mechanics", "source": "synthetic fixture (harness mechanics only)"}`

## port
- path: `docs\review\g9_samples\fail_port.png`
- meta: `{"app": "port", "window_title": "port-synth", "width": 64, "height": 48, "ui_state": "main", "input": "none", "capture_kind": "mechanics", "source": "synthetic fixture (harness mechanics only)"}`

## Geometry
- native: 64x48
- port:   64x48
- match: True

## Metrics
- total pixels: 3072
- differing pixels: 100 (ratio 0.032552)
- max channel delta: 215
- mean channel delta: 6.8251

## Artifacts

- native_png: `docs\review\g9_samples\fail_out\native.png`
- port_png: `docs\review\g9_samples\fail_out\port.png`
- diff_png: `docs\review\g9_samples\fail_out\diff.png`
