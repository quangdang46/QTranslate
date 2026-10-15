# G9: template size vs runtime placement — measured, not guessed (2026-10-15)

> Static measurement only (struct decode + arithmetic). No screenshot, no
> window opened. This does **not** resolve G9 — part (b), the runtime
> pixel diff, still needs a capture pair. It sharpens part (a): the native
> "size" is two different numbers and they must not be conflated.

## 1. The two numbers

| Source | Value | Meaning |
|---|---|---|
| DLG129 template (`G9_SPEC_NATIVE_WINDOW_2026-10-10.md`) | 340×201 **dialog units** | First-run size, before any placement is saved |
| Saved `WindowMainPlacement` in real `%APPDATA%/QTranslate/Options.json` | rcNormal (786,228)→(1316,658) = **530×430 px** at (786,228) | Runtime size on this machine |

Full blob decode (`<11i`, 44 bytes):

- `length=44, flags=0, showCmd=1`
- `ptMin=(-1,-1), ptMax=(-1,-1)` (four `FFFFFFFF` — the value the
  `_encode_placement` fix of 2026-10-15 restores; the `-32000` variant was
  never in the real blob)
- `rcNormal = (786, 228, 1316, 658)`

## 2. Template DU → px does not equal the placement

At 8pt MS Shell Dlg the dialog baseunit is ~6×13 to ~7×15, so 340×201 DU
converts to roughly **510×653 – 595×753 px** — neither axis near 530×430.
The placement size is therefore **not** the template scaled: it is a user-
or session-resized rect that native saved back via `FUN_004561F0` and
restores via `FUN_00422DDD` (checklist A7).

Consequences:

1. The port's `_place_main` fallback `root.geometry("526x366")` matches
   **neither** number (it was an older saved placement from another
   machine, baked in as a constant). When no placement blob exists, the
   faithful fallback is the DU→px conversion of the template, not a stale
   pixel constant from a different display.
2. Any future G9 capture protocol must record **which** size each side is
   showing (fresh-template vs restored-placement), or the diff measures
   window-manager state, not UI fidelity.
3. This is a port-side geometry note, not an RE state change: A7 stays
   `VERIFIED`, G9 stays `UNKNOWN`.

## 3. Proposed follow-up (needs a decision, not done here)

- Replace the `"526x366"` fallback with a DU→px computation from the
  measured template (340×201 DU at MS Shell Dlg 8pt), documenting the
  baseunit assumption.
- Add the size-origin (`template` vs `placement (WxH at X,Y)`) to the G9
  harness metadata so a future capture pair cannot silently compare a
  fresh native window against a restored port window.
