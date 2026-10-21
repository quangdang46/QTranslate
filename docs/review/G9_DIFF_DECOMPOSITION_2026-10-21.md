# G9 part (b) — the 2026-10-16 capture pair, decomposed (2026-10-21)

> **Scope:** a *measurement* of the one real native-vs-port capture pair this
> project has (`docs/review/g9_evidence/`), and the harness change it forced.
> **No row state is changed by this document** except the G9 row's own note,
> which now records a measured fact instead of an open question. **This does
> not open the Gate and does not assign a waiver** — see §7.

---

## 1. What was already on disk

The 2026-10-16 session (Windows 11 26200, AMD64) produced a complete,
acceptance-declared capture pair and a harness report:

| Artifact | Content |
|---|---|
| `g9_evidence/native.png` + `native.json` | `QTranslate.exe` 6.10.0 PE32 i386 via WoW64, `PrintWindow`, 530×409, `ui_state=main`, `input="hello world"` |
| `g9_evidence/port.png` + `port.json` | the port's Windows bundle (`dist/QTranslate/QTranslate.exe`, selftest 18/18), **desktop crop**, 530×409, same `ui_state`/`input` |
| `g9_evidence/out/report.{json,md}` | the harness result: **`FAIL`, diff_ratio 0.053508** vs `--max-diff-ratio 0.01` |

Every protocol field the harness knew about matched: same dimensions, same
`ui_state`, same `input`, same `size_origin` (`placement`), both sides
`capture_kind: acceptance`, both `sha256` verified against the file on disk.
The report was `evidence_kind: acceptance-declared`, `g9_evidence: true` —
*eligible for human review*.

**The document that recorded this (`FULL_FEATURE_UI_STATUS_2026-10-17.md`) did
not mention it.** It still described G9 part (b) as "no capture pair exists".
The pair existed; the sweep had not looked in `g9_evidence/`.

So the open question was never "can we capture?" — it was **"is the 5.35%
difference a fidelity failure?"** This document answers that.

---

## 2. Method

The two PNGs were decoded with the harness's own stdlib codec
(`tools/g9_screenshot_diff.py:png_decode`) — no new dependency, no second
implementation — and compared at the harness's own tolerance
(`--channel-tolerance 8`; a pixel differs when any channel delta exceeds 8).
The decomposition was computed twice, independently:

1. by a standalone script (`tools/_scratch/g9_decompose.py`) that walks the
   images row by row and column by column, and
2. by the harness itself, after the change described in §5.

Both agree exactly.

---

## 3. The result: 96.3% of the difference is the window frame

| Region | Pixels | Differing | Ratio |
|---|---:|---:|---:|
| Whole image | 216,770 | 11,599 | **5.3508 %** |
| **Window frame** (edge bands `L8 R8 T1 B8`) | 11,170 | **11,170** | **100.0000 %** |
| **Client area** (the rectangle left after removing the frame) | 205,600 | 429 | **0.2087 %** |

Every single frame pixel differs. Not one client pixel is excluded from the
429.

Measured directly on the frame band, at mid-height (y=200):

| Column | Native | Port |
|---|---|---|
| 0 | `(0, 0, 0)` | `(26, 26, 26)` |
| 3 | `(0, 0, 0)` | `(26, 26, 26)` |
| 7 | `(0, 0, 0)` | `(62, 62, 62)` |
| **8** | `(240, 240, 240)` | `(240, 240, 240)` — **content starts here** |

And on the bottom band (x=250):

| Row | Native | Port |
|---|---|---|
| 400 | `(240, 240, 240)` | `(240, 240, 240)` — **content ends here** |
| 401 | `(0, 0, 0)` | `(59, 59, 59)` |

**Native's frame is pure black; the port's frame is the desktop.** That is the
whole explanation. `PrintWindow` renders the native window's own border and
shadow (black, because the window does not paint its non-client area); the
port was captured by cropping it out of a desktop screenshot, so the pixels
outside the window are the desktop's `(26, 26, 26)` grey — and, at the very
bottom, `(22, 22, 66)`, a shade of the desktop wallpaper.

The two captures are **not two renderings of the same thing**. They are the
same window seen through two different capture mechanisms, and the mechanism
writes 16 columns and 9 rows of the image.

---

## 4. What the client-area difference actually is

The 429 differing client pixels are not spread evenly:

| Band | Differing pixels |
|---|---:|
| Title bar (y 1–29) | 379 |
| Service strip (y 370–400) | 36 |
| Help text (y 60–99) | 14 |

**379 of the 429 are the caption.** Windows dims an inactive window's caption
text and its minimise/maximise/close glyphs. Measured on the caption
("QTranslate", x 18–100, y 6–24) and the caption buttons (x 395–500, y 4–26):

| Region | Native | Port |
|---|---|---|
| Caption text — mean luminance of the darkest pixels | **131** (min 38) | **78** (min 0) |
| Caption buttons — mean luminance of the darkest pixels | **150** (min 146) | **53** (min 0) |

The native was captured **inactive**; the port was captured **active**. That
is window-manager state, not application pixels.

Excluding the caption entirely, the port's own pixels differ from native's by
**50 pixels out of 190,694 — 0.0262 %** — the 36 service-strip icon pixels and
the 14 help-text pixels (anti-aliasing on the red-underlined
"Show dictionary window" link).

> **Bottom line:** the port's main window is, to within a quarter of a
> percent of the application's own pixels, pixel-identical to native
> QTranslate 6.10.0. The 5.35% was an artifact of comparing a `PrintWindow`
> capture against a desktop crop of an unfocused window against a focused one.

---

## 5. The harness change this forced

`tools/g9_screenshot_diff.py` could not see any of this: it had no notion of a
capture method, no notion of activation state, and no way to separate the
frame from the client area. Given the pair, it correctly said "5.35% > 1%,
FAIL" — and a reader would reasonably have concluded the port's UI was
unfaithful. **That is a misleading negative, which is exactly the outcome the
harness's own design forbids elsewhere** (a `size_origin` mismatch is already
`BLOCKED` rather than `FAIL` for the same class of reason: the diff would
measure window-manager state, not the UI).

Three changes, all in `tools/g9_screenshot_diff.py`:

1. **`capture_method`** metadata (`printwindow` / `desktop-crop` /
   `unspecified`). A mismatch across sides ⇒ `BLOCKED` with the reason
   spelled out. *(New harness protocol rule 6, `G9_HARNESS.md` §4.)*
2. **`focus`** metadata (`active` / `inactive` / `unspecified`). A mismatch
   across sides ⇒ `BLOCKED`. *(New rule 7.)*
3. **Frame decomposition.** Every compare now measures the edge bands where
   *every* pixel differs, and reports the client-area diff ratio alongside
   the whole-image one. A difference **confined to the frame** with the client
   area within tolerance is `BLOCKED` (a capture artifact), not `FAIL`; a
   difference **inside** the client area still fails, so the rule can never
   mask a real gap. *(New `G9_HARNESS.md` §3.3.)*

`selftest` grew from 15 cases to **24** (`PASS 24/24`), nine of them new:

| Case | Pins |
|---|---|
| 16 | frame-only difference ⇒ `BLOCKED`, client ratio reported, `g9_evidence` false |
| 17 | frame band **and** a real client difference ⇒ `FAIL` (the rule does not mask) |
| 18 | `capture_method` mismatch ⇒ `BLOCKED` |
| 19 | `focus` mismatch ⇒ `BLOCKED` |
| 20 | matching `capture_method`/`focus` ⇒ `PASS` (no over-trigger) |
| 21 | an unknown `capture_method` value is rejected by the metadata loader |

The two sidecar files were re-stamped with the **measured** facts — not
assumptions: `native.json` → `capture_method: printwindow`, `focus: inactive`;
`port.json` → `capture_method: desktop-crop`, `focus: active`. The
`printwindow` / `desktop-crop` split is what the frame pixels themselves show
(§3); the focus split is what the caption luminance shows (§4). The port's own
`source` string already said "desktop-crop".

Re-running the harness on the same pair now produces:

```
BLOCKED: protocol mismatch: capture_method differs
  (native='printwindow' port='desktop-crop') -- one side renders the window
  frame and the other shows the desktop behind it, so the diff would measure
  the capture method, not UI fidelity
```

with the frame analysis still in the report (`out_2026-10-21/report.json`):
edge bands `L8 R8 T1 B8`, `client_diff_ratio 0.002087`. The 2026-10-16
`out/` directory is **left untouched** — it is the original evidence.

---

## 6. What this does and does not change

**Does:**

- Replace the open question "is the 5.35% a fidelity failure?" with a
  measured answer: **no — 96.3% of it was the window frame, and the
  application's own pixels match at 0.21% (0.026% excluding the caption).**
- Make the harness unable to produce that misleading negative again, for
  this capture method and for any other.
- Establish that the port's main window is visually faithful to native's, on
  the one real capture pair, at the pixel level.

**Does not:**

- **Open the Gate.** G9 part (b) is still `UNKNOWN`. The comparison the Gate
  needs is a *valid* one — same capture method, same activation state — and
  the pair on disk is not that.
- **Assign a waiver.** Per `RE_COVERAGE_CHECKLIST.md`'s waiver rule, only a
  human adds a `WAIVER:` token, and only on an `INFERRED`/`UNKNOWN` row. This
  document adds none.
- **Replace the human review.** The `2026-10-16` pair remains
  `evidence_kind: acceptance-declared` — a self-declared source string and a
  matching hash, which is file integrity, not proof of a genuine capture.
- **Cover the other 13 native surfaces.** `docs/review/native_screens/`
  holds 13 native captures; only the main window has a matching port
  capture taken under a protocol this project can compare.

---

## 7. What would actually close G9 part (b)

1. **Re-capture both sides the same way** — `PrintWindow` on both, or a
   desktop crop of the same 530×409 window rectangle on both — with both
   windows in the **same** activation state, and with `capture_method` and
   `focus` recorded in the sidecars. The harness will then produce a real
   whole-window number instead of refusing.
2. **Human review** of `native.png` / `port.png` / `diff.png` and the
   capture circumstances, as `G9_HARNESS.md` §3.1 and §6 have always
   required. No tool can do this part.
3. **A human-written waiver token** on the G9 row, if the reviewer accepts
   the result. The validator checks the token; it never writes one.

The port side of step 1 is the only part this host can do, and it is blocked
here: `screencapture` exits 1 with `could not create image from display`
(macOS Screen Recording is not granted to this process). The native side
needs a Windows host with the same capture method.

---

## 8. Reproduce

```bash
cd /Users/tranquangdang21/Projects/QTranslate

# harness self-test (24 cases)
python3 -I tools/g9_screenshot_diff.py selftest

# the pair, re-compared under the corrected protocol
python3 -I tools/g9_screenshot_diff.py compare \
    --native      docs/review/g9_evidence/native.png \
    --port        docs/review/g9_evidence/port.png \
    --native-meta docs/review/g9_evidence/native.json \
    --port-meta   docs/review/g9_evidence/port.json \
    --channel-tolerance 8 --max-diff-ratio 0.01 \
    --out docs/review/g9_evidence/out_2026-10-21

# the independent decomposition
python3 tools/_scratch/g9_decompose.py
```
