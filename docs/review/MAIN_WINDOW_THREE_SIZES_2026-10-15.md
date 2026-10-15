# Main window: three different sizes in three sources (2026-10-15)

> Static arithmetic comparison only. No screenshot, no window opened.
> Does not resolve G9. Records a real inconsistency so no future work
> silently picks one number as "the" native size.

## 1. The three numbers

| Source | Size | What it actually is |
|---|---|---|
| DLG129 template (binary `.rsrc`, `G9_SPEC_NATIVE_WINDOW_2026-10-10.md`) | 340×201 DU ≈ **595×753 px** @7×15 | First-run dialog size, before any placement is saved |
| Saved `WindowMainPlacement` (real `%APPDATA%` Options.json on this machine) | **530×430 px** at (786,228) | Runtime rect: user/session-resized, saved by `FUN_004561F0`, restored by `FUN_00422DDD` |
| `UI-FULL.html` `#main` → `screens.py` `MAIN_WIDTH/HEIGHT` | **516×423** | HTML spec figure (full window incl. native title bar); screens.py subtracts 30 px for the client area |

None equals either other. The HTML figure (516×423) is closest to the
saved placement (530×430) — consistent with the spec being drawn from a
screenshot of a *running, placed* window — and farthest from the template
(595×753), which no running window on this machine ever shows.

## 2. What each consumer should use

| Consumer | Correct source |
|---|---|
| `app._place_main` no-blob fallback | Template 595×753 (`TEMPLATE_GEOMETRY`) — fixed 2026-10-15 |
| `app._place_main` with blob | The blob's own rect (530×430 here) — already correct |
| `screens.py` reference builders | The HTML spec 516×423 — correct *for their purpose* (spec fidelity), not a claim about the binary |
| Any future G9 capture protocol | Must record size-origin per side (`template` vs `placement WxH at X,Y` vs `spec`), or the diff measures window-manager state, not UI fidelity |

## 3. Rule going forward

Never cite a main-window pixel size without its origin. "The native main
window is NxM" is an incomplete sentence — the complete ones are "the
template converts to …", "this machine's saved placement is …", "the
spec draws …". The `G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md` §3 proposal
(size-origin in harness metadata) stands.
