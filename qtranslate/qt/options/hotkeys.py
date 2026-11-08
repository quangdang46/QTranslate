"""The Hotkeys page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

WIRED: the rows are the real bindings from Options.json
(``config.HOTKEY_NAMES`` + ``format_hotkey`` -- all 17 are listed;
the bare Double-Ctrl gesture gets its own "Double Ctrl" label via
``_binding_label``),
"Enable hotkeys" writes ``HotKeys.EnableHotKeys`` and re-registers,
and clicking a row's hotkey cell arms a capture -- the next key press
is encoded into the same ``(modifiers << 8) | vk`` packing native uses
and saved. While armed, Del unbinds, a bare modifier press is ignored,
and a chord another action already uses asks before it is applied.
Esc is bindable but needs a double press: the first Esc arms a pending
Escape (the row shows a hint), the second Esc saves the Escape
binding, and any other key cancels the pending Escape and is then
recorded normally.

The capture itself ports the recorder conveniences .tmp's modal
``HotkeyRecorderDialog`` had (RE_COVERAGE_CHECKLIST.md "Remaining .tmp
surfaces audit"):

* pressing the SAME chord twice inside the double-click window sets
  bit15 -- native's ``FUN_0040AA88`` ``SetTimer(GetDoubleClickTime())``
  path, so every row can carry the "Double" prefix ``format_hotkey``
  displays;
* on the "Show main window" row, tapping Ctrl twice inside the
  ``DoubleCtrlDetector`` threshold saves the bare ``0x8000`` gesture
  (the detector itself stays paused while recording, exactly like the
  live feed's ``_options_recording`` check);
* a chip strip replaces the hint line while a binding is armed:
  Ctrl/Alt/Shift/Win toggle as pending modifiers, the special keys
  complete the chord by mouse, and Cancel backs out -- the live
  modifier preview shows held + pending modifiers on the row.

NB: ``build`` runs on the SHELL instance (a BasicsPage), so all page
behaviour lives in module functions and a small event filter -- never
``self._methods`` (see options/extensions.py for the same rule).
"""

import time

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import QMessageBox

from qtranslate import config as _C

from .base import OptionsBase, cfg_section, cfg_set, check, combo, label
from ..widgets import panel, rect, button

from qtranslate_style import FACE, THUMB

# Row label -> the Options.json HotKeys key. Every name in
# ``config.HOTKEY_NAMES`` must appear here: a key missing from ROWS is a
# binding the user cannot see, rebind or clear from this page.
ROWS = [
    ("HotKeyMainWindow", "Show main window"),
    ("HotKeyPopupWindow", "Show popup window"),
    ("HotKeyDictionary", "Show dictionary window"),
    ("HotKeyHistory", "Show history window"),
    ("HotKeyKeyboard", "Show keyboard window"),
    ("HotKeyListenText", "Listen to selected text"),
    ("HotKeyListenTranslation", "Listen to translation"),
    ("HotKeySpeechInput", "Start speech input"),
    ("HotKeyCopyTranslation", "Copy translation to clipboard"),
    ("HotKeyReplaceSelection", "Replace selected text"),
    ("HotKeyConvertTextLayout", "Fix text layout"),
    ("HotKeySwitchMouseMode", "Switch mouse mode"),
    ("HotKeyTranslateClipboard", "Translate clipboard content"),
    ("HotKeyTranslateClipboardInMainWindow",
     "Translate clipboard in main window"),
    ("HotKeyTranslateClipboardInPopupWindow",
     "Translate clipboard in popup window"),
    ("HotKeyTextRecognition", "Recognize text in image"),
    ("HotKeyDictionaryClipboard", "Dictionary from clipboard"),
]

# Options.json key -> the row's display label (for messages).
_ROW_LABEL = dict(ROWS)

# Qt key -> the Win32 VK the settings file stores (the common keys;
# letters/digits are their ASCII uppercase).
_VK = {"backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
       "escape": 0x1B, "esc": 0x1B, "space": 0x20, "delete": 0x2E,
       "insert": 0x2D, "home": 0x24, "end": 0x23, "prior": 0x21,
       "next": 0x22, "left": 0x25, "up": 0x26, "right": 0x27,
       "down": 0x28}
for _i in range(1, 25):           # VK_F1..VK_F24 are 0x70..0x87
    _VK["f%d" % _i] = 0x6F + _i

_VK_NAME = {}


def _build_vk_names():
    global _VK_NAME
    _VK_NAME = {
        Qt.Key_Backspace: "backspace", Qt.Key_Tab: "tab",
        Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
        Qt.Key_Escape: "esc", Qt.Key_Space: "space",
        Qt.Key_Delete: "delete", Qt.Key_Insert: "insert",
        Qt.Key_Home: "home", Qt.Key_End: "end",
        Qt.Key_PageUp: "prior", Qt.Key_PageDown: "next",
        Qt.Key_Left: "left", Qt.Key_Up: "up",
        Qt.Key_Right: "right", Qt.Key_Down: "down",
        Qt.Key_F1: "f1", Qt.Key_F2: "f2", Qt.Key_F3: "f3",
        Qt.Key_F4: "f4", Qt.Key_F5: "f5", Qt.Key_F6: "f6",
        Qt.Key_F7: "f7", Qt.Key_F8: "f8", Qt.Key_F9: "f9",
        Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
        Qt.Key_F13: "f13", Qt.Key_F14: "f14", Qt.Key_F15: "f15",
        Qt.Key_F16: "f16", Qt.Key_F17: "f17", Qt.Key_F18: "f18",
        Qt.Key_F19: "f19", Qt.Key_F20: "f20", Qt.Key_F21: "f21",
        Qt.Key_F22: "f22", Qt.Key_F23: "f23", Qt.Key_F24: "f24",
    }


# Shifted glyph -> (unshifted VK). US-layout: the recorder sees
# event.text() which is the SHIFTED character, but the stored dword
# must carry the key's VK or the chord decodes as a different key
# entirely (Ctrl+Shift+1 must not become VK_PRIOR).
_UNSHIFT_VK = {
    "!": 0x31, "@": 0x32, "#": 0x33, "$": 0x34, "%": 0x35,
    "^": 0x36, "&": 0x37, "*": 0x38, "(": 0x39, ")": 0x30,
    "_": 0xBD, "+": 0xBB, "{": 0xDB, "}": 0xDD, "|": 0xDC,
    ":": 0xBA, '"': 0xDE, "<": 0xBC, ">": 0xBE, "?": 0xBF,
    "~": 0xC0,
}
# Unshifted punctuation -> Win32 OEM VK (the ASCII code would collide
# with nav/special VKs in the packed dword).
_PUNCT_VK = {
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE,
    "/": 0xBF, "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD,
    "'": 0xDE,
}


def _vk_of(qkey: int, text: str) -> int:
    name = _VK_NAME.get(qkey)
    if name in _VK:
        return _VK[name]
    if len(text) == 1 and text.isascii() and text.isprintable():
        c = text
        if c in _UNSHIFT_VK:
            return _UNSHIFT_VK[c]
        if c in _PUNCT_VK:
            return _PUNCT_VK[c]
        if c.isalpha() or c.isdigit():
            return ord(c.upper())
        # Space and other ASCII that maps to itself.
        o = ord(c)
        return o if 0x20 <= o < 0x7F else 0
    if 0x41 <= qkey <= 0x5A:      # Qt.Key_A..Z are ASCII uppercase
        return qkey
    if 0x30 <= qkey <= 0x39:      # Qt.Key_0..9 are ASCII digits
        return qkey
    return 0


def encode_event(event) -> int:
    """A QKeyEvent -> the packed hotkey dword (modifiers << 8 | vk)."""
    mods = 0
    m = event.modifiers()
    if m & Qt.ControlModifier:
        mods |= 2
    if m & Qt.ShiftModifier:
        mods |= 4
    if m & Qt.AltModifier:
        mods |= 1
    if m & Qt.MetaModifier:
        mods |= 8
    vk = _vk_of(event.key(), event.text())
    if not vk or vk > 0xFF:
        # No main key (a bare modifier press) or a VK that does not
        # fit the packing's low byte: keep recording, save nothing.
        return 0
    return (mods << 8) | vk


# ------------------------------------------------------------- capture
#
# Shell state while a binding is armed (all on the Options shell):
#   _hk_recording      the HotKeys row key being captured (None = idle)
#   _hk_esc_armed      first Esc press seen; second one binds Escape
#   _hk_labels         row key -> its hotkey cell QLabel
#   _hk_hint           the "Click a hotkey..." line under the list
#   _hk_chips          chip name -> widget (hidden unless recording)
#   _hk_chip_mods      pending modifier bits from clicked mod chips
#   _hk_held_mods      modifier bits from physically held keys
#   _hk_pending_double (row key, code, deadline_ms) of the chord just
#                      saved -- an identical press inside the window
#                      upgrades it with bit15 (native's double-press)
#   _hk_dc             a DoubleCtrlDetector while HotKeyMainWindow records

# GetDoubleClickTime()'s stock value; native arms a SetTimer with it in
# the HotKeyCtrl window proc and the second identical chord inside the
# window sets bit15.
_DOUBLE_MS = 500.0

# Modifier bit -> display name, in format_hotkey's order (Ctrl, Shift,
# Alt, Win).
_MOD_NAMES = ((2, "Ctrl"), (4, "Shift"), (1, "Alt"), (8, "Win"))
_QT_MOD_BIT = {Qt.Key_Control: 2, Qt.Key_Shift: 4,
               Qt.Key_Alt: 1, Qt.Key_Meta: 8}

# The chip strip's special keys: (label, Win32 VK). Letters/digits stay
# physical-keyboard-only -- there are too many to chip and none are
# awkward to press.
_KEY_CHIPS = (("Esc", 0x1B), ("Tab", 0x09), ("Ent", 0x0D),
              ("Spc", 0x20), ("Bksp", 0x08),
              ("Left", 0x25), ("Up", 0x26), ("Right", 0x27),
              ("Down", 0x28))


def _now_ms():
    return time.monotonic() * 1000.0


def _eff_mods(shell) -> int:
    return (int(getattr(shell, "_hk_chip_mods", 0) or 0)
            | int(getattr(shell, "_hk_held_mods", 0) or 0))


def _mod_names(mods: int):
    return [name for bit, name in _MOD_NAMES if mods & bit]


def _preview_text(shell) -> str:
    """The live modifier preview shown on the recording row."""
    names = _mod_names(_eff_mods(shell))
    if names:
        return " + ".join(names) + " +"
    return "press keys... (same chord twice = Double)"


def _set_preview(shell, key):
    """Repaint the armed row: pending-Esc hint wins over the preview."""
    if getattr(shell, "_hk_esc_armed", False):
        return
    lab = (getattr(shell, "_hk_labels", {}) or {}).get(key)
    if lab is not None:
        try:
            lab.setText(_preview_text(shell))
        except Exception:
            pass


def _held_add(shell, bit):
    shell._hk_held_mods = int(getattr(shell, "_hk_held_mods", 0) or 0) | bit


def _held_remove(shell, bit):
    shell._hk_held_mods = (int(getattr(shell, "_hk_held_mods", 0) or 0)
                           & ~bit)


def _chip_toggle(shell, name):
    bit = dict((n, b) for b, n in _MOD_NAMES)[name]
    mods = int(getattr(shell, "_hk_chip_mods", 0) or 0)
    shell._hk_chip_mods = mods ^ bit
    key = getattr(shell, "_hk_recording", None)
    if key:
        _set_preview(shell, key)


def _chip_key(shell, vk):
    """A special-key chip completes the chord with pending modifiers."""
    key = getattr(shell, "_hk_recording", None)
    if not key:
        return
    if vk == 0x1B:
        # Esc keeps its arm-then-bind semantics through the chip too.
        if getattr(shell, "_hk_esc_armed", False):
            shell._hk_esc_armed = False
            _save_binding(shell, key, (_eff_mods(shell) << 8) | vk)
        else:
            shell._hk_esc_armed = True
            _set_preview(shell, key)
            lab = (getattr(shell, "_hk_labels", {}) or {}).get(key)
            if lab is not None:
                try:
                    lab.setText("press Esc again to bind, "
                                "any other key cancels")
                except Exception:
                    pass
        return
    _save_binding(shell, key, (_eff_mods(shell) << 8) | vk)


def _chip_cancel(shell):
    key = getattr(shell, "_hk_recording", None)
    if key:
        _cancel_recording(shell, key)


def _chip_w(text: str) -> int:
    """Chip width: ~7px per glyph at the page's 11px font, padded."""
    return max(22, len(text) * 7 + 12)


def _show_chips(shell, on):
    chips = getattr(shell, "_hk_chips", None) or {}
    for w in chips.values():
        try:
            w.setVisible(bool(on))
        except Exception:
            pass
    hint = getattr(shell, "_hk_hint", None)
    if hint is not None:
        try:
            hint.setVisible(not on)
        except Exception:
            pass


class _Recorder(QObject):
    """Captures the next key press while a binding is being recorded.

    Installed as an event filter on the Options shell; state lives on
    the shell (``_hk_recording`` / ``_hk_labels``) because ``build``
    runs with the shell as ``self``.
    """

    def eventFilter(self, obj, event):
        et = event.type()
        # The double-press window outlives the recording itself: the
        # chord just saved stays armed for _DOUBLE_MS so an identical
        # repeat upgrades it with bit15 (native's SetTimer path). Any
        # other key -- or the deadline passing -- closes the window.
        pend = getattr(obj, "_hk_pending_double", None)
        if (pend is not None and et == QEvent.Type.KeyPress
                and not event.isAutoRepeat()):
            pkey, pcode, deadline = pend
            code = encode_event(event)
            if code == pcode and _now_ms() < deadline:
                obj._hk_pending_double = None
                _save_binding(obj, pkey, pcode | 0x8000)
                return True
            obj._hk_pending_double = None
        key = getattr(obj, "_hk_recording", None)
        if not key:
            return False
        if et == QEvent.Type.KeyRelease:
            bit = _QT_MOD_BIT.get(event.key())
            if bit:
                _held_remove(obj, bit)
                _set_preview(obj, key)
                dc = getattr(obj, "_hk_dc", None)
                if dc is not None and event.key() == Qt.Key_Control:
                    # A completed second Ctrl tap inside the detector
                    # threshold saves the bare Double-Ctrl gesture.
                    if dc.on_control_released(_now_ms(), True):
                        _save_binding(obj, key, 0x8000)
            return True
        if et != QEvent.Type.KeyPress:
            return False
        if event.isAutoRepeat():
            return True
        k = event.key()
        dc = getattr(obj, "_hk_dc", None)
        if k in _QT_MOD_BIT:
            # A bare modifier press is previewed, never saved; on the
            # main-window row a Ctrl edge also feeds the double-Ctrl
            # detector exactly like the live key feed does.
            _held_add(obj, _QT_MOD_BIT[k])
            _set_preview(obj, key)
            if dc is not None:
                if k == Qt.Key_Control:
                    dc.on_control_pressed()
                else:
                    dc.on_other_key_pressed()
            return True
        if dc is not None:
            dc.on_other_key_pressed()
        if k == Qt.Key_Escape:
            # Esc is bindable, so it cannot be the plain cancel key.
            # The first press only arms a pending Escape (the row shows
            # a hint); the second press records it like any other key.
            if getattr(obj, "_hk_esc_armed", False):
                obj._hk_esc_armed = False
                code = encode_event(event)
                if code:
                    _save_binding(obj, key, code)
                else:
                    _cancel_recording(obj, key)
            else:
                obj._hk_esc_armed = True
                lab = (getattr(obj, "_hk_labels", {}) or {}).get(key)
                if lab is not None:
                    try:
                        lab.setText("press Esc again to bind, "
                                    "any other key cancels")
                    except Exception:
                        pass
        elif k == Qt.Key_Delete:
            # Delete is the explicit unbind (the row's "(none)").
            obj._hk_esc_armed = False
            _save_binding(obj, key, 0)
        else:
            # Any non-Esc key ends the pending-Escape state; the key
            # itself is then processed like any other press.
            obj._hk_esc_armed = False
            code = encode_event(event)
            if code:
                _save_binding(obj, key, code)
        return True


def _start_record(shell, key):
    shell._hk_recording = key
    shell._hk_esc_armed = False
    shell._hk_chip_mods = 0
    shell._hk_held_mods = 0
    shell._hk_pending_double = None
    # The bare Double-Ctrl gesture is only meaningful on the
    # show-main-window row (upstream's isDoubleCtrlEnabled lives on
    # SHOW_MAIN_WINDOW alone); other rows get no detector.
    shell._hk_dc = None
    if key == "HotKeyMainWindow":
        try:
            from ..hotkeys import DoubleCtrlDetector
            shell._hk_dc = DoubleCtrlDetector()
        except Exception:
            shell._hk_dc = None
    # Modifier chips are checkable; a previous capture may have left
    # some toggled on while the bitmask was reset.
    for name in ("Ctrl", "Alt", "Shift", "Win"):
        w = (getattr(shell, "_hk_chips", {}) or {}).get("mod:" + name)
        if w is not None:
            try:
                w.setChecked(False)
            except Exception:
                pass
    lab = (getattr(shell, "_hk_labels", {}) or {}).get(key)
    if lab is not None:
        try:
            lab.setText(_preview_text(shell))
        except Exception:
            pass
    _show_chips(shell, True)
    shell.setFocus(Qt.FocusReason.OtherFocusReason)


def _binding_label(code) -> str:
    """Row label for a packed hotkey dword.

    ``format_hotkey`` renders chords; the bare Double-Ctrl gesture
    (bit15 with no key -- ``HotKeyMainWindow=0x8000``) has no chord to
    name, so it gets the gesture's own label. That is the same words
    upstream shows on its separate "Double Ctrl" checkbox
    (``settings_hotkeys.double_ctrl_label``); the port's flat table has
    no second control, so the cell carries it.
    """
    try:
        code = int(code or 0)
    except Exception:
        code = 0
    if code & 0x8000 and not (code & 0xFFF):
        return "Double Ctrl"
    return _C.format_hotkey(code) or "(none)"


def _refresh_label(shell, key):
    lab = (getattr(shell, "_hk_labels", {}) or {}).get(key)
    if lab is not None:
        try:
            code = int(cfg_section("HotKeys").get(key, 0) or 0)
            lab.setText(_binding_label(code))
        except Exception:
            pass


def _cancel_recording(shell, key):
    """End the capture, keep the old binding."""
    shell._hk_recording = None
    shell._hk_esc_armed = False
    shell._hk_chip_mods = 0
    shell._hk_held_mods = 0
    shell._hk_dc = None
    _show_chips(shell, False)
    _refresh_label(shell, key)


def _conflicting_key(key, code):
    """Another HotKeys entry already bound to the same packed dword."""
    if not code:
        return None
    want = int(code) & 0xFFF
    hk = cfg_section("HotKeys")
    for other in _C.HOTKEY_NAMES:
        if other == key:
            continue
        if (int(hk.get(other, 0) or 0) & 0xFFF) == want:
            return other
    return None


# .tmp's preset combo labels (embedded_en.toml preset_label /
# preset_legacy / preset_modern / preset_custom); the kind is the
# config.HOTKEY_PRESETS name. The shown preset is identified from the
# bindings themselves, so a hand-edited set reports Custom like
# upstream's HotkeyPresets.identify.
_PRESET_LABELS = {"LEGACY": "Legacy QTranslate", "MODERN": "Modern",
                  "CUSTOM": "Custom"}
_PRESET_KINDS = {text: kind for kind, text in _PRESET_LABELS.items()}


def _reregister(shell):
    """Re-register so new bindings are live without a restart."""
    try:
        from .. import hotkeys as _HK
        app = getattr(shell, "app", None)
        _HK.uninstall()
        if app is not None:
            app.hotkeys = _HK.install(app)
    except Exception:
        pass


def _apply_preset(shell, kind):
    """Bulk-rebind every HotKey* to the preset (.tmp
    HotkeyDraftOperations.replacePreset), persist, re-register and
    repaint the rows -- the same tail _save_binding runs for one key."""
    try:
        cfg = _C.load() or {}
        cfg["HotKeys"] = _C.apply_hotkey_preset(
            cfg.get("HotKeys") or {}, kind)
        _C.save(cfg)
    except Exception:
        return
    _reregister(shell)
    for key, _action in ROWS:
        _refresh_label(shell, key)


def _preset_chosen(shell, pc):
    kind = _PRESET_KINDS.get(pc.currentText())
    if kind:
        _apply_preset(shell, kind)


def _save_binding(shell, key, code):
    if code:
        other = _conflicting_key(key, code)
        if other is not None:
            # Both actions would fire on the same chord (install()
            # registers every bound name). Warn and let the user pick
            # a different key or confirm the duplicate anyway.
            try:
                ans = QMessageBox.question(
                    shell,
                    "Hotkey already in use",
                    "This hotkey is already assigned to \"%s\".\n"
                    "Both actions will fire. Use it anyway?"
                    % _ROW_LABEL.get(other, other),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No)
            except Exception:
                ans = QMessageBox.No
            if ans != QMessageBox.Yes:
                shell._hk_recording = None
                shell._hk_esc_armed = False
                shell._hk_chip_mods = 0
                shell._hk_held_mods = 0
                shell._hk_dc = None
                _show_chips(shell, False)
                _refresh_label(shell, key)
                return
    cfg_set("HotKeys", key, int(code))
    _reregister(shell)
    shell._hk_recording = None
    shell._hk_esc_armed = False
    shell._hk_chip_mods = 0
    shell._hk_held_mods = 0
    shell._hk_dc = None
    _show_chips(shell, False)
    lab = (getattr(shell, "_hk_labels", {}) or {}).get(key)
    if lab is not None:
        try:
            lab.setText(_binding_label(code))
        except Exception:
            pass
    # Native's double-press: the same chord again inside the
    # double-click window re-saves it with bit15 set.
    shell._hk_pending_double = (
        (key, int(code), _now_ms() + _DOUBLE_MS) if code else None)


def _set_rows_enabled(shell, on):
    """EnableHotKeys=off greys the hotkey cells and blocks recording:
    the bindings stay in Options.json and come back when re-enabled."""
    for lab in (getattr(shell, "_hk_labels", {}) or {}).values():
        try:
            lab.setEnabled(bool(on))
        except Exception:
            pass


def _enable_toggled(shell, on):
    cfg_set("HotKeys", "EnableHotKeys", bool(on))
    _set_rows_enabled(shell, on)
    try:
        app = getattr(shell, "app", None)
        if app is not None and hasattr(app, "set_hotkeys_enabled"):
            app.set_hotkeys_enabled(bool(on))
    except Exception:
        pass


class HotkeysPage(OptionsBase):
    ORIGIN, SIZE = (1, 24), (650, 362)
    SEL = 1

    CHROME = {
        "panel": (10, 27, 142, 323),
        "row": (13, 29, 140),
        "face_row": None,
        "shadow_row": None,
        "rule": (356, 9, 645),
        "buttons": {
            "OK": (409, 361, 73, False),
            "Cancel": (490, 361, 73, False),
            "Apply": (571, 361, 73, False),
        },
    }

    def build(self):
        _build_vk_names()
        hk = cfg_section("HotKeys")
        # One recorder per shell; state on the shell itself.
        if getattr(self, "_hk_recorder", None) is None:
            self._hk_recorder = _Recorder(self)
            self.installEventFilter(self._hk_recorder)
            self._hk_recording = None
            self._hk_esc_armed = False
            self._hk_labels = {}
        # The "Enable hotkeys" checkbox: writes EnableHotKeys and
        # re-registers immediately, the way the tray item does.
        en = check(self, 159, 41, "Enable hotkeys",
                   bool(hk.get("EnableHotKeys", True)))
        en.toggled.connect(lambda v: _enable_toggled(self, v))
        # .tmp's preset combo (KeyboardPanel.kt): LEGACY/MODERN
        # bulk-rebind every HotKey*; CUSTOM clears them all. Sits on
        # the "Enable hotkeys" row -- the native page has no room for
        # an assignments group of its own.
        label(self, 280, 41, "Hotkey preset")
        pc = combo(self, 368, 30, 145,
                   _PRESET_LABELS[_C.hotkey_preset_kind(hk)],
                   h=18, values=list(_PRESET_LABELS.values()))
        pc.activated.connect(lambda _i: _preset_chosen(self, pc))
        # The list: 481 wide, 267 tall, with the vertical scrollbar's
        # track down the right and the horizontal one's along the
        # bottom. MEASURED off capture 2126.
        t = panel(self, 159, 60, 481, 267)
        rect(t, 623, 61, 16, 252, FACE)         # the vertical track
        rect(t, 161, 312, 462, 14, FACE)        # the horizontal track
        rect(t, 630, 77, 2, 164, THUMB)         # the vertical thumb
        rect(t, 177, 317, 412, 2, THUMB)        # the horizontal thumb
        label(t, 166, 71, "Action")
        label(t, 484, 71, "Hotkey")
        self._hk_labels = {}
        # 17 rows at the native pitch would run off the panel's bottom
        # (and into the OK/Cancel row), so the pitch tightens to fit:
        # first row centre 86, last 294, above the scrollbar track.
        first_y, pitch = 86, 13
        for i, (key, action) in enumerate(ROWS):
            label(t, 166, first_y + pitch * i, action)
            code = int(hk.get(key, 0) or 0)
            disp = _binding_label(code)
            lab = label(t, 484, first_y + pitch * i, disp)
            self._hk_labels[key] = lab
            # Click the hotkey cell to record a new binding.
            lab.mousePressEvent = (lambda _e, k=key:
                                   _start_record(self, k))
        # EnableHotKeys=off: the cells show greyed and refuse to arm.
        _set_rows_enabled(self, bool(hk.get("EnableHotKeys", True)))
        # The hint under the list: click a hotkey to change it. While a
        # binding is armed the hint hides and the recorder chip strip
        # takes its row (modifier toggles + special keys + Cancel).
        self._hk_hint = label(
            self, 166, 334,
            "Click a hotkey, then press the new keys "
            "(Esc twice binds, Del unbinds).", color="#555555")
        self._hk_chips = {}
        cx = 164
        for name, _bit in (("Ctrl", 2), ("Alt", 1), ("Shift", 4),
                           ("Win", 8)):
            w = button(self, cx, 326, _chip_w(name), name, h=16)
            w.setCheckable(True)
            w.setStyleSheet(
                "QPushButton:checked{background:#c8c4bc;"
                "border:1px solid #7a766c;}")
            w.clicked.connect(
                lambda _c=False, n=name: _chip_toggle(self, n))
            self._hk_chips["mod:" + name] = w
            cx += w.width() + 3
        for text, vk in _KEY_CHIPS:
            w = button(self, cx, 326, _chip_w(text), text, h=16)
            w.clicked.connect(
                lambda _c=False, v=vk: _chip_key(self, v))
            self._hk_chips["key:" + text] = w
            cx += w.width() + 3
        w = button(self, cx, 326, _chip_w("Cancel"), "Cancel", h=16)
        w.clicked.connect(lambda _c=False: _chip_cancel(self))
        self._hk_chips["cancel"] = w
        _show_chips(self, False)
