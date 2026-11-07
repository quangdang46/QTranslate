"""Regression: dictionary word chips (.tmp DictionaryChipController).

A multi-word dictionary search ("alpha, beta gamma") renders one
clickable chip per word; clicking a chip looks THAT word up, not the
whole field. A single-word search shows no chips and behaves as it
always did.

The lookup itself is stubbed (``dictionary_search.search`` is replaced
by a recorder), so the suite is offline and never touches a provider.

Skips (exit 0) when PySide6 or a usable QApplication is absent -- the
same rule the other Qt suites follow.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s%s" % (name, (" -- " + detail) if detail else ""))


# --- 1. the word split itself ---------------------------------------------
try:
    from qtranslate import dictionary_search as DS
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_dict_chips: dictionary_search does not import (%s)"
          % exc)
    raise SystemExit(0)

ck("comma and space separated words split",
   DS.parse_words("hello world,foo") == ["hello", "world", "foo"])
ck("single letters and punctuation-only tokens are dropped",
   DS.parse_words("a b! c d-") == ["d-"])
ck("duplicates collapse, order kept",
   DS.parse_words("one two one, TWO") == ["one", "two", "TWO"])
ck("letters, apostrophes and hyphens survive",
   DS.parse_words("don't stop well-known") == ["don't", "stop",
                                              "well-known"])
ck("the strip is capped",
   len(DS.parse_words(" ".join(
       chr(97 + i // 26) + chr(97 + i % 26) for i in range(30)))) == 20)
ck("empty input gives no words", DS.parse_words("") == [])
ck("numbers are not chip words",
   DS.parse_words("abc 123 def") == ["abc", "def"])

# --- 2. the window ----------------------------------------------------------
try:
    from PySide6.QtWidgets import QApplication, QPushButton
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_dict_chips: PySide6 is not importable (%s)" % exc)
    raise SystemExit(0)

try:
    from qtranslate.qt.app import QtApp
    import qtranslate.qt.app as _appmod
    # Isolate the history and the options file: this suite must not read
    # or write the user's real History.json / Options.json.
    _appmod.HISTORY_PATH = os.path.join(
        tempfile.mkdtemp(prefix="qt_chips_"), "History.json")
    from qtranslate import config as _C
    _C.DEFAULT_PATH = os.path.join(
        tempfile.mkdtemp(prefix="qt_chips_opt_"), "Options.json")
    from qtranslate.qt.dictionary import DictionaryWindow
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_dict_chips: the Qt front end does not import (%s)"
          % exc)
    raise SystemExit(0)

try:
    app = QtApp([])
except Exception as exc:                       # noqa: BLE001
    print("SKIP regress_dict_chips: no usable QApplication (%s)" % exc)
    raise SystemExit(0)

# Record the words the lookup is asked for; answer instantly so the
# worker thread never leaves the suite hanging.
searched = []
_orig_search = DS.search
DS.search = lambda word, **kw: (searched.append(word), ([], "stub"))[1]

win = None
try:
    win = DictionaryWindow(app)
    win.show()
    app.qapp.processEvents()

    def wait_searched(count, timeout=3.0):
        """The lookup runs on a worker thread; wait for the stub."""
        deadline = time.time() + timeout
        while len(searched) < count and time.time() < deadline:
            time.sleep(0.02)
            app.qapp.processEvents()

    def chips():
        return win.chip_strip.findChildren(QPushButton)

    # --- multi-word input -> chips, first word looked up -----------------
    win.inp.setText("hello world,foo-bar")
    win.do_search()
    app.qapp.processEvents()
    wait_searched(1)

    ck("multi-word input shows the chip strip", win.chip_strip.isVisible())
    words = [b.text() for b in chips()]
    ck("one chip per parsed word", words == ["hello", "world", "foo-bar"],
       str(words))
    ck("the result pane shrank to make room for the chips",
       win.out.geometry().height() == 228,
       "h=%d" % win.out.geometry().height())
    ck("the first word is looked up, not the whole string",
       searched and searched[-1] == "hello", str(searched))
    ck("the field keeps the whole input", win.inp.text() == "hello world,foo-bar")

    # --- a chip click looks up THAT word only -----------------------------
    searched.clear()
    chips()[1].click()
    app.qapp.processEvents()
    wait_searched(1)
    ck("clicking a chip fills the field with that word",
       win.inp.text() == "world", win.inp.text())
    ck("clicking a chip looks up that word only",
       searched == ["world"], str(searched))
    ck("the strip stays up so the other chips remain",
       win.chip_strip.isVisible()
       and [b.text() for b in chips()] == ["hello", "world", "foo-bar"])
    ck("the clicked chip is the selected one",
       chips()[1].property("selected") == "true"
       and chips()[0].property("selected") == "false")

    # --- single-word input behaves as before ------------------------------
    searched.clear()
    win.inp.setText("solo")
    win.do_search()
    app.qapp.processEvents()
    wait_searched(1)
    ck("single-word input hides the chips", not win.chip_strip.isVisible())
    ck("the result pane is back to full height",
       win.out.geometry().height() == 250,
       "h=%d" % win.out.geometry().height())
    ck("single-word input looks up the whole word",
       searched == ["solo"], str(searched))

    # --- junk input never makes chips --------------------------------------
    searched.clear()
    win.inp.setText("a 1 b!")
    win.do_search()
    app.qapp.processEvents()
    ck("input with no valid words makes no chips",
       not win.chip_strip.isVisible()
       and not any(b.text() for b in chips()))
finally:
    try:
        if win is not None:
            win.close()
            win.deleteLater()
    except Exception:
        pass
    DS.search = _orig_search
    try:
        app.qapp.processEvents()
    except Exception:
        pass

if fails:
    print("FAIL regress_dict_chips:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("OK: dictionary word chips (%d checks)" % n[0])
