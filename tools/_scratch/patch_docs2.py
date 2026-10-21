"""The doc updates the 2026-10-21 work made necessary.

Five documents are stale after the MainWindow split and the mouse-capture
fix:

1. `docs/review/PHASE7_APP_SPLIT_2026-10-16.md` -- says the split is "5 of
   6" with MainWindow outstanding.
2. `docs/RE_COVERAGE_CHECKLIST.md` row C8 -- says the handedness
   normalization is "ported 1:1 (`_buttons_swapped()` -> `SM_SWAPBUTTON`,
   down/up remapped)". The *behaviour* is now right and the *mechanism* is
   deliberately not carried across, and the reason is worth recording.
3. `docs/review/C3_C8_C10_MOUSE_2026-10-10.md` §C8 -- says the port "never
   consults `SM_SWAPBUTTON`". It did, and that was the bug.
4. `docs/review/MAIN_WINDOW_LAYOUT_DIVERGED_2026-10-16.md` -- three of its
   four divergences are closed.
5. `qtranslate/app.py`'s module docstring -- says the third pane is "not
   built here".
"""

from __future__ import annotations

import sys
from pathlib import Path

EDITS: list[tuple[Path, str, str]] = []

EDITS.append((
    Path("qtranslate/app.py"),
    """  - source RichEdit (id1000) / result RichEdit (id1017) with separator
    (native also has a third small pane, id1018 -- not built here; see
    docs/review/MAIN_WINDOW_LAYOUT_DIVERGED_2026-10-16.md)
    statics (id1134/1135)""",
    """  - source RichEdit (id1000) / result RichEdit (id1017) with separator
    (native's third small pane, id1018, is built too -- it is the `aux`
    strip; the main window's own body lives in
    `qtranslate.windows.MainWindow` since Phase 7 (6/6))
    statics (id1134/1135)"""))

EDITS.append((
    Path("docs/RE_COVERAGE_CHECKLIST.md"),
    """| C8 RawInput mouse | `FUN_00417E4E`: `GetRawInputData` -> normalize to `0x201`/`0x202` using `GetSystemMetrics(0x17)` handedness -> `FUN_004193F6` | VERIFIED | ported | **implemented 2026-10-10, mechanism substituted:** native uses **RawInput**; the port uses `WH_MOUSE_LL` because `SetWindowsHookExW` has 0 native callers and RawInput has no cross-platform path. The **handedness normalization is ported 1:1** (`_buttons_swapped()` -> `SM_SWAPBUTTON`, down/up remapped) since it is the part that changes behaviour |""",
    """| C8 RawInput mouse | `FUN_00417E4E`: `GetRawInputData` -> normalize to `0x201`/`0x202` using `GetSystemMetrics(0x17)` handedness -> `FUN_004193F6` | VERIFIED | ported | **implemented 2026-10-10, mechanism substituted:** native uses **RawInput**; the port uses `WH_MOUSE_LL` because `SetWindowsHookExW` has 0 native callers and RawInput has no cross-platform path. **2026-10-21: the handedness rule is ported 1:1 as a pure function** (`mouse_capture.normalize_raw_button()`, 18 assertions) but the *hook* deliberately does NOT apply it: Windows applies the swap when a raw button byte becomes a window *message*, and RawInput sits below that layer -- so `WH_MOUSE_LL`, whose `wParam` **is** the message, already reports the primary button as `WM_LBUTTONDOWN`. The previous code double-swapped, so a left-handed user's trigger could **never fire**; that is fixed. The own-window skip now works (it compared a handle from a throwaway `Tk()` that could never match) and the exclusion list is consulted against the window **under the cursor**, as native does (`FUN_004193F6` -> `FUN_004631DE`), not only the foreground window. `tests/regress_mouse_capture_c8.py` (56) + `tests/regress_mouse_capture.py` (41) |"""))

EDITS.append((
    Path("docs/review/C3_C8_C10_MOUSE_2026-10-10.md"),
    """Port's hook never consults `SM_SWAPBUTTON`, never does the own-window skip, and never runs the exclusion list.""",
    """Port's hook never consults `SM_SWAPBUTTON`, never does the own-window skip, and never runs the exclusion list.

> **Corrected 2026-10-21** (`docs/review/C3_C8_C10_MOUSE_2026-10-10.md` §C8
> was the stale half of this): the port *did* consult `SM_SWAPBUTTON`, and
> that was the defect. It applied the swap to the hook's messages **on top
> of** the swap Windows already applies, so for a left-handed user the hook
> waited for a button-up before a button-down -- the first click of every
> pair was dropped and the second was compared against the *previous*
> click's release point, past the 4px tolerance. A left-handed user's
> mouse-mode capture could never fire. The fix is not "consult the swap
> harder": the swap belongs to the **message** layer, and `WH_MOUSE_LL`'s
> `wParam` is already that layer, so the hook must not apply it again.
> Native's own rule is preserved 1:1 as the pure
> `mouse_capture.normalize_raw_button()`. The own-window skip existed but
> was dead code (it built a throwaway `Tk()` and destroyed it, so the
> handle could never match), and the exclusion list ran against the
> *foreground* window -- native's hotkey path -- instead of the window under
> the cursor.""" ))

EDITS.append((
    Path("docs/review/MAIN_WINDOW_LAYOUT_DIVERGED_2026-10-16.md"),
    """| **4** | Absolute placement — every control has explicit x/y/cx/cy | `_build_main` is **fluid** (`pack()` ×28, zero `place()`) | Native's controls are at fixed DU offsets; the port re-flows. With a saved placement of `530×430` (this machine) rather than the template's `595×376`, the port's fluid result and native's absolute layout diverge further. |""",
    """| **4** | Absolute placement — every control has explicit x/y/cx/cy | `_build_main` is **fluid** (`pack()` ×28, zero `place()`) | Native's controls are at fixed DU offsets; the port re-flows. With a saved placement of `530×430` (this machine) rather than the template's `595×376`, the port's fluid result and native's absolute layout diverge further. |

**Status 2026-10-21.** Divergences **1**, **2** and **3** are closed:

| # | Closed by | How |
|---|---|---|
| 1 | the third pane | `auxfrm` / `self.aux` (a 1-line RichEdit) is built, with its own separator — the port's band structure now matches native's: source, tool row, result, aux, service strip |
| 2 | the pane ids | `app.py` and `win32app.py` now say `ID_SRC = 1000` / `ID_OUT = 1017`; the *old* wrong ids (`1000` = source was labelled 1017) are gone |
| 3 | the overlay | the mic/headphone/listen buttons are `place()`d **over** the panes at their native offsets, not given a side column |

**#4 (fluid vs absolute) is still open** and is the one that needs a decision
rather than a fix: the port's bands are now *measured* against native's
(`docs/review/UI_FIDELITY_MAIN_WINDOW_2026-10-21.md` §4), and the residual
difference is two extra 16-17px bands and a different source-pane height --
which is a font-metric and layout-model question, not a mistake.

The main window's own body also moved on 2026-10-21: Phase 7 (6/6) extracted
it as `qtranslate.windows.MainWindow`, leaving thin delegators in `app.py`.
The split is verified behaviour-preserving: the widget geometry before and
after is **identical**, band for band."""))

EDITS.append((
    Path("docs/review/PHASE7_APP_SPLIT_2026-10-16.md"),
    """**A split is a MOVE, not a rewrite.**""",
    """**A split is a MOVE, not a rewrite.**

> **2026-10-21: the sixth class landed.** `MainWindow` is now
> `qtranslate.windows.MainWindow`, with `app.py` keeping a thin delegator
> per moved method (50 of them). The main window is not a window hanging off
> the app -- it *is* the app's own window -- so it is handed the live `App`
> and reads and writes its state there, exactly as the other five classes
> are handed `root` and `app`. The rewrite rules are: `self.<attr>` ->
> `self.app.<attr>`; an assignment target is always the App's; an internal
> call to another moved method stays internal. Verified behaviour-preserving:
> the widget geometry before and after the split is **identical**, band for
> band, and the suite is green (128 suites, 0 failed)."""))


def main() -> int:
    for path, old, new in EDITS:
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            print(f"{path}: anchor found {count} times (expected 1): "
                  f"{old[:70]!r}", file=sys.stderr)
            return 2
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"patched {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
