"""Regression: the tray menu is the REAL taskbar menu with the native order.

The user's correction: the tray context menu only appears on right-clicking
the taskbar icon -- it is not a standalone window. This suite pins

  * app._make_tray builds a pystray Icon (OS-drawn menu, not self-drawn),
  * the menu item order matches native screenshot 2126 / spec §5,
  * it is a checkable Enable-global-hotkeys + a Mouse mode radio group,
  * handlers write the setting they claim to write.

Guards the case where pystray/PIL are missing: the suite then asserts the
honest None return rather than pretending a tray exists.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk  # noqa: E402

import qtranslate.app as A  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


try:
    import pystray  # noqa: F401
    HAVE_PYSTRAY = True
except ImportError:
    HAVE_PYSTRAY = False

root = tk.Tk()
root.withdraw()
stub = A.App.__new__(A.App)
icon = A._make_tray(root, stub)

if HAVE_PYSTRAY:
    ck("_make_tray builds an Icon", icon is not None)
    if icon is not None:
        items = list(getattr(icon, "menu", None) or [])
        texts = []
        for it in items:
            t = getattr(it, "text", "")
            texts.append(t if t else "SEPARATOR")
        # native order (spec §5), minus the leading OS-side double-click
        WANT = ["Show main window", "Dictionary", "Text recognition",
                "History", "Keyboard", "Options...", "About QTranslate",
                "SEPARATOR", "Enable global hotkeys", "Mouse mode",
                "SEPARATOR", "Exit"]
        ck("tray menu order is the native order", texts == WANT,
           "got %s" % texts)
        ck("menu has 2 separators", texts.count("SEPARATOR") == 2,
           str(texts.count("SEPARATOR")))
        ck("Enable global hotkeys is a checkable item",
           any(getattr(i, "checked", None) for i in items
               if getattr(i, "text", "") == "Enable global hotkeys"))
        modes = [m for i in items
                 if getattr(i, "text", "") == "Mouse mode"
                 for m in (getattr(i, "submenu", None) or [])]
        ck("Mouse mode is a radio submenu with 3 modes",
           len(modes) == 3, str(len(modes)))
        ck("Mouse mode's first option is 'Show icon'",
           bool(modes) and modes[0].text == "Show icon",
           modes[0].text if modes else "-")

        # the handler must write the flag it names. Phase 7 (2026-10-16):
        # _make_tray's body moved to qtranslate/windows.py as
        # TrayController.build; A._make_tray is now a forwarder, so
        # inspect.getsource on it would only show the delegator.
        import inspect
        from qtranslate.windows import TrayController
        src = inspect.getsource(TrayController.build)
        ck("Enable-global-hotkeys handler writes General.EnableHotKeys",
           "EnableHotKeys" in src)
        ck("hotkeys toggle keeps a real state cell", "_hotkeys_on[" in src)
else:
    ck("no pystray -> honest None (no fake tray)", icon is None)

# pystray is absent on this host, so the live checks above are skipped. The
# ORDER is still pinned from source -- otherwise a green run here would be a
# single assertion that proves nothing (exactly the trap to avoid).
import re as _re  # noqa: E402

# Phase 7 (2026-10-16): the Menu(...) block moved to windows.py's
# TrayController.build, with app.py's indentation (4 spaces) now at the
# class's method-body indentation (8 spaces).
SRC = open("qtranslate/windows.py", encoding="utf-8").read()
START = SRC.find("menu = Menu(")
END = SRC.find("icon = pystray.Icon(", START)
ck("TrayController.build's Menu(...) block found", 0 <= START < END,
   "start=%d end=%d" % (START, END))
if 0 <= START < END:
    block = SRC[START:END]
    order = _re.findall(r'MenuItem\(\s*"([^"]+)"', block)
    SPEC = ["Show main window", "Dictionary", "Text recognition",
            "History", "Keyboard", "Options...", "About QTranslate",
            "Enable global hotkeys", "Mouse mode", "Exit"]
    ck("source menu order is the native order",
       order[:len(SPEC)] == SPEC, "got %s" % order)
    ck("menu declares exactly 2 separators",
       block.count("Menu.SEPARATOR") == 2,
       str(block.count("Menu.SEPARATOR")))
    ck("the tray menu path draws no window itself", "Toplevel" not in block)

root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_tray_menu: all checks ok (%d assertions)" % n[0])
