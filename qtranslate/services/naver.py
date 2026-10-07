"""Port of C:/Program Files (x86)/QTranslate/Services/Naver/Service.js (SERVICE_ID=30).

Two generations:
- Legacy (QTranslate 6.10 era): HmacMD5(deviceId + "\\n" + url + "\\n" + timestamp,
  key "v1.6.5_956d74858f"), header "PPG deviceId:base64(hmac)", Timestamp header.
  Endpoints POST /apis/n2mt|nsmt/translate, POST /apis/langs/dect — now 404.
- Current web (reversed 2026-10-07 from papago.naver.com Next.js chunks):
  POST /api/text/translation with URLSearchParams
  {source, target, text, dict, useGlossary, honorific}, header
  Accept-Language only, NO auth. Verified live.
  TTS: POST /api/tts/makeID -> GET /api/tts/{id}.
  Dict: /api/dictionary/search. pt/hi fall back to en.
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
import uuid

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


def _auth(url: str):
    ts = str(int(time.time() * 1000) - 19555)
    dev = str(uuid.uuid4())
    sig = hmac.new(_AUTH_KEY.encode(), f"{dev}\n{url}\n{ts}".encode(),
                   hashlib.md5).digest()
    header = (f"Authorization:PPG {dev}:{base64.b64encode(sig).decode()}\r\n"
              f"Timestamp:{ts}")
    return header, dev


def _post(path: str, body: str, extra_headers: str = "") -> dict:
    url = HOST + path
    _, dev = _auth(url)  # deviceId also goes in body for translate
    req = urllib.request.Request(
        url, data=body.encode(),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*",
                 "Accept-Language": "en-US;q=0.8",
                 "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
    # auth headers are per-request; rebuild for this exact url
    header, _ = _auth(url)
    for line in (header + "\r\n" + extra_headers).split("\r\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            req.add_header(k.strip(), v.strip())
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


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
        return json.loads(r.read().decode("utf-8"))


def detect(text: str) -> str:
    try:
        resp = _new_post("/api/langs/dect", {"query": text[:5000]})
        return resp.get("langCode", "")
    except Exception:
        pass
    # legacy fallback
    body = "query=" + urllib.parse.quote(text[:5000])
    resp = _post("/apis/langs/dect", body)
    return resp.get("langCode", "")


def translate(text: str, sl: str = "auto", tl: str = "en",
              use_glossary: bool = False, honorific: bool = False,
              with_dict: bool = False, locale: str = "en") -> tuple:
    if sl in ("pt", "hi"):
        sl = "en"
    if tl in ("pt", "hi"):
        tl = "en"
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
    mode = "n2mt" if (sl + tl) not in _N2MT_PAIRS else "nsmt"
    url = HOST + f"/apis/{mode}/translate"
    header, dev = _auth(url)
    body = ("deviceId={}&source={}&target={}&text={}".format(
        dev, sl, tl, urllib.parse.quote(text[:5000])))
    req = urllib.request.Request(
        url, data=body.encode(),
        headers={"User-Agent": "Mozilla/5.0",
                 "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
    for line in header.split("\r\n"):
        k, v = line.split(":", 1)
        req.add_header(k.strip(), v.strip())
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp.get("translatedText", ""), resp.get("srcLangType", sl)


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
