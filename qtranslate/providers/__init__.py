"""Provider contract + thin adapters — Slice 1 (approved 2026-10-15).

A provider is anything with ``name``, ``translate(text, src, tgt)`` and
``detect(text)`` (when the provider has one); ``langs()`` returns that
provider's OWN language table — tables are never merged (per-provider
``SUPPORTED_LANGS`` keep their own ``-1`` holes, indices and semantics).

Design decisions locked before this slice (design-only phase):

1. ``SUPPORTED_LANGS`` stays per-provider; no vocabulary merge.
2. ``detect_language`` stays owned by ``registry``; the contract only
   declares per-provider ``detect()``.
3. The SDK surface (``translate``/``detect``/``speak``/``dict_lookup``/
   ``Result``) comes later; ``back_translate`` stays internal.
4. ``bing`` is an **alias of ``microsoft``** (rule (b)): same adapter
   object, never a separate fallback-chain entry (both keys map to one
   callable, and native ``Services/`` has no Bing directory while
   ``SERVICE_NAMES`` has no ``bing`` key).
5. ``USES_AUTO_DETECT`` stays re-exported from ``registry`` through this
   slice; it becomes a contract attribute in a later slice, not this one.

Nothing here opens a window or touches the network at import time.
tkinter-free (pinned by ``tests/regress_provider_contract.py``).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Provider(Protocol):
    """Structural contract for a translate provider adapter."""

    name: str
    uses_auto_detect: bool

    def translate(self, text: str, src: str, tgt: str): ...

    def detect(self, text: str): ...

    def langs(self) -> tuple: ...


class _Adapter:
    """Thin wrapper around one existing ``_t_*`` callable.

    No provider logic is reimplemented here: ``_fn`` is the verbatim
    adapter body from ``registry`` and ``_detect_fn``/``_langs`` are the
    provider module's own functions/tables.
    """

    def __init__(self, name, fn, detect_fn=None, langs=(),
                 uses_auto_detect=False):
        self.name = name
        self._fn = fn
        self._detect_fn = detect_fn
        self._langs = tuple(langs)
        self.uses_auto_detect = bool(uses_auto_detect)

    def translate(self, text, src, tgt):
        return self._fn(text, src, tgt)

    def detect(self, text):
        if self._detect_fn is None:
            return -1
        return self._detect_fn(text)

    def langs(self):
        return self._langs


def build_adapters():
    """One adapter per TRANSLATORS key; ``bing`` shares microsoft's object.

    Rule (b): ``bing`` and ``microsoft`` resolve to the SAME adapter
    instance (alias, not a second provider). Callers using either key
    stay compatible; the fallback chain (dedupe by callable identity in
    ``registry.router_order``) never tries the same implementation twice.
    """
    from qtranslate import registry as _RG

    def _langs_of(module):
        return tuple(getattr(module, "SUPPORTED_LANGS", ()))

    specs = [
        ("google", _RG._t_google, _RG._google.detect,
         _RG._google, "google"),
        ("microsoft", _RG._t_bing, _RG._ms.detect_code,
         _RG._ms, "microsoft"),
        ("deepl", _RG._t_deepl, _RG._deepl.detect_code,
         _RG._deepl, "deepl"),
        ("yandex", _RG._t_yandex, _RG._yandex.detect,
         _RG._yandex, "yandex"),
        ("baidu", _RG._t_baidu, _RG._baidu.detect
         if hasattr(_RG._baidu, "detect") else None,
         _RG._baidu, "baidu"),
        ("naver", _RG._t_naver, _RG._naver.detect,
         _RG._naver, "naver"),
        ("youdao", _RG._t_youdao, None,
         _RG._youdao, "youdao"),
        ("promt", _RG._t_promt, None,
         _RG._promt, "promt"),
        ("babylon", _RG._t_babylon, None,
         _RG._babylon, "babylon"),
    ]
    table = {}
    for key, fn, det, mod, cap in specs:
        table[key] = _Adapter(key, fn, det, _langs_of(mod),
                              _RG.USES_AUTO_DETECT.get(cap, False))
    # Rule (b): alias shares the object — identity, not equality.
    table["bing"] = table["microsoft"]
    return table
