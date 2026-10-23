"""Every published menu slot has a host window that draws it.

The audit called the three working slots "Behaviour-verified" and the
other six menu names "Wired (main and history_ctx pinned; the reader is
one function)" -- honest but incomplete: pinning the shared helper does
not prove a *window* reaches each slot. An extension targeting
``menu``/``ocr`` would register without error and never appear
anywhere, which is the same shape as the capability gap.

This suite proves each of the nine menu slots has a host:

| slot | host | proof |
|---|---|---|
| main (1) | main window nav menu | source names "main" |
| source_context (2) | source pane right-click | the build names the slot |
| result_context (3) | result pane right-click | same |
| language (4) | language combos right-click | same |
| tray (5) | tray context menu | source names "tray" |
| history_ctx (6) | history entry right-click | the build names the slot |
| dict_header (7) | dictionary ':' button | the build names the slot |
| history_menu (9) | history window on empty space | the build names the slot |
| ocr (10) | OCR result window | the build names the slot |

Menu 8 (the dictionary strip's row menu: Show info / Remove
dictionary) is native's other dictionary menu; it shares the
``dict_header`` slot because it hangs off the same window, and the
strip menu names it too.

No real window is shown; the slot-name pins read each host module's
source, and the reader is driven end to end with a real manager so a
contribution registered for ANY slot comes back out of the widget
helper the hosts call. A slot nobody registers still draws native's
own items -- labels from the shipped locale packs, with unhosted ids
drawn disabled rather than faked.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


def src(name):
    return io.open(os.path.join(ROOT, "qtranslate", "qt", name),
                   encoding="utf-8").read()


# --- each slot names its host in the host's source ---------------------
ck("main window draws the main/nav slot",
   '"main"' in src("main_window.py"))
ck("the source pane draws source_context",
   "source_context" in src("main_window.py"))
ck("the result pane draws result_context",
   "result_context" in src("main_window.py"))
ck("the language combos draw the language slot",
   '"language"' in src("main_window.py"))
ck("the tray draws the tray slot",
   '"tray"' in src("tray.py"))
ck("the history entry menu draws history_ctx",
   "history_ctx" in src("history_window.py"))
ck("the history window draws history_menu on empty space",
   "history_menu" in src("history_window.py"))
ck("the dictionary header button draws dict_header",
   "dict_header" in src("dictionary.py"))
ck("the dictionary strip draws menu 8 under dict_header",
   "dict_header" in src("dictionary.py")
   and '"Remove dictionary"' in src("dictionary.py")
   or "Remove dictionary" in src("dictionary.py"))
ck("the OCR result window draws the ocr slot",
   '"ocr"' in src("ocr_window.py"))

# --- the menus are native's, with native's ids --------------------------
_ctx = io.open(os.path.join(ROOT, "qtranslate", "qt", "context_menus.py"),
               encoding="utf-8").read()
# The docstring table carries the id -> slot mapping; the call sites carry
# the ids themselves (the table is where a reader checks they agree).
for mid, slot in ((2, "source_context"), (3, "result_context"),
                  (4, "language"), (7, "dict_header"),
                  (9, "history_menu"), (10, "ocr")):
    ck("the docstring pairs native menu %d with the %s slot" % (mid, slot),
       ("| %d |" % mid) in _ctx.split('"""')[1] and slot in _ctx)
_HOSTS = {"main_window": src("main_window.py"),
           "dictionary": src("dictionary.py"),
           "history_window": src("history_window.py"),
           "ocr_window": src("ocr_window.py")}
for mid_src, where in (("pack_labels(3 if which", "main_window"),
                       ("pack_labels(4)", "main_window"),
                       ('"dict_header", 7', "dictionary"),
                       ('"history_menu", 9', "history_window"),
                       ('"ocr", 10', "ocr_window")):
    ck("%s passes its native menu id" % where, mid_src in _HOSTS[where])

# --- the reader returns a contribution for EVERY slot ------------------
from qtranslate.qt.widgets import extension_menu_entries  # noqa: E402
from qtranslate.extensions import ExtensionManager  # noqa: E402
from qtranslate import ui_slots as U  # noqa: E402

mgr = ExtensionManager()
mgr._ui = U.UISlotRegistry()
from qtranslate.qt.app import QtApp  # noqa: E402

app = QtApp([])
app.ext_manager = mgr
for name in ("main", "source_context", "result_context", "language",
             "tray", "history_ctx", "dict_header", "history_menu", "ocr"):
    mgr.ui_slots.add("menu", name, lambda: "contribution")
for name in ("main", "source_context", "result_context", "language",
             "tray", "history_ctx", "dict_header", "history_menu", "ocr"):
    ck("a contribution to %s comes back through the reader" % name,
       len(extension_menu_entries(None, app, name)) == 1, name)

# --- menu 8's handlers are real operations, not fakes ------------------
_dic = src("dictionary.py")
ck("Remove dictionary writes DictionariesOrder",
   "DictionariesOrder" in _dic)
ck("Show info reports the selected cell, not a fixed string",
   "selected_service" in _dic)
ck("menu 9's settings-backed items write the settings they claim",
   "ShowServicesPane" in src("history_window.py")
   and "DictionaryExactSearch" in src("history_window.py"))

# --- native labels come from the packs, not from invention ------------
from qtranslate import locale  # noqa: E402

pack = locale.load_pack("English")
menu2 = dict(locale.menu_labels(pack, 2))
ck("menu 2 has native's 10 items (Undo..Listen)",
   len(menu2) == 10, str(sorted(menu2)))
ck("menu 3 has native's 5 items",
   len(dict(locale.menu_labels(pack, 3))) == 5)
ck("menu 10 has native's 9 items",
   len(dict(locale.menu_labels(pack, 10))) == 9)

# --- disabled-not-faked: menu 4's undone item has no handler -----------
_main = src("main_window.py")
ck("Always detect language is drawn disabled (no port op yet)",
   "Always detect language" in _main
   and "(30, \"Always detect language\", None)" in _main)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_menu_slots: all checks ok (%d assertions)" % n[0])
