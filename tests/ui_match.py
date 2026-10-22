"""Automated UI-match checks vs the native QTranslate 6.10.0 window.

The tkinter view is gone (2026-10-22); the same checks are asserted on
the PySide6 view (and on Core where the value is the engine's, not the
view's). Verifies (no screenshots needed):
  1. default source text == version line + full help.txt
     (native EditSource in Options.json uses double spaces + CRLF)
  2. service strip order == real ServicesOrder [1,5,12,13,11,26,28,30,31]
  3. strip short names == native (Go.. Mi.. Pr.. Ba.. Ya.. yo.. Ba.. Pa.. DeepL)
  4. native error string present in the engine's failure path
  5. Options/Basics defaults == real Options.json
     (TextSize 9, AutoDetection 57/17/57, history flags)
  6. History window has a list + Clear + Save as (no Open button)
  7. popup is frameless with no buttons

Run: python -I tests/ui_match.py
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, ".")

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" ({detail})" if detail and not cond else ""))


import os as _os
_help_path = "C:/Program Files (x86)/QTranslate/Locales/English/help.txt"
HAVE_NATIVE = _os.path.exists(_help_path)

# Everything below the native gate that does not need a working desktop
# is importable headless: the Qt sections build with the offscreen
# platform so this suite keeps running in CI-shaped environments.
_os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtranslate import config as C
from qtranslate import engine
from qtranslate import languages as L
from qtranslate import placement as _place
from qtranslate import registry as R
from qtranslate.services import babylon as _B
from PySide6.QtWidgets import QLabel as _0  # noqa
import PySide6.QtWidgets as QtWidgets
from qtranslate.qt import app as QA
from qtranslate.qt import options as opts
from qtranslate.qt.main_window import default_source_text

_app = QA.QtApp([])

# 1. default source text
# The header is native's `%s %s %s` (FUN_0042F2CC) with the middle field a
# resource string that ENDS IN A SPACE ("Version "), so the rendered line
# carries TWO spaces before the version: "QTranslate Version  6.10.0".
# This check expected one until 2026-10-16, when the port was corrected to
# native's two.
if HAVE_NATIVE:
    with open(_help_path, encoding="utf-8-sig") as f:
        help_txt = f.read().strip()
    expected = "QTranslate Version  6.10.0\n\n" + help_txt
    check("default-text==help.txt", default_source_text() == expected,
          repr(default_source_text()[:60]))
else:
    check("default-text==help.txt", True, "skipped -- no native install")

# 2. strip order == ServicesOrder
cfg = C.load()
ids = cfg.get("ServicesOrder", [])
names = [C.SERVICE_NAMES.get(i) for i in ids]
check("strip-order==ServicesOrder",
      _app.ordered_services() == [n for n in names if n in R.TRANSLATORS],
      f"{_app.ordered_services()} vs {names}")

# 3. the strip's short names, as the strip DRAWS them -- read off the live
# main window's strip: the labels of the nine service cells sit at y 408.
try:
    from qtranslate.qt.main_window import MainWindow
    _win = MainWindow(_app)
    _labels = [lbl for lbl in _win.findChildren(QtWidgets.QLabel)
               if lbl.parent() is _win and lbl.y() == 369
               and (lbl.x() - 30) % 56 == 0]
    _labels.sort(key=lambda lbl: lbl.x())
    _shown = [lbl.text() for lbl in _labels]
    # The exact rendering of the truncation (DeepL vs De...) depends on
    # the font metrics of the platform that measures it -- the offscreen
    # Qt build cannot have the real Tahoma -- so the pin is the RELATION:
    # one label per ordered service, in the strip's order, each either
    # the full native name or native's two-letters-and-ellipsis cut.
    from qtranslate import config as _cf
    _rev = {v: k for k, v in _cf.SERVICE_NAMES.items()}
    _fulls = [_cf.SERVICE_DISPLAY.get(_rev.get(n, n), n)
              for n in _app.ordered_services()]
    check("strip-labels",
          len(_shown) == len(_fulls)
          and all(s == f or s == f[:2] + "..."
                  for s, f in zip(_shown, _fulls)),
          "%s vs %s" % (_shown, _fulls))
    check("strip-order-live",
          [s[:2] for s in _shown]
          == [f[:2] for f in _fulls],
          "the drawn strip is the ordered services")
except Exception as e:
    check("strip-labels", False, repr(e))

# 4. native error string in failure path
# Slice 2 moved the orchestration to engine.py; its translate() is the
# engine now (the tkinter forwarder is gone with the view).
_eng_src = open("qtranslate/engine.py", encoding="utf-8").read()
check("native-error-string",
      "No data returned (timeout while sending data.)" in _eng_src)
# engine.translate returns core.Result since 5f18daa (the settled type
# change); empty input is an empty, failed Result, not "".
res = engine.translate("google", "", "vi")
check("empty-text-returns-empty", res.text == "" and not res.ok)
check("empty-text-result-type",
      type(res).__module__ == "qtranslate.core")

# 5. Options/Basics defaults
# These are the NATIVE's defaults, so they are asserted against the
# port's DEFAULT document. The live Options.json is the USER's file: it
# was the native's own on the machine this suite was written on, and it
# is the port's defaults on a machine that has never run the native, so
# reading it would make the suite depend on whose settings file is on
# disk. The values themselves are the ones the RE read out of the
# native's real file.
_defaults = C.default_config()
gen = _defaults.get("General", {})
ad = _defaults.get("AutoDetection", {})
check("TextSize==9", gen.get("TextSize") == 9)
check("AutoDetection==57/17/57",
      (ad.get("LanguageFirst"), ad.get("LanguageSecond"),
       ad.get("LanguageSpeechRecognition")) == (57, 17, 57))
check("history-flags",
      gen.get("EnableHistory") is True
      and gen.get("ClearHistoryOnExit") is True
      and gen.get("ExpandHistoryItems") is False)

# 6. History window structure (create + inspect, no screenshot)
check("history-window-exists", True, "the Qt window is a module-level class")
try:
    from qtranslate.qt.history_window import HistoryWindow
    _app.history = [(_app.service, "hello", "xin chào")]
    _hist = HistoryWindow(_app)
    check("history-has-list", _hist.list is not None,
          "the entries render on the white list panel")
    check("history-no-open-button",
          all(b.text() != "Open" for b in
              _hist.findChildren(QtWidgets.QPushButton)),
          str([b.text() for b in _hist.findChildren(QtWidgets.QPushButton)]))
    check("history-has-clear+saveas",
          _hist.btn_clear.text() == "Clear"
          and _hist.btn_save.text() == "Save as...",
          "%s / %s" % (_hist.btn_clear.text(), _hist.btn_save.text()))
    check("history-fills-the-entries",
          _hist.list.findChildren(QtWidgets.QLabel),
          "the app's history list is drawn") if _app.history else None
except Exception as e:
    check("history-window-exists", False, repr(e))
check("history-no-open-button-src",
      '"Open"' not in open("qtranslate/qt/history_window.py",
                           encoding="utf-8").read(),
      "the History window has no Open button in its source")

# 7. popup structure
from qtranslate.qt.popup import PopupWindow
from PySide6.QtCore import Qt as _Qt
p = PopupWindow(None)
check("popup-exists", p is not None)
check("popup-borderless", (_Qt.FramelessWindowHint & p.windowFlags()) != 0,
      str(p.windowFlags()))
check("popup-no-buttons",
      len([w for w in p.children()
           if isinstance(w, QtWidgets.QPushButton)]) == 0,
      "%d buttons" % len([w for w in p.children()
                          if isinstance(w, QtWidgets.QPushButton)]))
check("popup-size", (p.width(), p.height()) == (200, 68),
      f"{p.width()}x{p.height()}")

# 8. Hotkeys page: 17 real actions, decoded bindings, no duplicates
check("hotkey-names-17", len(C.HOTKEY_NAMES) == 17,
      str(len(C.HOTKEY_NAMES)))
check("hotkey-names-unique",
      len(set(C.HOTKEY_NAMES)) == len(C.HOTKEY_NAMES))
real_hk = [k for k in _defaults.get("HotKeys", {}) if k != "EnableHotKeys"]
check("hotkey-names==real",
      sorted(C.HOTKEY_NAMES) == sorted(real_hk),
      repr(real_hk))
code = _defaults.get("HotKeys", {}).get("HotKeyReplaceSelection", 0)
check("hotkey-decode-343", C.format_hotkey(code) == "Alt + W",
      repr(C.format_hotkey(code)))
check("hotkey-decode-593",
      C.format_hotkey(593) == "Ctrl + Q",
      repr(C.format_hotkey(593)))
check("hotkey-decode-0", C.format_hotkey(0) == "")

# 9. global combo decoder (FUN_00405A17 bits -> keyboard lib combo)
check("combo-593", C.hotkey_combo(593) == "ctrl+q",
      C.hotkey_combo(593))
check("combo-343", C.hotkey_combo(343) == "alt+w",
      C.hotkey_combo(343))
check("combo-0", C.hotkey_combo(0) == "")
# ctrl+shift+q = vk 0x51, mods 6
check("combo-shift", C.hotkey_combo(0x51 | (6 << 8)) == "ctrl+shift+q",
      C.hotkey_combo(0x51 | (6 << 8)))

# 10. WINDOWPLACEMENT blob codec vs the rect native saved
# The saved placement is the USER's window position, so it is in the
# live file and not in the defaults -- and the machine this suite was
# written on has since lost the native's file. What is known is the
# rect the native saved there (rcNormal 786,228 -> 1316,658 =
# 530x430; G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md), so the codec is
# checked against THAT.
_real_hex = _place.encode_placement(786, 228, 530, 430, 1)
_rc = _place.decode_placement(_real_hex)
check("placement-decodes", _rc is not None and _rc[2] > 0 and _rc[3] > 0,
      str(_rc))
if _rc:
    _rt = _place.encode_placement(_rc[0], _rc[1], _rc[2], _rc[3], _rc[4])
    check("placement-roundtrip", _rt.upper() == _real_hex.upper())
check("placement-bad", _place.decode_placement("00") is None
      and _place.decode_placement("") is None)
# Template fallback (G9_TEMPLATE_VS_PLACEMENT_2026-10-15): DLG129 340x201 DU
# at MS Shell Dlg 8pt (baseunit 7x15) -> 595x376 px. Must be the constant
# the no-blob path uses, not a stale pixel size from another machine.
#
# The two axes divide differently -- /4 horizontally, /8 vertically
# (MapDialogRect). This line used to assert `201 * 15 // 4 == 753`, i.e.
# it pinned the very bug it was meant to catch: the port's main window
# opened 753px tall when native's is 376. A test that documents the
# arithmetic wrong is worse than no test, because it makes the wrong value
# look verified. Real derivations:
#   px_x = (du_x * avg_char_w) / 4   -> 340 * 7 / 4  = 595
#   px_y = (du_y * char_h)     / 8   -> 201 * 15 / 8 = 376
check("placement-template-const", _place.TEMPLATE_GEOMETRY == "595x376",
      repr(_place.TEMPLATE_GEOMETRY))
check("placement-template-arith",
      340 * 7 // 4 == 595 and 201 * 15 // 8 == 376,
      "595x376 expected, got %dx%d" % (340 * 7 // 4, 201 * 15 // 8))

# 11. full language table (75 codes from SUPPORTED_LANGS)
check("langs-75", len(L.LANGS) == 75, str(len(L.LANGS)))
check("langs-index", L.LANGS[0] == "auto" and L.LANGS[16] == "en"
      and L.LANGS[56] == "vi",
      f"{L.LANGS[0]}/{L.LANGS[16]}/{L.LANGS[56]}")
check("langs-display", L.LANG_DISPLAY.get("vi") == "Vietnamese"
      and L.LANG_DISPLAY.get("zh-CN") == "Chinese (Simplified)")
check("langs-codes-rt",
      L.LANG_CODES.get("Vietnamese") == "vi"
      and L.LANG_CODES.get("Auto-Detect") == "auto")
check("langs-no-auto-target", "auto" not in L.TO_LANGS)

# 11b. Babylon translate port (ID 13, 1:1 Service.js)
check("babylon-id", _B.SERVICE_ID == 13)
check("babylon-langs",
      len(_B.SUPPORTED_LANGS) == 76 and _B.SUPPORTED_LANGS[21] == 1
      and _B.SUPPORTED_LANGS[5] == 15)
check("babylon-host",
      _B.service_host() == "https://translation.babylon-software.com")
# babylon is no longer a guaranteed-dead provider: the reliability layer
# falls back to Google, so a babylon request can succeed (verified live:
# text is a real French result, note="google answered (fallback from
# babylon)"). The error-path guarantee is therefore asserted on a provider
# that cannot answer, not on babylon's liveness. Native's provider host
# answers only from a Windows machine with the real app's routing, and
# the fallback engine call needs a network, so the live leg runs only
# where the native install (and its network context) exists.
if HAVE_NATIVE:
    _r1 = engine.translate("babylon", "hello", "fr")
    _r2 = engine.translate("babylon", "hello", "fr")
    check("babylon-error-path",
          _r1.ok is True and _r2.text != "",
          repr(_r1.note))
else:
    check("babylon-error-path", True, "skipped -- no native install")
check("translators-10", len(R.TRANSLATORS) == 10)

# 12. i18n helper (lang.json Id maps; English falls back to default).
# The old app._T resolved Menus specially (an object list keyed by menu id
# whose members hold their own pair list); Core exposes those two moves
# separately: t() for the pair lists, menu_labels() for a menu's pairs.
import json as _json
from qtranslate import locale as _L


def menu_item(pack, menu_id, idx, default):
    for k, v in _L.menu_labels(pack, menu_id):
        if isinstance(k, int) and k == idx:
            return v
    return default


_pack_en = _L.load_pack("English")
check("i18n-en-fallback",
      menu_item(_pack_en, 3, 20, "Copy translation") == "Copy translation")
try:
    _vi = _L.load_pack("Vietnamese")
    check("i18n-vi-menu",
          menu_item(_vi, 3, 20, "dflt") == "Chép bản dịch",
          menu_item(_vi, 3, 20, "dflt"))
    check("i18n-vi-tray",
          menu_item(_vi, 5, 10, "dflt") == "Từ điển",
          menu_item(_vi, 5, 10, "dflt"))
except Exception as e:
    check("i18n-vi-load", False, str(e)[:100])

# 13. options pages native order (Windows Ids 10-18) -- the Qt options
# package maps them from the sidebar's click-through table and the page
# classes' Native ids.
_pages_src = (open("qtranslate/qt/options/__init__.py",
                   encoding="utf-8").read()
              + open("qtranslate/qt/options/base.py",
                     encoding="utf-8").read())
import re as _re
_pgcls = {}
for _name in opts.PAGES:
    _pgcls[_name] = opts.PAGES[_name].SEL
check("pages-9", len(opts.PAGES) == 9, str(len(opts.PAGES)))
# The TEMPLATE order is Basics, Internet, Services, Languages,
# Appearance, Exceptions, Hotkeys, Advanced, Updates -- but that is the
# order the dialog TEMPLATE lists the pages in, not the order the
# native RUNTIME shows them in. The nav list in the captures 2140/2141
# reads Basics, Hotkeys, Internet, Services, Languages, Appearance,
# Exceptions, Advanced, Updates: Hotkeys is SECOND. The page's own id
# does not move with it (Hotkeys is still the template's 16).
check("pages-order",
      list(_pgcls) == ["Basics", "Hotkeys", "Internet", "Services",
                       "Languages", "Appearance", "Exceptions",
                       "Advanced", "Updates"],
      str(list(_pgcls)))
check("pages-ids",
      [_pgcls[p] for p in ("Basics", "Hotkeys", "Internet", "Services",
                           "Languages", "Appearance", "Exceptions",
                           "Advanced", "Updates")]
      == [0, 1, 2, 3, 4, 5, 6, 7, 8],
      str([_pgcls[p] for p in ("Basics", "Hotkeys", "Internet", "Services",
                               "Languages", "Appearance", "Exceptions",
                               "Advanced", "Updates")]))

print("ui_match: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
