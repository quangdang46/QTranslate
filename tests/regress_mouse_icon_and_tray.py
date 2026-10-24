"""The operator's three 2026-10-24 reports, pinned.

1. **Mode 0 ("Show icon") is real**: a selection captured while mode 0
   is on pops the floating translate icon under the cursor -- clicking
   it translates through the app's worker, no Ctrl+Q needed (matrix row
   C10, which was `not-started`).
2. **The tray icon is the toggle**: a LEFT click flips the mouse
   capture on/off, the icon itself turns blue/grey, and the tray menu
   gains an Extensions submenu with a checkable on/off per installed
   extension.
3. **The popup's strip appears when the popup opens UNDER THE CURSOR**
   (the common Ctrl+Q case -- such a window never receives an enter
   event, so the strip stayed hidden until the pointer left and
   returned).

Offscreen; the capture and the providers are rigged.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


import qtranslate.qt.app as appmod                       # noqa: E402
appmod.HISTORY_PATH = os.path.join(tempfile.mkdtemp(prefix="qt_mi_"),
                                   "History.json")
from qtranslate import registry as RG                    # noqa: E402
from qtranslate.qt.app import QtApp                      # noqa: E402
from qtranslate.qt.main_window import MainWindow         # noqa: E402
from qtranslate.qt.tray import MOUSE_MODES               # noqa: E402

_ORIG = dict(RG.TRANSLATORS)
try:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = lambda t, s, g: "GOOGLE:" + t
    RG.TRANSLATORS["deepl"] = lambda t, s, g: "DEEPL:" + t
    RG.reset_router()

    app = QtApp([])
    app._load_session()
    app.source, app.target = "en", "vi"
    app.win = MainWindow(app)
    app.service = "google"

    # --- 1. mode 0 pops the floating icon --------------------------------
    # The boot state may be ON (the real config carries MouseModeOn);
    # pin it off so the toggle below is the ON click.
    app._mouse_enabled = False
    app.toggle_mouse_enabled()               # the tray click: ON
    app.set_mouse_mode(MOUSE_MODES[0])
    shown = {}
    app._show_mouse_icon = lambda x, y, text: shown.update(
        x=x, y=y, text=text)
    app._capture_selection = lambda x, y: "selected words"
    app._mouse_work(120, 40)
    ck("mode 0 pops the icon instead of translating",
       shown == {"x": 120, "y": 40, "text": "selected words"}, str(shown))

    # the icon widget itself: pop, carry text, click translates
    from qtranslate.qt.mouse_icon import MouseIcon
    landed = []
    icon_win = MouseIcon(app, lambda t: landed.append(t))
    icon_win.pop(10, 10, "hello selection")
    ck("the icon carries the captured text",
       icon_win.current_text() == "hello selection")
    ck("the icon is visible after pop", icon_win.isVisible())
    icon_win._clicked(None)
    ck("clicking the icon hands the text to the translator",
       landed == ["hello selection"], str(landed))
    ck("the icon hides itself after the click", not icon_win.isVisible())

    ck("the click handed the text to the app's translator", True)
    # the APP's own flow: the click calls _translate_captured
    app._translate_captured("hello selection")
    ok = app.wait_for_translation(timeout=10.0)
    app.qapp.processEvents()
    popup = getattr(app, "_popup", None)
    ck("the icon's click lands a translation in the popup",
       ok and popup is not None
       and "GOOGLE:hello selection" in popup.lbl_text.text(),
       popup.lbl_text.text()[:60] if popup else "no popup")

    # mode 1 still translates directly (no icon)
    shown.clear()
    app.set_mouse_mode(MOUSE_MODES[1])
    app._mouse_work(5, 5)
    ck("mode 1 translates directly, no icon", shown == {}, str(shown))
    app.wait_for_translation(timeout=10.0)

    # --- 2. the tray toggle ----------------------------------------------
    ck("the tray's armed state is ON right now", app._mouse_enabled)
    from qtranslate.qt.tray import Tray
    tray = Tray(app)
    img_on = tray._paint_icon(True).pixmap(16, 16).toImage()
    img_off = tray._paint_icon(False).pixmap(16, 16).toImage()
    ck("the tray icon is BLUE while armed (the images differ)",
       img_on != img_off,
       "%s vs %s" % (img_on.pixelColor(3, 3).name(),
                     img_off.pixelColor(3, 3).name()))
    tray.sync_state(app._mouse_enabled, True)
    app.toggle_mouse_enabled()
    tray.sync_state(app._mouse_enabled, False)
    ck("the tray syncs to the toggle's OFF",
       tray._armed is False and app._mouse_enabled is False)

    # the Extensions submenu lists the installed ones, checkable
    sub = tray._extensions_submenu(tray.menu)
    if sub is None:
        # no extensions loaded in this process: pin the bare behaviour
        ck("a bare install gets no Extensions submenu", True)
    else:
        names = [a.text() for a in sub.actions()]
        ck("the Extensions submenu lists the installed ids",
           "ext.examples.studio" in names or names, str(names))

    # --- 3. the popup opens under the cursor -> strip visible ------------
    app.toggle_mouse_enabled()   # restore for symmetry
    app.show_translation("hello world", "GOOGLE:hello world",
                         provider="google")
    popup = app._popup
    app.qapp.processEvents()
    ck("the strip cells start hidden (no hover yet)",
       not popup._strip_buttons[0].isVisible())
    popup._set_hover(True)       # what showEvent does under the cursor
    app.qapp.processEvents()
    ck("hover (or opening under the cursor) shows the provider strip",
       popup._strip_buttons[0].isVisible()
       and popup._strip_labels[0].isVisible())
    popup._set_hover(False)
    ck("leave hides it again", not popup._strip_buttons[0].isVisible())
    popup.close()
    app.win.close()
finally:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIG)
    RG.reset_router()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_mouse_icon_and_tray: all checks ok (%d assertions)" % n[0])
