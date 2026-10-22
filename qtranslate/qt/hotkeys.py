"""The global hotkeys, on PySide6.

Native registers exactly the hotkeys bound in its settings file, and
the routing mirrors the help.txt the native ships: PopupWindow =>
translate the selection and show the popup, MainWindow => show the main
window, ReplaceSelection => translate the selection and retype it,
ListenText/ListenTranslation => speak, Dictionary/DictionaryClipboard =>
the dictionary window, History => the history window, Keyboard => the
virtual keyboard, ConvertTextLayout => fix the layout, CopyTranslation
=> copy the result, TextRecognition => OCR, SwitchMouseMode => cycle
the mouse mode, TranslateClipboard* => translate the clipboard, and
SpeechInput => the offline SAPI recogniser.

The binding's PACKING is the core's (``config.hotkey_combo``), so the
two front ends cannot disagree about which key a binding is.
"""
from __future__ import annotations

from qtranslate.platforms import keyboard_module as _keyboard

# The actions the settings file can bind, and what each one does. The
# value is the name of the QtApp method.
ACTIONS = {
    "HotKeyPopupWindow": "hotkey_popup",
    "HotKeyMainWindow": "show_main_window",
    "HotKeyReplaceSelection": "hotkey_replace_selection",
    "HotKeyListenText": "hotkey_listen_text",
    "HotKeyListenTranslation": "hotkey_listen_translation",
    "HotKeyDictionary": "open_dictionary",
    "HotKeyDictionaryClipboard": "hotkey_dictionary_clipboard",
    "HotKeyHistory": "open_history",
    "HotKeyKeyboard": "open_keyboard",
    "HotKeyConvertTextLayout": "hotkey_convert_layout",
    "HotKeyCopyTranslation": "hotkey_copy_translation",
    "HotKeyTextRecognition": "open_ocr",
    "HotKeyTranslateClipboard": "hotkey_translate_clipboard",
    "HotKeyTranslateClipboardInMainWindow": "hotkey_translate_clipboard",
    "HotKeyTranslateClipboardInPopupWindow": "hotkey_popup",
    "HotKeySpeechInput": "hotkey_speech_input",
    "HotKeySwitchMouseMode": "hotkey_switch_mouse_mode",
}


def install(app) -> list:
    """Register the hotkeys the settings file binds.

    Returns the list of "name=combo" that were bound, so the caller
    can report what is live. A hotkey the settings file leaves unbound
    is not registered at all -- native does not register it either, and
    an unbound key that fires is worse than one that does nothing.
    """
    keyboard = _keyboard()
    if keyboard is None:
        # `keyboard` needs a desktop session (and admin rights on
        # Windows); without it there are no global hotkeys, which is
        # the same degradation native's own code path has. Off Windows
        # it is not even imported: on macOS the import aborts the
        # process when the Accessibility permission is missing.
        return []

    from qtranslate import config
    try:
        hk = (config.load() or {}).get("HotKeys", {}) or {}
    except Exception:
        hk = {}
    if not hk.get("EnableHotKeys", True):
        return []

    bound = []
    for name, method in ACTIONS.items():
        combo = config.hotkey_combo(hk.get(name, 0) or 0)
        if not combo:
            continue
        fn = getattr(app, method, None)
        if fn is None:
            continue
        # ``keyboard`` fires the callback on ITS OWN listener thread,
        # not Qt's. Running it straight would let the handler touch
        # widgets from the wrong thread, which crashes the process
        # outright (access violation, not a catchable exception).
        # ``app._on_ui`` re-runs the handler on the UI thread instead.
        safe = (lambda f: (lambda: app._on_ui(f)))(fn)
        try:
            keyboard.add_hotkey(combo, safe)
            bound.append("%s=%s" % (name, combo))
        except Exception:
            continue
    return bound
