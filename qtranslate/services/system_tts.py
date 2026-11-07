"""macOS system TTS voices -- port of system-services'
MacTtsBackend + VoiceLocaleMapper.

``say -v ?`` lists installed voices as ``Name    locale    # sample``;
the locale's language subtag is matched against the requested language
the same way upstream's ``VoiceLocaleMapper.preferred`` does: exact
tag first, then language membership.
"""
import re
import subprocess

_VOICE_LINE = re.compile(
    r"^(.+?)\s+([A-Za-z]{2,8}(?:[_-](?:[A-Za-z]{4}|[A-Za-z]{2}"
    r"|[0-9]{3}))*)\s+#")


def discover_voices(timeout=10.0):
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


def _lang_of(locale):
    return locale.replace("_", "-").split("-", 1)[0].lower()


def preferred_voice(lang, voices=None):
    """VoiceLocaleMapper.preferred: exact locale tag, else any voice
    whose locale covers the requested language. ``auto``/empty -> the
    system default voice (None)."""
    if not lang or lang.lower() in ("auto", "autodetect"):
        return None
    voices = voices if voices is not None else discover_voices()
    tag = lang.replace("_", "-")
    want = tag.lower()
    for voice_id, locale in voices:
        if locale.replace("_", "-").lower() == want:
            return voice_id
    base = _lang_of(tag)
    for voice_id, locale in voices:
        if _lang_of(locale) == base:
            return voice_id
    return None
