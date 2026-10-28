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

Two registration mechanisms, because the platforms do not share one:

  * **Windows** -- the ``keyboard`` package (a Win32 keyboard hook). It
    fires on its own listener thread, so each handler is wrapped in
    ``app._on_ui``.
  * **macOS** -- Carbon ``RegisterEventHotKey`` (``macos_hotkeys``).
    ``keyboard`` CANNOT be used there: its import aborts the process
    inside CoreFoundation on macOS 26, and an event tap would need the
    Accessibility permission an unsigned bundle does not have. The
    Carbon path delivers on the UI thread and needs no permission.
"""
from __future__ import annotations

from qtranslate.platforms import keyboard_module as _keyboard


def _log(msg):
    """Temporary diagnostic: append to ~/.qtranslate_hotkeys.log."""
    try:
        import os
        import time
        path = os.path.join(os.path.expanduser("~"),
                            ".qtranslate_hotkeys.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass

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


def _settings():
    """The HotKeys section, and whether the feature is on."""
    from qtranslate import config
    try:
        hk = (config.load() or {}).get("HotKeys", {}) or {}
    except Exception:
        hk = {}
    return hk, bool(hk.get("EnableHotKeys", True))


def _macos_table():
    """The Carbon table on macOS, or ``None`` elsewhere."""
    import sys
    if sys.platform != "darwin":
        return None
    try:
        from qtranslate import macos_hotkeys
        if not macos_hotkeys.available():
            return None
        return macos_hotkeys.table()
    except Exception:
        return None


def install(app) -> list:
    """Register the hotkeys the settings file binds.

    Returns the list of "name=combo" that were bound, so the caller
    can report what is live. A hotkey the settings file leaves unbound
    is not registered at all -- native does not register it either, and
    an unbound key that fires is worse than one that does nothing.
    """
    from qtranslate import config

    hk, enabled = _settings()
    if not enabled:
        return []

    macos = _macos_table()
    keyboard = None if macos is not None else _keyboard()
    _log("install: macos_table=%s keyboard=%s enable=%s"
         % (macos is not None, keyboard is not None, enabled))
    if macos is None and keyboard is None:
        _log("install: NO backend available")
        return []

    bound = []
    for name, method in ACTIONS.items():
        combo = config.hotkey_combo(hk.get(name, 0) or 0)
        if not combo:
            continue
        fn = getattr(app, method, None)
        if fn is None:
            continue
        if macos is not None:
            # Carbon delivers on the main run loop, i.e. the UI thread.
            # The wrapper is still harmless there and keeps one shape.
            if macos.add(name, combo, (lambda f: lambda: app._on_ui(f))(fn)):
                bound.append("%s=%s" % (name, combo))
            continue
        # ``keyboard`` fires the callback on ITS OWN listener thread, not
        # Qt's. Running it straight would let the handler touch widgets
        # from the wrong thread, which crashes the process outright (an
        # access violation, not a catchable exception). ``app._on_ui``
        # re-runs the handler on the UI thread instead.
        safe = (lambda f: (lambda: app._on_ui(f)))(fn)
        try:
            keyboard.add_hotkey(combo, safe)
            bound.append("%s=%s" % (name, combo))
        except Exception:
            continue
    _log("install: bound=%r" % (bound,))
    return bound


def uninstall() -> None:
    """Release every registration, so a toggle can re-register cleanly."""
    import sys
    if sys.platform == "darwin":
        try:
            from qtranslate import macos_hotkeys
            macos_hotkeys.table().clear()
        except Exception:
            pass
        return
    keyboard = _keyboard()
    if keyboard is None:
        return
    try:
        keyboard.unhook_all_hotkeys()
    except Exception:
        pass
