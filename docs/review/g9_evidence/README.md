# G9 evidence (native vs port screenshots)

This directory holds the **real** captures for a G9 comparison. It is currently
**empty / BLOCKED**: no native-vs-port capture pair has been produced yet, so
no G9 acceptance result exists.

Do not place synthetic fixtures here — those live in `docs/review/g9_samples/`
and are mechanics-only. Everything written here must come from `capture` on a
genuine native window and a genuine port window under identical protocol (see
`docs/review/G9_HARNESS.md` §4).

Expected layout after a real run:

```
docs/review/g9_evidence/
  native.png   native.json
  port.png     port.json
  out/         report.json  report.md  diff.png  native.png  port.png
```

Status: **BLOCKED — awaiting a capture pair taken under a MATCHED
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

## Attempt 2026-10-09 — BLOCKED (both sides, different reasons)

Recorded in full in `docs/review/G9_RESULT_2026-10-09.md`. Two independent
blocks, neither invented around:

- **Native:** `QTranslate.6.10.0.exe` is `IMAGE_FILE_MACHINE_I386` (32-bit
  x86, GUI subsystem). This host is `arm64` Darwin 25.4.0 with no `wine` /
  `wine64`. It cannot execute here at all.
- **Port:** tkinter constructs fine, but Screen Recording is not granted —
  `screencapture` and PIL's `ImageGrab` both fail with
  `could not create image from display` / `…from rect` (exit 1, no file).
  That is a human permission grant away, not a code defect.

**No proxy baseline was created and this directory received no files.**

## Attempt 2026-10-10 — BLOCKED again (both sides re-checked, unchanged)

Re-verified rather than assumed, because G9 is the last open row and a
block that has "probably" changed is exactly the kind worth re-testing:

- **Native:** still `PE32 executable (GUI) Intel 80386`, and still no
  `wine`/`wine64` on `PATH`. Unchanged — the binary cannot execute on
  `arm64` Darwin 25.4.0.
- **Port:** the display itself is *reachable* — under Python 3.11 (which has
  `_tkinter`; the Homebrew 3.14 build does not) `Tk()` succeeds and reports
  `2560x1440`. So the port can render. Capture still cannot: `screencapture -x`
  exits 1 with `could not create image from display` and produces no file.
  Same human permission grant as 2026-10-09.

The distinction matters for how this row reads: the port-side block is not
"no GUI" but "GUI renders, capture is denied". Nothing about that is a code
defect, and it does not become evidence of anything by being retried.

**This directory still received no files.** The G9 row stays `UNKNOWN` and
the Gate stays `BLOCKED (1)`.

*(Superseded 2026-10-21 — the directory DOES hold the acceptance pair now;
see the section above.)*

## 2026-10-16 — re-verified on a different host: the reason changed

The two attempts above were recorded on **arm64 Darwin 25.4.0**, where a
32-bit i386 PE32 cannot execute at all and there was no `wine`. That is no
longer this host. Re-checked rather than inherited:

| Side | Then (arm64 Darwin) | Now (AMD64 Windows 11) |
|---|---|---|
| Native `QTranslate.6.10.0.exe` | `PE32 i386`, unrunnable, no wine | **`PE32 i386` and `C:\Windows\SysWOW64` is present** — WoW64 runs 32-bit x86 natively. The installed copy at `%ProgramFiles(x86)%\QTranslate\QTranslate.exe` is the **same 1,462,272-byte binary** (sha256 `f35a3bc8e09e217130ff97efe85ba02bd86573b2e0796b003526604454338227`), so there is no x64 rebuild to wait for. |
| Port | Tk rendered; `screencapture` denied by Screen Recording | Tk renders; the capture ban is now an **explicit operator instruction** ("đừng dùng tool chụp hình"), not an OS permission. |

So G9's part (b) is blocked **by policy, not by capability** — a materially
different statement, and worth having right, because the fix for each is
different. The arm64/wine reasoning above is kept for the record but must
not be read as current.

`tests/regress_g9_part_a_complete.py` pins the machine facts (the PE32
machine type, SysWOW64's presence) so the next reader cannot inherit the
stale reason again.

### What would unblock it

Per the operator's own analysis (2026-10-16), if G9 part (b) is ever wanted:

- **A — Windows VM, separate from the working desktop.** The port is a
  ordinary Tkinter Win32 app that depends on `user32` (mouse capture),
  `OLEACC` (cursor text) and the registry, so a Linux container with Xvfb
  cannot host it. A VM keeps the keyboard/mouse and desktop of the working
  machine untouched, which is the requirement.
- **B — Docker + Xvfb.** Lighter, but only viable if the Windows APIs are
  stubbed or the test is restricted to pure-Tk surfaces. Rejected for this
  app on dependency grounds.

Either way the capture must come from `tools/g9_screenshot_diff.py capture`
on a genuine native window and a genuine port window, with matching
`ui_state`, `input` **and** `size_origin` (added 2026-10-16).

Until then: **no files here**, G9 stays `UNKNOWN`, the Gate stays
`BLOCKED (1)`.
