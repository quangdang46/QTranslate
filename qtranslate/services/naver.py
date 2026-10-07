"""1:1 port of Services/Naver/Service.js (SERVICE_ID=30).

Legacy part (QTranslate 6.10 era, endpoints now 404 server-side):
serviceHeader/Host/Link, uuid/toBase64/buildAuthData (HmacMD5 over
deviceId + url + timestamp, key "v1.6.5_956d74858f"), isN2MT pair rule,
detect pair, translate pair (with pt|hi -> EN fallback and
srcLangType/tarLangType resolution), SupportedLanguages.

Current-web extension (reversed 2026-10-07 from papago.naver.com
Next.js chunks, all LIVE-OK, no auth): _new_post, translate path via
/api/text/translation, translate_instant, TTS makeID/fetch, dictionary
search, speaker map. Clearly marked EXTENSION, not native.
"""
import base64
import hashlib
import hmac
import json
import random
import time
import urllib.parse
import urllib.request
import uuid

from qtranslate.common import (
    NL2,
    UNKNOWN_LANGUAGE,
    ENGLISH_LANGUAGE,
    Capability,
    ServiceHeader,
    code_from_language,
    encode_post_param,
    format_q,
    is_language,
    language_from_code,
    limit_source,
    parse_json_lenient,
    post_header,
    prepare_source,
    read_response_text,
    Options,
)

SERVICE_ID = 30
SERVICE_NAME = "Papago"
HOST = "https://papago.naver.com"
_AUTH_KEY = "v1.6.5_956d74858f"

SUPPORTED_LANGS = [-1, "auto", -1, -1, -1, -1, -1, -1, -1, -1, -1, "zh-CN",
                   "zh-TW", -1, -1, -1, -1, "en", -1, -1, -1, "fr", -1, "de",
                   -1, -1, -1, "hi", -1, -1, "id", "it", -1, "ja", -1, "ko",
                   -1, -1, -1, -1, -1, -1, -1, -1, "pt", -1, "ru", -1, -1, -1,
                   "es", -1, -1, "th", -1, -1, -1, "vi", -1, -1, -1, -1, -1,
                   -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]

_N2MT_PAIRS = {"enhi", "enpt", "hien", "pten"}


def service_header() -> ServiceHeader:
    return ServiceHeader(
        30, "Papago",
        "Naver Papago is a multilingual machine translation cloud service "
        "provided by Naver Corporation." + NL2 + service_host() + NL2 +
        "© NAVER Corp.",
        Capability.TRANSLATE | Capability.DETECT_LANGUAGE)


def service_host() -> str:
    return "https://papago.naver.com"


def service_link(text="", sl=1, tl=17) -> str:
    link = service_host()
    if text:
        link += format_q("/?sk={0}&tk={1}&st={2}",
                         code_from_language(sl, SUPPORTED_LANGS)
                         if isinstance(sl, int) else sl,
                         code_from_language(tl, SUPPORTED_LANGS)
                         if isinstance(tl, int) else tl,
                         urllib.parse.quote(text))
    return link


def uuid4_js() -> str:
    """Port of uuid(): time-seeded v4 template (not RFC uuid4)."""
    b = int(time.time() * 1000)

    def rep(m):
        nonlocal b
        a = (b + int(16 * random.random())) % 16 | 0
        b = b // 16
        return ("%x" % a) if m.group(0) == "x" else ("%x" % (3 & a | 8))

    import re
    return re.sub(r"[xy]",
                  lambda m: ("%x" % ((b + int(16 * random.random())) % 16 | 0))
                  if m.group(0) == "x" else ("%x" % (3 & int(
                      (b + int(16 * random.random())) % 16) | 8)),
                  "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx")


def _auth(url: str):
    """Port of buildAuthData(b). Returns (header_block, device_id)."""
    ts = str(int(time.time() * 1000) - 19555)
    dev = str(uuid.uuid4())
    sig = hmac.new(_AUTH_KEY.encode(), f"{dev}\n{url}\n{ts}".encode(),
                   hashlib.md5).digest()
    header = (f"Authorization:PPG {dev}:{base64.b64encode(sig).decode()}\r\n"
              f"Timestamp:{ts}")
    return header, dev


def _post_legacy(path: str, body: str) -> dict:
    url = HOST + path
    header, _ = _auth(url)
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*",
               "Accept-Language": "en-US;q=0.8",
               "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
    for line in header.split("\r\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    req = urllib.request.Request(url, data=body.encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return parse_json_lenient(read_response_text(r))


def is_n2mt(sl_code: str, tl_code: str) -> bool:
    """Port of isN2MT: true unless pair is en-hi/en-pt/hi-en/pt-en."""
    return (sl_code + tl_code) not in _N2MT_PAIRS


def detect(text: str) -> int:
    """Port of detect pair. Returns a lang *index*.

    Legacy endpoint first (faithful to native; 404 server-side now),
    then the current-web /api/langs/dect as fallback (EXTENSION).
    """
    body = "query=" + urllib.parse.quote(limit_source(text))
    try:
        resp = _post_legacy("/apis/langs/dect", body)
        if resp.get("langCode"):
            return language_from_code(resp["langCode"], SUPPORTED_LANGS)
    except Exception:
        pass
    try:
        resp = _new_post("/api/langs/dect", {"query": text[:5000]})
        if resp.get("langCode"):
            return language_from_code(resp["langCode"], SUPPORTED_LANGS)
    except Exception:
        pass
    return UNKNOWN_LANGUAGE


def detect_code(text: str) -> str:
    """Convenience: detect() resolved to a language code string."""
    return code_from_language(detect(text), SUPPORTED_LANGS)


def _coerce(sl, tl):
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    if sl_code in ("pt", "hi"):
        sl_code = code_from_language(ENGLISH_LANGUAGE, SUPPORTED_LANGS)
    if tl_code in ("pt", "hi"):
        tl_code = code_from_language(ENGLISH_LANGUAGE, SUPPORTED_LANGS)
    return sl_code, tl_code


def translate_legacy(text: str, sl=1, tl=17) -> tuple:
    """Port of legacy translate pair (now 404 server-side).

    Returns (text, src_index, tl_index) with src/tarLangType resolution.
    sl/tl accept indices or codes.
    """
    sl_code, tl_code = _coerce(sl, tl)
    mode = "n2mt" if is_n2mt(sl_code, tl_code) else "nsmt"
    url = HOST + f"/apis/{mode}/translate"
    header, dev = _auth(url)
    body = ("deviceId={}&source={}&target={}&text={}".format(
        dev, sl_code, tl_code, urllib.parse.quote(limit_source(
            prepare_source(text)))))
    headers = {"User-Agent": "Mozilla/5.0",
               "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
    for line in header.split("\r\n"):
        k, v = line.split(":", 1)
        headers[k.strip()] = v.strip()
    req = urllib.request.Request(url, data=body.encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = parse_json_lenient(read_response_text(r))
    out = resp.get("translatedText", "") if resp else ""
    src_idx = language_from_code(resp.get("srcLangType", ""),
                                 SUPPORTED_LANGS) if resp else UNKNOWN_LANGUAGE
    tl_idx = language_from_code(resp.get("tarLangType", ""),
                                SUPPORTED_LANGS) if resp else UNKNOWN_LANGUAGE
    return out, src_idx, tl_idx


# ------------------------------------------------- EXTENSION: current web API
# (reversed 2026-10-07 from papago.naver.com Next.js chunks; LIVE-OK, no
# auth — not part of the QTranslate 6.10 Service.js)

def _new_post(path: str, params: dict, locale: str = "en",
              as_json: bool = False) -> dict:
    """POST to the current web API (no auth needed).

    Translate/TTS/detect use URLSearchParams (form); dictionary/search
    uses a JSON body.
    """
    if as_json:
        body = json.dumps(params).encode()
        ctype = "application/json"
    else:
        body = urllib.parse.urlencode(params).encode()
        ctype = "application/x-www-form-urlencoded; charset=utf-8"
    req = urllib.request.Request(
        HOST + path, data=body,
        headers={"User-Agent": "Mozilla/5.0",
                 "Accept-Language": locale,
                 "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=20) as r:
        return parse_json_lenient(read_response_text(r))


def translate(text: str, sl: str = "auto", tl: str = "en",
              use_glossary: bool = False, honorific: bool = False,
              with_dict: bool = False, locale: str = "en") -> tuple:
    """Current-web translate (EXTENSION). Returns (text, src_lang_type)."""
    try:
        resp = _new_post("/api/text/translation", {
            "source": sl, "target": tl, "text": text[:5000],
            "dict": str(with_dict).lower(),
            "useGlossary": str(use_glossary).lower(),
            "honorific": str(honorific).lower(),
        }, locale)
        if resp.get("translatedText") is not None:
            return resp.get("translatedText", ""), resp.get("srcLangType", sl)
    except Exception:
        pass
    # legacy fallback (QTranslate 6.10 era, now 404 server-side)
    try:
        out, _, _ = translate_legacy(text, sl, tl)
        return out, sl
    except Exception:
        return "", sl


def translate_instant(text: str, sl: str = "auto", tl: str = "en",
                      locale: str = "en") -> tuple:
    """Tiny/instant variant: POST /api/text/translation/instant."""
    resp = _new_post("/api/text/translation/instant", {
        "source": sl, "target": tl, "text": text[:5000],
    }, locale)
    return resp.get("translatedText", ""), resp.get("srcLangType", sl)


# Speaker map reversed from papago Next.js chunk (ta={ko:[...],en:[...],...}).
# First entry = male-ish default, second = female-ish. gender 0/1 picks index.
TTS_SPEAKERS = {
    "ko": ["jinho", "kyuri"], "en": ["matt", "clara"],
    "de": ["tim", "lena"], "es": ["jose", "carmen"],
    "fr": ["louis", "roxane"], "ja": ["shinji", "yuri"],
    "ru": ["aleksei", "vera"], "th": ["sarawut", "somsi"],
    "zh-CN": ["liangliang", "meimei"], "zh-TW": ["kuanlin", "chiahua"],
}


def tts_make_id(text: str, language: str = "en", gender: int = 0,
                speed: int = 0, locale: str = "en") -> str:
    """POST /api/tts/makeID -> id string for GET /api/tts/{id}.

    Body (reversed from chunk): URLSearchParams
    {alpha:"0", pitch:"0", speaker, speed, text}. speed -2 means -1 for
    en/fr. Returns the id string (TTS_MAKE_ID response shape).
    """
    speakers = TTS_SPEAKERS.get(language, TTS_SPEAKERS["en"])
    speaker = speakers[gender % len(speakers)]
    if speed == -2 and language in ("en", "fr"):
        speed = -1
    resp = _new_post("/api/tts/makeID", {
        "alpha": "0", "pitch": "0", "speaker": speaker,
        "speed": str(speed), "text": text[:5000],
    }, locale)
    if isinstance(resp, dict):
        return resp.get("id", "") or resp.get("ttsId", "")
    return str(resp)


def tts(text: str, language: str = "en", gender: int = 0,
        speed: int = 0, locale: str = "en") -> bytes:
    """Full TTS: makeID then fetch audio."""
    return tts_fetch(tts_make_id(text, language, gender, speed, locale))


# Back-compat alias (old signature: source/speaker/locale)
def tts_legacy(text: str, source: str = "en", speaker: str = "nara",
               locale: str = "en") -> bytes:
    speakers = TTS_SPEAKERS.get(source, TTS_SPEAKERS["en"])
    gender = speakers.index(speaker) if speaker in speakers else 0
    return tts(text, source, gender, 0, locale)


def tts_fetch(tts_id: str) -> bytes:
    """GET /api/tts/{id} -> audio bytes."""
    req = urllib.request.Request(
        HOST + f"/api/tts/{tts_id}",
        headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def dictionary_search(text: str, source: str = "en", target: str = "ko",
                      locale: str = "en") -> dict:
    """POST /api/dictionary/search {text,source,target,clientType}.

    Reversed from chunk (useDictionary): s(o.SEARCH, {...e.params,
    clientType: o.CLIENT_TYPE ?? "WEB"}).
    """
    return _new_post("/api/dictionary/search", {
        "text": text[:5000], "source": source, "target": target,
        "clientType": "WEB",
    }, locale, as_json=True)
