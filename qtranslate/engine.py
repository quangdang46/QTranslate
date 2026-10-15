"""TranslationEngine — Slice 2 (approved 2026-10-15).

Owns the orchestration that lived inline in ``app.do_translate``:
pick → detect → execute (with the ``auto_detect`` branch) → reliability
fallback → back-translation → J7 phonetics. Behavior is preserved
1:1; ``app.do_translate`` becomes a thin forwarder with the SAME
signature, so every existing caller is unchanged.

Locked decisions (design phase):
- ``detect_language`` stays owned by ``registry``; the engine calls it.
- ``SUPPORTED_LANGS`` stays per-provider; nothing merged here.
- ``back_translate`` stays internal (not part of any public SDK yet).
- Request shaping happens exactly ONCE (inside the router; the
  no-router fallback shapes explicitly because it bypasses the router).
- tkinter-free (pinned by ``tests/regress_engine.py``).
"""
from __future__ import annotations

from qtranslate.core import Result


def _cfg_safe():
    """Options.json as a dict, or {} if it cannot be read."""
    try:
        from qtranslate import config as _C
        return _C.load() or {}
    except Exception:
        return {}


def _router(sink=None):
    """``registry.build_router``; None when the reliability layer is absent."""
    try:
        from qtranslate import registry as _RG
        return _RG.build_router(sink)
    except Exception:
        return None


def translate(service, text, target, src="auto", auto_detect=False,
              back_translate=False):
    """Port of ``FUN_00404A12``: pick → execute → fallbacks.

    Returns a ``core.Result`` (``.text``, ``.provider_used``,
    ``.phonetics``). Signature mirrors the historical ``do_translate``
    exactly so the forwarder in ``app.py`` needs no adapter. Inside, the
    request travels as a frozen ``core.TranslationRequest`` (Phase 2
    deliverable): derived copies via ``with_src``/``shaped`` mean a
    fallback never sees a mutated request.
    """
    from qtranslate import registry as _RG
    from qtranslate.registry import (TRANSLATORS, _t_google, call_with_sink,
                                     apply_phonetics)
    from qtranslate.core import TranslationRequest as _TReq

    req = _TReq(service=service or "", text=(text or "").strip(),
                target=target, src=src, auto_detect=bool(auto_detect),
                back_translate=bool(back_translate))
    text = req.text
    service = req.service
    if not text:
        return Result("", "", service or "", note="empty request")
    # Request shaping (RemoveLineBreaks collapse + 5000-char cut) happens
    # ONCE inside ProviderRouter.translate via reliability.normalize_request.
    # The _router-is-None fallback shapes explicitly (it bypasses the router).
    try:
        # FUN_00404a12's dispatcher echoes the source when it equals the
        # destination and never calls the service
        # (docs/review/SOURCE_LANGUAGE_RULE_2026-10-10.md).
        if req.src == req.target:
            return Result(service or "", text, service or "",
                          note="src == target: echo")
        # Native calls the service's own `usesAutoDetectCode` JS hook
        # (FUN_0045f6c1) and stores the answer at request+0x50; the
        # translate stage (FUN_004606ba) runs detect itself only when that
        # flag is false. The hook answers live in runtime-loaded
        # Services/*/Service.js (absent from the artifact), so the
        # per-service table is a declared port-side capability, NOT
        # native-derived.
        # RE-closed 2026-10-15: `DAT_0054941f` is the true
        # `AlwaysDetectLanguage` flag (nav-menu 0x808e; the Options-page
        # byte `DAT_005494e6` is RemoveLineBreaks). The orchestrator packs
        # it into FUN_004606ba, whose first branch detects even for a
        # concrete source.
        req = req.shaped(text)  # shaping is text-only; src/tgt unchanged
        src = req.src
        if src == "auto":
            if req.auto_detect or not _RG.uses_auto_detect(service):
                req = req.with_src(_RG.detect_language(text))
                src = req.src
        elif req.auto_detect:
            _det = _RG.detect_language(text)
            if _det and _det != "auto":
                req = req.with_src(_det)
                src = req.src
        # One fresh sink per call, so J7's phonetics travels with this
        # call's own result (worker threads must not share module state).
        _sink = [""]
        _r = _router(_sink)
        if _r is None:
            # Reliability layer failed to import: bare provider call rather
            # than failing. Shape here (this path bypasses the only shaper).
            try:
                from qtranslate import reliability as _rel0
                text = _rel0.normalize_request(
                    text, src, target,
                    remove_line_breaks=bool(_cfg_safe().get(
                        "Advanced", {}).get("RemoveLineBreaks", False)))[0]
            except Exception:
                text = text[:5000]
            out = call_with_sink(TRANSLATORS.get(service, _t_google),
                                 text[:5000], src, target, _sink)
            if not out:
                return Result(service or "",
                              "No data returned (timeout while sending data.)",
                              service or "",
                              note="no data returned (timeout)")
            if req.back_translate:
                try:
                    back = TRANSLATORS.get(service, _t_google)(
                        out[:5000], target, src)
                    if back:
                        out += f"\n\n--- back-translation ---\n{back}"
                except Exception:
                    pass
            out = apply_phonetics(out, service, _sink[0])
            return Result(service or "", out, service or "",
                          phonetics=_sink[0])
        res = _r.translate(service, text, src, target,
                           config=_cfg_safe(), phonetics_sink=_sink)
        out = res.text
        # From here the "service" that matters is the one that ANSWERED —
        # res.provider_used — for back-translation and J7's phonetics.
        service = res.provider_used or service
        if not res.ok:
            # native error string id 190
            return Result(service or "",
                          "No data returned (timeout while sending data.)",
                          service or "",
                          note="no data returned (timeout)")
        if req.back_translate and not out.startswith("No data"):
            try:
                # Back-translate through the provider that ACTUALLY answered.
                _bfn = TRANSLATORS.get(res.provider_used, _t_google)
                back = _bfn(out[:5000], target, src)
                if back:
                    out += f"\n\n--- back-translation ---\n{back}"
            except Exception:
                pass
        out = apply_phonetics(out, service, res.phonetics)
        return Result(res.provider_used, out, res.requested,
                      res.failures, res.attempts, res.note,
                      phonetics=res.phonetics)
    except Exception:
        return Result(service or "",
                      "No data returned (timeout while sending data.)",
                      service or "",
                      note="exception: no data returned (timeout)")
