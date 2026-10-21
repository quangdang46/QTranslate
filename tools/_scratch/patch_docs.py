"""Correct the two review documents that the 2026-10-21 work made stale.

* `FULL_FEATURE_UI_STATUS_2026-10-17.md` claims the port's main window has
  the native's service icon strip. On this platform it did not -- the strip
  was three oversized buttons with six of the nine services off-screen.
* `g9_evidence/README.md` says the directory holds no files and that the
  comparison is pending. The acceptance capture pair landed on 2026-10-16
  and was compared; what was missing was the PROTOCOL, and that is what the
  2026-10-21 work found.
"""

from __future__ import annotations

import sys
from pathlib import Path

EDITS: list[tuple[Path, str, str]] = []

EDITS.append((
    Path("docs/review/FULL_FEATURE_UI_STATUS_2026-10-17.md"),
    """| `2131.png` (516×423) | `main.png` (516×393) | Main window | **Close** — same panes, toolbar, boot text. Native has service icon strip; port has it too. |""",
    """| `2131.png` (516×423) | `main.png` (516×393) | Main window | **Close** — same panes, toolbar, boot text. Native has service icon strip; port has it too. **Corrected 2026-10-21: the port did NOT have the strip off Windows** — its buttons were character-sized (230 px each, 2334 px needed inside a 587 px window), so six of the nine services were off-screen and the macOS capture showed no strip at all. Fixed, with native's own icons recovered from the installer payload: `docs/review/UI_FIDELITY_MAIN_WINDOW_2026-10-21.md`. |"""))

EDITS.append((
    Path("docs/review/FULL_FEATURE_UI_STATUS_2026-10-17.md"),
    """| `qt-fj5` (P1) | **G9 part (b)** — native-vs-port pixel comparison | Screenshots banned on this host; needs human reviewer to open `native.png`/`port.png`/`diff.png` and confirm capture circumstances | Human review + human-written waiver token |""",
    """| `qt-fj5` (P1) | **G9 part (b)** — native-vs-port pixel comparison | The acceptance capture pair **does** exist (2026-10-16) and was compared; what was missing was a *matched protocol*. The 5.35 % whole-image difference is **97.5 % window frame** — the native was captured with `PrintWindow` and the port by cropping the desktop, and the native was unfocused while the port was focused. The application's own pixels match at **0.21 %** (0.026 % excluding the caption). The harness now refuses a pair whose capture method or activation state disagree. The remaining 12 native surfaces still have no matching port capture, and the human review + waiver are still required. | Human review + human-written waiver token, plus a re-capture of the other 12 surfaces under a matched protocol. See `docs/review/G9_DIFF_DECOMPOSITION_2026-10-21.md`. |"""))

EDITS.append((
    Path("docs/review/g9_evidence/README.md"),
    """Status: **BLOCKED — awaiting a runnable native + port capture pair.**
Non-synthetic PASS/FAIL may only be recorded once such a pair exists.
""",
    """Status: **BLOCKED — awaiting a capture pair taken under a MATCHED
protocol.** A pair exists (2026-10-16, see below), but it was taken with two
different capture methods and two different window activation states, so
the comparison it produced measured the capture, not the UI.
Non-synthetic PASS/FAIL may only be recorded once such a pair exists.

## 2026-10-21 — the pair exists; the protocol did not

Re-read on 2026-10-21: `native.png` + `port.png` + `out/report.{json,md}`
have been here since 2026-10-16, and the report says `FAIL, diff_ratio
0.053508`. That FAIL was **not** a fidelity failure.

Decomposed by pixel (`docs/review/G9_DIFF_DECOMPOSITION_2026-10-21.md`):

| region | pixels | differing | ratio |
|---|---:|---:|---:|
| whole image | 216,770 | 11,599 | 5.3508 % |
| window frame (edge bands L8 R8 T1 B8) | 11,170 | **11,170** | **100 %** |
| **client area** (the app's own pixels) | 205,600 | 429 | **0.2087 %** |

The native's frame pixels are `(0,0,0)` — `PrintWindow` rendering the
window's own border — and the port's are the desktop's `(26,26,26)`, because
the port was captured by cropping the desktop. The native was also captured
**inactive** (dimmed caption glyphs, mean luminance 131/150) while the port
was **active** (78/53), so the caption text differs too.

Three changes followed:

1. `capture_method` and `focus` became declared metadata; a mismatch across
   the two sides is a protocol mismatch and the comparison is `BLOCKED`,
   never a `FAIL`.
2. The harness now measures the frame band and reports the **client-area**
   ratio, and a difference confined to the frame is `BLOCKED` rather than a
   misleading `FAIL`.
3. The re-run is at `g9_evidence/out_2026-10-21/`; the 2026-10-16 `out/`
   is left untouched as the original evidence.
"""))

EDITS.append((
    Path("docs/review/g9_evidence/README.md"),
    """This directory still received no files.** The G9 row stays `UNKNOWN` and
the Gate stays `BLOCKED (1)`.""",
    """This directory still received no files.** The G9 row stays `UNKNOWN` and
the Gate stays `BLOCKED (1)`.

*(Superseded 2026-10-21 — the directory DOES hold the acceptance pair now;
see the section above.)*"""))


def main() -> int:
    for path, old, new in EDITS:
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            print(f"{path}: anchor found {count} times (expected 1): "
                  f"{old[:60]!r}", file=sys.stderr)
            return 2
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"patched {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
