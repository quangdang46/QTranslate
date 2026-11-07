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


_GTTS_MAX_CHUNK = 200


def _gt_partition(text):
    """GoogleTTSService.partitionText: word-boundary chunks of <=200."""
    acc = [""]
    for word in (text or "").split():
        cur = acc[-1]
        if len((cur + " " + word).strip()) > _GTTS_MAX_CHUNK and cur:
            acc.append(word)
        else:
            acc[-1] = word if not cur else cur + " " + word
    return [c for c in acc if c.strip()]


def _gt_chunks_endpoint(text, lang, slow, client, with_index):
    """One pass over the chunks; returns concatenated MP3 bytes."""
    chunks = _gt_partition(text)
    out = []
    for idx, chunk in enumerate(chunks):
        params = [("client", client), ("ie", "UTF-8"), ("tl", lang),
                  ("q", chunk)]
        if with_index:
            params += [("total", str(len(chunks))), ("idx", str(idx)),
                       ("textlen", str(len(chunk)))]
        url = (GOOGLEAPIS_TTS_HOST + "/translate_tts?"
               + urllib.parse.urlencode(params))
        out.append(_fetch_audio(url, "googleapis translate_tts"))
    return b"".join(out)


def _google_tts_chunked(text, lang, slow=False):
    """plugins/google-services GoogleTTSService.synthesize: chunked
    requests on translate.googleapis.com -- primary client=gtx with
    total/idx/textlen, fallback client=tw-ob. ``speed`` is accepted by
    the Kotlin signature but never sent to the endpoint."""
    try:
        return _gt_chunks_endpoint(text, lang, slow, "gtx", True)
    except Exception:
        return _gt_chunks_endpoint(text, lang, slow, "tw-ob", False)


def google_tts(text, lang, slow=False, tkk="0.0"):
    """Port of Google serviceListenRequest: /translate_tts?client=gtx&tk=...

    The plugins/google-services GoogleTTSService path (chunked
    googleapis endpoint) runs first -- it is the Kotlin plugin's
    primary. The legacy translate.google.com + tk-token URL and the
    single-shot googleapis URL remain as extra fallbacks.
    """
    try:
        return _google_tts_chunked(text, lang, slow)
    except Exception as e:
        print("google chunked tts failed (%s); trying legacy" % e)
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


# ---------------------------------------------------------------- Bing TTS
# Port of .tmp plugins/bing-services BingTTSService: POST
# bing.com/tfettts with an SSML body + the same scraped session
# credentials the translator uses (IG/token/key/MUID cookie via
# session.bing_session's shared opener).

_BING_TTS_URL = "https://www.bing.com/tfettts"
_BING_TTS_CHUNK = 500          # Kotlin MAX_CHUNK_LENGTH

# (locale, gender, neural voice) per provider language code, verbatim
# from BingTTSService.defaultVoiceMap. App codes are translated first:
# "iw"->"he", "zh-CN"->"zh-Hans", "zh-TW"->"zh-Hant".
_BING_VOICES = {
    "af": ("af-ZA", "Female", "af-ZA-AdriNeural"),
    "am": ("am-ET", "Female", "am-ET-MekdesNeural"),
    "ar": ("ar-SA", "Male", "ar-SA-HamedNeural"),
    "ary": ("ar-MA", "Female", "ar-MA-MounaNeural"),
    "arz": ("ar-EG", "Male", "ar-EG-ShakirNeural"),
    "ast": ("es-ES", "Female", "es-ES-ElviraNeural"),
    "be": ("ru-RU", "Female", "ru-RU-SvetlanaNeural"),
    "bg": ("bg-BG", "Male", "bg-BG-BorislavNeural"),
    "bn": ("bn-IN", "Female", "bn-IN-TanishaaNeural"),
    "ca": ("ca-ES", "Female", "ca-ES-JoanaNeural"),
    "cs": ("cs-CZ", "Male", "cs-CZ-AntoninNeural"),
    "cy": ("cy-GB", "Female", "cy-GB-NiaNeural"),
    "da": ("da-DK", "Female", "da-DK-ChristelNeural"),
    "de": ("de-DE", "Female", "de-DE-KatjaNeural"),
    "el": ("el-GR", "Male", "el-GR-NestorasNeural"),
    "en": ("en-US", "Female", "en-US-AriaNeural"),
    "en-GB": ("en-GB", "Female", "en-GB-SoniaNeural"),
    "es": ("es-ES", "Female", "es-ES-ElviraNeural"),
    "et": ("et-EE", "Female", "et-EE-AnuNeural"),
    "fa": ("fa-IR", "Female", "fa-IR-DilaraNeural"),
    "fi": ("fi-FI", "Female", "fi-FI-NooraNeural"),
    "fr": ("fr-FR", "Female", "fr-FR-DeniseNeural"),
    "fr-CA": ("fr-CA", "Female", "fr-CA-SylvieNeural"),
    "ga": ("ga-IE", "Female", "ga-IE-OrlaNeural"),
    "gu": ("gu-IN", "Female", "gu-IN-DhwaniNeural"),
    "he": ("he-IL", "Male", "he-IL-AvriNeural"),
    "hi": ("hi-IN", "Female", "hi-IN-SwaraNeural"),
    "hr": ("hr-HR", "Male", "hr-HR-SreckoNeural"),
    "hu": ("hu-HU", "Male", "hu-HU-TamasNeural"),
    "id": ("id-ID", "Male", "id-ID-ArdiNeural"),
    "is": ("is-IS", "Female", "is-IS-GudrunNeural"),
    "it": ("it-IT", "Male", "it-IT-DiegoNeural"),
    "iu": ("iu-CANS-CA", "Female", "iu-Cans-CA-SiqiniqNeural"),
    "iu-Latn": ("iu-LATN-CA", "Female", "iu-Latn-CA-SiqiniqNeural"),
    "ja": ("ja-JP", "Female", "ja-JP-NanamiNeural"),
    "jav": ("jv-ID", "Female", "jv-ID-SitiNeural"),
    "kk": ("kk-KZ", "Female", "kk-KZ-AigulNeural"),
    "km": ("km-KH", "Female", "km-KH-SreymomNeural"),
    "kn": ("kn-IN", "Female", "kn-IN-SapnaNeural"),
    "ko": ("ko-KR", "Female", "ko-KR-SunHiNeural"),
    "lo": ("lo-LA", "Female", "lo-LA-KeomanyNeural"),
    "lt": ("lt-LT", "Female", "lt-LT-OnaNeural"),
    "lv": ("lv-LV", "Female", "lv-LV-EveritaNeural"),
    "mk": ("mk-MK", "Female", "mk-MK-MarijaNeural"),
    "ml": ("ml-IN", "Female", "ml-IN-SobhanaNeural"),
    "mr": ("mr-IN", "Female", "mr-IN-AarohiNeural"),
    "ms": ("ms-MY", "Male", "ms-MY-OsmanNeural"),
    "mt": ("mt-MT", "Female", "mt-MT-GraceNeural"),
    "my": ("my-MM", "Female", "my-MM-NilarNeural"),
    "nb": ("nb-NO", "Female", "nb-NO-PernilleNeural"),
    "nl": ("nl-NL", "Female", "nl-NL-ColetteNeural"),
    "pl": ("pl-PL", "Female", "pl-PL-ZofiaNeural"),
    "ps": ("ps-AF", "Female", "ps-AF-LatifaNeural"),
    "pt": ("pt-BR", "Female", "pt-BR-FranciscaNeural"),
    "pt-BR": ("pt-BR", "Female", "pt-BR-FranciscaNeural"),
    "pt-PT": ("pt-PT", "Female", "pt-PT-FernandaNeural"),
    "ro": ("ro-RO", "Male", "ro-RO-EmilNeural"),
    "ru": ("ru-RU", "Female", "ru-RU-DariyaNeural"),
    "sk": ("sk-SK", "Male", "sk-SK-LukasNeural"),
    "sl": ("sl-SI", "Male", "sl-SI-RokNeural"),
    "sr-Cyrl": ("sr-RS", "Female", "sr-RS-SophieNeural"),
    "su": ("su-ID", "Female", "su-ID-TutiNeural"),
    "sv": ("sv-SE", "Female", "sv-SE-SofieNeural"),
    "ta": ("ta-IN", "Female", "ta-IN-PallaviNeural"),
    "te": ("te-IN", "Male", "te-IN-ShrutiNeural"),
    "th": ("th-TH", "Male", "th-TH-NiwatNeural"),
    "tr": ("tr-TR", "Female", "tr-TR-EmelNeural"),
    "uk": ("uk-UA", "Female", "uk-UA-PolinaNeural"),
    "ur": ("ur-IN", "Female", "ur-IN-GulNeural"),
    "uz": ("uz-UZ", "Female", "uz-UZ-MadinaNeural"),
    "vi": ("vi-VN", "Male", "vi-VN-NamMinhNeural"),
    "yue": ("zh-HK", "Female", "zh-HK-HiuGaaiNeural"),
    "zh-Hans": ("zh-CN", "Female", "zh-CN-XiaoxiaoNeural"),
    "zh-Hant": ("zh-CN", "Female", "zh-CN-XiaoxiaoNeural"),
}
_BING_LANG_ALIAS = {"iw": "he", "zh-CN": "zh-Hans", "zh-TW": "zh-Hant"}


def _bing_voice(lang):
    code = _BING_LANG_ALIAS.get(lang or "", lang or "")
    return _BING_VOICES.get(code) or _BING_VOICES["en"]


def _bing_chunks(text):
    """Kotlin partitionText: the running chunk is acc.lastOrNull(); on
    overflow the full chunk stays and the word starts a new one."""
    chunks = []
    for word in (text or "").split():
        cur = chunks[-1] if chunks else ""
        nxt = word if not cur else cur + " " + word
        if len(nxt) > _BING_TTS_CHUNK:
            if word:
                chunks.append(word)
        elif chunks:
            chunks[-1] = nxt
        else:
            chunks.append(nxt)
    return [c for c in chunks if c.strip()]


def _bing_ssml(text, locale, gender, voice, rate):
    esc = (text.replace("&", "&amp;").replace("<", "&lt;")
           .replace(">", "&gt;").replace('"', "&quot;")
           .replace("'", "&apos;"))
    return ("<speak version='1.0' xml:lang='%s'>"
            "<voice xml:lang='%s' xml:gender='%s' name='%s'>"
            "<prosody rate='%s'>%s</prosody></voice></speak>"
            % (locale, locale, gender, voice, rate, esc))


def bing_tts(text, lang, slow=False):
    """Bing neural TTS -> concatenated MP3 bytes (Kotlin chunking)."""
    from qtranslate import session as _S
    s = _S.bing_session()
    locale, gender, voice = _bing_voice(lang)
    rate = "-25.00%" if slow else "+0.00%"
    opener = s.get("opener")
    out = bytearray()
    for chunk in _bing_chunks(text):
        body = urllib.parse.urlencode({
            "ssml": _bing_ssml(chunk, locale, gender, voice, rate),
            "token": s["token"],
            "key": s["key"],
        }).encode("utf-8")
        url = ("%s?isVertical=1&IG=%s&IID=%s"
               % (_BING_TTS_URL, urllib.parse.quote(str(s["IG"])),
                  urllib.parse.quote(str(s.get("iid", "")))))
        req = urllib.request.Request(
            url, data=body,
            headers={**_UA,
                     "Content-Type":
                         "application/x-www-form-urlencoded; charset=utf-8",
                     "Origin": "https://www.bing.com",
                     "Referer": "https://www.bing.com/translator"})
        with _S._net_open(req, opener) as r:
            data = r.read()
        if not _looks_like_audio(data):
            raise RuntimeError("bing tts returned non-audio response "
                               "(%d bytes)" % len(data))
        out += data
    if not out:
        raise RuntimeError("bing tts produced no audio")
    return bytes(out)
