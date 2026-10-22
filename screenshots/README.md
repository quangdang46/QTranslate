# Screenshots

`screens/` holds captures of the **PySide6 front end** (`qtranslate/qt/`),
refreshed by `tools/shots.py` on 2026-10-22. They replace the tkinter
captures that were here before: the PySide6 view is the one measured
against the native captures in `docs/review/native_screens/` and is the
one `qtranslate-pyside6-spec.md` describes.

Regenerate with:

    uv tool run --python 3.12 --with PySide6 --with pillow python tools/shots.py

`hist.png`, `kbd.png`, `popup.png` and `tray.png` are not yet written —
`qtranslate/qt/history_window.py`, `keyboard.py`, `popup.py` and `tray.py`
are still being built. `tools/shots.py` skips a window it cannot import
rather than leaving a stale picture in place.

`app.png` is the last capture of the TKINTER port's main window (kept as
a historical artifact; the capture scripts for it were removed
2026-10-15 per user instruction, so it is not regenerated).

These are illustrative captures, not the acceptance evidence: the
rigorous, pixel-measured comparison against the native captures lives in
`docs/review/ui_qt/` (the renders) and `docs/review/ui_compare/`
(the diff images and the ink-vs-native ratio each one measures).
