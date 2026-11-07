#!/usr/bin/env python3
""".tmp TranslationRule port: General.TranslationRules source->target
overrides applied by the MAIN translation flow only (explicit source
pre-resolves; AUTO re-resolves from detected language and
re-translates once)."""
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
try:
    from qtranslate.qt.app import QtApp  # noqa: E402
    from qtranslate.qt.main_window import MainWindow  # noqa: E402
    from qtranslate import engine  # noqa: E402
    from qtranslate.core import Result  # noqa: E402

    app = QtApp([])
    app.win = MainWindow(app)

    calls = []

    from qtranslate.services.google_translate import SUPPORTED_LANGS
    _EN_IDX = list(SUPPORTED_LANGS).index("en")

    def fake_translate(service, text, target, src="auto", **kw):
        calls.append((target, src))
        # source_language is an INDEX into SUPPORTED_LANGS; auto -> -1
        # slot so source_language_code reports "" like a real detect
        # miss would (rules then simply do not fire).
        return Result(service, "ok",
                      source_language=(_EN_IDX if src == "auto"
                                       else _EN_IDX))

    orig = engine.translate
    engine.translate = fake_translate
    try:
        cfg = _C.load() or {}
        cfg.setdefault("General", {})["TranslationRules"] = [
            {"source": "en", "target": "ja"},
            {"source": "zh-CN", "target": "ko"},
        ]
        _C.save(cfg)

        print("== rule parsing ==")
        ck("rules parsed", app._translation_rules() == {
            "en": "ja", "zh-CN": "ko"}, str(app._translation_rules()))
        ck("exact match", app._rule_target("en") == "ja")
        ck("regional fallback", app._rule_target("zh-CN") == "ko")
        ck("no rule", app._rule_target("fr") is None)

        print("== explicit source pre-resolves ==")
        app.source, app.target = "en", "vi"
        calls.clear()
        app._translate("hello", apply_rules=True)
        ck("rule target used", calls == [("ja", "en")], str(calls))
        calls.clear()
        app._translate("bonjour", apply_rules=True)  # source still en
        ck("rule applies to source not text", calls == [("ja", "en")])

        print("== auto source re-resolves ==")
        app.source, app.target = "auto", "vi"
        calls.clear()
        app._pending_rule_target = None
        res = app._translate("hello", apply_rules=True)
        ck("auto: first vi then rule ja",
           calls == [("vi", "auto"), ("ja", "en")], str(calls))
        ck("pending target set", app._pending_rule_target == "ja")

        print("== rules off for quick paths ==")
        calls.clear()
        app._pending_rule_target = None
        app._translate("hello")           # apply_rules defaults False
        ck("no rules without opt-in", calls == [("vi", "auto")],
           str(calls))
        ck("no pending target", app._pending_rule_target is None)

        print("== no rule for detected ==")
        cfg["General"]["TranslationRules"] = [
            {"source": "de", "target": "fr"}]
        _C.save(cfg)
        calls.clear()
        app._pending_rule_target = None
        app._translate("hello", apply_rules=True)
        ck("detected en has no rule -> single call",
           calls == [("vi", "auto")], str(calls))
    finally:
        engine.translate = orig

    print("== _show_main_result applies pending target ==")
    cfg = _C.load() or {}
    cfg["General"]["TranslationRules"] = [{"source": "en",
                                           "target": "ja"}]
    _C.save(cfg)
    app.source, app.target = "auto", "vi"
    app._pending_rule_target = "ja"
    fake_calls = []

    def fake2(service, text, target, src="auto", **kw):
        fake_calls.append((target, src))
        return Result(service, "translated",
                      source_language=_EN_IDX)

    engine.translate = fake2
    try:
        app.win.src.setPlainText("hello")
        app.on_go()
        app.wait_for_translation(timeout=5)
    finally:
        engine.translate = orig
    ck("rule target moved session target", app.target == "ja",
       app.target)
    ck("rule re-translated to ja",
       ("ja", "en") in fake_calls, str(fake_calls))
finally:
    _C.DEFAULT_PATH = _saved
    try:
        os.unlink(_tmp)
    except OSError:
        pass

print()
if FAIL:
    print("regress_translation_rules: %d FAILED: %s" % (len(FAIL), FAIL))
    sys.exit(1)
print("regress_translation_rules: all checks ok")
