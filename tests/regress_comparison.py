#!/usr/bin/env python3
"""Comparison services (.tmp ParallelComparisonUseCase +
ServicePreset.comparisonTranslatorIds): configured translators
re-translate the source in parallel and render as rows in the extra
pane's Compare mode."""
import os
import sys
import tempfile
import time

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

    app = QtApp([])
    app.win = MainWindow(app)
    win = app.win

    def drain(seconds=5.0):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.qapp.processEvents()
            time.sleep(0.01)
        app.qapp.processEvents()

    print("== config parsing ==")
    app.service = "deepl"      # primary is never a comparison candidate
    cfg = _C.load() or {}
    ck("no comparison services by default",
       app._comparison_services() == [])
    cfg.setdefault("General", {})["ComparisonServices"] = [
        "google", "microsoft", "google"]
    _C.save(cfg)
    svcs = app._comparison_services()
    ck("dedup keeps order", svcs[:2] == ["google", "microsoft"], str(svcs))
    cfg["General"]["ComparisonServices"] = "microsoft|google"
    _C.save(cfg)
    ck("string form parses", set(app._comparison_services())
       == {"microsoft", "google"})

    print("== primary excluded / disabled excluded ==")
    app.service = "google"
    cfg["General"]["ComparisonServices"] = ["google", "microsoft"]
    _C.save(cfg)
    ck("primary never compares itself",
       app._comparison_services() == ["microsoft"])
    cfg["DisabledServices"] = ["microsoft"]
    _C.save(cfg)
    ck("disabled service not compared",
       app._comparison_services() == [])
    cfg.pop("DisabledServices", None)
    _C.save(cfg)

    print("== compare mode ==")
    win.set_extra_mode("compare")
    ck("compare mode persisted",
       (_C.load() or {}).get("General", {}).get("ExtraOutputType")
       == "Compare")
    ck("compare button checked",
       win._extra_buttons["compare"].isChecked())
    ck("gear hidden in compare mode",
       not win.extra_gear.isVisibleTo(win.extra_wrap))

    print("== parallel fetch ==")
    cfg["General"]["ComparisonServices"] = ["google", "microsoft"]
    _C.save(cfg)
    app.service = "deepl"
    calls = []
    from qtranslate import engine as _eng
    _orig_translate = _eng.translate

    class _Res:
        def __init__(self, ok, text):
            self.ok = ok
            self.text = text
            self.provider_used = "x"
            self.source_language_code = "en"

    def fake_translate(service, text, target, src="auto", **kw):
        calls.append(service)
        return _Res(True, "out-%s" % service)

    _eng.translate = fake_translate
    try:
        app._run_comparison("hello")
        drain()
    finally:
        _eng.translate = _orig_translate
    ck("both services called", sorted(calls) == ["google", "microsoft"],
       str(calls))
    rows = getattr(app, "_compare_rows", {})
    ck("rows landed", rows.get("google", {}).get("text") == "out-google"
       and rows.get("microsoft", {}).get("text") == "out-microsoft",
       str(rows))
    pane = win.back.toPlainText()
    ck("pane shows provider blocks",
       "Google" in pane and "Microsoft" in pane
       and "out-google" in pane and "out-microsoft" in pane,
       pane[:200])

    print("== failure row ==")
    def fake_fail(service, text, target, src="auto", **kw):
        return _Res(False, "boom-%s" % service)
    _eng.translate = fake_fail
    try:
        app._run_comparison("hello")
        drain()
    finally:
        _eng.translate = _orig_translate
    ck("failure renders", "boom-google" in win.back.toPlainText())

    print("== stale generation ==")
    gen_before = getattr(app, "_compare_gen", 0)
    app._compare_row_done(gen_before - 1, "google", "stale", "")
    ck("stale row dropped",
       app._compare_rows.get("google", {}).get("text") != "stale")

    print("== empty config hint ==")
    cfg["General"]["ComparisonServices"] = []
    _C.save(cfg)
    app._compare_render()
    ck("hint shown", "No comparison services" in win.back.toPlainText())

    print("== quick popup comparison (.tmp quickTranslationComparisonPolicy) ==")
    from qtranslate.qt.popup import PopupWindow
    cfg["General"]["ComparisonServices"] = ["google", "microsoft"]
    _C.save(cfg)
    app.service = "deepl"
    pop = PopupWindow(app)
    app._popup = pop
    pop.set_text("hello", "hola", "English to Spanish (DeepL)")
    calls.clear()
    _eng.translate = fake_translate
    try:
        app._popup_compare("hello")
        drain()
    finally:
        _eng.translate = _orig_translate
    ck("popup compare fetched secondaries",
       sorted(calls) == ["google", "microsoft"], str(calls))
    ck("popup compare strip filled",
       "out-google" in (pop._cmp_text or "")
       and "out-microsoft" in (pop._cmp_text or ""),
       repr((pop._cmp_text or "")[:120]))
    ck("popup compare widget visible",
       pop.compare.isVisibleTo(pop) or pop.compare.isVisible())
    # New translation clears the strip; empty config hides it.
    pop.set_text("bye", "adiós", "English to Spanish (DeepL)")
    ck("new translation clears compare", not pop._cmp_text)
    cfg["General"]["ComparisonServices"] = []
    _C.save(cfg)
    app._popup_compare("bye")
    ck("ineligible config hides compare", not pop._cmp_text)
    app._popup = None
    pop.close()
finally:
    _C.DEFAULT_PATH = _saved_default
    try:
        os.unlink(_tmp)
    except OSError:
        pass

print()
if FAIL:
    print("regress_comparison: %d FAILED: %s" % (len(FAIL), FAIL))
    sys.exit(1)
print("regress_comparison: all checks ok")
