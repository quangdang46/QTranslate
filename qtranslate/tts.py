"""Python ports of QTranslate text-to-speech serviceListenRequest functions.

Reversed from QTranslate 6.10.0 - Services/Google Translate, Yandex,
Baidu Service.js. Each function returns raw MP3 bytes via stdlib urllib.

Live endpoint status (verified 2026-11-07, qt-p6r):

  * Google ``translate.google.com/translate_tts`` -- ALIVE (MP3 bytes).
    ``google_tts`` also falls back to ``translate.googleapis.com``
    (the endpoint the Kotlin rewrite's GoogleTTSService uses) when the
    classic host fails.
  * Yandex ``tts.voicetech.yandex.net`` -- DEAD: DNS resolves but every
    connection times out (verified with a 10s socket timeout). Kept for
    native parity; callers get an exception, never silent garbage.
  * Baidu ``tts.baidu.com/text2audio`` -- DEAD: the host answers but the
    TTS backend returns HTTP 200 with a JSON error body
    (``{"err_no":503,"err_detail":"Failed connect to jtts engine"}``),
    and the alternate ``tsn.baidu.com`` host errors the same way.
    ``_fetch_audio`` rejects non-audio bodies so this surfaces as a
    failure (-> offline voice fallback) instead of bogus "MP3" bytes.
  * Naver Papago TTS -- ALIVE (see ``naver_tts`` / services/naver.py).
"""

import urllib.request

from qtranslate.common import encode_get_param
from qtranslate.services.google_translate import tk as _google_tk

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

GOOGLE_TTS_HOST = "https://translate.google.com"
# The Kotlin rewrite (plugins/google-services GoogleTTSService) uses the
# googleapis host for the same translate_tts endpoint, with client=gtx as
# primary and client=tw-ob as its fallback.
GOOGLEAPIS_TTS_HOST = "https://translate.googleapis.com"
YANDEX_TTS_HOST = "https://tts.voicetech.yandex.net"
BAIDU_TTS_HOST = "https://tts.baidu.com"


def _fetch_bytes(url):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _looks_like_audio(data):
    """Cheap magic-byte check so a provider's JSON/HTML error body can
    never be mistaken for MP3 audio (Baidu's dead backend returns HTTP
    200 + ``{"err_no":503,...}``)."""
    if len(data) < 4:
        return False
    head = data[:12]
    return (head.startswith(b"ID3")                # MP3 with ID3 tag
            or head[:3] == b"Ogg"                   # Ogg/Vorbis/Opus
            or head[:4] == b"fLaC"                  # FLAC
            or head[:4] == b"RIFF"                  # WAV
            or (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0))  # MP3 frame sync


def _fetch_audio(url, what):
    """Fetch TTS bytes and refuse non-audio responses honestly."""
    data = _fetch_bytes(url)
    if not _looks_like_audio(data):
        raise RuntimeError("%s returned non-audio response (%d bytes)"
                           % (what, len(data)))
    return data


def google_tts(text, lang, slow=False, tkk="0.0"):
    """Port of Google serviceListenRequest: /translate_tts?client=gtx&tk=...

    REVERTED 2026-10-15 (peer finding): the ``listen_url`` delegation
    silently changed three behaviors — ``urllib.parse.quote`` (keeps
    ``/``) vs ``encode_get_param`` (encodes ``%2F`` + truncates at
    MAX_URI_LEN), the caller-supplied ``tkk`` seed (dropped), and the
    fixed host vs ``service_host()`` domain override. A dedup that
    changes the contract is not a dedup. This keeps the original builder
    verbatim; unifying the two shapes (if ever) needs a URL-equivalence
    matrix first, not a silent swap.
    """
    url = (GOOGLE_TTS_HOST + "/translate_tts?ie=UTF-8&q={0}&tl={1}"
           "&client=gtx&tk={2}").format(
               encode_get_param(text), lang, _google_tk(text, tkk))
    if slow:
        url += "&ttsspeed=0.24"
    try:
        return _fetch_audio(url, "google translate_tts")
    except Exception:
        # Same endpoint on the googleapis host used by the Kotlin
        # rewrite's GoogleTTSService (client=gtx, no tk token needed).
        fb = (GOOGLEAPIS_TTS_HOST + "/translate_tts?client=gtx&ie=UTF-8"
              "&tl={0}&q={1}").format(lang, encode_get_param(text))
        if slow:
            fb += "&ttsspeed=0.24"
        return _fetch_audio(fb, "googleapis translate_tts")


def _yandex_voice(lang):
    mapping = {"en": "en_GB", "sv": "sv_SE", "da": "da_DK", "cs": "cs_CZ",
               "ca": "ca_ES", "ar": "ar_AE"}
    if lang in mapping:
        return mapping[lang]
    return lang + "_" + lang.upper()


def yandex_tts(text, lang, slow=False):
    """Port of Yandex serviceListenRequest: tts.voicetech.yandex.net/tts."""
    url = (YANDEX_TTS_HOST + "/tts?format=mp3&quality=hi&platform=web"
           "&application=translate&lang={0}&text={1}").format(
               _yandex_voice(lang), encode_get_param(text))
    if slow:
        url += "&speed=0.7"
    # Host is dead in the wild (connect timeouts, verified 2026-11-07);
    # kept for native parity. _fetch_audio still guards the body.
    return _fetch_audio(url, "yandex tts")


def baidu_tts(text, lang, slow=False):
    """Port of Baidu serviceListenRequest: tts.baidu.com/text2audio."""
    url = (BAIDU_TTS_HOST + "/text2audio?lan={0}&ie=UTF-8&text={1}").format(
        lang, encode_get_param(text))
    if slow:
        url += "&spd=1"
    # Backend dead in the wild (HTTP 200 + JSON err_no=503, verified
    # 2026-11-07); _fetch_audio turns that body into an exception so
    # callers fall back to the offline voice instead of playing JSON.
    return _fetch_audio(url, "baidu text2audio")


def naver_tts(text, lang="en", gender=0, speed=0, locale="en"):
    """Naver Papago TTS via current web API — verified live 2026-10-07.

    makeID then GET /api/tts/{id}; returns MP3 bytes. Speaker auto-picked
    per language (TTS_SPEAKERS map in services/naver.py).
    """
    from qtranslate.services import naver as _naver
    return _naver.tts(text, lang, gender, speed, locale)
