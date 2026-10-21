"""Second patch: hoist the frame decomposition above the protocol checks.

The frame decomposition is a *measurement* of the two images, not a verdict.
Computing it before the protocol checks means a BLOCKED report still carries
the numbers a reviewer needs (how much of the difference is frame, and what
the client-area ratio is), instead of only a refusal.
"""

from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("tools/g9_screenshot_diff.py")

BLOCK = '''    # --- frame decomposition -------------------------------------------------
    # A window's edge pixels come from the *capture*, not from the
    # application: PrintWindow renders the window's own frame, a desktop crop
    # shows what is behind it. Measure the band where every pixel differs
    # and report the client-area (frame-excluded) ratio alongside the raw
    # one, so a FAIL is attributable instead of mysterious.
    mask = _diff_mask(npx, ppx, nw, nh, args.channel_tolerance)
    bands = _frame_bands(mask, nw, nh)
    client = _client_metrics(mask, nw, nh, bands["client_rect"])
    report["frame_analysis"] = {
        "edge_bands": {k: bands[k] for k in ("left", "right", "top", "bottom")},
        "client_rect": bands["client_rect"],
        "has_frame_band": any(bands[k] for k in ("left", "right", "top", "bottom")),
        "client_metrics": client,
        "note": (
            "edge_bands count pixels at each edge where EVERY pixel differs; "
            "client_rect is the remaining rectangle and client_diff_ratio is "
            "the diff ratio restricted to it."
        ),
    }

'''

HOIST_TARGET = '''    report["g9_evidence"] = False
    report["evidence_kind"] = "unknown"

'''

HOISTED = '''    report["g9_evidence"] = False
    report["evidence_kind"] = "unknown"

''' + BLOCK


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if text.count(BLOCK) != 1:
        print(f"block found {text.count(BLOCK)} times, expected 1", file=sys.stderr)
        return 2
    if text.count(HOIST_TARGET) != 1:
        print(f"hoist target found {text.count(HOIST_TARGET)} times, expected 1",
              file=sys.stderr)
        return 2
    # Remove the block from its current position, then insert it earlier.
    text = text.replace(BLOCK, "", 1)
    text = text.replace(HOIST_TARGET, HOISTED, 1)
    TARGET.write_text(text, encoding="utf-8")
    print("hoisted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
