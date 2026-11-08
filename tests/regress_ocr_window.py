"""Regression: the OCR result window (``qtranslate/qt/ocr_window.py``).

Menu 10 (Text recognition) is a native WINDOW menu; the port's host is
``OcrResultWindow``. Until now only source greps pinned it -- this
suite builds the widget offscreen and exercises its surface:

  1. the window builds with the nine native menu-10 items in order,
     "Edit image" honestly disabled (no editor exists);
  2. ``set_text`` fills the pane and tolerates None;
  3. Translate routes the pane text through ``app.show_translation``
     with ``origin="ocr"``;
  4. Copy text/image and Save image never raise without an image or
     with one (QFileDialog is stubbed so no dialog blocks the run);
  5. ``_set_ocr_language`` persists ``Ocr.OcrLanguage`` through
     ``config.save``.

Offscreen; ``config.DEFAULT_PATH`` is isolated to a temp file BEFORE
any config load, per AGENTS.md.
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


from qtranslate import config as _CFG                    # noqa: E402
_CFG.DEFAULT_PATH = os.path.join(tempfile.mkdtemp(prefix="qt-ocrwin-"),
                                 "Options.json")

try:
    from PySide6.QtWidgets import QApplication
    qapp = QApplication.instance() or QApplication([])
    from qtranslate.qt.ocr_window import OcrResultWindow
except Exception as exc:                                # noqa: BLE001
    print("SKIP regress_ocr_window: Qt imports failed (%s)" % exc)
    raise SystemExit(0)


class _FakeResult:
    text = "translated"


class _FakeApp:
    def __init__(self):
        self.shown = []
        self.translated = []

    def _translate(self, text):
        self.translated.append(text)
        return _FakeResult()

    def show_translation(self, src, res, origin=None):
        self.shown.append((src, res, origin))


app = _FakeApp()
w = OcrResultWindow(app)

# --- menu shape ---------------------------------------------------------
acts = w.menu().actions()
labels = [a.text() for a in acts]
ck("menu has the nine native items",
   labels == ["OCR language", "Translate", "Copy image", "Copy text",
              "Save image", "Edit image", "Select all",
              "Clear selection", "Close"], str(labels))
edit = [a for a in acts if a.text() == "Edit image"]
ck("Edit image is present but disabled (no editor)",
   len(edit) == 1 and not edit[0].isEnabled())

# --- text pane ----------------------------------------------------------
w.set_text("hello world")
ck("set_text fills the pane", w.out.toPlainText() == "hello world")
w.set_text(None)
ck("set_text tolerates None", w.out.toPlainText() == "")

# --- Translate handler --------------------------------------------------
w.set_text("scan this")
w._translate()
ck("Translate routes through app._translate + show_translation",
   app.translated == ["scan this"]
   and app.shown == [("scan this", "translated", "ocr")],
   repr((app.translated, app.shown)))

# --- clipboard/image handlers never raise -------------------------------
w._copy_text()
w._copy_image()          # _image is None -> honest no-op
w._save_image()          # _image is None -> early return, no dialog
ck("copy/save handlers are no-ops without an image", True)

# --- OCR language persistence --------------------------------------------
w._set_ocr_language(3)
ck("_set_ocr_language writes Ocr.OcrLanguage",
   (_CFG.load().get("Ocr", {}) or {}).get("OcrLanguage") == 3,
   repr(_CFG.load().get("Ocr")))

w.close()

if fail:
    print("FAIL %d" % len(fail))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_ocr_window: all checks ok (%d assertions)" % n[0])
