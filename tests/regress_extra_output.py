#!/usr/bin/env python3
"""Extra Output pane (.tmp ExtraOutputPanel): three modes on the lower
pane -- back translation, AI summary, AI rewrite -- with persisted
mode/options/source and a worker-driven refresh."""
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
_saved_default = _C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
_C.DEFAULT_PATH = _tmp
try:
    from qtranslate.qt.app import QtApp  # noqa: E402
    from qtranslate.qt.main_window import MainWindow  # noqa: E402
    from qtranslate.services import ai_translate as AI  # noqa: E402

    app = QtApp([])
    app.win = MainWindow(app)
    win = app.win

    print("== mode state ==")
    ck("default mode is back", win.extra_mode() == "back")
    ck("back button checked",
       win._extra_buttons["back"].isChecked())
    ck("gear hidden in back mode",
       not win.extra_gear.isVisibleTo(win.extra_wrap))

    win.set_extra_mode("summary")
    ck("mode persisted",
       (_C.load() or {}).get("General", {}).get("ExtraOutputType")
       == "Summarize")
    ck("summary button checked",
       win._extra_buttons["summary"].isChecked())
    ck("gear shown in summary mode",
       win.extra_gear.isVisibleTo(win.extra_wrap))
    ck("src btn shows Out",
       win.extra_src_btn.text() == "Out")

    win._cycle_extra_source()
    ck("source persisted Input",
       (_C.load() or {}).get("General", {}).get("ExtraOutputSource")
       == "Input")
    ck("src btn shows In", win.extra_src_btn.text() == "In")

    print("== option menu values ==")
    ck("summary default MEDIUM",
       win._extra_cfg().get("SummaryLength") in (None, "MEDIUM"))
    win._set_extra_option("SummaryLength", "LONG")
    ck("length persisted",
       (_C.load() or {}).get("General", {}).get("SummaryLength")
       == "LONG")
    win.set_extra_mode("rewrite")
    ck("rewrite mode",
       (_C.load() or {}).get("General", {}).get("ExtraOutputType")
       == "Rewrite")
    ck("rewrite button checked",
       win._extra_buttons["rewrite"].isChecked())

    print("== set_result mode guard ==")
    win.set_extra_mode("summary")
    win.set_result("kết quả\n\n--- back-translation ---\nresult")
    ck("summary mode: back pane NOT filled with back-trans",
       win.back.toPlainText() == "", repr(win.back.toPlainText())[:60])
    ck("out pane still split",
       "kết quả" in win.out.toPlainText())
    win.set_extra_mode("back")
    win.set_result("kết quả\n\n--- back-translation ---\nresult")
    ck("back mode: back pane filled",
       "result" in win.back.toPlainText())

    print("== refresh_extra_output ==")
    calls = []

    def fake_summarize(text, length="MEDIUM"):
        calls.append(("summarize", text, length))
        return "TL;DR version"

    def fake_rewrite(text, style="FORMAL"):
        calls.append(("rewrite", text, style))
        return "Rewritten version"

    AI.summarize = fake_summarize
    AI.rewrite = fake_rewrite

    app._last_src_text = "original long text"
    app._last_out_text = "translated text"
    # source=Input currently -> summary of the SOURCE text.
    win.set_extra_mode("summary")
    app.refresh_extra_output()
    app.wait_for_translation(timeout=5)
    ck("summarize called on source text",
       calls and calls[-1][0] == "summarize"
       and calls[-1][1] == "original long text",
       repr(calls[-1] if calls else None))
    ck("length LONG passed", calls[-1][2] == "LONG")
    ck("pane shows summary", "TL;DR" in win.back.toPlainText(),
       repr(win.back.toPlainText())[:60])
    ck("pane visible", win.extra_wrap.isVisibleTo(win)
       or win.extra_wrap.isVisible())

    # Flip source to Output -> rewrite? no, still summary -> out text.
    win._cycle_extra_source()   # Input -> Output
    app.refresh_extra_output()
    app.wait_for_translation(timeout=5)
    ck("summary now on translated text",
       calls[-1][1] == "translated text", repr(calls[-1]))

    win.set_extra_mode("rewrite")
    app.refresh_extra_output()
    app.wait_for_translation(timeout=5)
    ck("rewrite called", calls[-1][0] == "rewrite")
    ck("rewrite default style FORMAL", calls[-1][2] == "FORMAL")
    ck("pane shows rewrite", "Rewritten" in win.back.toPlainText())

    # back mode: refresh is a no-op.
    n = len(calls)
    win.set_extra_mode("back")
    app.refresh_extra_output()
    app.wait_for_translation(timeout=5)
    ck("back mode: no AI call", len(calls) == n)

    # Failure surfaces in the pane like .tmp's failure text.
    def boom(text, length="MEDIUM"):
        raise RuntimeError("no api key")
    AI.summarize = boom
    win.set_extra_mode("summary")
    app.refresh_extra_output()
    app.wait_for_translation(timeout=5)
    ck("error shown in pane", "error" in win.back.toPlainText().lower(),
       repr(win.back.toPlainText())[:80])

    # Contents persistence: AI-mode pane text must NOT land in
    # EditBackTranslation; back mode still does.
    win.set_extra_mode("summary")
    app._persist_contents()
    ck("AI mode: EditBackTranslation untouched",
       "TL;DR" not in ((_C.load() or {}).get("Contents", {}) or {})
       .get("EditBackTranslation", ""))
    win.set_extra_mode("back")
    win.back.setPlainText("back trans text")
    app._persist_contents()
    ck("back mode: EditBackTranslation saved",
       ((_C.load() or {}).get("Contents", {}) or {})
       .get("EditBackTranslation") == "back trans text")

    # ---- AutoCopyGuard (.tmp workspace/translation) -------------------
    clip = QApplication.clipboard()

    def clip_text():
        return clip.text()

    def set_mode(m):
        cfg = _C.load() or {}
        cfg.setdefault("General", {})["AutoCopyTranslation"] = m
        _C.save(cfg)

    set_mode("off")
    clip.clear()
    app._maybe_auto_copy("xin chào", "main")
    ck("auto-copy off: clipboard untouched", clip_text() == "")
    set_mode("quick")
    app._maybe_auto_copy("xin chào", "main")
    ck("quick mode: main origin not copied", clip_text() == "")
    app._maybe_auto_copy("xin chào", "quick")
    ck("quick mode: quick origin copied",
       clip_text() == "xin chào", repr(clip_text()))
    app._maybe_auto_copy("ocr text", "ocr")
    ck("quick mode: ocr origin not copied",
       clip_text() == "xin chào", repr(clip_text()))
    set_mode("all")
    app._maybe_auto_copy("main text", "main")
    ck("all mode: main copied", clip_text() == "main text")
    app._maybe_auto_copy("ocr text", "ocr")
    ck("all mode: ocr copied", clip_text() == "ocr text")
    clip.clear()
    app._maybe_auto_copy("", "main")
    app._maybe_auto_copy(None, "quick")
    ck("blank result never copies", clip_text() == "")
    set_mode("off")

    # .tmp MainContentView's extra-output listen button
    # (ListenToText TextSource.ExtraOutput): language follows
    # ExtraOutputSource -- Input->source(detected), Output->target.
    ck("extra listen button exists",
       getattr(win, "extra_listen", None) is not None)
    spoken = []
    app._speak = lambda text, lang="": spoken.append((text, lang))
    win.back.setPlainText("extra words")
    # Output mode (default): target language.
    cfg = _C.load() or {}
    cfg.setdefault("General", {})["ExtraOutputSource"] = "Output"
    _C.save(cfg)
    app.source, app.target = "en", "vi"
    app._detected_src = ""
    app._speak_extra()
    ck("extra listen: output->target",
       spoken[-1] == ("extra words", "vi"), repr(spoken[-1]))
    # Input mode with concrete source.
    cfg["General"]["ExtraOutputSource"] = "Input"
    _C.save(cfg)
    app._speak_extra()
    ck("extra listen: input->source",
       spoken[-1] == ("extra words", "en"), repr(spoken[-1]))
    # Input mode + auto source -> detected language.
    app.source = "auto"
    app._detected_src = "fr"
    app._speak_extra()
    ck("extra listen: auto->detected",
       spoken[-1] == ("extra words", "fr"), repr(spoken[-1]))
    # Blank pane -> silent.
    win.back.setPlainText("   ")
    n = len(spoken)
    app._speak_extra()
    ck("extra listen: blank silent", len(spoken) == n)
    cfg["General"]["ExtraOutputSource"] = "Output"
    _C.save(cfg)
finally:
    _C.DEFAULT_PATH = _saved_default
    try:
        os.unlink(_tmp)
    except OSError:
        pass

print()
if FAIL:
    print("regress_extra_output: %d FAILED: %s" % (len(FAIL), FAIL))
    sys.exit(1)
print("regress_extra_output: all checks ok")
