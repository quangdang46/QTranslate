"""Apply the G9 harness documentation updates.

Applied programmatically (the editor's exact-match pass kept rejecting long
markdown blocks). Every replacement asserts that its anchor was found exactly
once, so a drifted document fails loudly instead of silently skipping an
update.
"""

from __future__ import annotations

import sys
from pathlib import Path

DOC = Path("docs/review/G9_HARNESS.md")

EDITS: list[tuple[str, str]] = []

# --- 1. new section 3.3 on frame decomposition ---------------------------
EDITS.append((
    """stale `True` left over from a provenance check that ran out of order.

## 4. Capture protocol
""",
    """stale `True` left over from a provenance check that ran out of order.

### 3.3 Frame decomposition — a difference confined to the window frame is a capture artifact

Every compare measures the **frame analysis** and puts it in the report,
whatever the verdict:

| Field | Meaning |
|-------|---------|
| `frame_analysis.edge_bands` | pixels at each edge (`left`/`right`/`top`/`bottom`) where **every** pixel differs |
| `frame_analysis.client_rect` | the remaining rectangle — the application's own pixels |
| `frame_analysis.client_metrics.client_diff_ratio` | the diff ratio restricted to that rectangle |
| `frame_analysis.has_frame_band` | whether any edge band differs in every pixel |

A window's edge pixels come from the **capture**, not from the application:
`PrintWindow` renders the window's own border and shadow, while a desktop
crop shows whatever is behind the window. The two produce different edge
pixels for an otherwise identical UI — and a report that says only "5.35% of
pixels differ" reads as a fidelity failure when it is a measurement of the
capture method.

So when the difference is **confined to the frame** and the client area is
within tolerance, the result is `BLOCKED`, not `FAIL` — the same rule that
already makes a `size_origin` mismatch a block rather than a failure. The
client-area number stays in the report (`client_fidelity`), because *that* is
the fidelity measurement the reviewer needs.

A difference **inside** the client area still fails, even when a frame band is
also present: the frame rule must never mask a real fidelity gap
(`selftest` case 17 pins this).

Measured on the one real capture pair this project has
(`docs/review/g9_evidence/`): edge bands `L8 R8 T1 B8`, client ratio
**0.002087** against a whole-image ratio of **0.053508** — i.e. 97.5% of the
"5.35% difference" was window frame. See
`docs/review/G9_DIFF_DECOMPOSITION_2026-10-21.md`.

## 4. Capture protocol
"""))

# --- 2. metadata field table ---------------------------------------------
EDITS.append((
    """| `size_origin` | `template` / `placement` / `unspecified` — **must match across sides** (added 2026-10-16; see below) |
| `capture_kind` | `mechanics` or `acceptance` (§3.1) |
""",
    """| `size_origin` | `template` / `placement` / `unspecified` — **must match across sides** (added 2026-10-16; see below) |
| `capture_method` | `printwindow` / `desktop-crop` / `unspecified` — **must match across sides** (added 2026-10-21; see rule 6) |
| `focus` | `active` / `inactive` / `unspecified` — **must match across sides** (added 2026-10-21; see rule 7) |
| `capture_kind` | `mechanics` or `acceptance` (§3.1) |
"""))

# --- 3. protocol rules 6 and 7 -------------------------------------------
EDITS.append((
    """`unspecified` is the default and matches across sides only when both sides say
it; a capture that knows which it is should say so.
""",
    """`unspecified` is the default and matches across sides only when both sides say
it; a capture that knows which it is should say so.

6. **Same capture method** — one side `printwindow`, the other `desktop-crop`
   is a protocol mismatch, reported as `BLOCKED`. `PrintWindow` renders the
   window's own border and shadow; a desktop crop shows whatever is behind
   the window. The edge pixels then differ in **every** row even when the
   application's own pixels are identical. The native side of the project's
   only real capture pair was taken with `PrintWindow`; the port side was a
   desktop crop. The mismatch is visible in the frame band: the native's
   frame pixels are `(0,0,0)`, the port's are the desktop's `(26,26,26)`.
7. **Same activation state** — one side `active`, the other `inactive` is a
   protocol mismatch, reported as `BLOCKED`. Windows dims an inactive
   window's caption text and its minimise/maximise/close glyphs, so an
   unfocused native capture and a focused port capture differ in the chrome
   even when the application's own pixels are identical. Measured on the
   project's capture pair: the native's caption glyphs bottom out at
   luminance 131 (mean of the darkest pixels) and its caption buttons at
   150, while the port's are 78 and 53 — dimmed versus solid black.
"""))

# --- 4. selftest count ----------------------------------------------------
EDITS.append((
    """Expected: `selftest` → `PASS (15/15)` exit 0; `make-sample` prints""",
    """Expected: `selftest` → `PASS (24/24)` exit 0; `make-sample` prints"""))

# --- 5. result semantics table: add the frame-artifact block -------------
EDITS.append((
    """| `BLOCKED` | 2 | Comparison could not run on usable evidence: a missing/unreadable input, an undecodable image, a failed capture, a protocol mismatch, wrong-side metadata, or **invalid provenance**. |
""",
    """| `BLOCKED` | 2 | Comparison could not run on usable evidence: a missing/unreadable input, an undecodable image, a failed capture, a protocol mismatch (including `capture_method` / `focus` / `size_origin`), wrong-side metadata, **invalid provenance**, or a difference confined to the window frame (§3.3). |
"""))


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    for old, new in EDITS:
        count = text.count(old)
        if count != 1:
            print(f"anchor found {count} times (expected 1): {old[:70]!r}",
                  file=sys.stderr)
            return 2
        text = text.replace(old, new, 1)
    DOC.write_text(text, encoding="utf-8")
    print(f"applied {len(EDITS)} edits to {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
