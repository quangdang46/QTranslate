# TEST RESULTS

What was run, what came out, and what the numbers mean. Every number
here is from a run on 2026-10-22 on this machine (Windows 11 Pro
10.0.26200, AMD64, Python 3.12).

## 1. The regression suite

```
python -I tools/run_suites.py
```

```
133 suites, 0 failed, 67.0s
```

**133 suites, 0 failed.** The suite files are 135; two of them
(`live_bass.py`, `live_providers.py`) hit real endpoints and are run
separately, so the runner does not count them.

`ui_match.py` is the live-GUI suite: it builds the real app, drives it
and asserts 96 behaviours, from the strip's service order to the
history's structure to the hotkey codec. It is the suite that would
catch a regression in the UI itself, and it is the one that found the
strip's two-dot short names.

## 2. The pixel comparison

```
uv tool run --python 3.12 --with PySide6 --with pillow python tools/render_qt.py
uv tool run --python 3.12 --with PySide6 --with pillow python tools/render_qt.py --compare
```

The number is the fraction of pixels whose total ink differs by more
than 8 levels, between the native capture and the Qt render of the same
window, cropped to the client area. The method and the numbers are in
`BASELINE_RESULTS.md`.

| Screen | ink diff |
|---|---|
| dict | 0.0028 |
| updates | 0.0060 |
| internet | 0.0078 |
| services | 0.0135 |
| main | 0.0144 |
| exceptions | 0.0212 |
| appearance | 0.0252 |
| advanced | 0.0286 |
| languages | 0.0352 |
| hotkeys | 0.0391 |
| **mean** | **0.0194** |

The residual is the ClearType sub-pixel phase and the icon edges, not
the layout: the rectangles, the borders, the colours and the positions
are verifiable with `tools/ui_measure.py` and are shown to be right in
the diff images in `docs/review/ui_compare/`.

## 3. The live provider suite

```
python -I tests/live_providers.py
```

This one hits the real endpoints, so it is not part of the regression
run.

**The run on 2026-10-22: 19 of 21 live OK.** The two that are not:

| Check | Outcome | What it means |
|---|---|---|
| `bing.translate EN->VI` | `DEAD` -- `RuntimeError: Could not scrape Bing session (page layout changed?)` | the Microsoft provider scrapes Bing's page, and Bing changed it. It was OK on 2026-10-08. This is a live break in an endpoint, not a port defect, and it is recorded rather than papered over |
| `dict.wordreference` | `EMPTY` | WordReference needs the Playwright headless fallback (`playwright install chromium`), which is an optional dependency and is not installed here |

Everything else answered: Google translate and TTS, DeepL detect and
translate, Baidu detect and suggest, Yandex, Youdao, Naver's detect,
translate, dictionary and TTS, Reverso, and six of the eight dictionary
providers.

## 4. What the suite is for

The suite is not a coverage number. Each file asserts ONE behaviour,
and the file name says which. The groups:

| Group | What it pins | Files |
|---|---|---|
| `regress_dict_*` | the eleven dictionary providers: the URI, the codes, the response chain, the card, the window | 30 |
| `regress_core_*` | the `Result` shape and what the engine returns | 4 |
| `regress_history*` | the history list, its file, its exports | 5 |
| `regress_extension*` | the manifest loader, the overrides, the example extensions | 8 |
| `regress_hotkey*` | the 17 hotkeys, the codec, the double-press | 7 |
| `regress_options*` | the nine pages, the settings round trip | 6 |
| `regress_theme*` | the theme loader, the colour slots | 4 |
| `regress_ui_*` | the UI's structure: the panes, the slots, the parity fixes | 6 |
| `regress_windows*` | the five extracted window classes, byte-identical | 4 |
| the rest | one file per behaviour | the remainder |

Two suites are worth naming because of what they exist FOR:

- **`regress_wiring.py`** names the set of modules that nothing imports.
  A module can be complete, tested and dead at the same time, and a
  green test run says nothing about which. The set is written down, so
  it cannot grow silently.
- **`regress_docs_consistency.py`** checks that the documents agree with
  the code, so a document cannot quietly become a lie.

## 5. The failures that were open on 2026-10-22, and what they were

The three failures that were open when this programme started, and what
each one turned out to be. None of them was a test rewritten to pass.

| Suite | The failure | What it was | The fix |
|---|---|---|---|
| `regress_wiring.py` | the orphan set grew by four | the test did not understand relative imports, so the new `qtranslate/qt` package's modules looked unimported | the test now resolves `from .x import y`; the orphan set is back to the known four |
| `regress_options_pages_native.py` | the group boxes' titles came back empty | the group box has been drawn by hand since commit `fa77943`, and the test still expected tkinter's `Labelframe` | the group box carries its caption; the test reads it. The assertion's MEANING is unchanged: the Advanced page still has three group boxes named Advanced / Mouse mode / API keys |
| `ui_match.py` | 14 checks failed | eight of them grepped `qtranslate/app.py` for the strip's short names, which had moved to `windows.py` with the other windows; two asserted the Options page order as the TEMPLATE lists it, not as the native draws it; four read the live `Options.json`, which is the user's file | the strip is read off the rendered widgets; the page order is the native's runtime order, with the evidence in the comment; the defaults are read from the port's default document |

And the defects the failures were POINTING AT, which were fixed rather
than papered over:

- The Tk port drew the strip's short names with TWO dots (`Go..`); the
  native draws THREE (`Go...`, measured at x = 45, 49, 53).
- The port's settings defaults had `ExpandHistoryItems = True`; the
  native's own file had `False`.
- The port's `HotKeys` default section carried three of the native's
  seventeen keys, and had the replace-selection code (343 = Alt + W) on
  the wrong key.
