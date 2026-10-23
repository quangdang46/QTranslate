"""Single source of truth for provider dispatch (Phase 2 slice).

Replaces the three-source-of-truth layout ``CURRENT_STATE.md`` §3 names:
``app.TRANSLATORS`` / ``app.DICTS`` (hardcoded tables) plus the dead
``services.REGISTRY``. This module is stdlib-only and imports no tkinter,
so Core and headless callers can use it without a display.

Design (per ``ARCHITECTURE.md`` §3.2, alias-first migration — LANDED
2026-10-15, working tree):

1. This module OWNS the canonical tables and adapter bodies: the nine
   ``_t_*`` adapters were moved here verbatim from ``app.py`` (same
   bodies, same comments). Nothing adapter-shaped remains in ``app.py``.
2. ``app.TRANSLATORS`` / ``app.DICTS`` ARE aliases of these tables
   (``from qtranslate.registry import TRANSLATORS, DICTS``) — kept
   because ``ui_match`` and live UI code read ``A.TRANSLATORS``.
   There is exactly one definition of each table: here.
3. Also owned here: ``detectors()`` + ``detect_language()`` (the detect
   chain), ``USES_AUTO_DETECT`` + ``uses_auto_detect()`` (port-side
   auto-detect capability), ``call_with_sink()`` + ``apply_phonetics()``
   (J7 sink dispatch), ``SERVICE_LINKS`` + ``service_link()`` (provider
   home pages), ``router_order()`` (ServicesOrder → names) and
   ``build_router()`` (singleton + per-call clone). ``app._router`` and
   ``app.speak`` are thin forwarders; ``app.detect_language``,
   ``app._t_call``, ``app._apply_phonetics``, ``app._dict_service_link``
   are aliases.

Nothing here opens a window or touches the network at import time: the
values are function references, and provider modules are imported at this
module's top (they are stdlib/urllib-only, no tkinter anywhere in the
dependency chain — verified: ``grep -rn tkinter qtranslate/services/
qtranslate/session.py`` is empty). This module never imports ``app``
at module level (only lazily inside nothing — ``build_router`` builds
its own singleton now), so Core/headless callers stay display-free.
"""
from __future__ import annotations

from qtranslate.services import google_translate as _google
from qtranslate.services import deepl as _deepl
from qtranslate.services import yandex as _yandex
from qtranslate.services import baidu as _baidu
from qtranslate.services import naver as _naver
from qtranslate.services import youdao as _youdao
from qtranslate.services import microsoft as _ms
from qtranslate.services import promt as _promt
from qtranslate.services import babylon as _babylon
from qtranslate.services import dictionary as _dict
from qtranslate.services import spell as _spell
from qtranslate.session import bing_translate as _bing_tr


def _t_google(t, sl, tl, _sink=None):
    # `_sink` carries dt=rm's romanization back to do_translate for J7
    # (FUN_0042ED3F's entry[5]). The `_t_*` contract is a bare str, so the
    # field rides out through an optional mutable one-element list rather than
    # a second HTTP call or module state; see google_translate.translate.
    return _google.translate(t, sl, tl, out=_sink)


def _t_deepl(t, sl, tl):
    # Native sends codeFromLanguage(index); "auto" must stay lowercase.
    sl_c = "auto" if sl == "auto" else sl.upper()
    return _deepl.translate(t, sl_c, tl.upper())


def _t_yandex(t, sl, tl):
    # native serviceTranslateRequest: lang=codeFromLanguage(source);
    # "auto" is sent verbatim (no en guess).
    return _yandex.translate(t, sl, tl)


def _t_baidu(t, sl, tl):
    return _baidu.translate(t, sl, tl) if hasattr(_baidu, "translate") else ""


def _t_naver(t, sl, tl):
    out, _ = _naver.translate(t, sl, tl)
    return out


def _t_youdao(t, sl, tl):
    # native serviceTranslateRequest: from=codeFromLanguage(source).
    return _youdao.translate_web(t, sl, tl)


def _t_bing(t, sl, tl):
    # Microsoft/Bing accept auto source natively: serviceRequest sends
    # fromLang=codeFromLanguage(source||AUTO_DETECT_LANGUAGE) = "auto"
    # (Service.js). Do NOT force "en" -- pass the source through verbatim.
    return _bing_tr(t, sl, tl)


def _t_babylon(t, sl, tl):
    # native serviceTranslateRequest: codeFromLanguage(source).
    return _babylon.translate(t, sl, tl)


def _t_promt(t, sl, tl):
    # Native: a failed provider request surfaces as the app-level error
    # string, not as translation text. Let exceptions propagate so
    # do_translate() handles them uniformly (string id 190), like every
    # other adapter — do not fabricate an "[error] ..." pseudo-translation.
    paft, xsrf, op = _promt.session(sl, tl)
    out, _, _ = _promt.translate(t, sl, tl, paft, "", xsrf, op)
    return out


TRANSLATORS = {
    "google": _t_google,
    "deepl": _t_deepl,
    "yandex": _t_yandex,
    "baidu": _t_baidu,
    "naver": _t_naver,
    "youdao": _t_youdao,
    "bing": _t_bing,
    "microsoft": _t_bing,
    "promt": _t_promt,
    "babylon": _t_babylon,
}

DICTS = {
    "oxford": lambda w, sl, tl: _dict.oxford_lookup(w),
    "lingvo": lambda w, sl, tl: _dict.lingvo_lookup(w, sl, tl),
    "urban": lambda w, sl, tl: _dict.urban_lookup(w),
    "wikipedia": lambda w, sl, tl: _dict.wikipedia_lookup(w, sl, tl),
    "multitran": lambda w, sl, tl: _dict.multitran_lookup(w, sl, tl),
    "wordreference": lambda w, sl, tl: _dict.wordreference_lookup(w, sl, tl),
    "reverso": lambda w, sl, tl: _dict.reverso_lookup(w, sl, tl),
    "babylon": lambda w, sl, tl: _dict.babylon_dict_lookup(w, sl, tl),
    "imtranslator": lambda w, sl, tl: _dict.imtranslator_lookup(w, sl, tl),
    "google-search": lambda w, sl, tl: _dict.google_search_lookup(w, sl, tl),
    # youdao is the only TRANSLATE|DICTIONARY service (id 26) and its
    # dictionary half was missing here: `_ID2FN` mapped "youdao" to a key
    # this table had no entry for, so the lookup returned None and the
    # service silently never ran. Found 2026-10-16.
    #
    # `dictionary()` takes language CODES while the other entries forward
    # the raw sl/tl, so an index arriving here has to resolve through
    # youdao's own SupportedLanguages table first -- silently defaulting to
    # AUTO/en would mistranslate every non-English request.
    "youdao": lambda w, sl, tl: _youdao.dictionary(
        w,
        _youdao.code_from_language(sl, _youdao.SUPPORTED_LANGS)
        if isinstance(sl, int) else sl,
        _youdao.code_from_language(tl, _youdao.SUPPORTED_LANGS)
        if isinstance(tl, int) else tl)[0],
}


# --- the four other dispatch tables -------------------------------------
# Each capability the extension API can host needs a live table the app
# reads, the same shape TRANSLATORS/DICTS have: a name -> callable dict
# that an extension commits into and the app consumes. Without the table
# the capability is a word in a manifest; with it the extension's code
# actually runs.
#
# The signatures are the app's, not invented:
#   DICT_EXT      fn(word, src, tgt) -> the entry (same as DICTS)
#   SPELL_EXT     fn(text, lang) -> list of suggestions
#   OCR_EXT       fn(image_bytes, lang, api_key) -> text
#   TTS_EXT       fn(text, lang, slow) -> None (plays/saves the audio)
#   WORKFLOW_EXT  fn(text, src, tgt) -> text, run after a translation
DICT_EXT = {}
SPELL_EXT = {}
OCR_EXT = {}
TTS_EXT = {}
WORKFLOW_EXT = {}


def translators() -> dict:
    """Canonical translate table: name -> fn(text, src, tgt)."""
    return dict(TRANSLATORS)


def dicts() -> dict:
    """Canonical dictionary table: name -> fn(word, src, tgt)."""
    return dict(DICTS)


# --- app.py compatibility aliases (import here, not in app.py) ---
# app.py's own ``TRANSLATORS``/``DICTS`` literals are replaced by these
# imports in the alias slice; until then this block documents the target:
#   from qtranslate.registry import TRANSLATORS, DICTS
# Nothing imports these names from here yet — the alias flip lands next.


def google_suggest(text: str, lang: str = "en") -> list:
    """Spell suggestions (used by the main-window suggestion strip).

    ``SPELL_EXT`` is the live table an extension commits into
    (``api.register_spell``); a backend that raises falls through to the
    built-in suggester.
    """
    for name in sorted(SPELL_EXT):
        try:
            out = SPELL_EXT[name](text, lang)
        except Exception:
            continue
        if isinstance(out, list):
            return out
    return _spell.google_suggest(text, lang)


# --- auto-detect capability (native-derived) --------------------------------
# Native asks each service whether it accepts an auto source by calling the
# JS hook `usesAutoDetectCode` (host call `FUN_0043b8ce(this,
# L"usesAutoDetectCode", ...)`, the answer stored at request+0x50); the
# translate stage then runs detect itself only when the answer is false, or
# when the destination is also unset.
#
# The hook is NOT a per-service function. It is a *framework* function in
# `Services/Common.js`:
#
#     function usesAutoDetectCode(){
#         return SupportedLanguages[AUTO_DETECT_LANGUAGE] !== UNKNOWN_LANGUAGE_CODE
#     }
#
# with `AUTO_DETECT_LANGUAGE = 1` and `UNKNOWN_LANGUAGE_CODE = -1`
# (`Services/Common.js`: `var SupportedLanguages=null,UNKNOWN_LANGUAGE_CODE=-1,
# UNKNOWN_LANGUAGE=0,AUTO_DETECT_LANGUAGE=1,ENGLISH_LANGUAGE=17;`).
# `SupportedLanguages` is the per-service language table, so the answer is
# "does this service's own table hold a real code in slot 1?".
#
# The port's `SUPPORTED_LANGS` tables are transcriptions of exactly those
# per-service tables, so native's rule applies to them unchanged, and
# `qtranslate.common.uses_auto_detect_code` is the port of the hook. The
# table is therefore DERIVED, not hand-listed -- which is what closed the
# "carried over from the old hardcoded set" caveat.
#
# When the hook cannot be called or does not return a boolean, native leaves
# the request's auto-detect flag unset and the translate stage detects the
# language itself. The default here is the same: detect yourself.
#
#   docs/review/SOURCE_LANGUAGE_RULE_2026-10-10.md §1-§3 (the mechanism)
#   docs/review/AUTO_DETECT_CAPABILITY_2026-10-21.md (the truth table,
#     measured from the recovered Services/*/Service.js)
def _auto_capability() -> dict:
    """Derive the per-provider auto-detect capability from native's rule."""
    from qtranslate import common as _common
    modules = (
        ("google", _google),
        ("microsoft", _ms),
        ("deepl", _deepl),
        ("yandex", _yandex),
        ("baidu", _baidu),
        ("naver", _naver),
        ("youdao", _youdao),
        ("promt", _promt),
        ("babylon", _babylon),
    )
    table = {
        name: _common.uses_auto_detect_code(getattr(mod, "SUPPORTED_LANGS", ()))
        for name, mod in modules
    }
    # `bing` is an alias of `microsoft` (rule (b), providers/__init__.py): the
    # same adapter object, so the same capability.
    table["bing"] = table["microsoft"]
    return table


USES_AUTO_DETECT = _auto_capability()


def uses_auto_detect(service: str) -> bool:
    """Auto-detect capability (native default: detect-yourself)."""
    return bool(USES_AUTO_DETECT.get(service, False))


def auto_detect_code(service: str):
    """The provider's OWN auto code -- native's codeFromLanguage(1).

    Native sends each service its own slot-1 code, not a literal "auto":
    Microsoft "auto-detect", youdao "AUTO", Promt "au", Google/DeepL/Papago
    "auto". The port's request carries "auto" (what the UI shows) and the
    provider resolves it, so the conversion happens at the adapter boundary.

    Returns None when the service has no language table or no auto slot.
    """
    from qtranslate import common as _common
    modules = {
        "google": _google, "microsoft": _ms, "deepl": _deepl,
        "yandex": _yandex, "baidu": _baidu, "naver": _naver,
        "youdao": _youdao, "promt": _promt, "babylon": _babylon,
    }
    mod = modules.get(service)
    if mod is None and service == "bing":
        # `bing` is an alias of `microsoft` (rule (b)): same adapter, so the
        # same provider table and the same auto code.
        mod = modules["microsoft"]
    if mod is None:
        return None
    langs = getattr(mod, "SUPPORTED_LANGS", ())
    try:
        code = langs[_common.AUTO_DETECT_LANGUAGE]
    except (IndexError, TypeError):
        return None
    if code == _common.UNKNOWN_LANGUAGE_CODE:
        return None
    return code


def detectors() -> tuple:
    """Canonical detect chain: one zero-arg-text callable per provider.

    Replaces the hardcoded ``candidates`` tuple in ``app.detect_language``
    (the third source of truth CURRENT_STATE.md §3 names, next to the
    translate/dict tables). Each entry takes ``text`` and returns a code,
    an index, or ``-1``/falsy on failure — ``detect_language`` normalizes.
    Order matches the old tuple so fallback priority is unchanged.
    """
    return (
        # `detect` returns a language INDEX (native's languageFromCode);
        # `detect_code` resolves it against Google's own table. The chain
        # must yield code strings -- an index that reaches a provider
        # adapter is read as that provider's own index, which is a
        # different language (or an AttributeError when the adapter calls
        # `str.upper` on it).
        lambda t: _google.detect_code(t),
        lambda t: _deepl.detect_code(t),
        lambda t: _ms.detect_code(t),
        lambda t: _naver.detect_code(t),
        lambda t: _baidu.detect_code(t),
        lambda t: _yandex.detect_code(t),
    )


def detect_language(text):
    """Port of FUN_00460354 detect-retry loop: providers in order.

    Moved verbatim from ``app.detect_language`` (Phase 2 slice).
    detect() across providers returns mixed types (DeepL/Yandex return
    lang indices like the native languageFromCode; Naver/Baidu return
    code strings), so everything is normalized to a code string here.
    """
    for fn in detectors():
        try:
            lang = fn(text[:500])
        except Exception:
            continue
        # A detector must answer with a CODE string. Anything else (an index,
        # a number) is a vocabulary leak: it would reach the provider
        # adapter as that provider's own index, which names a different
        # language. Skip it and let the next detector answer rather than
        # putting a non-string into the request's `src`.
        if not isinstance(lang, str) or not lang or lang == "-1":
            continue
        return lang
    return "auto"


def router_order() -> list:
    """Fallback order: ServicesOrder ids → names, TRANSLATORS-only appended.

    Mirrors the ``app._router`` construction (working tree 2026-10-15):
    ``config.services_order()`` numeric ids mapped through
    ``config.SERVICE_NAMES``, unknown ids skipped, names present in the
    translate table but absent from ServicesOrder appended in table order.

    Slice 1 rule (b) 2026-10-15: keys that resolve to the SAME callable
    are deduped by identity, so an alias (``bing`` → ``microsoft``) never
    enters the chain as a second entry. Native ``Services/`` has no Bing
    directory and ``SERVICE_NAMES`` has no ``bing`` key, so ``bing`` is a
    port alias, not an independent provider; trying it twice would burn
    the shared retry budget on one implementation.
    """
    from qtranslate import config as _C
    try:
        ids = _C.services_order()
    except Exception:
        ids = list(_C.DEFAULT_SERVICES_ORDER)
    table = translators()
    order = [_C.SERVICE_NAMES[i] for i in ids
             if i in _C.SERVICE_NAMES and _C.SERVICE_NAMES[i] in table]
    for name in table:
        if name not in order:
            order.append(name)
    # Dedupe by callable identity: keep the first key per callable (the
    # ServicesOrder winner, e.g. "microsoft"), drop later aliases ("bing").
    seen, deduped = set(), []
    for name in order:
        fn = table.get(name)
        if id(fn) in seen:
            continue
        seen.add(id(fn))
        deduped.append(name)
    return deduped


def call_with_sink(fn, text, src, tgt, sink):
    """Invoke an adapter, handing it the romanization sink if it takes one.

    Moved verbatim from ``app._t_call`` (Phase 2 slice). Only ``_t_google``
    declares ``_sink``; every other adapter keeps the bare ``(t, sl, tl)``
    contract. Structural probe (signature), not an identity check, so
    re-binding the table keeps phonetics flowing.
    """
    import inspect as _inspect
    try:
        wants = "_sink" in _inspect.signature(fn).parameters
    except (TypeError, ValueError):
        wants = False
    return fn(text, src, tgt, _sink=sink) if wants else fn(text, src, tgt)


def apply_phonetics(out, service, romanization=""):
    """J7 — append phonetics when ReadPhonetically is on (moved from app).

    ``FUN_0042ED3F`` appends "\\r\\r" + string-resource 186 + entry[5] to
    the result pane when ``General.ReadPhonetically`` is on and entry[5]
    is non-empty. Source here is Google's ``dt=rm`` romanization; other
    providers supply none. The ``service == "google"`` guard is
    load-bearing: the sink is filled by Google's callable only.
    """
    try:
        from qtranslate import phonetics as _PH
        from qtranslate import config as _C
        if service == "google":
            return _PH.append_phonetics(
                out, romanization,
                enabled=_PH.phonetics_enabled(_C.load()))
    except Exception:
        pass
    return out


SERVICE_LINKS = {
    "google": "https://translate.google.com/",
    "deepl": "https://www.deepl.com/translator",
    "yandex": "https://translate.yandex.com/",
    "baidu": "https://fanyi.baidu.com/",
    "naver": "https://papago.naver.com/",
    "youdao": "https://fanyi.youdao.com/",
    "bing": "https://www.bing.com/translator",
    "microsoft": "https://www.bing.com/translator",
    "promt": "https://www.online-translator.com/",
    "babylon": "https://translation.babylon-software.com/",
    "reverso": "https://www.reverso.net/",
}

DEFAULT_LINK = "https://translate.google.com/"


def service_link(service: str) -> str:
    """Provider home page (was ``app._dict_service_link``)."""
    return SERVICE_LINKS.get(service, DEFAULT_LINK)


def _google_for_call(t, sl, tl, _sink, _base=None):
    """Per-call Google closure (was inline in ``app._router``).

    Same body as ``_t_google`` but fills *this call's* sink. The shared
    router's callables are reused across concurrent ``do_translate`` calls
    on worker threads, so a sink on the shared table would hand one call
    another call's romanization.
    """
    (_sink or [""])[0] = ""
    return _t_google(t, sl, tl, _sink=_sink)


def build_router(sink=None):
    """A ``ProviderRouter`` over the canonical tables, ServicesOrder order.

    ``sink`` is the per-call J7 phonetics sink: when given, the returned
    router is a clone whose Google entry fills that sink (sharing health
    and policy with a process-wide singleton so a dead provider stays
    dead). No ``app`` import — ``registry`` stays tkinter-free, which the
    ``registry does not import app at module level`` static check pins.
    """
    from qtranslate.reliability import ProviderRouter
    global _ROUTER_SINGLETON
    try:
        _ROUTER_SINGLETON
    except NameError:
        _ROUTER_SINGLETON = None
    if _ROUTER_SINGLETON is None:
        _ROUTER_SINGLETON = ProviderRouter(
            dict(TRANSLATORS), order=router_order())
    if sink is None:
        return _ROUTER_SINGLETON
    # Per-call clone: same callables except google fills this call's sink;
    # shares the singleton's health + policy so dead stays dead. This is the
    # outer ProviderRouter (translate() level: max_chars/remove_line_breaks
    # live here), not the inner FallbackRouter (route() level) — the clone
    # must carry the same shaping flags, which is why both are forwarded.
    from qtranslate import reliability as _rel
    try:
        callables = dict(_ROUTER_SINGLETON.router.callables)
        # Only fill the per-call sink for the canonical Google callable. An
        # extension that overrides "google" must not be silently reverted to
        # the built-in just because the call carries a phonetics sink.
        if callables.get("google") is _t_google:
            def _g(t, sl, tl, _s=sink):
                return _google_for_call(t, sl, tl, _s)
            callables["google"] = _g
        return ProviderRouter(
            callables, order=list(_ROUTER_SINGLETON.router.order),
            health=_ROUTER_SINGLETON.health,
            policy=_ROUTER_SINGLETON.router.policy,
            max_chars=_ROUTER_SINGLETON.max_chars,
            remove_line_breaks=_ROUTER_SINGLETON.remove_line_breaks)
    except Exception:
        return _ROUTER_SINGLETON


def reset_router():
    """Drop the cached ``ProviderRouter`` so the next build re-reads the table.

    Called after a live change to ``TRANSLATORS`` (extension loading, Slice 8):
    the singleton captured ``dict(TRANSLATORS)`` and ``router_order()`` at build
    time, so a table mutation is invisible until it is rebuilt.
    """
    global _ROUTER_SINGLETON
    _ROUTER_SINGLETON = None
