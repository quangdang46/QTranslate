# Screenshots

`app.png` is a live capture of the port's main window, regenerated and
overwritten before each commit so the repo always reflects the current UI.

Regenerate:

```
python -I tools/capture_app.py screenshots/app.png
```

The same script output can serve as the **port** side of the G9
native-vs-port diff harness (`tools/g9_screenshot_diff.py`); `app.png` is a
port capture, not by itself a G9 acceptance result (G9 stays UNKNOWN until a
matching native capture exists and is reviewed).
