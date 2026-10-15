"""Key synthesis — port of `FUN_0043BD5C` (row: SendInput synth).

Native: Ctrl-down → key-down → `Sleep(0x20)` → key-up → Ctrl-up, via a
zeroed `tagINPUT` + `SendInput(1, &input, 0x1C)` (IAT `0x50D504`). The
port uses the `keyboard` package; this module wraps `send`/`write` so
the call sites are testable (the backend is injectable) and report
honestly instead of raising when the library is absent.
"""
from __future__ import annotations


def send(combo, backend=None):
    """Synthesize a combo like ``ctrl+c``; True when delivered.

    ``backend`` defaults to the `keyboard` package when importable.
    """
    try:
        kb = backend
        if kb is None:
            import keyboard as kb
        kb.send(combo)
        return True
    except Exception:
        return False


def write_text(text, backend=None, limit=2000):
    """Retype text (the `TaskConvertTextLayout` retype engine consumer);
    True when delivered."""
    try:
        kb = backend
        if kb is None:
            import keyboard as kb
        kb.write((text or "")[:limit])
        return True
    except Exception:
        return False
