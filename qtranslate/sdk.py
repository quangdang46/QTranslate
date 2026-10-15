"""Public SDK surface — Slice 5 (approved 2026-10-15).

Locked surface: ``translate``, ``detect``, ``speak``, ``dict_lookup``,
``Result``. ``back_translate`` stays internal (not exported here) until
its contract and callers are verified. Nothing here imports tkinter.

``translate``/``detect``/``dict_lookup`` run headless; ``speak`` routes
through ``player.play_text`` (BASS online → SAPI fallback), same as the
UI path.
"""
from __future__ import annotations

from qtranslate.core import Result

__all__ = ["Result", "translate", "detect", "speak", "dict_lookup",
           "back_translate_internal"]


def translate(service, text, target, src="auto", auto_detect=False):
    """Translate via the engine (same path as the UI)."""
    from qtranslate import engine as _ENG
    return _ENG.translate(service, text, target, src=src,
                          auto_detect=auto_detect)


def detect(text):
    """Detect the source language (registry detect-retry loop)."""
    from qtranslate import registry as _RG
    return _RG.detect_language(text)


def speak(text, lang):
    """Online mp3 → BASS; on failure fall back to offline SAPI."""
    try:
        from qtranslate import config as _C
        slow = bool(_C.load().get("Advanced", {}).get(
            "EnableSlowerListening", False))
    except Exception:
        slow = False
    from qtranslate.player import play_text
    play_text(text, lang, slow=slow)


def dict_lookup(word, src="en", target="vi", service="google"):
    """Look up one word through the DICTS table (offline XDXF included)."""
    from qtranslate.registry import DICTS
    fn = DICTS.get(service)
    if fn is None:
        raise KeyError("unknown dictionary: %r" % (service,))
    return fn(word, src, target)


def back_translate_internal(service, text, target, src):
    """Internal back-translation (NOT public API — kept out of __all__ use).

    Exposed as a named function only so the internal caller is testable;
    SDK consumers must not rely on it until the contract is verified.
    """
    from qtranslate import engine as _ENG
    res = _ENG.translate(service, text, target, src=src)
    if not res.ok:
        return res
    # Back-translate through the provider that answered, swapping src/tgt.
    return _ENG.translate(res.provider_used or service, res.text,
                          src, src=target)
