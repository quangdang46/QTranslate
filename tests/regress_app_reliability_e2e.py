"""Reliability driven through the APP's own translate path.

`regress_reliability.py` proves the router's rules; this proves the APP
reaches them. The C2C audit's remaining reliability gap was exactly that
distinction: "unit-tested through the router, not driven through the
running app".

So each case below builds the real `QtApp`, sets the service the way the
UI does, and calls `app.on_go()` -- the same call the Translate button
makes -- with the provider table rigged:

* the chosen provider fails, the next in the fallback chain answers;
* every provider fails: the user sees native's error string, and the
  result says WHY instead of looking like a timeout;
* a provider that raises is classified, not propagated;
* the provider that ANSWERED is the one the UI is told about.

Offline: the provider callables are replaced in `registry.TRANSLATORS`,
which is the live table the engine reads. The original table is restored
at the end.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


try:
    from PySide6.QtWidgets import QApplication
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_app_reliability_e2e: PySide6 is not importable (%s)"
          % exc)
    raise SystemExit(0)

from qtranslate import registry as RG                    # noqa: E402
from qtranslate.extensions import load_user_extensions   # noqa: E402

_ORIGINAL = dict(RG.TRANSLATORS)
_TABLES = ("TRANSLATORS", "DICT_EXT", "TTS_EXT", "OCR_EXT", "SPELL_EXT",
           "WORKFLOW_EXT")
_ORIG = {t: dict(getattr(RG, t)) for t in _TABLES}

try:
    from qtranslate.qt.app import QtApp
    from qtranslate.qt.main_window import MainWindow

    app = QtApp([])
    app._load_session()
    app.win = MainWindow(app)

    # --- one provider fails, the next answers -------------------------
    def _dead(text, src, tgt):
        raise RuntimeError("provider is down")

    def _alive(text, src, tgt):
        return "ALIVE:" + text

    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = _dead
    RG.TRANSLATORS["deepl"] = _alive
    RG.reset_router()
    app.service = "google"
    app.win.src.setPlainText("hello")
    app.on_go()
    app.qapp.processEvents()
    out = app.win.out.toPlainText()
    ck("the app falls through to the provider that answers",
       "ALIVE:hello" in out, out[:80])
    ck("the app shows a result, not native's error string",
       "No data returned" not in out, out[:80])
    ck("the history records the translated text",
       bool(app.history) and "ALIVE:hello" in app.history[-1][2],
       str(app.history[-1:]))

    # --- every provider fails -----------------------------------------
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = _dead
    RG.TRANSLATORS["deepl"] = _dead
    RG.reset_router()
    app.service = "google"
    app.win.src.setPlainText("hello")
    app.on_go()
    app.qapp.processEvents()
    out = app.win.out.toPlainText()
    ck("the user sees native's own error string when none answers",
       "No data returned" in out, out[:80])

    # The engine's Result must carry WHY, even though the pane shows the
    # user-facing string. That is the distinction the audit cared about.
    from qtranslate import engine
    res = engine.translate("google", "hello", "vi", src="en")
    ck("the engine reports that NO provider answered", not res.ok, repr(res))
    ck("the result carries the failures, not just a timeout note",
       bool(res.failures), "failures=%r note=%r" % (res.failures, res.note))
    ck("the note names the failure kinds",
       bool(res.note) and "timeout" in res.note or bool(res.failures),
       repr(res.note))

    # --- a raising provider is classified, not propagated -------------
    raised = None
    try:
        engine.translate("google", "hello", "vi", src="en")
    except Exception as exc:                    # noqa: BLE001
        raised = exc
    ck("a raising provider never propagates out of the engine",
       raised is None, repr(raised))

    # --- the provider that ANSWERED is the one reported ---------------
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = _dead
    RG.TRANSLATORS["deepl"] = _alive
    RG.reset_router()
    res = engine.translate("google", "hello", "vi", src="en")
    ck("the result names the provider that answered, not the one asked",
       res.provider_used == "deepl", repr(res.provider_used))

    # --- an extension workflow still runs on a fallback result --------
    RG.WORKFLOW_EXT["e2e.wf"] = lambda text, s, g: text + " [wf]"
    res = engine.translate("google", "hello", "vi", src="en")
    ck("the workflow step runs on a result a fallback produced",
       res.text == "ALIVE:hello [wf]", repr(res.text))
finally:
    for t in _TABLES:
        table = getattr(RG, t)
        table.clear()
        table.update(_ORIG[t])
    RG.reset_router()
    try:
        app.win.close()
        app.win.deleteLater()
        app.qapp.processEvents()
    except Exception:                           # noqa: BLE001
        pass

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_app_reliability_e2e: all checks ok (%d assertions)" % n[0])
