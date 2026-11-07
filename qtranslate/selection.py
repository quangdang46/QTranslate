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


def copy_selection(backend=None, send=None, read=None, sequence=None,
                   sleep=None, pressed=None,
                   start_ms=BACKOFF_START_MS, cap_ms=BACKOFF_CAP_MS,
                   steps=BACKOFF_STEPS) -> str:
    """Synthesize Ctrl+C and return the text that copy produced.

    ``backend`` is the key backend to inject in tests (the ``keyboard``
    package by default); ``send``/``read``/``sequence``/``sleep``/
    ``pressed`` are the other seams, all defaulted, so the behaviour is
    testable without a real clipboard or a real keystroke.

    Returns ``""`` when nothing provably new was captured: modifiers
    still held at the neutralization deadline, a copy that cannot be
    proven on a platform WITH a sequence counter (``send`` refused --
    nothing was copied, the clipboard is stale by definition -- or a
    delivered copy whose sequence never moved), or an empty clipboard
    after a confirmed change. The clipboard-as-it-stands fallback
    survives ONLY where the platform has no sequence counter at all
    (the copy could not be proven either way -- the "copy could not be
    attempted" semantic), pinned in ``tests/regress_selection_capture.py``.
    """
    from qtranslate import clipboard, sendkeys

    read = read or clipboard.read_text
    sequence = sequence or clipboard.sequence
    sleep = sleep or _default_sleep
    before = sequence()

    # Neutralization (.tmp awaitCopyNeutral / TriggerNeutralizer): NO
    # contaminating modifier may still be held when the synthetic Copy
    # goes out — a held Shift turns it into Ctrl+Shift+C, a held Alt
    # into a menu accelerator, and the Win key into a system chord.
    # Fail CLOSED on timeout: injecting anyway delivers the wrong chord
    # to the frontmost app, which is worse than not capturing.
    if not _neutralize_modifiers(pressed, sleep):
        return ""

    # .tmp SelectionCapture: snapshot the clipboard BEFORE the copy is
    # synthesized and restore it after the text is read, so triggering
    # a translation never destroys what the user had on their clipboard.
    snap = None
    try:
        snap = clipboard.snapshot()
    except Exception:
        snap = None
    try:
        return _capture_after_snapshot(
            backend, send, read, sequence, sleep, before,
            start_ms, cap_ms, steps)
    finally:
        if snap is not None:
            try:
                clipboard.restore(snap)
            except Exception:
                pass


def _capture_after_snapshot(backend, send, read, sequence, sleep,
                            before, start_ms, cap_ms, steps):
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
        return "" if seq_ok else read()

    if not seq_ok:
        # No sequence counter on this platform: nothing to poll, so
        # take one bounded pause and read -- the copy could not be
        # proven either way.
        sleep(0.15)
        return read()

    wait_ms = start_ms
    for _ in range(steps):
        sleep(wait_ms / 1000.0)
        now = sequence()
        # A mid-poll -1/None means the counter blinked, not that the
        # clipboard changed -- only a REAL new number is proof the
        # copy landed.
        if now is not None and now >= 0 and now != before:
            return read()
        wait_ms = min(wait_ms * 2, cap_ms)
    # The copy was delivered but the sequence NEVER moved: the frontmost
    # app had no selection (or refused the copy). Returning the stale
    # clipboard here is exactly the "Ctrl+Q translates last week's
    # clipboard" bug -- native's answer is "no selection, nothing to
    # translate". The read fallback lives only where the platform has
    # no sequence counter at all, handled above.
    return ""
