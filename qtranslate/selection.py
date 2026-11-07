"""Copy-capture: read the text the user has SELECTED in another app.

Native's help.txt says ``Ctrl+Q => Translate selected text and show it in
popup window``. "Selected" is not "whatever is already on the clipboard":
the selection has to be copied first. Native's engine for that is
``FUN_0043BF30``/``FUN_0043C02B`` (documented in ``NATIVE_ARCH.md`` item
4):

1. wait for Alt/Shift to be released (a modifier still held would change
   what the synthesized Ctrl+C means),
2. snapshot ``GetClipboardSequenceNumber``,
3. synthesize Ctrl+C,
4. poll the sequence number with exponential backoff (8ms .. 320ms) until
   it CHANGES -- that change is the proof the copy actually landed.

Step 4 is the part that matters. Reading the clipboard after a fixed
``sleep`` is a guess: a slow target app has not written yet, so the reader
gets the PREVIOUS clipboard content and silently translates the wrong
text. The sequence number makes "the copy landed" observable instead of
assumed.

The whole flow degrades honestly: where no clipboard backend or no key
synthesizer exists (off Windows, or the ``keyboard`` package is absent)
the caller gets the clipboard as it stands, which is the old behaviour --
no worse than before, and never a hang.
"""
from __future__ import annotations

# Native's backoff: 8ms doubling to 320ms. Eight steps reach the cap, and
# the total wait is under a second -- native's own budget for a copy that
# is not going to arrive at all.
BACKOFF_START_MS = 8
BACKOFF_CAP_MS = 320
BACKOFF_STEPS = 8


def _default_sleep(seconds):
    import time
    time.sleep(seconds)


def copy_selection(backend=None, send=None, read=None, sequence=None,
                   sleep=None, pressed=None,
                   start_ms=BACKOFF_START_MS, cap_ms=BACKOFF_CAP_MS,
                   steps=BACKOFF_STEPS) -> str:
    """Synthesize Ctrl+C and return the text that copy produced.

    ``backend`` is the key backend to inject in tests (the ``keyboard``
    package by default); ``send``/``read``/``sequence``/``sleep``/
    ``pressed`` are the other seams, all defaulted, so the behaviour is
    testable without a real clipboard or a real keystroke.

    Returns ``""`` when the copy never landed AND the clipboard was empty;
    otherwise the clipboard's text either way, because a target app that
    does not accept Ctrl+C still leaves the user's previous content, and
    translating that is better than translating nothing.
    """
    from qtranslate import clipboard, sendkeys

    read = read or clipboard.read_text
    sequence = sequence or clipboard.sequence
    sleep = sleep or _default_sleep
    before = sequence()

    # Neutralization (.tmp awaitCopyNeutral): NO modifier may still be
    # held when the synthetic Copy goes out — a held Shift turns it
    # into Ctrl+Shift+C, a held Alt into a menu accelerator, and the
    # trigger chord itself (Ctrl for Ctrl+Q, Option for Alt+W) would
    # contaminate the injected flags. Windows reads the ``keyboard``
    # package; macOS reads the real HID flags through CoreGraphics --
    # the package cannot even be imported there (SIGABRT).
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
        else:
            def pressed(_key):
                return False
    try:
        for key in ("alt", "shift"):
            for _ in range(20):
                if not pressed(key):
                    break
                sleep(0.01)
    except Exception:
        pass
    try:
        import sys as _sys
        if _sys.platform == "darwin":
            from qtranslate import macos_input as _mi
            _ALL = (0x00100000 | 0x00020000
                    | 0x00040000 | 0x00080000)
            for _ in range(30):
                if not (_mi.modifiers() & _ALL):
                    break
                sleep(0.01)
    except Exception:
        pass

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
    delivered = sendkeys.send("ctrl+c", backend=backend) if send is None \
        else send("ctrl+c")
    if not delivered:
        return read()

    # Exponential backoff until the sequence number moves. -1 means the
    # counter is unavailable (off Windows); in that case there is nothing
    # to observe, so take one bounded pause and read.
    if before is None or before < 0:
        sleep(0.15)
        return read()

    wait_ms = start_ms
    for _ in range(steps):
        sleep(wait_ms / 1000.0)
        now = sequence()
        if now is not None and now != before:
            return read()
        wait_ms = min(wait_ms * 2, cap_ms)
    # The copy was delivered but the sequence NEVER moved: the frontmost
    # app had no selection (or refused the copy). Returning the stale
    # clipboard here is exactly the "Ctrl+Q translates last week's
    # clipboard" bug -- native's answer is "no selection, nothing to
    # translate". The clipboard fallback lives only where the copy
    # could not even be attempted (send refused, or no sequence
    # counter), handled above.
    return ""
