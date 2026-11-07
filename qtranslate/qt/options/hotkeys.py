"""The Hotkeys page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

WIRED: the rows are the real bindings from Options.json
(``config.HOTKEY_NAMES`` + ``format_hotkey``), "Enable hotkeys" writes
``HotKeys.EnableHotKeys`` and re-registers, and clicking a row's hotkey
cell arms a capture -- the next key press is encoded into the same
``(modifiers << 8) | vk`` packing native uses and saved.

NB: ``build`` runs on the SHELL instance (a BasicsPage), so all page
behaviour lives in module functions and a small event filter -- never
``self._methods`` (see options/extensions.py for the same rule).
"""

from PySide6.QtCore import QObject, QEvent, Qt

from qtranslate import config as _C

from .base import OptionsBase, cfg_section, cfg_set, check, label
from ..widgets import panel, rect

from qtranslate_style import FACE, THUMB

# Row label -> the Options.json HotKeys key. Order is native's list
# order (the capture), mapped to the names the file carries.
ROWS = [
    ("HotKeyMainWindow", "Show main window"),
    ("HotKeyPopupWindow", "Show popup window"),
    ("HotKeyDictionary", "Show dictionary window"),
    ("HotKeyHistory", "Show history window"),
    ("HotKeyKeyboard", "Show keyboard window"),
    ("HotKeyListenText", "Listen to selected text"),
    ("HotKeyCopyTranslation", "Copy translation to clipboard"),
    ("HotKeyReplaceSelection", "Replace selected text"),
    ("HotKeySwitchMouseMode", "Switch mouse mode"),
    ("HotKeyTranslateClipboard", "Translate clipboard content"),
    ("HotKeyTranslateClipboardInMainWindow",
     "Translate clipboard in main window"),
    ("HotKeyTranslateClipboardInPopupWindow",
     "Translate clipboard in popup window"),
    ("HotKeyDictionaryClipboard", "Dictionary from clipboard"),
]

# Qt key -> the Win32 VK the settings file stores (the common keys;
# letters/digits are their ASCII uppercase).
_VK = {"backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
       "escape": 0x1B, "esc": 0x1B, "space": 0x20, "delete": 0x2E,
       "insert": 0x2D, "home": 0x24, "end": 0x23, "prior": 0x21,
       "next": 0x22, "left": 0x25, "up": 0x26, "right": 0x27,
       "down": 0x28}
for _i in range(1, 13):
    _VK["f%d" % _i] = 0x70 + _i - 1

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
    }


def _vk_of(qkey: int, text: str) -> int:
    name = _VK_NAME.get(qkey)
    if name in _VK:
        return _VK[name]
    if len(text) == 1 and text.isprintable():
        return ord(text.upper())
    if 0x41 <= qkey <= 0x5A:      # Qt.Key_A..Z are ASCII uppercase
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
    if not vk:
        return 0
    return (mods << 8) | vk


class _Recorder(QObject):
    """Captures the next key press while a binding is being recorded.

    Installed as an event filter on the Options shell; state lives on
    the shell (``_hk_recording`` / ``_hk_labels``) because ``build``
    runs with the shell as ``self``.
    """

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.KeyPress:
            return False
        key = getattr(obj, "_hk_recording", None)
        if not key:
            return False
        if event.key() in (Qt.Key_Escape, Qt.Key_Delete):
            _save_binding(obj, key, 0)
        else:
            code = encode_event(event)
            if code:
                _save_binding(obj, key, code)
        return True


def _start_record(shell, key):
    shell._hk_recording = key
    lab = (getattr(shell, "_hk_labels", {}) or {}).get(key)
    if lab is not None:
        try:
            lab.setText("press keys...")
        except Exception:
            pass
    shell.setFocus(Qt.FocusReason.OtherFocusReason)


def _save_binding(shell, key, code):
    cfg_set("HotKeys", key, int(code))
    # Re-register so the new binding is live without a restart.
    try:
        from .. import hotkeys as _HK
        app = getattr(shell, "app", None)
        _HK.uninstall()
        if app is not None:
            app.hotkeys = _HK.install(app)
    except Exception:
        pass
    shell._hk_recording = None
    lab = (getattr(shell, "_hk_labels", {}) or {}).get(key)
    if lab is not None:
        try:
            lab.setText(_C.format_hotkey(code) or "(none)")
        except Exception:
            pass


def _enable_toggled(shell, on):
    cfg_set("HotKeys", "EnableHotKeys", bool(on))
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
            self._hk_labels = {}
        # The "Enable hotkeys" checkbox: writes EnableHotKeys and
        # re-registers immediately, the way the tray item does.
        en = check(self, 159, 41, "Enable hotkeys",
                   bool(hk.get("EnableHotKeys", True)))
        en.toggled.connect(lambda v: _enable_toggled(self, v))
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
        for i, (key, action) in enumerate(ROWS):
            label(t, 166, 92 + 17 * i, action)
            code = int(hk.get(key, 0) or 0)
            disp = _C.format_hotkey(code) or "(none)"
            lab = label(t, 484, 92 + 17 * i, disp)
            self._hk_labels[key] = lab
            # Click the hotkey cell to record a new binding.
            lab.mousePressEvent = (lambda _e, k=key:
                                   _start_record(self, k))
        # The hint under the list: click a hotkey to change it.
        label(self, 166, 334, "Click a hotkey, then press the new keys.",
              color="#555555")
