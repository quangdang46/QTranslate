"""Pin menu-1 items 60/61/62 (the last dead toggles) — offscreen Qt.

* 60 "Clear input on Drag && Drop" -> General.ClearInputOnDragDrop:
  ON (default) a drop REPLACES the source pane; OFF appends.
* 61 "Auto-cleanup of translation" -> General.AutoCleanupTranslation:
  an emptied source clears the result/back panes (default off).
* 62 "Save contents on exit" -> General.SaveContentsOnExit: gates
  Contents.* persist/restore (default on = pre-toggle behaviour).

SAFETY: config.DEFAULT_PATH points at a throwaway file — the Options
pages' write-through rule would otherwise touch the user's real
Options.json (that accident already happened once).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from PySide6.QtWidgets import QApplication  # noqa: E402

qapp = QApplication.instance() or QApplication([])

_tmp = tempfile.mkdtemp(prefix="qt_mnu_")
import qtranslate.config as _C  # noqa: E402
_C.DEFAULT_PATH = os.path.join(_tmp, "Options.json")
import qtranslate.qt.app as _appmod  # noqa: E402
_appmod.HISTORY_PATH = os.path.join(_tmp, "History.json")
import qtranslate.qt.app as _qa  # noqa: E402
from qtranslate.qt.main_window import MainWindow  # noqa: E402

app = _qa.QtApp([])
win = MainWindow(app)
app.win = win  # _persist_contents/_restore_contents read app.win
win.show()
qapp.processEvents()


def _write_general(**kw):
    cfg = _C.load() or {}
    cfg.setdefault("General", {}).update(kw)
    _C.save(cfg)


def _menu_action(text):
    # _nav_menu execs modally; _build_nav_menu returns the same menu
    # for inspection.
    m = win._build_nav_menu()
    for a in m.actions():
        if a.text() == text:
            return a
    return None


# --- the menu items are live checkables, not dead entries ---------------
for label, key, default_on in [
        ("Clear input on Drag && Drop", "ClearInputOnDragDrop", True),
        ("Auto-cleanup of translation", "AutoCleanupTranslation", False),
        ("Save contents on exit", "SaveContentsOnExit", True)]:
    a = _menu_action(label)
    ck("menu has %r" % label, a is not None)
    if a is not None:
        ck("%r is checkable" % label, a.isCheckable())
        ck("%r defaults to %s" % (label, default_on),
           a.isChecked() == default_on)

# --- 60: drop replaces by default, appends when disabled -----------------
win.src.setPlainText("existing text")
win._drop_text("dropped")
ck("drop replaces input by default",
   win.src.toPlainText() == "dropped", win.src.toPlainText())
_write_general(ClearInputOnDragDrop=False)
win.src.setPlainText("existing text")
win._drop_text("dropped")
ck("drop appends when ClearInputOnDragDrop is off",
   win.src.toPlainText() == "existing text\ndropped",
   win.src.toPlainText())
_write_general(ClearInputOnDragDrop=True)

# --- 61: emptied source clears result panes only when enabled ------------
win.out.setPlainText("a translation")
win.back.setPlainText("a back translation")
win.src.setPlainText("")
win._src_text_changed()
qapp.processEvents()
ck("auto-cleanup off keeps stale result",
   win.out.toPlainText() == "a translation")
_write_general(AutoCleanupTranslation=True)
win.src.setPlainText("")
win._maybe_auto_cleanup()
ck("auto-cleanup on clears result+back",
   win.out.toPlainText() == "" and win.back.toPlainText() == "")
# Non-empty source must NOT clean up.
win.out.setPlainText("keep me")
win.src.setPlainText("still typing")
win._maybe_auto_cleanup()
ck("auto-cleanup leaves non-empty source alone",
   win.out.toPlainText() == "keep me")
_write_general(AutoCleanupTranslation=False)

# --- 62: Contents persist/restore gated ----------------------------------
win.src.setPlainText("persist me")
win.out.setPlainText("and me")
app._persist_contents()
ck("contents persist by default",
   (_C.load().get("Contents") or {}).get("EditSource") == "persist me")
_write_general(SaveContentsOnExit=False)
win.src.setPlainText("")
win.out.setPlainText("")
app._persist_contents()
ck("disabled save-on-exit writes nothing new",
   (_C.load().get("Contents") or {}).get("EditSource") == "persist me")
ck("_contents_enabled honours the flag",
   app._contents_enabled() is False)
_write_general(SaveContentsOnExit=True)
ck("_contents_enabled defaults on",
   app._contents_enabled() is True)

# --- 85-88: the "On startup" radio group --------------------------------
cfg = _C.load() or {}
cfg.setdefault("General", {}).pop("MainWindowStartupAction", None)
_C.save(cfg)
m = win._build_nav_menu()
texts = [a.text() for a in m.actions()]
ck("startup group present", "On startup" in texts, str(texts))
acts = {a.text(): a for a in m.actions()}
for label in ("Show window", "Minimize to tray",
              "Restore previous state"):
    ck("startup action %r exists and is checkable" % label,
       label in acts and acts[label].isCheckable())
# Legacy config without the key derives from MainWindowShowOnLoad.
cfg = _C.load() or {}
cfg["General"]["MainWindowShowOnLoad"] = False
_C.save(cfg)
m2 = win._build_nav_menu()
a2 = {a.text(): a for a in m2.actions()}
ck("missing StartupAction derives tray from ShowOnLoad",
   a2["Minimize to tray"].isChecked()
   and not a2["Show window"].isChecked())
# Picking an action persists the int (not bool) + the legacy mirror.
a2["Restore previous state"].trigger()
ck("startup action persists int 2",
   (_C.load()["General"].get("MainWindowStartupAction") == 2)
   and _C.load()["General"].get("MainWindowShowOnLoad") is False,
   str(_C.load()["General"]))

# --- 130: Help submenu ----------------------------------------------------
help_act = None
for a in m.actions():
    if a.menu() is not None and a.text() == "Help":
        help_act = a
        break
ck("Help is a submenu", help_act is not None)
if help_act is not None:
    htexts = [x.text() for x in help_act.menu().actions()]
    ck("help submenu entries",
       all(t in htexts for t in
           ("How to use", "Contact us", "Check for updates",
            "Automatically check for updates")), str(htexts))
    auto_act = [x for x in help_act.menu().actions()
                if x.text() == "Automatically check for updates"][0]
    ck("auto-check reflects Update.CheckForUpdates",
       auto_act.isChecked()
       == bool((_C.load().get("Update") or {})
               .get("CheckForUpdates", True)))
    before = auto_act.isChecked()
    auto_act.trigger()
    ck("auto-check toggle writes the Updates key",
       (_C.load().get("Update") or {}).get("CheckForUpdates")
       == (not before))

# --- Advanced.RemoveLineBreaks on the VISIBLE pane (.tmp
#     prepareInputText via UpdateInputText) -------------------------
cfg = _C.load() or {}
cfg.setdefault("Advanced", {})["RemoveLineBreaks"] = True
_C.save(cfg)
try:
    win._rlb_cache = None          # force the mtime-keyed reload
    win.src.setPlainText("line one\nline two\r\nline three")
    ck("pane flattens newlines",
       win.src.toPlainText() == "line one line two line three",
       repr(win.src.toPlainText()))
    win.src.setPlainText("a  b   c")
    # Kotlin's replace("  "," ") is single-pass non-overlapping:
    # "a  b   c" -> "a b  c" (one pair survives) -- pinned verbatim.
    ck("pane collapses double space (single pass)",
       win.src.toPlainText() == "a b  c",
       repr(win.src.toPlainText()))
    win.src.setPlainText("  padded  ")
    ck("pane trims edges", win.src.toPlainText() == "padded",
       repr(win.src.toPlainText()))
    win.src.setPlainText("plain text stays")
    ck("clean text untouched",
       win.src.toPlainText() == "plain text stays")
finally:
    cfg["Advanced"]["RemoveLineBreaks"] = False
    _C.save(cfg)
    win.src.setPlainText("")

win.close()

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_menu_toggles_60_62: all checks ok (%d assertions)" % n[0])
