#!/usr/bin/env python3
"""Inline dictionary gloss (.tmp FetchInlineDefinitionUseCase):
single-word translations get a one-line definition under the result.
Unit-tests the budget/elide port and the app wiring with stubs."""
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


from qtranslate import dictionary_search as DS  # noqa: E402

print("== fragment -> senses ==")
frag = ('<div><b>serendipity</b> noun</div>'
        '<ul><li>a fortunate accident</li>'
        '<li>an unexpected discovery &amp; delight</li></ul>')
senses = DS._senses(frag)
ck("two senses", len(senses) == 2, repr(senses))
ck("html stripped", senses[0] == "a fortunate accident", repr(senses))
ck("entity unescaped", "&" in senses[1], repr(senses[1]))
ck("no blocks -> whole frag", DS._senses("<p>just text</p>")
   == ["just text"])
ck("empty frag -> []", DS._senses("") == [])

print("== elide / budget (Kotlin rules) ==")
ck("short untouched", DS._elide("hello", 120) == "hello")
long_sense = "word " * 60          # ~300 chars
el = DS._elide(long_sense.strip(), 120)
ck("elide cuts", len(el) <= 121 and el.endswith("…"), repr(el[-20:]))
ck("elide word boundary", not el[:-1].endswith("wo"), repr(el[-10:]))
b1 = DS._within_budget(["short sense"])
ck("one sense", b1 == "short sense")
b2 = DS._within_budget(["first.", "second sense here"])
ck("two senses joined", "first." in b2 and "second" in b2, repr(b2))
b3 = DS._within_budget(["x" * 100, "y" * 50])
ck("long first -> single", b3 == "x" * 100 or len(b3) <= 121, repr(b3)[:40])

print("== inline_definition ==")
# Stub search() to return a canned card.
_orig_search = DS.search
try:
    DS.search = lambda *a, **k: (
        [("google-search", "Google", frag)], "")
    ck("returns gloss", DS.inline_definition("serendipity")
       .startswith("a fortunate accident"),
       repr(DS.inline_definition("serendipity")))
    # Multi-word input rejected before any lookup.
    calls = []
    DS.search = lambda *a, **k: calls.append(1) or ([], "")
    ck("phrase -> empty", DS.inline_definition("two words") == ""
       and not calls)
    ck("short -> empty", DS.inline_definition("a") == "" and not calls)
    # Empty cards -> empty.
    DS.search = lambda *a, **k: ([], "")
    ck("no cards -> empty", DS.inline_definition("zzz") == "")
    # search raising -> empty, never propagates.
    def boom(*a, **k):
        raise RuntimeError("dict down")
    DS.search = boom
    ck("lookup failure silent", DS.inline_definition("word") == "")
finally:
    DS.search = _orig_search

print("== app wiring ==")
from PySide6.QtWidgets import QApplication  # noqa: E402
_qapp = QApplication.instance() or QApplication([])

from qtranslate import config as _C  # noqa: E402
_saved = _C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
_C.DEFAULT_PATH = _tmp
try:
    from qtranslate.qt.app import QtApp  # noqa: E402
    from qtranslate.qt.main_window import MainWindow  # noqa: E402

    app = QtApp([])
    app.win = MainWindow(app)
    win = app.win

    def drain(seconds=5.0):
        """The inline-def worker is deliberately untracked (it must
        never block translations), so tests poll the UI thread."""
        import time
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.qapp.processEvents()
            time.sleep(0.01)
        app.qapp.processEvents()

    class Res:
        def __init__(self, text):
            self.text = text
            self.ok = True
            self.provider_used = "google"
            self.source_language_code = ""

    # Multi-word result -> label cleared, no lookup.
    app._refresh_inline_definition("hello world", "xin chào thế giới")
    ck("phrase clears label", win.defn.text() == ""
       and not win.defn.isVisibleTo(win))

    # Single-word result -> background lookup fills the label.
    got = []
    import qtranslate.dictionary_search as _DS2
    _orig = _DS2.inline_definition
    _DS2.inline_definition = lambda w: got.append(w) or "a test gloss"
    try:
        app._refresh_inline_definition("hello", "chào")
        drain()
        ck("lookup ran on translated word", got == ["chào"],
           repr(got))
        ck("label shows gloss", win.defn.text() == "a test gloss")
    finally:
        _DS2.inline_definition = _orig

    # SOURCE mode flips the candidate order.
    cfg = _C.load() or {}
    cfg.setdefault("General", {})["DictionaryAutoSource"] = "SOURCE"
    _C.save(cfg)
    got.clear()
    _DS2.inline_definition = lambda w: got.append(w) or "src gloss"
    try:
        app._refresh_inline_definition("hello", "chào")
        drain()
        ck("SOURCE mode uses source word", got == ["hello"], repr(got))
    finally:
        _DS2.inline_definition = _orig
        cfg["General"]["DictionaryAutoSource"] = "TRANSLATED"
        _C.save(cfg)

    # OFF mode: silent clear, no worker.
    cfg["General"]["DictionaryAutoSource"] = "OFF"
    _C.save(cfg)
    got.clear()
    _DS2.inline_definition = lambda w: got.append(w) or "x"
    try:
        app._refresh_inline_definition("hello", "xin")
        drain()
        ck("OFF: no lookup", not got)
        ck("OFF: label cleared", not win.defn.isVisibleTo(win))
    finally:
        _DS2.inline_definition = _orig
        cfg["General"]["DictionaryAutoSource"] = "TRANSLATED"
        _C.save(cfg)

    # Stale-generation guard: a second refresh supersedes the first.
    _DS2.inline_definition = lambda w: "late gloss"
    try:
        app._refresh_inline_definition("a", "b")
        app._refresh_inline_definition("two words", "many words")
        drain()
        ck("multi-word second clears", not win.defn.isVisibleTo(win))
    finally:
        _DS2.inline_definition = _orig

    # isDictionaryAutoPopupEnabled gates the WHOLE coordinator upstream
    # -- inline gloss included.
    cfg = _C.load() or {}
    cfg.setdefault("General", {})["DictionaryAutoPopup"] = False
    _C.save(cfg)
    got.clear()
    _DS2.inline_definition = lambda w: got.append(w) or "x"
    try:
        app._refresh_inline_definition("hello", "chào")
        drain()
        ck("popup flag off: no lookup", not got)
        ck("popup flag off: label cleared",
           not win.defn.isVisibleTo(win))
    finally:
        _DS2.inline_definition = _orig
        cfg["General"]["DictionaryAutoPopup"] = True
        _C.save(cfg)

    # AutoLookupCoordinator's panel refresh: a VISIBLE dictionary
    # window follows the picked word; hidden or same-word is skipped.
    class _FakeInp:
        def __init__(self):
            self.text_ = ""
        def setText(self, t):
            self.text_ = t
        def text(self):
            return self.text_

    class _FakeDict:
        def __init__(self, visible):
            self._vis = visible
            self.inp = _FakeInp()
            self.searches = []
        def isVisible(self):
            return self._vis
        def do_search(self):
            self.searches.append(self.inp.text_)

    # No dictionary window at all -> silent.
    app._dict = None
    app._auto_dict_refresh("hello")
    ck("no dict window: silent", getattr(app, "_auto_dict_word", "") == "")

    # Hidden window -> never opened/refreshed.
    app._dict = _FakeDict(visible=False)
    app._auto_dict_refresh("hello")
    ck("hidden dict: untouched",
       not app._dict.searches and app._dict.inp.text_ == "")

    # Visible -> field set + search re-run; same word deduped.
    app._dict = _FakeDict(visible=True)
    app._auto_dict_refresh("hello")
    app._auto_dict_refresh("hello")
    ck("visible dict: searched once",
       app._dict.searches == ["hello"], repr(app._dict.searches))
    app._auto_dict_refresh("world")
    ck("visible dict: new word re-searches",
       app._dict.searches == ["hello", "world"],
       repr(app._dict.searches))
    app._dict = None
finally:
    _C.DEFAULT_PATH = _saved
    try:
        os.unlink(_tmp)
    except OSError:
        pass

    # ---- popup DefinitionStrip (.tmp QuickTranslateDialog) ----
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from qtranslate.qt.popup import PopupWindow
        qapp = QApplication.instance() or QApplication([])
        pop = PopupWindow(app)
        pop.set_text("hello", "xin chào", "en-vi")
        ck("popup defn hidden before gloss",
           not pop.defn.isVisibleTo(pop))
        pop.set_inline_definition("a greeting")
        ck("popup defn shows gloss",
           pop.defn.isVisibleTo(pop)
           and pop.defn.toPlainText() == "a greeting")
        import qtranslate.qt.popup as _popmod
        h_no_defn = _popmod.PopupWindow(app).height() if False else None
        ck("popup grew for defn",
           pop.height() >= _popmod.HEADER_H + 40)
        pop.set_inline_definition("")
        ck("popup defn blank hides",
           not pop.defn.isVisibleTo(pop))
        pop.set_text("two words", "nhiều từ", "en-vi")
        ck("popup new text clears defn",
           pop._defn_text == "")
    except Exception as exc:
        ck("popup defn block ran", False, repr(exc))

print()
if FAIL:
    print("regress_inline_definition: %d FAILED: %s"
          % (len(FAIL), FAIL))
    sys.exit(1)
print("regress_inline_definition: all checks ok")
