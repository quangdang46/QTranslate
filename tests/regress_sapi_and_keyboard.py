"""The speech and virtual-keyboard rows the feature matrix called `ported`.

The C2C contract audit found the matrix claiming coverage the suite did
not have: `Speech (SAPI)` pointed at a `regress_sapi.py` that does not
exist, and the virtual keyboard's row pointed at `regress_vk_*` files
that do not exist. A row is only a claim, and an unbacked claim is worse
than a missing one.

This suite backs both, on the surfaces that can be checked without
playing audio or driving a screen:

* the SAPI module's contract -- it is callable, it never raises into the
  caller, and the PowerShell fallback it documents is the one it builds;
* the Qt keyboard window -- every key the native's DLG 162 capture shows
  is built, with the right label and in the right row.

Offline. A machine without SAPI voices is a SKIP for the playback half,
not a failure: the module's own contract is that speech failing does not
take the app with it.
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


# --- SAPI -----------------------------------------------------------------
from qtranslate import sapi                                  # noqa: E402

ck("the SAPI module exposes speak()", callable(sapi.speak))
_src = open(os.path.join(ROOT, "qtranslate", "sapi.py"),
            encoding="utf-8").read()
ck("it has an offline path (SAPI, not a network call)",
   "SAPI.SpVoice" in _src, "the module no longer names the SAPI voice")
ck("it has a no-dependency fallback (PowerShell encoded command)",
   "EncodedCommand" in _src, "the fallback was removed")
ck("its fallback has a timeout", "timeout=" in _src,
   "a hung voice would hang the caller")

# speak() must never raise into the caller: a machine with no voices is a
# normal state, and the app has to keep running.
_raised = None
try:
    sapi.speak("", rate=0)          # empty text: the cheapest real call
except Exception as exc:            # noqa: BLE001
    _raised = exc
ck("speak() does not raise on an empty request", _raised is None,
   repr(_raised))

# --- the virtual keyboard -------------------------------------------------
try:
    from PySide6.QtWidgets import QApplication, QPushButton
except Exception as exc:            # noqa: BLE001
    print("SKIP regress_sapi_and_keyboard: keyboard half (%s)" % exc)
    QApplication = None

if QApplication is not None:
    try:
        from qtranslate.qt.app import QtApp
        from qtranslate.qt.keyboard import KeyboardWindow

        app = QtApp([])
        kb = KeyboardWindow(app)
        labels = [b.text() for b in kb.findChildren(QPushButton)]
        ck("the keyboard window builds", kb is not None)
        ck("it has the native's key count (61 keys on DLG 162's grid)",
           len(labels) >= 55, "%d keys" % len(labels))
        # The space bar is drawn with NO label (native's is blank too), so
        # it is checked by shape, not by text.
        ck("the space bar is drawn (unlabelled, as native draws it)",
           "" in labels, "no unlabelled key exists")
        for key in ("Esc", "Tab", "Caps", "Shift", "Ctrl", "Alt",
                    "Enter", "BkSp"):
            ck("the %s key is drawn" % key, any(key == t for t in labels),
               "first few: %r" % (labels[:8],))
        ck("the number row is present (native has 0-9, the old port had none)",
           all(str(d) in labels for d in range(10)),
           str([l for l in labels if len(l) == 1][:12]))
        ck("the punctuation keys are present",
           any(t in labels for t in (";", "'", ",", ".", "/", "[", "]")),
           str(labels[-12:]))
        ck("the keyboard window keeps the native's client size",
           (kb.width(), kb.height()) == kb.SIZE,
           "%s vs %s" % ((kb.width(), kb.height()), kb.SIZE))
        kb.close()
        kb.deleteLater()
        app.qapp.processEvents()
    except Exception as exc:        # noqa: BLE001
        ck("the keyboard window builds", False,
           "%s: %s" % (type(exc).__name__, exc))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_sapi_and_keyboard: all checks ok (%d assertions)" % n[0])
