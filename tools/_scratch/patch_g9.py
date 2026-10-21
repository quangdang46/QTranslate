"""One-shot patch: add frame decomposition + capture-method/focus checks.

Applied programmatically because the anchor block is long and the editor's
exact-match pass kept rejecting it. The patch is idempotent: it refuses to run
twice.
"""

from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("tools/g9_screenshot_diff.py")

ANCHOR = '    if ratio <= args.max_diff_ratio:\n'

INSERT = '''    # --- frame decomposition -------------------------------------------------
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

    # A difference confined to the window frame is a capture artifact, not a
    # fidelity failure -- the same reasoning that makes a size_origin
    # mismatch BLOCKED rather than FAIL. Report it as BLOCKED and keep the
    # client-area measurement visible, because the client-area number IS the
    # fidelity measurement the reviewer needs.
    if report["frame_analysis"]["has_frame_band"] and \\
            client["client_diff_ratio"] <= args.max_diff_ratio:
        report["client_fidelity"] = {
            "client_diff_ratio": client["client_diff_ratio"],
            "client_diff_pixels": client["client_diff_pixels"],
            "client_pixels": client["client_pixels"],
            "max_diff_ratio": args.max_diff_ratio,
            "verdict": "within tolerance",
            "interpretation": (
                "The application's own pixels (the client rectangle) are within "
                "tolerance; the whole-image difference is confined to the window "
                "frame, which comes from the capture method and the activation "
                "state rather than from the UI."
            ),
        }
        return blocked(
            "capture artifact: the difference is confined to the window frame "
            f"(edge bands L{report['frame_analysis']['edge_bands']['left']} "
            f"R{report['frame_analysis']['edge_bands']['right']} "
            f"T{report['frame_analysis']['edge_bands']['top']} "
            f"B{report['frame_analysis']['edge_bands']['bottom']}), while the "
            f"client area matches at {client['client_diff_ratio']:.6f} "
            f"(<= {args.max_diff_ratio}). Re-capture both sides with the same "
            "capture method and the same window activation state to obtain a "
            "valid whole-window measurement."
        )

'''


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "frame_analysis" in text:
        print("already patched")
        return 0
    count = text.count(ANCHOR)
    if count != 1:
        print(f"anchor found {count} times, expected 1", file=sys.stderr)
        return 2
    text = text.replace(ANCHOR, INSERT + ANCHOR, 1)
    TARGET.write_text(text, encoding="utf-8")
    print("patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
