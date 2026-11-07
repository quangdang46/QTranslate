#!/usr/bin/env python3
""".tmp selectionReadSource (TRANSLATE_AND_READ): General.
SelectionReadSource picks WHICH text mouse-mode-3 speaks --
"translation" (default: the result, after it lands) or "source"
(the captured selection, immediately, in the source language)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from PySide6.QtWidgets import QApplication  # noqa: E402
_qapp = QApplication.instance() or QApplication([])

from qtranslate import config as _C  # noqa: E402
_saved = _C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
_C.DEFAULT_PATH = _tmp

from qtranslate.qt.app import QtApp  # noqa: E402
from qtranslate.core import Result  # noqa: E402

app = QtApp([])

# Capture what _translate_captured does without real translation.
started = {}
orig_start = app._start_translation
orig_popup_loading = getattr(app, "_popup_loading", None)
spoken = []
orig_speak = app._speak
app._popup_loading = lambda t: None
app._speak = lambda text, lang="": spoken.append((text, lang))
app._start_translation = lambda text, done: (
    started.setdefault("done", done), True)[1]
try:
    # --- default: TRANSLATION -------------------------------------
    app._translate_captured("hello", speak=True)
    ck("default: no immediate speak", spoken == [], repr(spoken))
    done = started["done"]
    done("hello", Result("google", "xin chào"))
    ck("default: speaks result", spoken == [("xin chào", "")],
       repr(spoken))
    ck("default read_source", app._read_source() == "translation")

    # --- SOURCE ----------------------------------------------------
    spoken.clear()
    started.clear()
    cfg = _C.load() or {}
    cfg.setdefault("General", {})["SelectionReadSource"] = "source"
    _C.save(cfg)
    ck("source read_source", app._read_source() == "source")

    app.source = "en"
    app._translate_captured("bonjour", speak=True)
    ck("source: speaks selection immediately",
       spoken == [("bonjour", "en")], repr(spoken))
    # ...and the translation result is NOT spoken a second time.
    done = started["done"]
    done("bonjour", Result("google", "xin chào"))
    ck("source: result not spoken", spoken == [("bonjour", "en")],
       repr(spoken))

    # auto source -> falls back to the detected language cache
    spoken.clear()
    started.clear()
    app.source = "auto"
    app._detected_src = "fr"
    app._translate_captured("salut", speak=True)
    ck("source auto uses detected",
       spoken == [("salut", "fr")], repr(spoken))

    # --- options page writer ---------------------------------------
    from PySide6.QtWidgets import QComboBox
    from qtranslate.qt.options import languages as LANG

    class _Cmb:
        def __init__(self, i):
            self.i = i
        def currentIndex(self):
            return self.i

    LANG._set_read_source(_Cmb(0))
    ck("writer translation",
       app._read_source() == "translation")
    LANG._set_read_source(_Cmb(1))
    ck("writer source", app._read_source() == "source")
    LANG._set_read_source(_Cmb(9))   # out of range -> translation
    ck("writer oob safe",
       app._read_source() == "translation")
finally:
    app._start_translation = orig_start
    app._speak = orig_speak
    if orig_popup_loading is not None:
        app._popup_loading = orig_popup_loading
    _C.DEFAULT_PATH = _saved
    try:
        os.unlink(_tmp)
    except OSError:
        pass

if FAIL:
    print("\nregress_read_source: %d FAILURES" % len(FAIL))
    sys.exit(1)
print("\nregress_read_source: all checks ok")
