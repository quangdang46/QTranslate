"""Port of Services/DeepL/Service.js (SERVICE_ID=31) plus the
plugins/deepl-services rewrite.

serviceHeader/Host/Link, getSourceLanguage and detect
(LMT_split_into_sentences) still follow the legacy JS. The legacy
LMT_handle_jobs translate endpoint now answers with an "update DeepL"
wall, so translate() follows plugins/deepl-services instead: official
api.deepl.com/v2 first when General.DeeplApiKey is set, then the
oneshot-free.www.deepl.com/v1/translate free web endpoint.
"""
from __future__ import annotations

import json
import urllib.request
from qtranslate import common

from qtranslate.common import (
    NL2,
    UNKNOWN_LANGUAGE,
    Capability,
    ServiceHeader,
    code_from_language,
    encode_get_param,
    format_q,
    is_language,
    language_from_code,
    limit_source,
    parse_json_lenient,
    post_header,
)

SERVICE_ID = 31
SERVICE_NAME = "DeepL"
HOST = "https://www2.deepl.com"

SUPPORTED_LANGS = [
    -1, "auto", -1, -1, -1, -1, -1, -1, -1, "BG", -1, "ZH", -1, -1, "CS",
    "DA", "NL", "EN", "ET", "FI", -1, "FR", -1, "DE", "EL", -1, -1, -1,
    "HU", -1, -1, "IT", -1, "JA", -1, -1, "LV", "LT", -1, -1, -1, -1, -1,
    "PL", "PT", "RO", "RU", -1, "SK", "SL", "ES", -1, "SV", -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1,
]

def service_header() -> ServiceHeader:
    return ServiceHeader(
        31, "DeepL",
        "DeepL trains artificial intelligence to understand and translate "
        "texts." + NL2 + "https://www.deepl.com",
        Capability.TRANSLATE | Capability.DETECT_LANGUAGE)


def service_host() -> str:
    return "https://www2.deepl.com"


def service_link(text="", sl=1, tl=17) -> str:
    c = "https://www.deepl.com/translator"
    if text and is_language(sl, SUPPORTED_LANGS) \
            and is_language(tl, SUPPORTED_LANGS):
        c += format_q("#{0}/{1}/{2}",
                      code_from_language(sl, SUPPORTED_LANGS).lower(),
                      code_from_language(tl, SUPPORTED_LANGS).lower(),
                      encode_get_param(text))
    return c


def get_source_language(obj: dict, key: str) -> int:
    """Port of getSourceLanguage(a,b). Returns a lang *index*."""
    try:
        if obj and obj.get("result") and obj["result"].get(key):
            return language_from_code(obj["result"][key], SUPPORTED_LANGS)
    except (KeyError, TypeError, IndexError):
        pass
    return UNKNOWN_LANGUAGE


def _post_jsonrpc(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {}
    for line in post_header(True).split("\r\n"):
        if ": " in line:
            k, v = line.split(": ", 1)
            headers[k] = v
    headers["Accept"] = "*/*"
    req = urllib.request.Request(HOST + "/jsonrpc", data=data,
                                 headers=headers)
    with common.http_open(req) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding", "") == "gzip" \
                or raw[:2] == b"\x1f\x8b":
            import gzip
            raw = gzip.decompress(raw)
        return parse_json_lenient(raw.decode("utf-8"))


def detect(text: str) -> int:
    """Port of serviceDetectLanguageRequest/Response.

    Returns a language *index* into SUPPORTED_LANGS (like the native,
    which resolves via languageFromCode).
    """
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "LMT_split_into_sentences",
        "params": {
            "texts": [limit_source(text)],
            "lang": {"lang_user_selected": "auto",
                     "user_preferred_langs": ["EN"]},
        },
    }
    return get_source_language(_post_jsonrpc(payload), "lang")


def detect_code(text: str) -> str:
    """Convenience: detect() resolved to a language code string."""
    return code_from_language(detect(text), SUPPORTED_LANGS)


OFFICIAL_HOST = "https://api.deepl.com"
# plugins/deepl-services DeepLTranslatorService: the free web endpoint
# is the oneshot-free JSON API -- the legacy www2.deepl.com jsonrpc
# jobs endpoint now answers with an "update DeepL" wall, so it is gone
# from the translate path (detect() still uses it; that endpoint lives).
WEB_HOST = "https://oneshot-free.www.deepl.com"
WEB_MIN_INTERVAL = 2.0        # minimumWebRequestIntervalMillis = 2_000
WEB_BACKOFF = 10.0            # rateLimitBackoffMillis = 10_000
WEB_MAX_RETRIES = 1           # maxWebRetries
WEB_MAX_CHARS = 5_000         # MAX_WEB_CHARACTERS
_WEB_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
    "Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]
_web_lock = None
_last_web_at = [0.0]


def _web_lock_obj():
    global _web_lock
    if _web_lock is None:
        import threading
        _web_lock = threading.Lock()
    return _web_lock


def _pace_web_request():
    """paceWebRequest: >=2s between free-web calls, like upstream."""
    import time as _t
    with _web_lock_obj():
        wait = WEB_MIN_INTERVAL - (_t.time() - _last_web_at[0])
        if wait > 0:
            _t.sleep(wait)
        _last_web_at[0] = _t.time()


def _web_code(code: str) -> str:
    """toWebCode: zh variants collapse to 'zh'; otherwise the tag
    before '-' lowercased."""
    c = (code or "").upper()
    if c.startswith("ZH"):
        return "zh"
    return c.split("-")[0].lower()


def _split_for_web(text: str):
    """splitForWeb: <=5000-char chunks on a whitespace boundary in the
    chunk's second half."""
    text = text or ""
    if len(text) <= WEB_MAX_CHARS:
        return [text]
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + WEB_MAX_CHARS, n)
        if end < n:
            boundary = None
            for i in range(end - 1, start + WEB_MAX_CHARS // 2, -1):
                if text[i].isspace():
                    boundary = i
                    break
            if boundary is not None:
                end = boundary + 1
        chunks.append(text[start:end])
        start = end
    return [c for c in chunks if c]


def _is_web_rate_limited(body: str, status: int) -> bool:
    low = (body or "").lower()
    return (status == 429
            or "too many requests" in low
            or '"code":1042911' in (body or ""))


def _web_post(body: dict):
    """postWeb: POST the JSON body; one retry after
    max(10s, Retry-After) on a rate-limit response."""
    import time as _t
    import urllib.error
    import random as _r
    url = WEB_HOST + "/v1/translate"
    data = json.dumps(body).encode()
    for attempt in range(WEB_MAX_RETRIES + 1):
        _pace_web_request()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json",
                     "Accept": "application/json",
                     "Accept-Language": "en-US,en;q=0.9",
                     "Accept-Encoding": "identity",
                     "Authorization": "None",
                     "User-Agent": _r.choice(_WEB_UAS)})
        status = 0
        try:
            with common.http_open(req) as r:
                raw = r.read().decode("utf-8", "replace")
                status = getattr(r, "status", 200) or 200
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            status = e.code
            if not _is_web_rate_limited(raw, status):
                raise
        if not _is_web_rate_limited(raw, status):
            return raw
        if attempt >= WEB_MAX_RETRIES:
            raise RuntimeError(
                "DeepL free endpoint is rate-limited. Add an API key "
                "for official access or try again later.")
        _t.sleep(WEB_BACKOFF)
    raise RuntimeError("unreachable")


def _web_translate_once(text: str, sl: str, tl: str) -> str:
    body = {"text": [text], "target_lang": _web_code(tl)}
    if sl and sl.upper() != "AUTO":
        body["source_lang"] = _web_code(sl)
    raw = _web_post(body)
    obj = parse_json_lenient(raw)
    translations = (obj or {}).get("translations") or []
    for t in translations:
        if isinstance(t, dict) and (t.get("text") or "").strip():
            return t["text"]
    raise ValueError("DeepL free endpoint returned no translated text")


def _web_translate(text: str, sl: str, tl: str) -> str:
    """translateWeb: chunk >5000 chars, join the per-chunk results."""
    return "".join(_web_translate_once(c, sl, tl)
                   for c in _split_for_web(text))


def _deepl_api_key() -> str:
    """General.DeeplApiKey -- the deepl-services plugin's apiKey
    secret; blank means the free web endpoint only."""
    try:
        from qtranslate import config as _C
        return str((_C.load() or {}).get("General", {})
                   .get("DeeplApiKey", "") or "")
    except Exception:
        return ""


def _official_code(code: str, source: bool = False) -> str:
    """DeepLTranslatorService.toDeepLCode/toDeepLSourceCode: uppercase
    tag, ZH -> ZH-HANS, and source-side Portuguese collapses to PT."""
    c = (code or "").upper()
    if c == "ZH":
        return "ZH-HANS"
    if source and c in ("PT-BR", "PT-PT", "PT"):
        return "PT"
    # DeepL's target_lang has no bare "EN" -- the regional variants are
    # required; EN-US is the API's default English target.
    if not source and c == "EN":
        return "EN-US"
    return c


def official_translate(text: str, sl: str, tl: str,
                       api_key: str) -> str:
    """POST api.deepl.com/v2/translate -- DeepLTranslatorService.
    translateOfficial's request/response shape."""
    body = {"text": [limit_source(text)],
            "target_lang": _official_code(tl)}
    if sl and sl.upper() != "AUTO":
        body["source_lang"] = _official_code(sl, source=True)
    req = urllib.request.Request(
        OFFICIAL_HOST + "/v2/translate?key=" + api_key,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with common.http_open(req) as r:
        obj = json.loads(r.read().decode("utf-8"))
    translations = obj.get("translations") or []
    if not translations:
        raise ValueError("no translation in official response")
    return translations[0].get("text") or ""


def translate(text: str, sl=1, tl=17) -> str:
    """plugins/deepl-services DeepLTranslatorService.translate.

    sl/tl are language indices (1 = auto), like the native which calls
    codeFromLanguage() on them. Plain codes are accepted too.

    plugins/deepl-services: a configured General.DeeplApiKey switches
    to the official API first; any failure (including auth rejection)
    falls back to the free web endpoint below.
    """
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    api_key = _deepl_api_key()
    if api_key:
        try:
            return official_translate(text, sl_code, tl_code, api_key)
        except Exception:
            pass
    # translateWeb -- the free oneshot endpoint (the legacy jsonrpc
    # jobs endpoint now returns an "update DeepL" wall).
    return _web_translate(text, sl_code, tl_code)
