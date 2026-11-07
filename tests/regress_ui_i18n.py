"""Pin UI-language localization of chrome (offscreen Qt).

The lang packs carry window captions (Windows section), sidebar page
names, Options footer buttons (dialog 2 Controls), page control labels
(each page dialog's Controls pairs) and tray/context menu labels
(Menus section). ``General.LocaleFoderName`` picks the pack; English is
the fallback for a missing/broken pack or an untranslated string.

SAFETY: the Options pages write settings through on build (every
checked-by-default checkbox re-saves its value), so this suite points
``config.DEFAULT_PATH`` at a THROWAWAY file -- patching ``config.load``
to return a synthetic dict would let those writes clobber the user's
real Options.json (that exact accident destroyed it once; see git log).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

qapp = QApplication.instance() or QApplication([])

from qtranslate import config as _C  # noqa: E402
from qtranslate import locale as _L  # noqa: E402
import qtranslate.qt.app as _qa  # noqa: E402

app = _qa.QtApp([])

_tmp = tempfile.mkdtemp(prefix="qt-i18n-")
_opt = os.path.join(_tmp, "Options.json")
_saved_path = _C.DEFAULT_PATH
_C.DEFAULT_PATH = _opt
try:
    # --- Vietnamese -----------------------------------------------------
    _C.save({"General": {"LocaleFoderName": "Vietnamese"}})
    ck("ui_pack resolves Vietnamese",
       _L.ui_pack().get("LanguageCode") == "vi")
    ck("window captions translate",
       _L.ui_caption(3, "History") == "Lịch sử tra cứu")
    ck("footer button captions translate",
       _L.ui_control_caption(2, 2, "Cancel") == "Hủy")

    from qtranslate.qt.options import BasicsPage, AppearancePage
    basics = BasicsPage(app)
    basics.show()
    qapp.processEvents()
    texts = [w.text() for w in basics.findChildren(QLabel)]
    ck("sidebar page names are translated",
       "Cơ bản" in texts and "Ngôn ngữ" in texts, str(texts[:12]))
    ck("page control labels are translated",
       any("Ngôn ngữ giao diện" in t for t in texts), str(texts))
    basics.close()
    basics.deleteLater()

    app_page = AppearancePage(app)
    app_page.show()
    qapp.processEvents()
    atexts = [w.text() for w in app_page.findChildren(QLabel)]
    ck("appearance labels translate (Theme)",
       any("Chủ đề" in t for t in atexts), str(atexts[:14]))
    app_page.close()
    app_page.deleteLater()

    # The write-through controls must have written ONLY to the temp file.
    live = json.load(open(_opt))
    ck("page build writes only to the temp config",
       set(live) <= {"General"} or "Basics" not in live, str(sorted(live)))

    # --- English / fallback ----------------------------------------------
    _C.save({"General": {"LocaleFoderName": "English"}})
    ck("English pack is the identity",
       _L.ui_caption(3, "History") == "History"
       and _L.ui_page_caption("Basics") == "Basics")
    _C.save({"General": {"LocaleFoderName": "Klingon"}})
    ck("unknown locale falls back to English",
       _L.ui_pack().get("LanguageCode") == "en")
finally:
    _C.DEFAULT_PATH = _saved_path
    import shutil
    shutil.rmtree(_tmp, ignore_errors=True)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_ui_i18n: all checks ok (%d assertions)" % n[0])
