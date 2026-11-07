"""Copy-capture: read the text the user has SELECTED in another app.

Native's help.txt says ``Ctrl+Q => Translate selected text and show it in
popup window``. "Selected" is not "whatever is already on the clipboard":
the selection has to be copied first. Native's engine for that is
``FUN_0043BF30``/``FUN_0043C02B`` (documented in ``NATIVE_ARCH.md`` item
4):

1. wait for contaminating modifiers (Shift/Alt/Win on Windows,
   Shift/Ctrl/Option on macOS) to be released -- a modifier still held
   would change what the synthesized copy means; the wait is bounded
   (~2s, .tmp TriggerNeutralizer's budget) and fails CLOSED,
2. snapshot ``GetClipboardSequenceNumber``,
3. synthesize Ctrl+C,
4. poll the sequence number with exponential backoff (8ms .. 320ms) until
   it CHANGES -- that change is the proof the copy actually landed.

Step 4 is the part that matters. Reading the clipboard after a fixed
``sleep`` is a guess: a slow target app has not written yet, so the reader
gets the PREVIOUS clipboard content and silently translates the wrong
text. The sequence number makes "the copy landed" observable instead of
assumed.

The whole flow degrades honestly, and the stale-clipboard paths are
fail-CLOSED wherever they can be proven: where a sequence counter
exists (Windows ``GetClipboardSequenceNumber``, macOS NSPasteboard
``changeCount``) a copy that cannot be proven -- send refused, or the
sequence never moving -- returns ``""``, because the clipboard still
holds whatever it held before, i.e. stale by definition. Only on a
platform with NO counter at all is the copy's fate unobservable, and
only there does the old clipboard-as-it-stands read survive: one
bounded pause, one read, never a hang. Where no key synthesizer exists
the caller gets the clipboard as it stands, which is the old behaviour
-- no worse than before.
"""
from __future__ import annotations

# Native's backoff: 8ms doubling to 320ms. Eight steps reach the cap, and
# the total wait is under a second -- native's own budget for a copy that
# is not going to arrive at all.
BACKOFF_START_MS = 8
BACKOFF_CAP_MS = 320
BACKOFF_STEPS = 8

# .tmp SelectionCapture.restoreWithRetry: a BUSY clipboard is retried up
# to 3 attempts, 50ms apart; any other restore failure is permanent and
# fails after a single attempt. Either way a failed restore suppresses
# the captured action -- the caller must never act on text copied while
# the user's own clipboard could not be put back.
RESTORE_MAX_ATTEMPTS = 3
RESTORE_RETRY_DELAY_S = 0.05

# Modifier-neutralization budget (.tmp TriggerNeutralizer waits 2000ms
# and fails CLOSED). A still-held Shift at the deadline would turn the
# synthesized copy into Ctrl+Shift+C -- a different chord delivered to
# the frontmost app -- so on timeout the capture aborts instead of
# injecting. The chord family's OWN modifier is exempt (Ctrl for
# Ctrl+C on Windows, Command for Cmd+C on macOS): .tmp
# ChordNeutralization.watchedSet excludes it for the same reason.
NEUTRALIZE_BUDGET_S = 2.0
NEUTRALIZE_STEP_S = 0.01
_NEUTRALIZE_STEPS = int(NEUTRALIZE_BUDGET_S / NEUTRALIZE_STEP_S)

# Contaminating modifiers polled through the ``keyboard`` backend
# (Windows). "ctrl" is deliberately absent: it is the copy chord's own
# modifier family. The Win key is watched too -- a held Win turns the
# copy into a system chord.
_NEUTRALIZE_KEYS = (
    "alt", "shift",
    "left windows", "right windows", "windows", "meta",
)

# macOS HID flags that contaminate the delivered Cmd+C. Command
# (0x00100000) is the chord's own modifier and is exempt; Shift,
# Control and Alternate still change what Cmd+C means.
_DARWIN_CONTAMINATING = (0x00020000 | 0x00040000 | 0x00080000)


def _default_sleep(seconds):
    import time
    time.sleep(seconds)


def _neutralize_modifiers(pressed, sleep) -> bool:
    """Wait for contaminating modifiers to come up; False on timeout.

    ``pressed`` is the injected ``key -> bool`` seam (tests, or the
    ``keyboard`` package). When it is ``None`` the real backend is
    resolved: the ``keyboard`` package where it can run (Windows), else
    macOS HID flags via ``macos_input.modifiers()`` -- the package
    cannot even be imported there (SIGABRT). Where NO modifier source
    exists at all the wait cannot observe anything, so it reports
    released rather than hanging the capture forever.
    """
    if pressed is None:
        try:
            from qtranslate.platforms import keyboard_module
            _kb = keyboard_module()
        except Exception:
            _kb = None
        if _kb is not None:
            def pressed(key):
                try:
                    return bool(_kb.is_pressed(key))
                except Exception:
                    return False
    try:
        if pressed is not None:
            for _ in range(_NEUTRALIZE_STEPS):
                held = False
                for key in _NEUTRALIZE_KEYS:
                    try:
                        if pressed(key):
                            held = True
                            break
                    except Exception:
                        continue
                if not held:
                    return True
                sleep(NEUTRALIZE_STEP_S)
            return False
        import sys as _sys
        if _sys.platform == "darwin":
            from qtranslate import macos_input as _mi
            for _ in range(_NEUTRALIZE_STEPS):
                try:
                    held = bool(_mi.modifiers() & _DARWIN_CONTAMINATING)
                except Exception:
                    return True
                if not held:
                    return True
                sleep(NEUTRALIZE_STEP_S)
            return False
    except Exception:
        pass
    return True


_LAST_REASON = ""


def last_reason() -> str:
    """Why the most recent ``copy_selection`` returned "" (or "ok").

    Diagnostic only -- the app logs it next to the empty-capture line so
    a missing icon/popup can be told apart: held modifiers, refused
    send, unmoved sequence counter, or an actually-empty clipboard.
    """
    return _LAST_REASON


def copy_selection(backend=None, send=None, read=None, sequence=None,
                   sleep=None, pressed=None,
                   start_ms=BACKOFF_START_MS, cap_ms=BACKOFF_CAP_MS,
                   steps=BACKOFF_STEPS, snapshot=None, restore=None) -> str:
    """Synthesize Ctrl+C and return the text that copy produced.

    ``backend`` is the key backend to inject in tests (the ``keyboard``
    package by default); ``send``/``read``/``sequence``/``sleep``/
    ``pressed`` are the other seams, all defaulted, so the behaviour is
    testable without a real clipboard or a real keystroke. ``snapshot``
    and ``restore`` are the clipboard-snapshot seams, likewise defaulted
    to ``clipboard.snapshot``/``clipboard.restore``.

    Returns ``""`` when nothing provably new was captured: modifiers
    still held at the neutralization deadline, a copy that cannot be
    proven on a platform WITH a sequence counter (``send`` refused --
    nothing was copied, the clipboard is stale by definition -- or a
    delivered copy whose sequence never moved), an empty clipboard
    after a confirmed change, or a clipboard that could not be restored
    after the copy (.tmp ``CaptureFailure.RESTORE_FAILED`` -- the action
    is NOT dispatched on unrestored clipboard state). The
    clipboard-as-it-stands fallback survives ONLY where the platform
    has no sequence counter at all (the copy could not be proven either
    way -- the "copy could not be attempted" semantic), pinned in
    ``tests/regress_selection_capture.py``.
    """
    from qtranslate import clipboard, sendkeys

    global _LAST_REASON
    _LAST_REASON = "ok"
    read = read or clipboard.read_text
    sequence = sequence or clipboard.sequence
    sleep = sleep or _default_sleep
    snapshot = snapshot or clipboard.snapshot
    restore = restore or clipboard.restore

    # Neutralization (.tmp awaitCopyNeutral / TriggerNeutralizer): NO
    # contaminating modifier may still be held when the synthetic Copy
    # goes out — a held Shift turns it into Ctrl+Shift+C, a held Alt
    # into a menu accelerator, and the Win key into a system chord.
    # Fail CLOSED on timeout: injecting anyway delivers the wrong chord
    # to the frontmost app, which is worse than not capturing.
    if not _neutralize_modifiers(pressed, sleep):
        _LAST_REASON = "modifiers-held"
        return ""

    # The clipboard baseline is taken AFTER neutralization, immediately
    # before the snapshot+copy — a token from before the (up to 2s)
    # modifier wait can be stale and misattribute an external copy to
    # our synthetic one.
    before = sequence()

    # .tmp SelectionCapture: snapshot the clipboard BEFORE the copy is
    # synthesized and restore it after the text is read, so triggering
    # a translation never destroys what the user had on their clipboard.
    # Fail CLOSED when the snapshot fails: copying without a restore
    # path can destroy the user's clipboard contents.
    try:
        snap = snapshot()
    except Exception:
        _LAST_REASON = "snapshot-failed"
        return ""
    if snap is None:
        _LAST_REASON = "snapshot-failed"
        return ""
    try:
        out = _capture_after_snapshot(
            backend, send, read, sequence, sleep, before,
            start_ms, cap_ms, steps)
        if not out and _LAST_REASON == "ok":
            _LAST_REASON = "empty-read"
    except Exception:
        # The restore is still owed when the capture itself blew up;
        # its result is moot once the exception propagates.
        try:
            _restore_with_retry(restore, snap, sleep)
        except Exception:
            pass
        raise
    if not _restore_with_retry(restore, snap, sleep):
        # .tmp SelectionCapture: the copy landed but the user's
        # clipboard could not be put back -- fail CLOSED. Returning the
        # text here would dispatch an action on clipboard state the
        # user did not leave there.
        _LAST_REASON = "restore-failed"
        return ""
    return out


def _restore_with_retry(restore, snap, sleep) -> bool:
    """Restore the snapshot with .tmp ``restoreWithRetry`` semantics.

    ``clipboard.ClipboardBusyError`` is the only retryable failure
    (another process holds the clipboard open): retried up to
    ``RESTORE_MAX_ATTEMPTS`` total, ``RESTORE_RETRY_DELAY_S`` apart. A
    plain False or any other exception is permanent and fails after ONE
    attempt. Never raises for restore failures; ``sleep``/``restore``
    seam errors propagate to the caller's guard.
    """
    from qtranslate import clipboard as _cb
    for attempt in range(1, RESTORE_MAX_ATTEMPTS + 1):
        try:
            if restore(snap):
                return True
            busy = False
        except _cb.ClipboardBusyError:
            busy = True
        except Exception:
            busy = False
        if not busy or attempt >= RESTORE_MAX_ATTEMPTS:
            return False
        sleep(RESTORE_RETRY_DELAY_S)
    return False


def _capture_after_snapshot(backend, send, read, sequence, sleep,
                            before, start_ms, cap_ms, steps):
    global _LAST_REASON
    from qtranslate import sendkeys

    # Platform-aware fail-closed. ``before`` is the one snapshot taken
    # before the copy; a platform WITH a counter returns a real number
    # (>=0), one WITHOUT returns -1/None. A single -1 could be
    # transient, so probe the counter once more before declaring the
    # platform blind -- and a valid probe doubles as a fresh baseline,
    # since it is still taken before the copy goes out.
    if before is None or before < 0:
        try:
            probe = sequence()
        except Exception:
            probe = None
        if probe is not None and probe >= 0:
            before = probe
    seq_ok = before is not None and before >= 0

    delivered = sendkeys.send("ctrl+c", backend=backend) if send is None \
        else send("ctrl+c")
    if not delivered:
        # The copy was refused before it went out. Where a sequence
        # counter exists that is PROOF nothing was copied -- the
        # clipboard still holds whatever it held before, i.e. stale by
        # definition, so fail closed with "". Only where the platform
        # has no counter at all is the copy's fate unobservable, and
        # only there does the bounded read fallback survive (the "copy
        # could not be attempted" semantic; no copy means the clipboard
        # cannot have changed, so no wait is needed either).
        _LAST_REASON = ("send-refused+seq" if seq_ok
                        else "send-refused-no-seq")
        return "" if seq_ok else read()

    if not seq_ok:
        # No sequence counter on this platform: nothing to poll, so
        # take one bounded pause and read -- the copy could not be
        # proven either way.
        sleep(0.15)
        _LAST_REASON = "no-seq-read"
        return read()

    wait_ms = start_ms
    for _ in range(steps):
        sleep(wait_ms / 1000.0)
        now = sequence()
        # A mid-poll -1/None means the counter blinked, not that the
        # clipboard changed -- only a REAL new number is proof the
        # copy landed.
        if now is not None and now >= 0 and now != before:
            _LAST_REASON = "ok"
            return read()
        wait_ms = min(wait_ms * 2, cap_ms)
    # The copy was delivered but the sequence NEVER moved: the frontmost
    # app had no selection (or refused the copy). Returning the stale
    # clipboard here is exactly the "Ctrl+Q translates last week's
    # clipboard" bug -- native's answer is "no selection, nothing to
    # translate". The read fallback lives only where the platform has
    # no sequence counter at all, handled above.
    _LAST_REASON = "seq-unchanged"
    return ""
