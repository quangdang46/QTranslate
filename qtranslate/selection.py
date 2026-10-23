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

    # Native waits for the modifier keys to come up first: a held Shift
    # turns Ctrl+C into Ctrl+Shift+C, which many apps do not treat as copy.
    if pressed is None:
        try:
            import keyboard

            def pressed(key):
                try:
                    return bool(keyboard.is_pressed(key))
                except Exception:
                    return False
        except Exception:
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
    return read()
