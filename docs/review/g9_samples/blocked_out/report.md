# G9 screenshot-diff report

- tool: `g9_screenshot_diff` v1
- timestamp: 2026-10-09T14:54:34
- **result: `BLOCKED`** — protocol mismatch: ui_state/input differ (native ui_state='main' input='none'; port ui_state='options' input='none')
- evidence kind: **unknown**
- eligible as G9 acceptance evidence: **False**

## Tolerance
- per-channel absolute tolerance: 4
- max diff ratio allowed: 0.005

## native
- path: `docs\review\g9_samples\blocked_native.png`
- meta: `{"app": "native", "window_title": "native-synth", "width": 64, "height": 48, "ui_state": "main", "input": "none", "capture_kind": "mechanics", "source": "synthetic fixture (harness mechanics only)"}`

## port
- path: `docs\review\g9_samples\blocked_port.png`
- meta: `{"app": "port", "window_title": "port-synth", "width": 64, "height": 48, "ui_state": "options", "input": "none", "capture_kind": "mechanics", "source": "synthetic fixture (harness mechanics only)"}`
