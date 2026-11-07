"""Key synthesis — port of `FUN_0043BD5C` (row: SendInput synth).

Native: Ctrl-down → key-down → `Sleep(0x20)` → key-up → Ctrl-up, via a
zeroed `tagINPUT` + `SendInput(1, &input, 0x1C)` (IAT `0x50D504`). The
port uses the `keyboard` package on Windows; this module wraps
`send`/`write` so the call sites are testable (the backend is injectable)
and report honestly instead of raising when the library is absent.

Two hard rules learned on macOS (2026-10-28):

- NEVER ``import keyboard`` directly. On macOS the import ABORTS the
  process inside CoreFoundation (SIGABRT, ``__CFDataValidateRange``) —
  a ``try`` cannot catch it. The only door is
  ``platforms.keyboard_module()``, which returns ``None`` off Windows.
- On macOS the synthesis goes through ``qtranslate.macos_input``
  (CoreGraphics CGEvent), which needs the Accessibility grant and
  reports False honestly when it is missing.
"""
from __future__ import annotations


def _backend_module(backend=None):
    """The key backend: an injected fake, ``keyboard_module()``, or None."""
    if backend is not None:
        return backend
    try:
        from qtranslate.platforms import keyboard_module
        return keyboard_module()
    except Exception:
        return None


def send(combo, backend=None):
    """Synthesize a combo like ``ctrl+c``; True when delivered.

    ``backend`` defaults to the platform backend (``keyboard`` on
    Windows, CoreGraphics on macOS). On macOS the combo's primary
    modifier is delivered as Command — see ``macos_input``'s docstring.
    """
    kb = _backend_module(backend)
    if kb is not None:
        try:
            kb.send(combo)
            return True
        except Exception:
            return False
    try:
        import sys
        if sys.platform == "darwin":
            from qtranslate import macos_input
            return macos_input.send(combo)
    except Exception:
        pass
    return False


def write_text(text, backend=None, limit=2000):
    """Retype text (the `TaskConvertTextLayout` retype engine consumer);
    True when delivered."""
    text = (text or "")[:limit]
    kb = _backend_module(backend)
    if kb is not None:
        try:
            kb.write(text)
            return True
        except Exception:
            return False
    try:
        import sys
        if sys.platform == "darwin":
            from qtranslate import macos_input
            return macos_input.type_text(text)
    except Exception:
        pass
    return False
