# The four `not-started` rows, re-verified 2026-10-12 — no port work in any

> Read-only verification. Each of the four rows the checklist keeps
> `not-started` **deliberately** was re-checked against the current tree and
> the artifacts. The verdict in all four cases: the classification is
> correct, and there is nothing to implement. What changed is that each
> verdict is now re-measured rather than inherited.
>
> **No row state changed by this document.** The tally, the Gate line, and
> every row's state belong to the checklist owner.

## 1. C10 — proven negative, correctly not-started

The row narrows the claim to "no cursor change on the capture path" and
records the port's `WH_MOUSE_LL` as a mechanism substitution. Verified:

- `qtranslate/mouse_capture.py:25` already documents the substitution
  ("`SetWindowsHookExW` has 0 callers in [native]"), and `:218` is the
  port's own hook install — so the divergence is declared in the code,
  not hidden.
- There is no cursor-icon feature to build: the proven negative means the
  work item does not exist. `not-started` = "no feature", correct.

## 2. F13 — architectural divergence, correctly not-started

The row's byte-search claim reproduces, with one notation caveat worth
recording so nobody re-derives it wrong:

- `CLSID_JScript {F414C260-…}` is present **as raw LE GUID bytes** at file
  `0x127dd8` of `QTranslate.6.10.0.exe`. It is **not** present as braced
  text, narrow or wide — a text search for the braces finds nothing.
  The row's braces are notation, not the search method.
- `Chakra` / `16D51579-…` absent in every encoding (narrow, wide, raw).
- The conclusion is unaffected: native requests the classic engine CLSID
  and names no version. The port is Python with a Python-class Extension
  SDK (`docs/EXTENSION_SDK.md` §5), so there is no script engine to port.
  `not-started` = "conscious divergence", correct.

## 3. G9 — blocked harness, correctly not-started (with one stale detail)

- Part (b), the fidelity comparison, is still uncapturable on this host
  (i386 native, no Screen Recording grant) — unchanged.
- The row's port note says "`app.py:318` sizes to `526x366`". That line
  number is stale: the size now lives in `_place_main` as the **fallback**
  when no saved `WindowMainPlacement` exists, and the comment documents
  it as a decoded runtime placement ("526x366 at 876,292 on this machine").
  The docstring's `340x201` is the dialog template. So the live question
  is placement-vs-template for the no-saved-placement case — a Phase 7
  product decision the G9 spec doc already records as such, not RE work.
- `app.py` is neither session's file; no edit made here.

## 4. J6 — dependency decision, correctly not-started

- `qtranslate/speech_input.py` builds the upload URL and Content-Type
  (`audio/x-flac`) but performs no encode; its module docstring states
  the capture path is unimplemented, and `tests/regress_speech_input.py`
  pins the URL builder only. The port declares the gap instead of faking it.
- `requirements.txt` adds no FLAC provider, and the row correctly frames
  vendoring libFLAC (statically linked 1.2.1, verified: `reference libFLAC
  1.2.1 20070917` present, `fLaC` present) as a product decision.
  `not-started` = "awaiting a dependency decision", correct.

## 5. What this closes

With `ca1f025` (dict-card header slots) landed and these four rows
re-verified as correctly not-started, there is no remaining port work in
this session's files (`qtranslate/dict_render.py`, `qtranslate/headless.py`,
`qtranslate/services/dictionary.py`, `tests/regress_dict_card.py`,
`tests/regress_google_romanization.py`,
`tests/regress_plugin_js_recovered.py`). Baseline at this commit:
**17 pass / 6 fail of 23**, the six the unchanged `_tkinter` blocker.
