"""Update the G9 checklist row with what was measured on 2026-10-21.

The RE state stays `UNKNOWN`: G9 part (b) still needs a human reviewer and a
human-written waiver. The PORT state moves from `not-started` to `analysed`,
because the main window has now been measured against the native's own
pixels — the fidelity work is under way and partly done, not untouched.

The note records the measured numbers rather than an open question.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TARGET = Path("docs/RE_COVERAGE_CHECKLIST.md")

NEW_NOTE = (
    "| **classification (unchanged):** (a) is complete, but (b) needs a real "
    "native-vs-port comparison that a human reviews (`G9_HARNESS.md` §3.1/§6: "
    "a `PASS` is only *eligible for* review, never proof the captures are "
    "real). Port note: `app.py` still disagrees with itself — its docstring "
    "says `340x201` (correct template) while the window opens at the saved "
    "runtime placement; template-vs-placement is a Phase 7 **decision**. "
    "Theme colours remain unmeasured; DLU→px is recorded as a RANGE, not a "
    "number, because the conversion needs the dialog font's real "
    "`GetTextMetrics`. **Measured 2026-10-21** "
    "(`docs/review/G9_DIFF_DECOMPOSITION_2026-10-21.md`, "
    "`docs/review/UI_FIDELITY_MAIN_WINDOW_2026-10-21.md`): the one real "
    "acceptance capture pair (native `QTranslate.exe` via WoW64 vs the "
    "port's Windows bundle, both 530x409) diffs **5.3508 %** whole-image, "
    "but **97.5 % of that is the window frame** — the native was captured "
    "with `PrintWindow` (frame rendered black) and the port by cropping the "
    "desktop (frame shows the desktop). The **client area** — the "
    "application's own pixels — matches at **0.2087 %**, and at **0.0262 %** "
    "excluding the caption (the native was captured unfocused, so Windows "
    "dimmed its caption text; measured luminance 131/150 vs the port's "
    "78/53). The harness now measures the frame band, reports the "
    "client-area ratio, and refuses a pair whose `capture_method` or `focus` "
    "disagree (`tools/g9_screenshot_diff.py`, `G9_HARNESS.md` §3.3/§4 "
    "rules 6-7; `selftest` 24/24). Separately, the port's main window was "
    "**wrong off Windows in three measurable ways** — the service strip's "
    "buttons were character-sized (230 px each, 2334 px needed inside a "
    "587 px window, 6 of 9 services off-screen), the Translate button was "
    "clipped off the tool row, and the source pane opened with a 3-line stub "
    "instead of native's help file. All three are fixed, with native's own "
    "assets recovered from the installer payload and the EXE's RT_ICON "
    "resources (`qtranslate/assets/`), and pinned by "
    "`tests/regress_main_window_fidelity.py` (43 assertions). **The row "
    "stays `UNKNOWN`:** the remaining 12 native surfaces still have no "
    "matching port capture, and the human review + waiver are still "
    "required."
)


def main() -> int:
    lines = TARGET.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("| G9 Visual fidelity to native"):
            break
    else:
        print("G9 row not found", file=sys.stderr)
        return 2

    # The row is a single markdown table row: split on the pipe cells.
    cells = line.rstrip("\n").split(" | ")
    if len(cells) < 5:
        print(f"unexpected G9 row shape ({len(cells)} cells)", file=sys.stderr)
        return 2
    # cells: item, evidence, RE state, port state, note
    cells[3] = " analysed"
    cells[4] = NEW_NOTE
    lines[i] = " | ".join(cells) + "\n"
    TARGET.write_text("".join(lines), encoding="utf-8")
    print("G9 row updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
