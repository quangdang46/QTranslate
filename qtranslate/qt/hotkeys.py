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

``HotKeyMainWindow=0x8000`` (the "Double" bit15 prefix) is not a chord
at all: it is upstream's Double Ctrl gesture -- two genuine Control
taps under 400 ms apart, never a Ctrl+key chord -- detected by
``DoubleCtrlDetector`` below. It needs the raw key stream, so it rides
the CGEventTap's key observer on macOS and a dedicated ``keyboard.hook``
listener on the ``keyboard`` backend. The Carbon fallback sees only
completed chords and leaves the gesture unbound (documented
degradation, never a false trigger).
"""
from __future__ import annotations

import threading
import time

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
    "HotKeyMainWindow": "hotkey_main_window",
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


# ------------------------------------------------------- Double Ctrl
#
# .tmp's DoubleCtrlDetector (ui-swing .../input/DoubleCtrlDetector.kt)
# is a pure state machine over Control press/release edges: two genuine
# Ctrl taps less than DOUBLE_CTRL_THRESHOLD_MS apart fire SHOW_MAIN_WINDOW
# once. A tap counts only when its press was observed before the release
# (orphan/synthetic releases are ignored) and no other key was pressed
# while Ctrl was down (Ctrl+C is a chord, not a tap). SHOW_MAIN_WINDOW's
# Options.json dword carries the gesture as bit15 -- the "Double" prefix
# ``config.format_hotkey`` displays -- and ``config.hotkey_combo`` yields
# no chord for HotKeyMainWindow=0x8000, so install() feeds the raw key
# stream to this detector instead of registering a combo.
DOUBLE_CTRL_THRESHOLD_MS = 400.0

# ``keyboard``-package key names for the Control keys (its hook reports
# left/right variants separately from plain "ctrl").
_CTRL_KEY_NAMES = frozenset({"ctrl", "left ctrl", "right ctrl"})


class DoubleCtrlDetector:
    """Faithful port of .tmp ``DoubleCtrlDetector``.

    Tracking runs unconditionally; only firing is gated on ``active``
    (upstream passes ``effectiveHotkeysEnabled && binding.isEnabled &&
    isDoubleCtrlEnabled`` at release time). ``last_tap`` is ``None`` --
    not a ``0`` sentinel -- because a real event can land at or near
    zero, which would make the first tap of a session pair with itself.
    """

    def __init__(self, threshold_ms=DOUBLE_CTRL_THRESHOLD_MS):
        self._threshold_ms = threshold_ms
        self._down = False
        self._press_observed = False
        self._part_of_combination = False
        self._last_tap_ms = None

    def on_control_pressed(self):
        if not self._down:
            self._down = True
            self._press_observed = True
            self._part_of_combination = False

    def on_other_key_pressed(self):
        self._part_of_combination = True

    def reset(self):
        """Forget all tap state (disable/pause transitions upstream)."""
        self._down = False
        self._press_observed = False
        self._part_of_combination = False
        self._last_tap_ms = None

    def on_control_released(self, now_ms, active):
        """True only when this release completes a tap pair in-window."""
        if not self._down or not self._press_observed:
            self._down = False
            self._press_observed = False
            return False
        self._down = False
        self._press_observed = False
        if self._part_of_combination:
            self._part_of_combination = False
            self._last_tap_ms = None
            return False
        if not active:
            return False
        previous = self._last_tap_ms
        if previous is not None and now_ms - previous < self._threshold_ms:
            self._last_tap_ms = None
            return True
        self._last_tap_ms = now_ms
        return False


# Live Double Ctrl feed state, so uninstall() can tear down whichever
# backend install() wired: {"stop": threading.Event|None,
# "observer": ("tap", table)|None}.
_DC_FEED = {"stop": None, "observer": None}


def _double_ctrl_code(hk) -> int:
    try:
        return int((hk or {}).get("HotKeyMainWindow", 0) or 0)
    except Exception:
        return 0


def _start_keyboard_feed(keyboard, on_key) -> bool:
    """Feed ``on_key`` from the ``keyboard`` package's global hook.

    The Windows/X11 backend gets the same gesture through a dedicated
    ``keyboard.hook`` listener on a daemon thread; the hook only
    OBSERVES (``suppress`` stays off) so typing is unaffected. Returns
    False when the package has no usable hook -- the gesture then stays
    unbound, an honest degradation that can never false-fire.
    """
    hook = getattr(keyboard, "hook", None)
    if hook is None:
        return False
    stop = threading.Event()
    ready = threading.Event()
    live = [False]
    cancelled = [False]

    def _cb(event):
        if not live[0] or cancelled[0]:
            return
        try:
            name = str(getattr(event, "name", "") or "").lower()
            etype = str(getattr(event, "event_type", "") or "").lower()
            if name in _CTRL_KEY_NAMES:
                on_key("ctrl", etype == "down")
            elif etype == "down":
                on_key("other", True)
        except Exception:
            pass

    def _run():
        try:
            with hook(_cb):
                live[0] = True
                ready.set()
                stop.wait()
        except Exception:
            pass
        finally:
            live[0] = False
            ready.set()

    thread = threading.Thread(target=_run,
                              name="qtranslate-double-ctrl",
                              daemon=True)
    thread.start()
    if not ready.wait(2.0) or not thread.is_alive():
        # Too slow or dead: cancel so a late-starting hook can never
        # feed the detector after install() reported the gesture
        # unbound, and ask the thread to exit if it is still starting.
        cancelled[0] = True
        stop.set()
        return False
    _DC_FEED["stop"] = stop
    return True


def _stop_double_ctrl() -> None:
    """Tear down the feed install() wired, whichever backend it was."""
    stop = _DC_FEED.get("stop")
    _DC_FEED["stop"] = None
    if stop is not None:
        try:
            stop.set()
        except Exception:
            pass
    obs = _DC_FEED.get("observer")
    _DC_FEED["observer"] = None
    if obs is not None:
        try:
            _kind, table = obs
            table.set_key_observer(None)
        except Exception:
            pass


def _install_double_ctrl(app, hk, backend, keyboard):
    """Wire the bit15 "Double Ctrl" gesture; return its bound label.

    Only HotKeyMainWindow's bit15 arms the detector -- upstream's
    ``isDoubleCtrlEnabled`` exists on SHOW_MAIN_WINDOW alone, and a
    ``0x8000`` bit on any other HotKey* name is ignored rather than
    guessed at. ``backend``/``keyboard`` are install()'s already-resolved
    backends. Returns ``None`` when the gesture is not configured or no
    backend can see raw Control edges (the Carbon table only sees
    completed chords): unbound beats wrong.
    """
    if not (_double_ctrl_code(hk) & 0x8000):
        return None
    detector = DoubleCtrlDetector()
    was_recording = [False]

    def _fire():
        try:
            # The same target the HotKeyMainWindow chord dispatches to
            # (ACTIONS), so double-Ctrl and a bound chord behave alike:
            # capture selection, translate into the main window, show.
            fn = getattr(app, ACTIONS["HotKeyMainWindow"], None)
            if fn is None:
                fn = app.show_main_window
            app._on_ui(fn)
        except Exception:
            pass

    def _on_key(kind, pressed):
        try:
            # The options page recording a binding is upstream's pause:
            # the detector resets on the transition so a tap before or
            # during recording can never pair with one after.
            recording = _options_recording(app)
            if recording and not was_recording[0]:
                detector.reset()
            was_recording[0] = recording
            if recording:
                return
            # ``active`` mirrors upstream's doubleCtrlEffective(): the
            # global switch is on (install() only runs then), the
            # SHOW_MAIN_WINDOW binding carries bit15 (checked above),
            # and nothing is paused (the recording check just above).
            if kind == "ctrl":
                if pressed:
                    detector.on_control_pressed()
                elif detector.on_control_released(
                        time.monotonic() * 1000.0, True):
                    _fire()
            elif pressed:
                detector.on_other_key_pressed()
        except Exception:
            pass

    if backend is not None and backend[0] == "tap":
        _kind, table = backend
        if table.set_key_observer(_on_key):
            _DC_FEED["observer"] = ("tap", table)
            return "HotKeyMainWindow=double-ctrl"
        table.set_key_observer(None)
        return None
    if backend is not None:
        # Carbon RegisterEventHotKey reports only completed chords --
        # there is no raw Control stream for the detector to ride.
        _log("install: double-ctrl needs the tap backend; "
             "carbon backend cannot see raw Control edges")
        return None
    if keyboard is not None and _start_keyboard_feed(keyboard, _on_key):
        return "HotKeyMainWindow=double-ctrl"
    return None


def _options_recording(app) -> bool:
    """True while the Hotkeys page is capturing a new binding."""
    try:
        opts = getattr(app, "_opts", None)
        return bool(getattr(opts, "_hk_recording", None))
    except Exception:
        return False


_suppress_supported = None


def _add_hotkey_suppressed(keyboard, combo, safe) -> bool:
    """Register ``combo`` with key suppression where the backend allows.

    ``keyboard.add_hotkey`` gained a ``suppress`` parameter in 0.13
    (it lives in ``blocking_hotkeys`` instead of ``nonblocking_hotkeys``,
    so a fired hotkey no longer leaks its keys to the foreground app).
    requirements.txt pins 0.13.5, but a zero-install run
    (``uv run --with keyboard``) can resolve an older build, so the
    parameter is detected from the signature and the call falls back to
    the plain form rather than failing registration outright.
    """
    global _suppress_supported
    if _suppress_supported is None:
        try:
            import inspect
            _suppress_supported = ("suppress" in inspect.signature(
                keyboard.add_hotkey).parameters)
        except Exception:
            _suppress_supported = False
    try:
        if _suppress_supported:
            keyboard.add_hotkey(combo, safe, suppress=True)
        else:
            keyboard.add_hotkey(combo, safe)
        return True
    except TypeError:
        # Signature lied (e.g. a wrapper without **kwargs) -- register
        # without suppression rather than lose the hotkey entirely.
        try:
            keyboard.add_hotkey(combo, safe)
            return True
        except Exception:
            return False
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

    # install() may follow a previous install() without an uninstall()
    # (callers are supposed to pair them, but a stale feed would leak a
    # listener thread or a tap observer either way).
    _stop_double_ctrl()

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
        if _add_hotkey_suppressed(keyboard, combo, safe):
            bound.append("%s=%s" % (name, combo))
    # HotKeyMainWindow=0x8000 has no chord (hotkey_combo yields ""), so
    # the loop above never sees it: the "Double" bit15 gesture is wired
    # to the raw-key detector instead. A dword carrying BOTH bit15 and a
    # chord ("Double Ctrl + Q") still registers the chord normally --
    # upstream's chord and double-Ctrl mechanisms are independent, and
    # the chord firing on a single press is correct there.
    label = _install_double_ctrl(app, hk, backend, keyboard)
    if label:
        bound.append(label)
    _log("install: bound=%r" % (bound,))
    return bound


def uninstall() -> None:
    """Release every registration, so a toggle can re-register cleanly."""
    _stop_double_ctrl()
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
