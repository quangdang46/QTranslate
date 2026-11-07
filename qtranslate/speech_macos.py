"""Speech input on macOS — ``SFSpeechRecognizer`` via PyObjC.

Native QTranslate 6.10's speech input is mic -> FLAC -> Google's
full-duplex speech URL (``qtranslate/speech_input.py``); that API is
retired and there is no macOS-specific native path to mirror, so this
module is the port's own best-effort replacement using the OS speech
framework. It is deliberately honest: every failure mode returns ``""``
from :func:`recognize` and records a machine-readable reason readable
via :func:`last_reason`, so the caller can render a status line instead
of pretending recognition worked.

Requirements (all enforced, none assumed):

* macOS 10.15+ (``SFSpeechRecognizer`` does not exist before that).
* PyObjC with the ``Speech`` and ``AVFoundation`` wrappers
  (``pip install pyobjc-framework-Speech pyobjc-framework-AVFoundation``;
  ``pyobjc-framework-Cocoa`` pulls both in on most installs).
* TCC permissions, prompted the first time:
    - Speech recognition: ``NSSpeechRecognitionUsageDescription`` must be
      present in the app bundle's ``Info.plist`` or the system denies
      the request outright. For an *unbundled* ``python`` process the
      responsible process is the terminal/launcher, so the prompt is
      attributed there -- grant it under System Settings > Privacy &
      Security > Speech Recognition (and Microphone for the engine tap).
    - Microphone: ``NSMicrophoneUsageDescription`` for the
      ``AVAudioEngine`` input tap.
  Bundled apps (the ``qtranslate.spec`` path) must add BOTH keys to the
  plist; see ``qtranslate.spec`` / the bundle docs.

API shape::

    text = speech_macos.recognize(timeout_s=10)   # blocking, worker thread
    if not text:
        ... speech_macos.last_reason() ...        # e.g. "speech-permission-denied"

:func:`recognize` is safe to call from any thread; it blocks up to
``timeout_s`` seconds and returns the best final transcription, or ``""``
on silence/failure. It is NOT safe to call on the Qt UI thread -- the
caller (``QTranslateApp.hotkey_speech_input``) must hop to a worker and
marshal the result back with ``app._on_ui``.

Everything PyObjC is imported lazily inside the functions that need it,
so this module imports cleanly on Linux/Windows and in test environments
without PyObjC installed.
"""
from __future__ import annotations

import sys
import threading
import time

# SFSpeechRecognizerAuthorizationStatus (Speech/SFSpeechRecognizer.h).
_AUTH_NOT_DETERMINED = 0
_AUTH_DENIED = 1
_AUTH_RESTRICTED = 2
_AUTH_AUTHORIZED = 3

# SFSpeechRecognitionTaskHint.
_TASK_HINT_DICTATION = 1

# Why the last recognize() call returned "". Module-global rather than an
# exception because the API contract is "str in, str out"; callers that
# want the reason read it immediately after the call (same thread or
# after join -- recognize() is blocking, so there is no race in practice).
_LAST_REASON = ""


def _set_reason(reason: str) -> str:
    global _LAST_REASON
    _LAST_REASON = reason
    return ""


def last_reason() -> str:
    """Machine-readable reason the previous :func:`recognize` returned "".

    Empty string means the last call either succeeded or has not run yet.
    Reasons: ``unsupported-platform``, ``macos-too-old``,
    ``pyobjc-unavailable``, ``speech-permission-not-determined`` (request
    timed out / dismissed), ``speech-permission-denied``,
    ``speech-permission-restricted``, ``recognizer-unavailable``,
    ``session-init:<err>``, ``recognition-error:<err>``, ``no-speech``.
    """
    return _LAST_REASON


def _speech_frameworks():
    """``(Speech, AVFoundation)`` modules, or None when unusable.

    Lazy on purpose: importing PyObjC frameworks at module scope would
    break the Qt app on Windows/Linux and in minimal test envs.
    """
    if sys.platform != "darwin":
        return None
    try:
        # macOS 10.15 gate: SFSpeechRecognizer was introduced there.
        # NSProcessInfo.operatingSystemVersion avoids parsing sw_vers.
        from Foundation import NSProcessInfo
        v = NSProcessInfo.processInfo().operatingSystemVersion()
        if (v.majorVersion(), v.minorVersion(), v.patchVersion()) < (10, 15, 0):
            return None
    except Exception:
        pass  # version probe failed -- let the import decide below
    try:
        import Speech  # noqa: F401  (pyobjc-framework-Speech / Cocoa)
        import AVFoundation  # noqa: F401
    except Exception:
        return None
    import Speech as _S
    import AVFoundation as _A
    return _S, _A


def available() -> bool:
    """True when the OS-level pieces exist (platform + PyObjC + 10.15+)."""
    return _speech_frameworks() is not None


def authorization_status() -> int | None:
    """Current TCC speech-recognition status, or None if unavailable.

    Returns one of the ``_AUTH_*`` values (0=notDetermined, 1=denied,
    2=restricted, 3=authorized). Does NOT prompt.
    """
    mods = _speech_frameworks()
    if mods is None:
        return None
    Speech, _ = mods
    try:
        return int(Speech.SFSpeechRecognizer.authorizationStatus())
    except Exception:
        return None


def request_authorization(timeout_s: float = 60.0) -> int | None:
    """Ask macOS for speech-recognition permission; blocks up to timeout.

    Shows the system TCC prompt when status is notDetermined. Returns the
    resulting status int, or None when the framework is unavailable or
    the prompt never answered within ``timeout_s``.
    """
    mods = _speech_frameworks()
    if mods is None:
        return None
    Speech, _ = mods
    status = authorization_status()
    if status in (_AUTH_DENIED, _AUTH_RESTRICTED, _AUTH_AUTHORIZED):
        return status
    done = threading.Event()
    box = {"status": None}

    def _handler(*args):
        # The TCC status arrives as the first (only meaningful) arg; the
        # exact block arity varies across macOS versions, so accept both.
        box["status"] = int(args[0]) if args else None
        done.set()

    try:
        Speech.SFSpeechRecognizer.requestAuthorization_(_handler)
    except Exception:
        return status
    deadline = time.monotonic() + timeout_s
    while not done.is_set() and time.monotonic() < deadline:
        _pump_runloop(0.1)
    return box["status"]


def _pump_runloop(seconds: float) -> None:
    """Run the current NSRunLoop briefly so main-queue blocks can fire.

    SFSpeechRecognizer delivers its result handler on an internal queue,
    but requestAuthorization's completion and any AppKit-adjacent work
    can land on the main queue; pumping covers both without depending on
    which thread recognize() was called from.
    """
    try:
        from Foundation import NSRunLoop, NSDate
        NSRunLoop.currentRunLoop().runMode_beforeDate_(
            "NSDefaultRunLoopMode",
            NSDate.dateWithTimeIntervalSinceNow_(seconds))
    except Exception:
        time.sleep(seconds)


class _SpeechSession:
    """One recognition pass: mic tap -> SFSpeechAudioBufferRecognitionRequest.

    Owns the AVAudioEngine input tap and the recognition task so
    :func:`recognize` stays a thin orchestration layer. ``run`` blocks up
    to ``timeout_s`` and returns the best transcription seen ("" if none).
    """

    def __init__(self, Speech, AVFoundation, recognizer):
        self._Speech = Speech
        self._AVF = AVFoundation
        self._recognizer = recognizer
        self._request = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
        self._request.setShouldReportPartialResults_(True)
        self._request.setTaskHint_(_TASK_HINT_DICTATION)
        self._engine = AVFoundation.AVAudioEngine.alloc().init()
        self._done = threading.Event()
        self._text = ""
        self._error = None
        self._tap_installed = False
        self._task = None  # SFSpeechRecognitionTask -- must stay retained

    # -- callbacks (invoked on Speech/audio queues; must be thread-safe) --

    def _on_buffer(self, buffer):
        try:
            self._request.appendAudioPCMBuffer_(buffer)
        except Exception:
            pass

    def _on_result(self, *args):
        # Apple contract: (SFSpeechRecognitionResult, NSError); tolerate
        # arity drift across OS versions rather than dropping callbacks.
        result = args[0] if args else None
        error = args[1] if len(args) > 1 else None
        try:
            if error is not None:
                self._error = str(error)
                self._done.set()
                return
            if result is not None:
                try:
                    transcription = result.bestTranscription()
                    if transcription is not None:
                        text = transcription.formattedString()
                        if text:
                            self._text = text
                except Exception:
                    pass
                try:
                    if result.isFinal():
                        self._done.set()
                except Exception:
                    pass
        except Exception:
            pass

    # -- lifecycle -------------------------------------------------------

    def _teardown(self, node):
        try:
            self._request.endAudio()
        except Exception:
            pass
        try:
            self._engine.stop()
        except Exception:
            pass
        try:
            if self._tap_installed and node is not None:
                node.removeTapOnBus_(0)
        except Exception:
            pass
        try:
            self._request.finalize()
        except Exception:
            pass

    def _cancel_task(self):
        try:
            if self._task is not None:
                self._task.cancel()
                self._task = None
        except Exception:
            pass

    def run(self, timeout_s: float) -> str:
        """Record from the default input until final result or timeout."""
        node = None
        try:
            node = self._engine.inputNode()
            fmt = node.outputFormatForBus_(0)
            node.installTapOnBus_bufferSize_format_block_(
                0, 4096, fmt, self._on_buffer)
            self._tap_installed = True
        except Exception as exc:
            self._error = "audio-input:%s" % exc
            self._done.set()
        if self._error is None:
            try:
                # Keep the task object: nothing else retains it, and a
                # deallocated task cancels the recognition silently.
                self._task = self._recognizer \
                    .recognitionTaskWithRequest_resultHandler_(
                        self._request, self._on_result)
            except Exception as exc:
                self._error = "task:%s" % exc
                self._done.set()
        if self._error is None:
            try:
                self._engine.start()
            except Exception as exc:
                # Engine start can fail when the mic TCC grant is missing;
                # the tap simply never delivers buffers and we time out --
                # but reporting the start error is more honest.
                self._error = "engine:%s" % exc
                self._done.set()

        deadline = time.monotonic() + max(0.1, timeout_s)
        while not self._done.is_set() and time.monotonic() < deadline:
            _pump_runloop(0.05)
        self._teardown(node)
        # The task may still flush a final result during teardown; wait
        # briefly for it so the last words are not lost.
        grace = time.monotonic() + 0.5
        while not self._done.is_set() and self._text == "" \
                and time.monotonic() < grace:
            _pump_runloop(0.05)
        # Only now is it safe to cancel: endAudio + the grace window let
        # the final transcription land first.
        self._cancel_task()
        return self._text or ""


def recognize(timeout_s: float = 10.0, auth: int | None = None,
              recognizer=None, session=None) -> str:
    """Block up to ``timeout_s`` seconds; return recognized text or "".

    ``auth``: override the TCC status lookup (tests inject 0-3). When
    None, the real ``SFSpeechRecognizer.authorizationStatus()`` is used
    and a notDetermined status triggers ``requestAuthorization`` (which
    can itself block up to ``timeout_s`` on the system prompt).

    ``recognizer``: injectable recognizer object (needs ``isAvailable``
    and ``recognitionTaskWithRequest_resultHandler_``). When None, a
    default-locale ``SFSpeechRecognizer`` is created.

    ``session``: injectable session object with ``run(timeout_s) -> str``
    (and optionally an ``error`` attribute). When None, a real
    :class:`_SpeechSession` is built. Passing a fake session plus
    ``auth=3`` exercises the whole orchestration path without PyObjC.

    Never raises for expected failures; check :func:`last_reason`.
    """
    global _LAST_REASON
    _LAST_REASON = ""

    if sys.platform != "darwin":
        return _set_reason("unsupported-platform")

    if auth is None:
        mods = _speech_frameworks()
        if mods is None:
            return _set_reason("pyobjc-unavailable-or-macos-too-old")
        status = authorization_status()
        if status is None:
            return _set_reason("speech-status-unavailable")
    else:
        status = int(auth)
    if status == _AUTH_NOT_DETERMINED:
        status = request_authorization(timeout_s=min(timeout_s, 60.0))
        if status is None:
            return _set_reason("speech-permission-not-determined")

    if status == _AUTH_DENIED:
        return _set_reason("speech-permission-denied")
    if status == _AUTH_RESTRICTED:
        return _set_reason("speech-permission-restricted")
    if status != _AUTH_AUTHORIZED:
        return _set_reason("speech-permission-unknown(%d)" % status)

    if session is None:
        mods = _speech_frameworks()
        if mods is None:
            return _set_reason("pyobjc-unavailable")
        Speech, AVFoundation = mods
        if recognizer is None:
            try:
                recognizer = Speech.SFSpeechRecognizer.alloc().init()
            except Exception as exc:
                return _set_reason("recognizer-init:%s" % exc)
        try:
            if not recognizer.isAvailable():
                return _set_reason("recognizer-unavailable")
        except Exception:
            return _set_reason("recognizer-unavailable")
        try:
            session = _SpeechSession(Speech, AVFoundation, recognizer)
        except Exception as exc:
            return _set_reason("session-init:%s" % exc)

    try:
        text = session.run(timeout_s) or ""
    except Exception as exc:  # noqa: BLE001 - never propagate to hotkey
        return _set_reason("recognition-error:%s" % exc)
    if text:
        return text
    err = getattr(session, "error", None) or getattr(session, "_error", None)
    if err:
        return _set_reason("recognition-error:%s" % err)
    return _set_reason("no-speech")
