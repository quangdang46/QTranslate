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
    "HotKeyTranslateClipboardInPopupWindow": "hotkey_popup_clipboard",
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
    """The macOS backend, or ``None`` elsewhere.

    Preference order: the CGEventTap (``macos_tap``) first -- Carbon's
    ``RegisterEventHotKey`` accepts registrations under Qt but its
    events never arrive on this host. The Carbon table stays as the
    fallback for a machine without the Accessibility grant (the tap
    needs it; Carbon does not, and may work where the tap cannot).
    Returns ``(kind, table)``.
    """
    import sys
    if sys.platform != "darwin":
        return None
    try:
        from qtranslate import macos_tap
        if macos_tap.available():
            return "tap", macos_tap.table()
    except Exception:
        pass
    try:
        from qtranslate import macos_hotkeys
        if macos_hotkeys.available():
            return "carbon", macos_hotkeys.table()
    except Exception:
        pass
    return None


def _options_recording(app) -> bool:
    """True while the Hotkeys page is capturing a new binding."""
    try:
        opts = getattr(app, "_opts", None)
        return bool(getattr(opts, "_hk_recording", None))
    except Exception:
        return False


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

    backend = _macos_table()
    keyboard = None if backend is not None else _keyboard()
    _log("install: macos_backend=%s keyboard=%s enable=%s"
         % (backend[0] if backend else None, keyboard is not None,
            enabled))
    if backend is None and keyboard is None:
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
        if backend is not None:
            kind, table = backend
            # Both backends fire OFF the UI thread's own context: the
            # Carbon path on the main run loop, the tap on its worker --
            # so the _on_ui wrap is required either way. And while the
            # Hotkeys page is RECORDING a binding, the chord being
            # pressed is the new binding, not the action -- firing it
            # would translate whatever happens to be selected every
            # time the user rebinds a key. The tap's consume_guard is
            # the same check one level down: while recording, the chord
            # must also pass THROUGH to the recorder unconsumed.
            def _recording():
                return _options_recording(app)
            try:
                table.consume_guard = (lambda: not _recording())
            except Exception:
                pass
            safe = (lambda f: (lambda: None if _recording()
                               else app._on_ui(f)))(fn)
            ok = False
            try:
                ok = table.add(name, combo, safe)
            except Exception:
                ok = False
            if not ok and kind == "tap":
                # The tap needs the Accessibility grant; Carbon does
                # not. A machine without the grant may still get the
                # Carbon registration (it delivers on hosts where its
                # run-loop integration works).
                try:
                    from qtranslate import macos_hotkeys
                    ok = macos_hotkeys.table().add(name, combo, safe)
                except Exception:
                    ok = False
            if ok:
                bound.append("%s=%s" % (name, combo))
            continue
        # ``keyboard`` fires the callback on ITS OWN listener thread, not
        # Qt's. Running it straight would let the handler touch widgets
        # from the wrong thread, which crashes the process outright (an
        # access violation, not a catchable exception). ``app._on_ui``
        # re-runs the handler on the UI thread instead. Same recording
        # guard as the macOS backends: a chord pressed to BIND a hotkey
        # is not the action firing.
        safe = (lambda f: (lambda: None if _options_recording(app)
                           else app._on_ui(f)))(fn)
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
            from qtranslate import macos_tap
            macos_tap.table().clear()
        except Exception:
            pass
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
