"""Python ports of QTranslate text-to-speech serviceListenRequest functions.

Reversed from QTranslate 6.10.0 - Services/Google Translate, Yandex,
Baidu Service.js. Each function returns raw MP3 bytes via stdlib urllib.
"""

import urllib.parse
import urllib.request

from qtranslate.services.google_translate import tk as _google_tk

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

GOOGLE_TTS_HOST = "https://translate.google.com"
YANDEX_TTS_HOST = "https://tts.voicetech.yandex.net"
BAIDU_TTS_HOST = "https://tts.baidu.com"


def _fetch_bytes(url):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def google_tts(text, lang, slow=False, tkk="0.0"):
    """Port of Google serviceListenRequest: /translate_tts?client=gtx&tk=..."""
    url = (GOOGLE_TTS_HOST + "/translate_tts?ie=UTF-8&q={0}&tl={1}"
           "&client=gtx&tk={2}").format(
               urllib.parse.quote(text), lang, _google_tk(text, tkk))
    if slow:
        url += "&ttsspeed=0.24"
    return _fetch_bytes(url)


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
               _yandex_voice(lang), urllib.parse.quote(text))
    if slow:
        url += "&speed=0.7"
    return _fetch_bytes(url)


def baidu_tts(text, lang, slow=False):
    """Port of Baidu serviceListenRequest: tts.baidu.com/text2audio."""
    url = (BAIDU_TTS_HOST + "/text2audio?lan={0}&ie=UTF-8&text={1}").format(
        lang, urllib.parse.quote(text))
    if slow:
        url += "&spd=1"
    return _fetch_bytes(url)
