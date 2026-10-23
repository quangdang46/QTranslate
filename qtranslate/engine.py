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

The reliability audit's open items (docs/review/
RELIABILITY_WIRING_AUDIT_2026-10-10.md §2/§3/§7), settled here:

- **A detection that names no source is recorded, not swallowed.** The
  request degrades to ``src="auto"`` and the service resolves the source
  itself where it can; it is NOT stopped. See ``_detect_source``.
- **The classified failures reach the caller.** A failed route used to
  come back as the bare native error string with the failures dropped on
  the floor; they are now in ``Result.failures`` and in the note.
- **Every failure is logged** through the reliability log sink (§7), so
  the "which layer failed" report is answerable from a file.
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


def _detect_source(text):
    """(src, failure) — the port's detect chain and its diagnosis.

    ``registry.detect_language`` returns the ``"auto"`` sentinel when it
    cannot name the source language: either every detector failed, or a
    detector answered ``"auto"`` (it could not tell either). The port
    cannot tell those apart — the per-detector exceptions are swallowed
    upstream — so the failure is recorded at chain level
    (``reliability.detect_failure``).

    **The request is not stopped.** Two reasons, both from the evidence:

    1. Native passes the auto source through in the same situation
       (``FUN_004606ba`` substitutes a concrete code only when the
       service's ``usesAutoDetectCode`` hook answered false; the request
       otherwise carries whatever the source slot held).
    2. Several of the port's providers accept ``"auto"`` natively — Naver's
       language table carries ``"auto"``, Google's and DeepL's do too — so
       stopping would turn a working translation into an error.
       ``registry.USES_AUTO_DETECT`` is *derived* from those tables by
       native's own rule (Common.js's ``usesAutoDetectCode``), so a policy
       keyed on it rests on a measured truth table, not on a declared
       guess — see docs/review/AUTO_DETECT_CAPABILITY_2026-10-21.md.

    What was missing was the signal, not the policy: the failure is now
    recorded (``Result.failures``) and logged.
    """
    from qtranslate import registry as _RG
    from qtranslate import reliability as _REL
    lang = _RG.detect_language(text)
    if lang and lang != "auto":
        return lang, None
    return "auto", _REL.detect_failure()


def _run_workflows(text, src, target):
    """Let an extension's workflow step act on a finished translation.

    ``registry.WORKFLOW_EXT`` is the live table an extension commits
    into (``api.register_workflow``). Each step receives
    ``(text, src, target)`` and returns the text to show; a step that
    raises is skipped rather than failing the translation, because a
    broken extension must not take a successful translation with it.
    With no extension the table is empty and this is the identity.
    """
    from qtranslate import registry as _RG
    table = getattr(_RG, "WORKFLOW_EXT", None)
    if not table:
        return text
    out = text
    for name in sorted(table):
        try:
            result = table[name](out, src, target)
        except Exception:
            continue
        if isinstance(result, str):
            out = result
    return out


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
    from qtranslate import reliability as _REL

    # §7: the failures of this request land in the log file. The sink is
    # installed once per process and never replaced, so an app (or a test)
    # that installed its own sink keeps it.
    _REL.ensure_log_sink()

    req = _TReq(service=service or "", text=(text or "").strip(),
                target=target, src=src, auto_detect=bool(auto_detect),
                back_translate=bool(back_translate))
    text = req.text
    service = req.service
    if not text:
        return Result("", "", service or "", note="empty request")
    # Failures raised outside the provider route (a detection that named
    # no source, a back-translation that died) are collected here so they
    # reach the caller and the log.
    extra = []
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
        # flag is false. The hook is a *framework* function in
        # `Services/Common.js` -- it tests the service's own language table
        # (`SupportedLanguages[AUTO_DETECT_LANGUAGE] !== UNKNOWN_LANGUAGE_CODE`)
        # -- so the per-service capability is DERIVED from the port's own
        # transcribed tables, not hand-listed.
        #   docs/review/AUTO_DETECT_CAPABILITY_2026-10-21.md
        # RE-closed 2026-10-15: `DAT_0054941f` is the true
        # `AlwaysDetectLanguage` flag (nav-menu 0x808e; the Options-page
        # byte `DAT_005494e6` is RemoveLineBreaks). The orchestrator packs
        # it into FUN_004606ba, whose first branch detects even for a
        # concrete source.
        req = req.shaped(text)  # shaping is text-only; src/tgt unchanged
        src = req.src
        if src == "auto":
            if req.auto_detect or not _RG.uses_auto_detect(service):
                _lang, _det_fail = _detect_source(text)
                if _det_fail is not None:
                    extra.append(_det_fail)
                    _REL.log_failure(_det_fail)
                req = req.with_src(_lang)
                src = req.src
            else:
                # The service resolves the auto source itself. Native sends
                # each service its OWN slot-1 code (`codeFromLanguage(1)`):
                # Microsoft "auto-detect", youdao "AUTO", Promt "au" -- not a
                # literal "auto". The request keeps the canonical "auto"
                # (that is what the UI shows); the provider's own spelling
                # is applied at the adapter boundary.
                _own = _RG.auto_detect_code(service)
                if _own:
                    req = req.with_src(_own)
                    src = req.src
        elif req.auto_detect:
            _lang, _det_fail = _detect_source(text)
            if _det_fail is not None:
                extra.append(_det_fail)
                _REL.log_failure(_det_fail)
            if _lang and _lang != "auto":
                req = req.with_src(_lang)
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
                              failures=tuple(extra),
                              note="no data returned (timeout)")
            if req.back_translate:
                try:
                    back = TRANSLATORS.get(service, _t_google)(
                        out[:5000], target, src)
                    if back:
                        out += f"\n\n--- back-translation ---\n{back}"
                except Exception as exc:
                    _bf = _REL.Failure(
                        provider=service or "back-translation",
                        kind=_REL.classify(exc),
                        detail="back-translation failed: %s" % (exc,))
                    extra.append(_bf)
                    _REL.log_failure(_bf)
            out = apply_phonetics(out, service, _sink[0])
            return Result(service or "", out, service or "",
                          failures=tuple(extra),
                          phonetics=_sink[0])
        res = _r.translate(service, text, src, target,
                           config=_cfg_safe(), phonetics_sink=_sink)
        out = res.text
        # From here the "service" that matters is the one that ANSWERED —
        # res.provider_used — for back-translation and J7's phonetics.
        service = res.provider_used or service
        if not res.ok:
            # native error string id 190 — the text the user sees. The note
            # and the failures carry WHY: the route's own note names the
            # kinds ("no provider answered (timeout, provider-dead): google,
            # yandex") and `failures` holds one classified Failure per
            # provider. Dropping them here is what made a dead endpoint
            # indistinguishable from a timeout.
            # ``provider_used`` MUST stay empty here. `Result.ok` is
            # `bool(provider_used)`, and this branch is precisely "no
            # provider answered" -- filling it with the REQUESTED service
            # made a total failure report ok=True, which is the bug the
            # app-level reliability suite caught. `requested` carries
            # which service was asked.
            return Result("",
                          "No data returned (timeout while sending data.)",
                          service or "",
                          failures=tuple(res.failures) + tuple(extra),
                          attempts=res.attempts,
                          note=res.note or "no data returned (timeout)")
        note = res.note
        if req.back_translate and not out.startswith("No data"):
            try:
                # Back-translate through the provider that ACTUALLY answered.
                _bfn = TRANSLATORS.get(res.provider_used, _t_google)
                back = _bfn(out[:5000], target, src)
                if back:
                    out += f"\n\n--- back-translation ---\n{back}"
            except Exception as exc:
                # The back-translation half silently never ran: the user
                # asked for it and the result looks like a translation
                # without one. Record it (result + log) instead.
                _bf = _REL.Failure(
                    provider=res.provider_used or service or "back-translation",
                    kind=_REL.classify(exc),
                    detail="back-translation failed: %s" % (exc,))
                extra.append(_bf)
                _REL.log_failure(_bf)
                note = ("%s; back-translation failed" % note).lstrip("; ")
        out = apply_phonetics(out, service, res.phonetics)
        out = _run_workflows(out, src, target)
        return Result(res.provider_used, out, res.requested,
                      tuple(res.failures) + tuple(extra),
                      res.attempts, note,
                      phonetics=res.phonetics)
    except Exception:
        return Result(service or "",
                      "No data returned (timeout while sending data.)",
                      service or "",
                      failures=tuple(extra),
                      note="exception: no data returned (timeout)")
