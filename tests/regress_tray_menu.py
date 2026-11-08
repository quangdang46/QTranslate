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

# The tray labels come from the UI-language pack now; pin the config to
# a throwaway English one so the assertions do not follow the user's
# LocaleFoderName (and no write-through can touch the real file).
import tempfile as _tf  # noqa: E402
from qtranslate import config as _C  # noqa: E402
_C.DEFAULT_PATH = os.path.join(_tf.mkdtemp(prefix="tray_i18n_"),
                               "Options.json")

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
# qt-v74 added the port's own "Check for updates..." after the native
# entries (native has no update UI in the tray); the native order above
# it is unchanged.
# Image search joined between Dictionary and Text recognition -- the
# .tmp tray order (system_tray_menu.image_search) and the port's new
# Commons image-search dialog.
# The labels now come from the UI-language pack (menu 5): English id
# 80 is "Options" -- the pack's own string, not the old hardcoded
# "Options..." -- and every other entry resolves to the same English
# text under the default locale.
WANT = ["QTranslate", "Show main window", "Dictionary", "Image search",
        "Text recognition", "Translate document",
        "History", "Keyboard", "Options", "About QTranslate",
        "Check for updates...",
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

# The Extensions submenu's per-extension on/off switch must persist the
# state the user just CLICKED, not the state captured when the menu was
# built. Qt emits triggered(checked) with the post-toggle value; a
# lambda defaulting `on=act.isChecked()` froze the build-time state and
# every click wrote the pre-click value back -- the switch could never
# change. Pin the round-trip on the live menu.
from PySide6.QtWidgets import QMenu  # noqa: E402
from qtranslate.extensions import (read_disabled_extensions,  # noqa: E402
                                   write_disabled_extensions)


class _ExtStub:
    _manifests = {"ext.demo": {}}


write_disabled_extensions(set())          # known baseline: all enabled
_app.ext_manager = _ExtStub()
_em = QMenu()
sub = tray._extensions_submenu(_em)
ck("extensions submenu appears with a stub manager", sub is not None)
act = next((a for a in sub.actions() if a.text() == "ext.demo"), None)
ck("extension action exists and starts checked", act is not None
   and act.isChecked(), str(act))
# trigger() on a checkable action flips checked and emits
# triggered(new_state) -- the same thing a real menu click does.
act.trigger()
ck("first click persists the extension as disabled",
   "ext.demo" in read_disabled_extensions(),
   str(read_disabled_extensions()))
act.trigger()
ck("second click persists the extension as enabled",
   "ext.demo" not in read_disabled_extensions(),
   str(read_disabled_extensions()))
write_disabled_extensions(set())
_app.ext_manager = None

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_tray_menu: all checks ok (%d assertions)" % n[0])
