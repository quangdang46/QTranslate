"""Translate must not freeze the window.

The evidence came from measurement, not from reading the code:
``tools/measure_translate.py`` timed ``QtApp.on_go()`` with a 400ms
provider and got 402ms -- the UI thread held for essentially the whole
network round trip, so the window was frozen with every translation.
The port's own overhead was ~3ms; the network is the whole story.

The FIX is to run the request on a worker and cross only the finished
translation back to the UI thread (``QtApp._start_translation`` +
``_on_ui``). This suite pins three things:

1. one translate holds the UI thread for FAR less than the provider
   takes (the regression number: under a tenth of the latency);
2. the result still lands -- pane text AND history -- through
   ``wait_for_translation()``;
3. a second request while one is in flight is dropped, not queued
   (native keeps one task, and stacked answers arrive in stale order).
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import registry as RG  # noqa: E402
from qtranslate.qt.app import QtApp  # noqa: E402
from qtranslate.qt.main_window import MainWindow  # noqa: E402

ORIGINAL = dict(RG.TRANSLATORS)
LATENCY = 0.4


def slow(text, src, tgt):
    time.sleep(LATENCY)
    return "MEASURED:" + text


try:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = slow
    RG.reset_router()

    app = QtApp([])
    app._load_session()
    # _load_session reads the REAL Options.json; a live session whose
    # source equals its target makes the engine echo the input instead
    # of calling the rigged provider. Pin the pair so this suite tests
    # the worker, not the machine's config.
    app.source, app.target = "en", "vi"
    app.win = MainWindow(app)
    app.service = "google"

    # --- the UI thread is not held by the network ----------------------
    app.win.src.setPlainText("hello")
    start = time.perf_counter()
    started = app.on_go()
    blocked = time.perf_counter() - start
    # If on_go returned False the worker never ran, and the check below
    # would wait on nothing -- so the call itself has to have started one.
    ck("on_go starts a worker", started, repr(started))
    ck("one translate barely holds the UI thread",
       blocked < LATENCY / 10,
       "held %.0fms for a %.0fms provider" % (blocked * 1000,
                                              LATENCY * 1000))
    # --- ... and the finished translation still lands ----------------
    ok = app.wait_for_translation(timeout=10.0)
    ck("the background request finishes", ok)
    ck("the result pane shows the translation",
       "MEASURED:hello" in app.win.out.toPlainText(),
       app.win.out.toPlainText()[:60])
    ck("the history keeps the finished translation",
       bool(app.history)
       and "MEASURED:hello" in app.history[-1][2],
       str(app.history[-1:]))
    # --- a request on top of a live one is dropped, not stacked -------
    RG.TRANSLATORS["google"] = lambda t, s, g: (time.sleep(LATENCY),
                                                "SECOND:" + t)[1]
    RG.reset_router()
    app.win.src.setPlainText("second")
    app.on_go()
    dropped = app.on_go() is False
    # Give the first worker its slot, then clean up deterministically.
    app.wait_for_translation(timeout=10.0)
    ck("a second request while one runs is dropped", dropped)

    try:
        app.win.close()
        app.win.deleteLater()
        app.qapp.processEvents()
    except Exception:                           # noqa: BLE001
        pass
finally:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(ORIGINAL)
    RG.reset_router()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_translate_off_ui: all checks ok (%d assertions)" % n[0])
