"""macOS system spell checker -- the ``system-services`` plugin's
MacSpellCheckerBackend equivalent, in-process instead of through the
packaged helper binary .tmp ships.

Reference: plugins/system-services/.../spell/MacSpellCheckerBackend.kt
+ SystemSpellCheckerService.kt. The Kotlin backend shells out to a
helper that wraps NSSpellChecker; on macOS the same API is reachable
directly through pyobjc, so the port calls
``NSSpellChecker.checkSpellingOfString`` and
``guessesForWordRange`` itself -- same findings, no subprocess, no
helper to package.

Output shape matches ``services.bing_spell.check`` so the app's
correction list, context menu and apply path work unchanged:
``{"correctedText", "corrections": [{original, startIndex, endIndex,
suggestions, type}]}``.

Availability is honest: ``available()`` is False off-macOS or without
pyobjc, and ``check`` returns None then so the caller can fall back to
the network backend.
"""
from __future__ import annotations

import sys


def available():
    return sys.platform == "darwin"


def _checker():
    try:
        from AppKit import NSSpellChecker
        return NSSpellChecker.sharedSpellChecker()
    except Exception:
        return None


def _language_tag(lang):
    """App lang code -> BCP-47 NSSpellChecker understands."""
    lang = (lang or "").strip()
    if not lang or lang in ("auto", "auto-detect"):
        return "en"
    return lang


def check(text, lang="en"):
    """Spell-check ``text``; returns the bing_spell-shaped dict, or
    None when the backend is unavailable (caller falls back)."""
    if not available() or not (text or "").strip():
        return None
    checker = _checker()
    if checker is None:
        return None
    try:
        return _check_macos(checker, text, _language_tag(lang))
    except Exception:
        return None


def _check_macos(checker, text, lang):
    import Foundation
    from AppKit import NSRange

    ns_text = Foundation.NSString.stringWithString_(text)
    corrections = []
    # NSSpellChecker ranges are UTF-16 units -- the same unit
    # QTextCursor.position() reports and bing_spell offsets use, so
    # corrections stay in UTF-16.
    pos16 = 0
    length16 = ns_text.length()
    while pos16 < length16:
        try:
            res = getattr(
                checker,
                "checkSpellingOfString_startingAt_language_wrap_"
                "inSpellDocumentWithTag_wordCount_reconnectOnError_")(
                    ns_text, pos16, lang, True, 0, None, True)
        except Exception:
            break
        if isinstance(res, tuple):
            rng = res[0]
        else:
            rng = res
        loc = int(getattr(rng, "location", -1))
        span = int(getattr(rng, "length", 0) or 0)
        if loc < 0 or loc == 0x7FFFFFFFFFFFFFFF or loc < pos16 \
                or span <= 0 or loc >= length16:
            break
        end16 = min(loc + span, length16)
        guesses = []
        try:
            g = getattr(
                checker,
                "guessesForWordRange_inString_language_"
                "inSpellDocumentWithTag_")(
                    NSRange(loc, span), ns_text, lang, 0)
            guesses = [str(x) for x in (g or [])][:5]
        except Exception:
            pass
        corrections.append({
            "original": str(ns_text.substringWithRange_(
                NSRange(loc, span))),
            "startIndex": loc,
            "endIndex": end16,
            "suggestions": guesses,
            "type": "SPELLING",
        })
        pos16 = end16
    # correctedText: splice each top suggestion into the ORIGINAL
    # offsets in one pass -- applying them to a mutable copy shifts
    # later spans.
    corrected = []
    cursor = 0
    for c in corrections:
        s, e = c["startIndex"], c["endIndex"]
        corrected.append(_utf16_slice(text, cursor, s))
        corrected.append(c["suggestions"][0] if c["suggestions"]
                         else _utf16_slice(text, s, e))
        cursor = e
    corrected.append(_utf16_slice(text, cursor, length16))
    return {"correctedText": "".join(corrected),
            "corrections": corrections}


def _utf16_slice(text, start16, end16):
    """Substring of ``text`` between UTF-16 offsets."""
    return text[_utf16_to_py(text, start16):_utf16_to_py(text, end16)]


def _utf16_to_py(text, utf16_index):
    """Map a UTF-16 offset (NSString/QTextCursor units) to a Python
    str index. Astral characters count as two UTF-16 units."""
    count = 0
    i = 0
    n = len(text)
    while i < n and count < utf16_index:
        count += 2 if ord(text[i]) > 0xFFFF else 1
        i += 1
    return i
