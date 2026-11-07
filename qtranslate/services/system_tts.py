"""System TTS voices -- port of system-services' MacTtsBackend +
VoiceLocaleMapper (macOS ``say``), WindowsTtsBackend (SAPI SpVoice)
and LinuxTtsBackend (eSpeak/eSpeak-NG), dispatched on
``sys.platform``.

macOS: ``say -v ?`` lists installed voices as ``Name    locale    #
sample``; the locale's language subtag is matched against the
requested language the same way upstream's ``VoiceLocaleMapper.
preferred`` does: exact tag first, then language membership.

Windows: SAPI ``SpVoice.GetVoices`` tokens are enumerated through
comtypes (lazily imported -- the dependency stays optional, see
requirements.txt) and each token's ``Language`` LCID is resolved to a
locale tag via ``kernel32.LocaleNameFromLCID``. ``speak`` picks the
best-matching token exactly like ``preferred_voice`` and falls back
to the default voice for ``auto``/unmatched languages.

Linux: the .tmp ``LinuxTtsBackend`` runs ``espeak-ng`` (falling back
to ``espeak``) and parses ``--voices`` -- pty, language, age/gender,
voice name, file, other languages -- where the voice id is field 3
and the locale field 1, exactly like upstream's column mapping.
"""
import re
import subprocess
import sys

_VOICE_LINE = re.compile(
    r"^(.+?)\s+([A-Za-z]{2,8}(?:[_-](?:[A-Za-z]{4}|[A-Za-z]{2}"
    r"|[0-9]{3}))*)\s+#")


def discover_voices(timeout=10.0):
    """[(voice_id, locale)] for the platform's system voices."""
    if sys.platform == "win32":
        return [(name, loc) for _tok, name, loc in _sapi_voices()]
    if sys.platform == "linux":
        return _discover_voices_linux(timeout)
    return _discover_voices_macos(timeout)


def _discover_voices_macos(timeout):
    """[(voice_id, locale)] from ``say -v ?``; [] when say is absent."""
    try:
        out = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True,
            timeout=timeout).stdout
    except Exception:
        return []
    voices = []
    for line in out.splitlines():
        m = _VOICE_LINE.match(line)
        if m:
            voices.append((m.group(1).strip(), m.group(2)))
    # distinctBy id, keep first -- upstream ordering
    seen = set()
    return [v for v in voices if not (v[0] in seen or seen.add(v[0]))]


# ------------------------------------------------------------- Linux
# LinuxTtsBackend equivalent (.tmp system-services): eSpeak /
# eSpeak-NG, located espeak-ng first then espeak.

def _espeak_exe():
    """Path to espeak-ng or espeak (upstream's locate order), or None."""
    import shutil
    for name in ("espeak-ng", "espeak"):
        try:
            exe = shutil.which(name)
        except Exception:
            exe = None
        if exe:
            return exe
    return None


def _discover_voices_linux(timeout=10.0):
    """[(voice_id, locale)] from ``espeak --voices``; [] when absent.

    Column layout (upstream LinuxTtsBackend.discoverVoices):
    ``pty language age/gender voice-name file other-langs`` -- the
    voice id passed to ``-v`` is field 3, the locale is field 1."""
    exe = _espeak_exe()
    if not exe:
        return []
    try:
        out = subprocess.run(
            [exe, "--voices"], capture_output=True, text=True,
            timeout=timeout).stdout
    except Exception:
        return []
    voices = []
    for line in out.splitlines()[1:]:  # header row
        fields = line.split()
        if len(fields) < 5 or not fields[0].isdigit():
            continue
        voices.append((fields[3], fields[1]))
    # distinctBy id, keep first -- upstream ordering
    seen = set()
    return [v for v in voices if not (v[0] in seen or seen.add(v[0]))]


# ------------------------------------------------------------- Windows
# SAPI SpVoice voice tokens (SpVoiceToken.GetDescription /
# GetAttribute("Language") -> LCID). comtypes is an optional dep
# (requirements.txt); absent -> empty list / speak() returns False so
# the caller can use qtranslate.sapi's PowerShell fallback.

def _lcid_locale(lcid):
    """LCID -> locale tag via kernel32.LocaleNameFromLCID ("" off-Windows)."""
    if not lcid:
        return ""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(85)
        n = ctypes.windll.kernel32.LocaleNameFromLCID(
            int(lcid), 0, buf, len(buf))
        return buf.value if 0 < n <= len(buf) else ""
    except Exception:
        return ""


def _sapi_voices(sp=None):
    """[(token, name, locale)] from SAPI.SpVoice.GetVoices; [] when
    comtypes/SAPI is unavailable. Windows-only path."""
    try:
        import comtypes.client
    except Exception:
        return []
    try:
        if sp is None:
            sp = comtypes.client.CreateObject("SAPI.SpVoice")
        voices = sp.GetVoices()
        out = []
        for i in range(int(getattr(voices, "Count", 0) or 0)):
            tok = voices.Item(i)
            try:
                name = str(tok.GetDescription() or "")
            except Exception:
                name = ""
            try:
                lcid = int(tok.GetAttribute("Language") or 0)
            except Exception:
                lcid = 0
            out.append((tok, name, _lcid_locale(lcid)))
        return out
    except Exception:
        return []


def _lang_of(locale):
    return locale.replace("_", "-").split("-", 1)[0].lower()


def _preferred_index(lang, voices):
    """Index into ``voices`` per VoiceLocaleMapper.preferred: exact
    locale tag first, then language membership. -1 when none."""
    tag = lang.replace("_", "-")
    want = tag.lower()
    for i, (_vid, locale) in enumerate(voices):
        if locale.replace("_", "-").lower() == want:
            return i
    base = _lang_of(tag)
    for i, (_vid, locale) in enumerate(voices):
        if _lang_of(locale) == base:
            return i
    return -1


def preferred_voice(lang, voices=None):
    """VoiceLocaleMapper.preferred: exact locale tag, else any voice
    whose locale covers the requested language. ``auto``/empty -> the
    system default voice (None)."""
    if not lang or lang.lower() in ("auto", "autodetect"):
        return None
    voices = voices if voices is not None else discover_voices()
    idx = _preferred_index(lang, voices)
    return voices[idx][0] if idx >= 0 else None


def speak(text, lang="", slow=False):
    """Speak ``text`` through the Windows system voice (SAPI SpVoice)
    with VoiceLocaleMapper-style voice matching.

    Returns True when SAPI spoke; False when comtypes/SAPI is missing
    or the platform is not Windows, so the caller can fall back to
    ``qtranslate.sapi.speak`` (PowerShell SAPI).
    """
    if sys.platform != "win32":
        return False
    try:
        import comtypes.client
        sp = comtypes.client.CreateObject("SAPI.SpVoice")
        entries = _sapi_voices(sp)
        idx = _preferred_index(lang or "", [(n, l) for _t, n, l in entries]) \
            if lang and lang.lower() not in ("auto", "autodetect") else -1
        if idx >= 0:
            sp.Voice = entries[idx][0]
        sp.Rate = -4 if slow else 0
        sp.Speak(text)
        return True
    except Exception:
        return False
