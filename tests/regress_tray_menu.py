"""Regression: the tray menu is the native taskbar menu with the native order.

The user's correction: the tray context menu only appears on right-clicking
the taskbar icon -- it is not a standalone window. This suite pins
  * the Qt tray builds a QSystemTrayIcon with a context menu,
  * the menu item order matches native screenshot 2126 / spec §5,
  * it is a checkable Enable-global-hotkeys + a Mouse mode radio group,
  * handlers write the setting they claim to write.

The tkinter suite walked its own pystray Icon; the Qt menu is checked the
same way, headlessly (no icon.show()) -- QMenu builds offline, so the
ORDER is asserted on the live menu rather than guessed from source.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtranslate.qt import app as QA  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


_app = QA.QtApp([]) if hasattr(QA.QtApp, "_core") else None
if _app is None:
    print("regress_tray_menu: no QtApp; skipped")
    raise SystemExit(0)

from qtranslate.qt.tray import Tray  # noqa: E402

tray = Tray(_app)  # the OS's own menu, offscreen
menu = tray.menu
texts = [a.text() for a in menu.actions() if a.text()]
# SEPARATOR positions matter: a separator action has no text.
order = []
for a in menu.actions():
    order.append("SEPARATOR" if a.isSeparator() else a.text())

# The Qt menu leads with the disabled bold header ("QTranslate"), which
# the tk/pystray menu could not draw -- it was the OS's own. The entries
# keep native's order under it.
WANT = ["QTranslate", "Show main window", "Dictionary", "Text recognition",
        "History", "Keyboard", "Options...", "About QTranslate",
        "SEPARATOR", "Enable global hotkeys",
        "Mouse mode", "SEPARATOR", "Exit"]
ck("tray menu carries every native entry",
   all(w == "SEPARATOR" or w in texts for w in WANT if w != "SEPARATOR"),
   "got %s" % texts)
# A double-click on the icon shows the main window (see _activated), so
# the first ACTION is Show main window, right under the header.
head = [t for t in order if t != "QTranslate"]
ck("the first action is Show main window", head[0] == "Show main window",
   "head=%s" % (head[:1],))
collapsed = [t for t in order if t != "SEPARATOR"]
want_collapsed = [w for w in WANT if w != "SEPARATOR"]
ck("tray menu order is the native order", collapsed == want_collapsed,
   "got %s" % collapsed)

hot = tray.act_hotkeys
ck("Enable global hotkeys is a checkable item", hot is not None
   and hot.isCheckable(),
   str(hot))

mode_actions = tray._mode_actions
ck("Mouse mode is a radio submenu with 3 modes",
   set(mode_actions) == set(("Show icon", "Show translation",
                             "Show translation and read")),
   str(sorted(mode_actions)))
for act in mode_actions.values():
    if not act.isCheckable():
        ck("Mouse mode options are checkable", False, "not checkable")
        break
else:
    ck("Mouse mode options are checkable", True)

# the handler must write the flag it names: the check just above pins the
# live menu; this one pins that the write-back is the setting itself.
import inspect
src = inspect.getsource(Tray._toggle_hotkeys)
ck("Enable-global-hotkeys handler writes the hotkeys setting",
   "set_hotkeys_enabled" in src, src[:120])
src = inspect.getsource(Tray._set_mouse_mode)
ck("Mouse mode handler writes the mode",
   "set_mouse_mode" in src, src[:120])

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_tray_menu: all checks ok (%d assertions)" % n[0])
