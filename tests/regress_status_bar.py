"""Regression: the main window's status bar (port of .tmp's
``StatusBar``/``NotificationPopover``, gated by
``toolbarVisibility.isStatusBarVisible``).

The port contract, pinned here:

  1. ``General.ShowStatusBar`` defaults TRUE (upstream
     ``UiConfiguration.isStatusBarVisible = true``) and the main
     window's ``statusbar`` strip is visible by default;
  2. the strip shows the LATEST notification posted to
     ``qtranslate.notify``'s bus — severity glyph plus title/body —
     and falls back to upstream's "Ready" line before any post;
  3. clicking the strip lists the buffered notifications (the bar
     keeps its own last-10 view; ``clear_history`` empties the list
     without touching the chip, like the popover's Clear all);
  4. ``ShowStatusBar=False`` hides the strip AND shrinks the window's
     minimum height back, so the provider buttons are never covered;
  5. the Options -> Basics "Toolbars" group carries the
     "Show status bar" checkbox writing the same key.

Offscreen; no provider calls, no windows shown.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import config as _CFG                    # noqa: E402
from qtranslate import notify as _N                      # noqa: E402

# Isolate from the developer's live Options.json.
_CFG.DEFAULT_PATH = os.path.join(tempfile.mkdtemp(prefix="qt-status-"),
                                 "Options.json")


def _set(**general):
    cfg = _CFG.load() or {}
    cfg.setdefault("General", {}).update(general)
    _CFG.save(cfg)


ck("ShowStatusBar default is upstream's true",
   _CFG.default_config()["General"].get("ShowStatusBar") is True)

from qtranslate import registry as RG                    # noqa: E402
_ORIG = dict(RG.TRANSLATORS)
try:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = lambda t, s, g: "GOOGLE:" + t
    RG.reset_router()

    from qtranslate.qt.app import QtApp                  # noqa: E402
    from qtranslate.qt.main_window import MainWindow     # noqa: E402

    app = QtApp([])
    app._load_session()
    app.source, app.target = "en", "vi"
    app.win = MainWindow(app)
    win = app.win
    sb = getattr(win, "statusbar", None)
    ck("the main window has a status bar", sb is not None)
    if sb is None:
        raise SystemExit(1)

    def vis(w, top):
        try:
            return w.isVisibleTo(top)
        except Exception:
            return False

    # ---- default: visible, "Ready", grown minimum --------------------
    win.apply_pane_visibility()
    ck("status bar visible by default", vis(sb, win))
    ck("empty bar shows upstream's ready message",
       sb.latest_text() == "Ready", sb.latest_text())
    ck("minimum height grew for the strip",
       win.minimumHeight() == win.SIZE[1] + win._sb_extra,
       "%d vs %d+%d" % (win.minimumHeight(), win.SIZE[1],
                        win._sb_extra))
    ck("the strip docks at the bottom edge",
       sb.y() + sb.height() <= win.height()
       and sb.y() >= win.height() - sb.height() - 4,
       "y=%d h=%d win=%d" % (sb.y(), sb.height(), win.height()))

    # ---- a posted notification lands on the chip ----------------------
    _N.notify("info", "Copied", "text to clipboard",
              bus=_N.default_bus())
    app.qapp.processEvents()
    ck("chip shows the latest notification's title",
       "Copied" in sb.latest_text(), sb.latest_text())
    ck("chip appends the body",
       "clipboard" in sb.latest_text(), sb.latest_text())
    ck("history kept the post", len(sb._history) == 1)

    _N.notify("error", "Boom", "It broke", bus=_N.default_bus())
    app.qapp.processEvents()
    ck("a newer post replaces the chip",
       sb.latest_text().startswith("Boom"), sb.latest_text())
    ck("history keeps both, newest last",
       len(sb._history) == 2 and sb._history[-1].title == "Boom")

    # ---- toggle off ----------------------------------------------------
    _set(ShowStatusBar=False)
    win.apply_pane_visibility()
    ck("ShowStatusBar=False hides the strip", not vis(sb, win))
    ck("minimum height shrinks back",
       win.minimumHeight() == win.SIZE[1],
       str(win.minimumHeight()))
    _set(ShowStatusBar=True)
    win.apply_pane_visibility()
    ck("re-enabled strip is back", vis(sb, win))

    # ---- the popover's Clear -------------------------------------------
    sb.clear_history()
    ck("clear empties the history list", len(sb._history) == 0)
    ck("clear keeps the chip (upstream keeps the message)",
       "Boom" in sb.latest_text(), sb.latest_text())

    # ---- the Options checkbox ------------------------------------------
    from qtranslate.qt.options import basics as _basics       # noqa: E402
    from PySide6.QtWidgets import QCheckBox                  # noqa: E402
    page = _basics.BasicsPage(app)
    boxes = [c for c in page.findChildren(QCheckBox)
             if c.text() == "Show status bar"]
    ck("Basics has a 'Show status bar' checkbox", len(boxes) == 1,
       str(len(boxes)))
    if boxes:
        ck("checkbox reads the stored value",
           boxes[0].isChecked() is True)
        boxes[0].setChecked(False)
        app.qapp.processEvents()
        ck("unchecking persists General.ShowStatusBar=false",
           (_CFG.load() or {}).get("General", {}).get(
               "ShowStatusBar") is False)
        _set(ShowStatusBar=True)
finally:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIG)
    RG.reset_router()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print(" -", f)
    sys.exit(1)
print("PASS %d checks" % n[0])
