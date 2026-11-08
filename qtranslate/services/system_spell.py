"""System spell checker -- the ``system-services`` plugin's
MacSpellCheckerBackend + WindowsSpellCheckerBackend equivalents,
dispatched on ``sys.platform``.

macOS: the Kotlin backend shells out to a helper that wraps
NSSpellChecker; on macOS the same API is reachable directly through
pyobjc, so the port calls
``NSSpellChecker.checkSpellingOfString`` and
``guessesForWordRange`` itself -- same findings, no subprocess, no
helper to package.

Windows: the Kotlin backend binds the Windows 8+ Spell Checking COM
API (ISpellCheckerFactory) through JNA vtable calls; the port does
the same through ctypes (stdlib -- no dependency). CLSID
{7ab36653-1796-484b-bdfa-e74f1db7c1dc} / IID
{8e018a9d-2415-4677-bf08-794ea61f94bb}, method slots and the
action->suggest/replacement mapping mirror JnaWindowsSpellNative.

Output shape matches ``services.bing_spell.check`` so the app's
correction list, context menu and apply path work unchanged:
``{"correctedText", "corrections": [{original, startIndex, endIndex,
suggestions, type}]}``.

Availability is honest: ``available()`` is False off-macOS/Windows/
Linux or without the platform backend, and ``check`` returns None
then so the caller can fall back to the network backend.

Linux: the .tmp ``LinuxSpellCheckerBackend`` shells out to an
installed Ispell-protocol engine (enchant-2 preferred, hunspell
fallback). This port uses ``aspell -a`` -- the same ``@(#)`` header
and ``&``/``#`` finding rows, dependency-free and present on most
desktop installs -- since it speaks the identical pipe protocol.
"""
from __future__ import annotations

import ctypes
import re
import subprocess
import sys


def available():
    return sys.platform in ("darwin", "win32", "linux")


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
    try:
        if sys.platform == "win32":
            return _check_win(text, lang)
        if sys.platform == "linux":
            return _check_linux(text, lang)
        checker = _checker()
        if checker is None:
            return None
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
    return {"correctedText": _corrected_text(text, corrections),
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


def _utf16_len(text):
    """Length of ``text`` in UTF-16 code units (NSString/QTextCursor
    units -- what both platform spell APIs report)."""
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in text)


def _corrected_text(text, corrections):
    """Splice each correction's top suggestion into the ORIGINAL
    offsets in one pass -- applying them to a mutable copy shifts
    later spans."""
    corrected = []
    cursor = 0
    total = _utf16_len(text)
    for c in corrections:
        s, e = c["startIndex"], c["endIndex"]
        corrected.append(_utf16_slice(text, cursor, s))
        corrected.append(c["suggestions"][0] if c["suggestions"]
                         else _utf16_slice(text, s, e))
        cursor = e
    corrected.append(_utf16_slice(text, cursor, total))
    return "".join(corrected)


# ------------------------------------------------------------- Windows
# Port of JnaWindowsSpellNative (WindowsSpellCheckerBackend.kt): the
# Windows 8+ Spell Checking COM API bound through ctypes vtable calls.
# Method slots count IUnknown's three entries, exactly like upstream's
# ``call(instance, index, ...)``. Strings cross as LPCWSTR; returned
# LPWSTR buffers are CoTaskMemAlloc'd and freed with CoTaskMemFree.

_SPELL_FACTORY_CLSID = "7ab36653-1796-484b-bdfa-e74f1db7c1dc"
_SPELL_FACTORY_IID = "8e018a9d-2415-4677-bf08-794ea61f94bb"
_RPC_E_CHANGED_MODE = -2147417850  # CoInitializeEx already done


def _guid_bytes(value):
    """UUID string -> 16-byte COM GUID (Data1-3 little-endian)."""
    import uuid
    u = uuid.UUID(value)
    return (u.time_low.to_bytes(4, "little")
            + u.time_mid.to_bytes(2, "little")
            + u.time_hi_version.to_bytes(2, "little")
            + u.bytes[8:])


def _vtbl(obj, index, restype, argtypes):
    """Bind vtable slot ``index`` of COM object ``obj`` (int address)."""
    if isinstance(obj, int):
        obj = ctypes.c_void_p(obj)
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(vtbl[0][index])


def _release(obj):
    """IUnknown::Release (vtable slot 2)."""
    if obj:
        try:
            _vtbl(obj, 2, ctypes.c_long, [])(obj)
        except Exception:
            pass


def _win_language_tag(lang, supported):
    """SpellLanguageMapper.nativeTag: exact tag (case-insensitive),
    else base-language match; a regional tag with no exact match gets
    no fallback. auto/empty -> "en". None when unsupported."""
    tag = (lang or "").strip()
    if not tag or tag in ("auto", "auto-detect"):
        tag = "en"
    want = tag.replace("_", "-")
    for s in supported:
        if s.replace("_", "-").lower() == want.lower():
            return s
    if "-" in want:
        return None
    base = want.split("-", 1)[0].lower()
    for s in supported:
        if s.replace("_", "-").split("-", 1)[0].lower() == base:
            return s
    return None


def _win_enum_strings(enumerator, ole):
    """IEnumString::Next -> [str]; each LPWSTR is CoTaskMem-freed."""
    out = []
    while True:
        val = ctypes.c_void_p()
        fetched = ctypes.c_ulong(0)
        hr = _vtbl(enumerator, 3, ctypes.c_long,
                   [ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_ulong)])(
            enumerator, 1, ctypes.byref(val), ctypes.byref(fetched))
        if val.value:
            try:
                out.append(ctypes.wstring_at(val.value))
            finally:
                ole.CoTaskMemFree(val)
        if hr == 1 or not fetched.value:  # S_FALSE / nothing left
            break
    return out


def _win_languages(factory, ole):
    """ISpellCheckerFactory::GetSupportedLanguages (slot 3)."""
    out = ctypes.c_void_p()
    hr = _vtbl(factory, 3, ctypes.c_long,
              [ctypes.POINTER(ctypes.c_void_p)])(
        factory, ctypes.byref(out))
    if hr < 0 or not out.value:
        raise RuntimeError("GetSupportedLanguages failed")
    try:
        return _win_enum_strings(out.value, ole)
    finally:
        _release(out.value)


def _win_create_checker(factory, tag):
    """ISpellCheckerFactory::CreateSpellChecker (slot 5)."""
    out = ctypes.c_void_p()
    hr = _vtbl(factory, 5, ctypes.c_long,
              [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)])(
        factory, tag, ctypes.byref(out))
    if hr < 0 or not out.value:
        raise RuntimeError("CreateSpellChecker failed")
    return out.value


def _win_suggest(checker, word, ole):
    """ISpellChecker::Suggest (slot 5) -> up to 5 candidates."""
    out = ctypes.c_void_p()
    hr = _vtbl(checker, 5, ctypes.c_long,
              [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)])(
        checker, word, ctypes.byref(out))
    if hr < 0 or not out.value:
        return []
    try:
        return _win_enum_strings(out.value, ole)[:5]
    finally:
        _release(out.value)


def _win_error(checker, err, text, total16, ole):
    """One ISpellingError -> correction dict, or None for action 0.

    Slots mirror upstream: 3=get_StartIndex, 4=get_Length,
    5=get_Type, 6=get_Replacement; action 1 -> ISpellChecker.Suggest,
    action 2 -> the error's own replacement string."""
    start = ctypes.c_ulong(0)
    length = ctypes.c_ulong(0)
    etype = ctypes.c_int(0)
    _vtbl(err, 3, ctypes.c_long, [ctypes.POINTER(ctypes.c_ulong)])(
        err, ctypes.byref(start))
    _vtbl(err, 4, ctypes.c_long, [ctypes.POINTER(ctypes.c_ulong)])(
        err, ctypes.byref(length))
    _vtbl(err, 5, ctypes.c_long, [ctypes.POINTER(ctypes.c_int)])(
        err, ctypes.byref(etype))
    end = start.value + length.value
    if length.value <= 0 or end > total16:
        raise RuntimeError("bad spelling error range")
    if etype.value == 0:
        return None
    original = _utf16_slice(text, start.value, end)
    suggestions = []
    if etype.value == 1:
        suggestions = _win_suggest(checker, original, ole)
    elif etype.value == 2:
        rep = ctypes.c_void_p()
        hr = _vtbl(err, 6, ctypes.c_long,
                  [ctypes.POINTER(ctypes.c_void_p)])(
            err, ctypes.byref(rep))
        if hr >= 0 and rep.value:
            try:
                suggestions = [ctypes.wstring_at(rep.value)]
            finally:
                ole.CoTaskMemFree(rep)
    return {"original": original,
            "startIndex": start.value,
            "endIndex": end,
            "suggestions": suggestions,
            "type": "SPELLING"}


def _win_collect(checker, errors, text, ole):
    """Drain IEnumSpellingError::Next (slot 3) into corrections.

    Unlike IEnumString, IEnumSpellingError::Next takes ONE out param
    (``Next([out] ISpellingError **value)`` -- spellcheck.idl) and
    returns S_OK/S_FALSE per item, not the (celt, items, fetched)
    triple. Passing the standard-enumerator signature writes the
    error pointer through the first arg -- which callers supply as a
    small integer count -- and crashes (verified live: AV writing
    0x1)."""
    corrections = []
    total16 = _utf16_len(text)
    while True:
        err = ctypes.c_void_p()
        hr = _vtbl(errors, 3, ctypes.c_long,
                   [ctypes.POINTER(ctypes.c_void_p)])(
            errors, ctypes.byref(err))
        if hr != 0 or not err.value:
            break
        try:
            finding = _win_error(checker, err.value, text, total16, ole)
        finally:
            _release(err.value)
        if finding:
            corrections.append(finding)
    return {"correctedText": _corrected_text(text, corrections),
            "corrections": corrections}


def _check_win(text, lang):
    """Windows spell check via ISpellCheckerFactory COM (ctypes)."""
    ole = ctypes.windll.ole32
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    ole.CoUninitialize.argtypes = []
    ole.CoCreateInstance.restype = ctypes.c_long
    ole.CoCreateInstance.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    ole.CoTaskMemFree.restype = None
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]

    init = ole.CoInitializeEx(None, 0)  # COINIT_APARTMENTTHREADED
    if init not in (0, 1, _RPC_E_CHANGED_MODE):  # S_OK / S_FALSE
        raise RuntimeError("CoInitializeEx failed")
    owns_apartment = init in (0, 1)
    factory = ctypes.c_void_p()
    try:
        clsid = ctypes.create_string_buffer(
            _guid_bytes(_SPELL_FACTORY_CLSID), 16)
        iid = ctypes.create_string_buffer(
            _guid_bytes(_SPELL_FACTORY_IID), 16)
        hr = ole.CoCreateInstance(
            ctypes.addressof(clsid), None, 1, ctypes.addressof(iid),
            ctypes.byref(factory))
        if hr < 0 or not factory.value:
            raise RuntimeError("ISpellCheckerFactory unavailable")
        tag = _win_language_tag(lang, _win_languages(factory.value, ole))
        if tag is None:
            return None
        checker = _win_create_checker(factory.value, tag)
        try:
            errors = ctypes.c_void_p()
            hr = _vtbl(checker, 4, ctypes.c_long,
                      [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)])(
                checker, text, ctypes.byref(errors))
            if hr < 0 or not errors.value:
                raise RuntimeError("ISpellChecker.Check failed")
            try:
                return _win_collect(checker, errors.value, text, ole)
            finally:
                _release(errors.value)
        finally:
            _release(checker)
    finally:
        if factory.value:
            _release(factory.value)
        if owns_apartment:
            ole.CoUninitialize()


# ------------------------------------------------------------- Linux
# Port of LinuxSpellCheckerBackend's contract: discover an installed
# Ispell-protocol engine, feed the text through ``-a`` pipe mode and
# parse the ``@(#)`` header + ``&``/``#`` finding rows. Upstream picks
# enchant-2 then hunspell; this port uses ``aspell``, which speaks the
# same protocol with no extra dependency. Offsets arrive as 1-based
# columns whose unit (chars/UTF-16/UTF-8 bytes) is engine-dependent,
# so -- like upstream's ``sourceOffset`` -- every plausible
# interpretation is tried and only a unique alignment is accepted.

_ASPELL_DICTS = None

# ``& word [line] column: sug, sug`` / ``# word [line] column``.
_ISSUE = re.compile(
    r"^([&#])\s+(.+?)\s+(?:(\d+)\s+)?(\d+)(?::\s*(.*))?$")


def _aspell_exe():
    """Path to aspell, or None when it is not installed."""
    import shutil
    try:
        return shutil.which("aspell")
    except Exception:
        return None


def _aspell_dicts(exe, timeout=5.0):
    """Installed aspell dictionary names via ``aspell dump dicts``.

    Cached per process; an empty set means discovery failed and the
    caller should try the requested language anyway (aspell itself
    reports a missing dictionary, which ``check`` turns into None)."""
    global _ASPELL_DICTS
    if _ASPELL_DICTS is not None:
        return _ASPELL_DICTS
    names = set()
    try:
        out = subprocess.run([exe, "dump", "dicts"], capture_output=True,
                             text=True, timeout=timeout)
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                line = line.strip()
                if line:
                    names.add(line.split()[0])
    except Exception:
        pass
    _ASPELL_DICTS = names
    return names


def _aspell_dict(lang, dicts):
    """Best installed dictionary for ``lang``: exact tag (``-``/``_``
    both tried), then base language, then any ``<base>_*`` variant.
    None when nothing matches."""
    tag = (lang or "").strip()
    if not tag or tag.lower() in ("auto", "auto-detect", "auto_detect"):
        tag = "en"
    base = re.split(r"[-_]", tag)[0].lower()
    cands = []
    for v in (tag, tag.replace("-", "_"), tag.replace("_", "-")):
        cands += [v, v.lower()]
    cands.append(base)
    for c in cands:
        if c in dicts:
            return c
    for d in sorted(dicts):
        dl = d.lower()
        if dl == base or dl.startswith(base + "_") \
                or dl.startswith(base + "-"):
            return d
    return None


def _linux_source_offset(line, word, position):
    """Map aspell's 1-based column to a Python str index.

    Returns the index only when exactly one interpretation (char,
    UTF-16 or UTF-8-byte column) places ``word`` at that spot -- the
    same ambiguity rejection upstream's ``sourceOffset`` does."""
    zero = position - 1
    if zero < 0:
        return None
    cands = set()
    if zero <= len(line):
        cands.add(zero)                       # char column
    cands.add(_utf16_to_py(line, zero))       # UTF-16 column
    try:
        prefix = line.encode("utf-8")[:zero].decode("utf-8")
        if len(prefix.encode("utf-8")) == zero:
            cands.add(len(prefix))            # UTF-8 byte column
    except Exception:
        pass
    ok = [i for i in cands
          if i + len(word) <= len(line)
          and line[i:i + len(word)] == word]
    return ok[0] if len(ok) == 1 else None


def _ispell_findings(source, output):
    """aspell ``-a`` output for ONE source line -> corrections with
    UTF-16 offsets local to that line, or None on malformed output.

    aspell's pipe mode is line-oriented (no cross-line context), so
    ``_check_linux`` feeds one line per invocation and this parser
    never has to guess which report block belongs to which line."""
    if not output.startswith("@(#)"):
        return None
    reports = output.split("\n", 1)[1] if "\n" in output else ""
    corrections = []
    for row in reports.splitlines():
        clean = row.rstrip("\r")
        if not clean or clean[0] in "*+-":
            continue
        m = _ISSUE.match(clean.strip())
        if not m:
            return None  # malformed finding -> caller falls back
        word = m.group(2)
        try:
            position = int(m.group(4))
        except (TypeError, ValueError):
            return None
        idx = _linux_source_offset(source, word, position)
        if idx is None:
            return None  # unaligned offset -> caller falls back
        start16 = _utf16_len(source[:idx])
        end16 = start16 + _utf16_len(word)
        suggestions = ([s.strip() for s in m.group(5).split(",")]
                       if m.group(5) else [])
        corrections.append({
            "original": word,
            "startIndex": start16,
            "endIndex": end16,
            "suggestions": suggestions[:5],
            "type": "SPELLING",
        })
    return corrections


def _check_linux(text, lang):
    """Linux spell check via ``aspell -a`` (Ispell pipe protocol).

    Returns the bing_spell-shaped dict, or None when aspell or a
    matching dictionary is absent -- the caller then falls back to
    the network backends. Text goes over stdin, never argv. Each
    source line gets its own ``aspell -a`` run: the pipe protocol is
    line-oriented, so this is semantically identical to one batch run
    while keeping report->line mapping unambiguous."""
    exe = _aspell_exe()
    if not exe or not (text or "").strip():
        return None
    dicts = _aspell_dicts(exe)
    tag = _aspell_dict(lang, dicts)
    if tag is None:
        if dicts:
            return None  # known dictionaries, none for this language
        # Discovery failed: try the base language and let aspell
        # itself report a missing dictionary (-> nonzero -> None).
        base = re.split(r"[-_]", (lang or "").strip())[0].lower()
        tag = base if base and base not in ("auto", "autodetect") \
            else "en"
    corrections = []
    line_start16 = 0
    for raw_line in text.split("\n"):
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line
        if not line:
            line_start16 += _utf16_len(raw_line) + 1
            continue
        try:
            proc = subprocess.run(
                [exe, "-a", "-l", tag],
                input=line.encode("utf-8"), capture_output=True,
                timeout=15)
        except Exception:
            return None
        if proc.returncode != 0:
            return None
        found = _ispell_findings(
            line, proc.stdout.decode("utf-8", "replace"))
        if found is None:
            return None
        for c in found:
            c["startIndex"] += line_start16
            c["endIndex"] += line_start16
            corrections.append(c)
        line_start16 += _utf16_len(raw_line) + 1  # + '\n'
    return {"correctedText": _corrected_text(text, corrections),
            "corrections": corrections}
