"""Regression: history back/forward restores the full entry and the live state.

qt-lg6: ``_nav_history`` used to restore only the pane texts -- the
service, the language pair and the pre-browse live state were all
ignored, so stepping forward past the newest entry left the last
history entry on screen forever.

Now: the first step away snapshots the live panes (texts, service,
pair); every step into history restores the entry's service through
``switch_service``, its stored pair through the combos, and both panes;
``new == len(history)`` restores the snapshot.

Offscreen, providers rigged, the history file under a temp dir.
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


from qtranslate import registry as RG                    # noqa: E402
import qtranslate.qt.app as appmod                       # noqa: E402
from qtranslate.qt.app import QtApp                      # noqa: E402
from qtranslate.qt.main_window import MainWindow         # noqa: E402
from qtranslate import config as _CFG                    # noqa: E402

# Isolate from the developer's live Options.json: the strip and the
# highlight follow ordered_services()/DisabledServices, so a real
# config would change which service cells exist.
_CFG.DEFAULT_PATH = os.path.join(tempfile.mkdtemp(prefix="qt-cfg-"),
                                 "Options.json")

_ORIG = dict(RG.TRANSLATORS)
root = tempfile.mkdtemp(prefix="qt_nav_")
appmod.HISTORY_PATH = os.path.join(root, "History.json")
try:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = lambda t, s, g: "GOOGLE:" + t
    RG.TRANSLATORS["deepl"] = lambda t, s, g: "DEEPL:" + t
    RG.reset_router()

    app = QtApp([])
    app._load_session()
    app.win = MainWindow(app)
    win = app.win

    # Two entries under DIFFERENT services and pairs.
    app.service, app.source, app.target = "google", "en", "vi"
    app.push_hist("google", "hello", "GOOGLE:hello",
                  src_lang="en", tgt_lang="vi")
    app.service, app.source, app.target = "deepl", "auto", "en"
    app.push_hist("deepl", "morning", "DEEPL:morning",
                  src_lang="auto", tgt_lang="en")

    # The live state the user is looking at before browsing.
    app.service, app.source, app.target = "google", "en", "vi"
    win.src.setPlainText("live question")
    win.out.setPlainText("LIVE:answer")
    app._nav_idx = len(app.history)

    # --- back once: the newest entry, with its own service+pair -------
    app.on_back()
    ck("back lands on the newest entry's text",
       win.src.toPlainText() == "morning"
       and win.out.toPlainText() == "DEEPL:morning",
       "%r / %r" % (win.src.toPlainText(), win.out.toPlainText()))
    ck("back restores the entry's SERVICE",
       app.service == "deepl", app.service)
    ck("the strip highlight follows the entry's service",
       any(b.property("service") == "deepl"
           and b.property("selected") == "true" for b in win.tabs))
    ck("back restores the entry's language pair",
       (app.source, app.target) == ("auto", "en"),
       "%s -> %s" % (app.source, app.target))
    ck("the source combo shows Auto-Detect for an auto entry",
       win.cmb_src.currentText() == "Auto-Detect",
       win.cmb_src.currentText())

    # --- back again: the older entry ----------------------------------
    app.on_back()
    ck("second back shows the older entry",
       win.src.toPlainText() == "hello"
       and win.out.toPlainText() == "GOOGLE:hello")
    ck("the older entry's service is restored",
       app.service == "google", app.service)
    ck("the older entry's pair is restored",
       (app.source, app.target) == ("en", "vi"),
       "%s -> %s" % (app.source, app.target))

    # --- forward back to live: the snapshot returns -------------------
    app.on_forward()
    ck("forward shows the newer entry again",
       win.src.toPlainText() == "morning")
    app.on_forward()
    ck("forward past the newest restores the live TEXTS",
       win.src.toPlainText() == "live question"
       and win.out.toPlainText() == "LIVE:answer",
       "%r / %r" % (win.src.toPlainText(), win.out.toPlainText()))
    ck("forward past the newest restores the live SERVICE",
       app.service == "google", app.service)
    ck("forward past the newest restores the live PAIR",
       (app.source, app.target) == ("en", "vi"),
       "%s -> %s" % (app.source, app.target))
    ck("the cursor is back at 'now'",
       app._nav_idx == len(app.history), str(app._nav_idx))
    ck("the browsing guard reads live again",
       win._browsing_history() is False)

    # --- bounds ---------------------------------------------------------
    app.on_back()
    app.on_back()
    n_before = app._nav_idx
    app.on_back()                      # before the oldest: no-op
    ck("back past the oldest is a no-op",
       app._nav_idx == n_before == 0, str(app._nav_idx))
    app.on_forward()
    app.on_forward()
    app.on_forward()                   # past 'now': clamped at len
    ck("forward past 'now' is clamped",
       app._nav_idx == len(app.history), str(app._nav_idx))

    # --- a fresh translation invalidates the browse snapshot -----------
    app.on_back()
    ck("browsing again works after the round trip",
       win.src.toPlainText() == "morning")
    app.push_hist("google", "again", "GOOGLE:again",
                  src_lang="en", tgt_lang="vi")
    app.on_forward()
    ck("a new push resets the cursor to 'now'",
       app._nav_idx == len(app.history)
       and app._nav_live is None,
       "%s / %r" % (app._nav_idx, app._nav_live))

    # --- legacy 3-slot entries still navigate --------------------------
    app.history.append(("google", "legacy", "LEGACY:out"))
    app._nav_idx = len(app.history)
    app.on_back()
    ck("a persisted triple restores service+panes",
       app.service == "google"
       and win.src.toPlainText() == "legacy"
       and win.out.toPlainText() == "LEGACY:out",
       "%s / %r / %r" % (app.service, win.src.toPlainText(),
                         win.out.toPlainText()))
    ck("a triple keeps the current pair (no stored slots)",
       (app.source, app.target) == ("auto", "en"),
       "%s -> %s" % (app.source, app.target))
finally:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIG)
    RG.reset_router()
    for w in [app.win]:
        try:
            w.close()
        except Exception:
            pass

if fail:
    print("FAIL regress_history_nav:")
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_history_nav: all checks ok (%d assertions)" % n[0])
