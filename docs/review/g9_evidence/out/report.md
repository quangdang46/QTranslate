# G9 screenshot-diff report

- tool: `g9_screenshot_diff` v1
- timestamp: 2026-10-16T22:08:21
- **result: `FAIL`** — diff_ratio 0.053508 > 0.01 (tol 8/channel)
- evidence kind: **acceptance-declared**
- eligible as G9 acceptance evidence: **True**

> file integrity (sha256) and a declared source string check out, and all protocol checks (dimensions/ui_state/input/geometry) agree. This does **NOT** prove the images were actually captured from the native app and the port -- only a human reviewing the actual screenshots, diff.png, and the capture circumstances can establish that. Treat as 'eligible for human review', not as a self-certifying G9 result.

> ⚠️ **File integrity + declared source checked out — this is NOT proof
> of real capture.** sha256 only shows the file matches what its own
> metadata claims; `source` is an unverified human-supplied string. A
> human must still review `native.png`/`port.png`/`diff.png` and the
> actual capture circumstances before this counts as a G9 result.

## Tolerance
- per-channel absolute tolerance: 8
- max diff ratio allowed: 0.01

## native
- path: `docs\review\g9_evidence\native.png`
- meta: `{"app": "native", "window_title": "QTranslate", "width": 530, "height": 409, "ui_state": "main", "input": "hello world", "capture_kind": "acceptance", "source": "QTranslate.exe 6.10.0 PE32 i386 via WoW64 on Win11 26200 AMD64, 2026-10-16", "size_origin": "placement", "sha256": "ed4feebcbeb9adcde348ec11d2db146907076c2ec4fc45e105a87b83daa372b3"}`

## port
- path: `docs\review\g9_evidence\port.png`
- meta: `{"app": "port", "window_title": "QTranslate", "width": 530, "height": 409, "ui_state": "main", "input": "hello world", "size_origin": "placement", "capture_kind": "acceptance", "source": "port bundle dist/QTranslate/QTranslate.exe desktop-crop selftest 18/18 Win11 26200 AMD64 2026-10-16", "sha256": "1f3f3ff1a763bf99a4d998dcbdc863e1a6f9e3d6d9680c34190f02dabd106ccc"}`

## Geometry
- native: 530x409
- port:   530x409
- match: True

## Metrics
- total pixels: 216770
- differing pixels: 11599 (ratio 0.053508)
- max channel delta: 255
- mean channel delta: 2.859

## Artifacts

- native_png: `docs\review\g9_evidence\out\native.png`
- port_png: `docs\review\g9_evidence\out\port.png`
- diff_png: `docs\review\g9_evidence\out\diff.png`
