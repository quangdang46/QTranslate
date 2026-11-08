#!/usr/bin/env python3
"""Hotkey recorder capture: bit15 double-press, Double Ctrl, chips.

Ports of native ``FUN_0040AA88`` recorder semantics that the inline
capture gained (see ``qtranslate/qt/options/hotkeys.py`` module docstring):

* the same chord pressed twice inside the double-click window re-saves
  it with bit15 -- the "Double" prefix ``format_hotkey`` displays;
* on the "Show main window" row, two Ctrl taps inside the
  ``DoubleCtrlDetector`` threshold save the bare ``0x8000`` gesture;
* while a binding is armed a chip strip offers modifier toggles
  (pending chord modifiers), special-key chips and Cancel, and the row
  shows a live modifier preview.

Headless: HotkeysPage builds offscreen against a temp Options.json;
key events are synthetic QKeyEvents fed through the page's event
filter, exactly what the shell receives while it has focus.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate import config as C  # noqa: E402

_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
with open(_tmp, "w", encoding="utf-8") as f:
    f.write("{}")
C.DEFAULT_PATH = _tmp
_saved_default = C.DEFAULT_PATH

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_qapp = QApplication.instance() or QApplication([])

import qtranslate.qt.options as _OPT  # noqa: E402  (fills PAGES)
import qtranslate.qt.options.hotkeys as HK  # noqa: E402
from qtranslate.qt.options.hotkeys import HotkeysPage  # noqa: E402

# The conflict prompt is modal; the chords below are picked outside the
# presets, but stub it anyway so a surprise can never hang the suite.
_orig_conflict = HK._conflicting_key
HK._conflicting_key = lambda key, code: None


def press(key, mods=Qt.NoModifier, text=""):
    return QKeyEvent(QEvent.Type.KeyPress, key, mods, text)


def release(key):
    return QKeyEvent(QEvent.Type.KeyRelease, key, Qt.NoModifier)


def feed(page, ev):
    return page._hk_recorder.eventFilter(page, ev)


def hkval(name):
    return int((C.load() or {}).get("HotKeys", {}).get(name, 0) or 0)


def ctrl_tap(page):
    feed(page, press(Qt.Key_Control, Qt.ControlModifier))
    feed(page, release(Qt.Key_Control))


def visible(widget):
    # The page is never shown() in this suite, so isVisible() is False
    # for every child; isHidden() reflects the explicit setVisible().
    return not widget.isHidden()


try:
    page = HotkeysPage(None)

    # --- chip strip presence -----------------------------------------
    ck("chip strip built", len(getattr(page, "_hk_chips", {})) == 14,
       str(len(getattr(page, "_hk_chips", {}))))
    ck("chips hidden while idle",
       not any(visible(w) for w in page._hk_chips.values()))
    ck("hint visible while idle", visible(page._hk_hint))

    # --- plain chord still records ------------------------------------
    HK._start_record(page, "HotKeyHistory")
    ck("recording armed", page._hk_recording == "HotKeyHistory")
    ck("chips shown while armed",
       any(visible(w) for w in page._hk_chips.values()))
    ck("hint hidden while armed", not visible(page._hk_hint))
    feed(page, press(Qt.Key_F5, Qt.ControlModifier | Qt.AltModifier))
    ck("chord saved", hkval("HotKeyHistory") == (0x3 << 8) | 0x74,
       hex(hkval("HotKeyHistory")))
    ck("recording ended", page._hk_recording is None)
    ck("chips hidden after save",
       not any(visible(w) for w in page._hk_chips.values()))

    # --- double-press same chord -> bit15 ------------------------------
    HK._start_record(page, "HotKeyListenText")
    feed(page, press(Qt.Key_F6, Qt.ControlModifier))
    ck("first press saved plain", hkval("HotKeyListenText") == 0x275,
       hex(hkval("HotKeyListenText")))
    feed(page, press(Qt.Key_F6, Qt.ControlModifier))
    ck("identical second press sets bit15",
       hkval("HotKeyListenText") == 0x8000 | 0x275,
       hex(hkval("HotKeyListenText")))

    # --- a different key closes the double window ----------------------
    HK._start_record(page, "HotKeyListenTranslation")
    feed(page, press(Qt.Key_F7, Qt.ControlModifier))
    ck("first chord saved", hkval("HotKeyListenTranslation") == 0x276,
       hex(hkval("HotKeyListenTranslation")))
    took = feed(page, press(Qt.Key_F8, Qt.ControlModifier))
    ck("different press passes through unrecorded", took is False)
    ck("different chord does not inherit bit15",
       hkval("HotKeyListenTranslation") == 0x276,
       hex(hkval("HotKeyListenTranslation")))
    # And a fresh single press of the second chord stays plain.
    HK._start_record(page, "HotKeyListenTranslation")
    feed(page, press(Qt.Key_F8, Qt.ControlModifier))
    ck("re-recorded chord has no bit15",
       hkval("HotKeyListenTranslation") == 0x277,
       hex(hkval("HotKeyListenTranslation")))

    # --- closed window does not upgrade ---------------------------------
    HK._start_record(page, "HotKeySpeechInput")
    feed(page, press(Qt.Key_F9, Qt.ControlModifier))
    page._hk_pending_double = None   # the 500ms deadline, simulated
    took = feed(page, press(Qt.Key_F9, Qt.ControlModifier))
    ck("expired window -> press ignored", took is False)
    ck("no upgrade without pending window",
       hkval("HotKeySpeechInput") == 0x278,
       hex(hkval("HotKeySpeechInput")))

    # --- live modifier preview ------------------------------------------
    HK._start_record(page, "HotKeyCopyTranslation")
    lab = page._hk_labels["HotKeyCopyTranslation"]
    feed(page, press(Qt.Key_Control, Qt.ControlModifier))
    ck("ctrl preview shows", lab.text() == "Ctrl +", lab.text())
    feed(page, press(Qt.Key_Shift,
                     Qt.ControlModifier | Qt.ShiftModifier))
    ck("ctrl+shift preview", lab.text() == "Ctrl + Shift +", lab.text())
    feed(page, release(Qt.Key_Shift))
    ck("release updates preview", lab.text() == "Ctrl +", lab.text())
    feed(page, release(Qt.Key_Control))
    ck("release clears preview",
       lab.text().startswith("press keys"), lab.text())
    # A chord pressed with the modifier held records it.
    feed(page, press(Qt.Key_F10, Qt.ControlModifier))
    ck("held modifier joins the chord",
       hkval("HotKeyCopyTranslation") == 0x279,
       hex(hkval("HotKeyCopyTranslation")))

    # --- Double Ctrl on the main-window row ------------------------------
    # The shipped default IS 0x8000, so first rebind the row to prove
    # the capture changes it.
    HK._start_record(page, "HotKeyMainWindow")
    feed(page, press(Qt.Key_F1, Qt.ControlModifier))
    ck("main row rebinds to a chord first",
       hkval("HotKeyMainWindow") == 0x270,
       hex(hkval("HotKeyMainWindow")))
    HK._start_record(page, "HotKeyMainWindow")
    ck("detector armed on main row", page._hk_dc is not None)
    ctrl_tap(page)
    ck("single tap does not save",
       page._hk_recording == "HotKeyMainWindow")
    ctrl_tap(page)
    ck("double Ctrl tap saves 0x8000",
       hkval("HotKeyMainWindow") == 0x8000,
       hex(hkval("HotKeyMainWindow")))
    ck("main row label shows Double Ctrl",
       page._hk_labels["HotKeyMainWindow"].text() == "Double Ctrl",
       page._hk_labels["HotKeyMainWindow"].text())

    # Other rows get no detector: Ctrl taps there record nothing.
    before = hkval("HotKeyDictionary")
    HK._start_record(page, "HotKeyDictionary")
    ck("no detector off the main row", page._hk_dc is None)
    ctrl_tap(page)
    ck("ctrl taps ignored on other rows",
       page._hk_recording == "HotKeyDictionary"
       and hkval("HotKeyDictionary") == before)
    HK._chip_cancel(page)

    # --- chips ------------------------------------------------------------
    HK._start_record(page, "HotKeyKeyboard")
    HK._chip_toggle(page, "Ctrl")
    ck("chip mod sets pending bit", page._hk_chip_mods == 2)
    ck("chip mod preview", "Ctrl" in
       page._hk_labels["HotKeyKeyboard"].text())
    HK._chip_toggle(page, "Alt")
    ck("second chip mod", page._hk_chip_mods == 3)
    HK._chip_key(page, 0x09)          # Tab chip
    ck("chip key completes chord",
       hkval("HotKeyKeyboard") == (0x3 << 8) | 0x09,
       hex(hkval("HotKeyKeyboard")))
    ck("chip mods cleared after save", page._hk_chip_mods == 0)

    # Esc chip keeps arm-then-bind.
    HK._start_record(page, "HotKeyTextRecognition")
    HK._chip_key(page, 0x1B)
    ck("esc chip first click arms", page._hk_esc_armed is True)
    ck("esc chip still recording", page._hk_recording is not None)
    HK._chip_key(page, 0x1B)
    ck("esc chip second click binds Escape",
       hkval("HotKeyTextRecognition") == 0x1B,
       hex(hkval("HotKeyTextRecognition")))

    # Cancel chip backs out without writing.
    before = hkval("HotKeyDictionaryClipboard")
    HK._start_record(page, "HotKeyDictionaryClipboard")
    HK._chip_cancel(page)
    ck("cancel chip ends recording",
       page._hk_recording is None
       and hkval("HotKeyDictionaryClipboard") == before)

    page.close()
finally:
    HK._conflicting_key = _orig_conflict
    try:
        page.close()
    except Exception:
        pass
    C.DEFAULT_PATH = _saved_default
    try:
        os.unlink(_tmp)
    except Exception:
        pass

if FAIL:
    print("FAIL %d" % len(FAIL))
    for f in FAIL:
        print("  -", f)
    raise SystemExit(1)
print("regress_hotkey_recorder: all checks ok")
