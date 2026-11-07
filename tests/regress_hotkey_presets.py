#!/usr/bin/env python3
"""Hotkey preset switcher (.tmp HotkeyPresets.kt / KeyboardPanel.kt,
ported for qt-4xy): LEGACY/MODERN bulk-rebind every HotKey* binding,
CUSTOM clears them all, and the active preset is identified from the
bindings -- never stored.

Config writes go to a temp Options.json via ``config.DEFAULT_PATH``;
the page itself is built offscreen to prove the combo exists, shows
the identified preset and applies a choice end to end.
"""
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


from qtranslate import config as C  # noqa: E402

_saved = C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
C.DEFAULT_PATH = _tmp

# --- preset tables ----------------------------------------------------
ck("preset order is legacy/modern/custom",
   C.HOTKEY_PRESET_ORDER == ("LEGACY", "MODERN", "CUSTOM"))
for kind in ("LEGACY", "MODERN", "CUSTOM"):
    vals = C.hotkey_preset_values(kind)
    ck("%s covers all 17 HotKey names" % kind,
       sorted(vals) == sorted(C.HOTKEY_NAMES))
ck("LEGACY binds the classic chords",
   C.hotkey_preset_values("LEGACY")["HotKeyPopupWindow"] == 0x251
   and C.hotkey_preset_values("LEGACY")["HotKeyDictionary"] == 0x244
   and C.hotkey_preset_values("LEGACY")["HotKeyReplaceSelection"] == 0x654)
ck("MODERN moves globals to Ctrl+Shift",
   C.hotkey_preset_values("MODERN")["HotKeyPopupWindow"] == 0x651
   and C.hotkey_preset_values("MODERN")["HotKeyDictionary"] == 0x644)
ck("CUSTOM clears every binding",
   all(v == 0 for v in C.hotkey_preset_values("CUSTOM").values()))
ck("no duplicate chords inside a preset",
   len({v for v in C.hotkey_preset_values("LEGACY").values() if v})
   == len([v for v in C.hotkey_preset_values("LEGACY").values() if v]))

# --- apply + identify + persistence ------------------------------------
hk = {"EnableHotKeys": False}
out = C.apply_hotkey_preset(hk, "LEGACY")
ck("apply LEGACY writes every name",
   all(out[n] == C.hotkey_preset_values("LEGACY")[n] for n in C.HOTKEY_NAMES))
ck("EnableHotKeys survives a preset",
   out["EnableHotKeys"] is False)
ck("input dict not mutated", "HotKeyDictionary" not in hk)
ck("identify LEGACY", C.hotkey_preset_kind(out) == "LEGACY")

out2 = C.apply_hotkey_preset(out, "MODERN")
ck("identify MODERN", C.hotkey_preset_kind(out2) == "MODERN")
ck("MODERN replace is Ctrl+Shift+R",
   out2["HotKeyReplaceSelection"] == 0x652)

out3 = C.apply_hotkey_preset(out2, "CUSTOM")
ck("CUSTOM zeroes every binding",
   all(out3[n] == 0 for n in C.HOTKEY_NAMES))
ck("identify CUSTOM after clear", C.hotkey_preset_kind(out3) == "CUSTOM")
ck("CUSTOM drops the Double prefix",
   out3["HotKeyMainWindow"] == 0)

custom = dict(C.hotkey_preset_values("LEGACY"))
custom["HotKeyDictionary"] = 0x245   # one hand edit
ck("hand-edited set identifies CUSTOM",
   C.hotkey_preset_kind(custom) == "CUSTOM")

# Persistence round-trip through Options.json.
cfg = C.default_config()
cfg["HotKeys"] = C.apply_hotkey_preset(cfg["HotKeys"], "MODERN")
C.save(cfg)
back = C.load()
ck("preset survives save/load",
   C.hotkey_preset_kind(back.get("HotKeys", {})) == "MODERN")
ck("EnableHotKeys still true after preset",
   back["HotKeys"]["EnableHotKeys"] is True)

# A fresh install starts on the upstream default preset (LEGACY).
fresh = C.default_config()["HotKeys"]
ck("fresh defaults identify LEGACY",
   C.hotkey_preset_kind(fresh) == "LEGACY",
   C.hotkey_preset_kind(fresh))
ck("fresh defaults carry all 17 keys",
   all(n in fresh for n in C.HOTKEY_NAMES))

# --- the page ----------------------------------------------------------
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402
_qapp = QApplication.instance() or QApplication([])

import qtranslate.qt.options as _OPT  # noqa: E402  (fills PAGES)
from qtranslate.qt.options.hotkeys import HotkeysPage  # noqa: E402

shell = HotkeysPage(None)
combos = [w for w in shell.findChildren(QComboBox)
          if w.count() == 3]
ck("hotkeys page has the preset combo", len(combos) == 1,
   str(len(combos)))
if combos:
    pc = combos[0]
    ck("combo offers Legacy/Modern/Custom",
       [pc.itemText(i) for i in range(pc.count())]
       == ["Legacy QTranslate", "Modern", "Custom"],
       [pc.itemText(i) for i in range(pc.count())])
    ck("combo shows the identified preset",
       pc.currentText() == "Modern",
       pc.currentText())
    # Drive the same path the activated signal takes.
    idx = pc.findText("Custom")
    pc.setCurrentIndex(idx)
    pc.activated.emit(idx)
    _qapp.processEvents()
    hk2 = (C.load() or {}).get("HotKeys", {})
    ck("choosing Custom clears every binding in Options.json",
       all(int(hk2.get(n, 0) or 0) == 0 for n in C.HOTKEY_NAMES))
    ck("EnableHotKeys preserved by Custom",
       hk2.get("EnableHotKeys") is True)
    # And the page's own identify agrees.
    ck("cleared config identifies CUSTOM",
       C.hotkey_preset_kind(hk2) == "CUSTOM")
    shell.close()

if FAIL:
    print("FAIL %d" % len(FAIL))
    for f in FAIL:
        print("  -", f)
    raise SystemExit(1)
print("regress_hotkey_presets: all checks ok")
