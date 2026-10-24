"""History persists across restarts; the main strip's highlight moves.

Two operator reports (2026-10-24, captures 2167/2168):

1. The History window came up EMPTY after a restart: the port held the
   history in memory only, so every restart wiped it. It now persists
   to ``History.json`` in the per-user data dir -- written on every
   push/delete/clear, loaded at boot, capped at 500 entries.
2. Clicking a provider in the MAIN window's strip switched the service
   but the FIRST button kept the highlight forever (the build set
   ``selected`` on button 0 and nothing ever moved it).
   ``highlight_service`` moves it now, at click time AND at boot (a
   session saved on DeepL must not open with Google lit up).

Offscreen, providers rigged, the history file under a temp dir.
"""
import io
import json
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


from qtranslate import registry as RG                    # noqa: E402
import qtranslate.qt.app as appmod                       # noqa: E402
from qtranslate.qt.app import QtApp                      # noqa: E402
from qtranslate.qt.main_window import MainWindow         # noqa: E402

_ORIG = dict(RG.TRANSLATORS)
root = tempfile.mkdtemp(prefix="qt_hist_")
CFG = os.path.join(root, "History.json")
appmod.HISTORY_PATH = CFG                # point the persistence at temp
try:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = lambda t, s, g: "GOOGLE:" + t
    RG.TRANSLATORS["deepl"] = lambda t, s, g: "DEEPL:" + t
    RG.reset_router()

    # --- 1. a push writes the file; a NEW app reads it back ------------
    app = QtApp([])
    app._load_session()
    app.source, app.target = "en", "vi"
    app.win = MainWindow(app)
    ck("a fresh app starts with an empty history", app.history == [],
       str(app.history[:1]))
    app.push_hist("google", "hello", "GOOGLE:hello")
    app.push_hist("deepl", "morning", "DEEPL:morning")
    ck("the push wrote the file",
       os.path.exists(CFG) and len(json.load(io.open(CFG,
                                                     encoding="utf-8"))) == 2,
       repr(io.open(CFG, encoding="utf-8").read()[:80]))

    app2 = QtApp([])
    ck("a RESTARTED app restores the history",
       [e[2] for e in app2.history] == ["GOOGLE:hello", "DEEPL:morning"],
       str(app2.history))

    # --- 2. clear and delete persist too -------------------------------
    from qtranslate.qt.history_window import HistoryWindow
    hw = HistoryWindow(app2)
    hw._delete(0, app2.history[0])
    ck("a delete persists",
       len(json.load(io.open(CFG, encoding="utf-8"))) == 1)
    hw._clear()
    ck("a clear persists an empty list",
       json.load(io.open(CFG, encoding="utf-8")) == [])
    hw.close()

    # --- 3. the main strip's highlight moves with the service ----------
    app.win.show()
    app.qapp.processEvents()
    btn = {b.property("service"): b for b in app.win.tabs}
    ck("the strip carries both rigged providers",
       set(btn) >= {"google", "deepl"}, str(sorted(btn)))
    ck("the restored service is highlighted at boot",
       btn["google"].property("selected") == "true"
       and btn["deepl"].property("selected") == "false",
       str(btn["google"].property("selected")))

    app.switch_service("deepl")
    ck("clicking a provider MOVES the highlight",
       btn["deepl"].property("selected") == "true"
       and btn["google"].property("selected") == "false",
       "%s/%s" % (btn["google"].property("selected"),
                  btn["deepl"].property("selected")))
    app.switch_service("google")
    ck("switching back moves it again",
       btn["google"].property("selected") == "true"
       and btn["deepl"].property("selected") == "false")

    app.win.close()
finally:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIG)
    RG.reset_router()
    appmod.HISTORY_PATH = None
    import shutil
    shutil.rmtree(root, ignore_errors=True)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_history_persist: all checks ok (%d assertions)" % n[0])
