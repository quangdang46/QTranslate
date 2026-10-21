"""Patch registry.py: derive the auto-detect capability from native's rule.

Applied programmatically because the block is long and the editor's
exact-match pass kept rejecting it. Every replacement asserts its anchor was
found exactly once.
"""

from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("qtranslate/registry.py")

OLD_CAPABILITY = '''# Port-side declared capability, mirroring the native `usesAutoDetectCode`
# hook. Native asks each service (FUN_0045f6c1 calls the JS hook and stores
# the boolean at request+0x50); the translate stage then runs detect itself
# only when the answer is false, or when the destination is also unset.
#
# This table is NOT native-derived: the hook's answers live in the
# runtime-loaded Services/*/Service.js, which PLUGIN_LOADER_FOUND_2026-10-10.md
# proves are absent from the recovered artifact. True here means "this
# provider's own API resolves an auto source", which is a port-side fact about
# the HTTP contract we do implement. Members were carried over from the old
# hardcoded _NATIVE_AUTO set so no behavior changed; the point of the table is
# that the claim is now attributed to the right axis.
#   docs/review/SOURCE_LANGUAGE_RULE_2026-10-10.md
USES_AUTO_DETECT = {"google": True, "microsoft": True, "bing": True,
                    "deepl": True}


def uses_auto_detect(service: str) -> bool:
    """Port-side auto-detect capability (native default: detect-yourself)."""
    return bool(USES_AUTO_DETECT.get(service, False))
'''

NEW_CAPABILITY = '''# --- auto-detect capability (native-derived) --------------------------------
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
'''

OLD_DETECTORS = '''    return (
        lambda t: _google.detect(t),
        lambda t: _deepl.detect_code(t),
        lambda t: _ms.detect_code(t),
        lambda t: _naver.detect_code(t),
        lambda t: _baidu.detect_code(t),
        lambda t: _yandex.detect_code(t),
    )
'''

NEW_DETECTORS = '''    return (
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
'''

OLD_LOOP = '''    for fn in detectors():
        try:
            lang = fn(text[:500])
            if lang and lang != -1:
                return lang
        except Exception:
            pass
    return "auto"
'''

NEW_LOOP = '''    for fn in detectors():
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
'''

EDITS = [
    (OLD_CAPABILITY, NEW_CAPABILITY),
    (OLD_DETECTORS, NEW_DETECTORS),
    (OLD_LOOP, NEW_LOOP),
]


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    for old, new in EDITS:
        count = text.count(old)
        if count != 1:
            print(f"anchor found {count} times (expected 1): {old[:60]!r}",
                  file=sys.stderr)
            return 2
        text = text.replace(old, new, 1)
    TARGET.write_text(text, encoding="utf-8")
    print(f"applied {len(EDITS)} edits to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
