# G9 screenshot-diff report

- tool: `g9_screenshot_diff` v1
- timestamp: 2026-10-21T05:36:58
- **result: `BLOCKED`** — protocol mismatch: capture_method differs (native='printwindow' port='desktop-crop') -- one side renders the window frame and the other shows the desktop behind it, so the diff would measure the capture method, not UI fidelity
- evidence kind: **unknown**
- eligible as G9 acceptance evidence: **False**

## Tolerance
- per-channel absolute tolerance: 8
- max diff ratio allowed: 0.01

## native
- path: `docs/review/g9_evidence/native.png`
- meta: `{"app": "native", "window_title": "QTranslate", "width": 530, "height": 409, "ui_state": "main", "input": "hello world", "capture_kind": "acceptance", "source": "QTranslate.exe 6.10.0 PE32 i386 via WoW64 on Win11 26200 AMD64, 2026-10-16", "size_origin": "placement", "sha256": "ed4feebcbeb9adcde348ec11d2db146907076c2ec4fc45e105a87b83daa372b3", "capture_method": "printwindow", "focus": "inactive"}`

## port
- path: `docs/review/g9_evidence/port.png`
- meta: `{"app": "port", "window_title": "QTranslate", "width": 530, "height": 409, "ui_state": "main", "input": "hello world", "size_origin": "placement", "capture_kind": "acceptance", "source": "port bundle dist/QTranslate/QTranslate.exe desktop-crop selftest 18/18 Win11 26200 AMD64 2026-10-16", "sha256": "1f3f3ff1a763bf99a4d998dcbdc863e1a6f9e3d6d9680c34190f02dabd106ccc", "capture_method": "desktop-crop", "focus": "active"}`
