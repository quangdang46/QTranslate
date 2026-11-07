"""Yandex Web translator -- the .tmp ``yandex-web-services`` plugin port.

Reference: .tmp/QTranslate/plugins/yandex-web-services
(YandexWebClient.kt, YandexWebTranslatorService.kt,
YandexWebLanguageMapper.kt). Free unofficial endpoint
``api.browser.yandex.com/instaserp/translate`` -- the same form POST
Chromium's YaBrowser issues (``brandID=int``, ``statLang``/``locale`` =
target, ``targetLang=auto``: the endpoint auto-detects the SOURCE, which
is why the Kotlin form carries no source field). Responses are a JSON
array whose first element is ``{text, from, to}``.

On an InvalidResponse/ServiceUnavailable-class failure the Kotlin
client retries through privacy-preserving Mozhi instances
(``mozhi.adminforge.de``, ``mozhi.pussthecat.org``) before giving up;
requests are paced at 750 ms like the Kotlin mutex.

No service id: joins TRANSLATORS after the native ServicesOrder entries
(registry.router_order's append rule), like the other plugin ports.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from qtranslate import common

ENDPOINT = "https://api.browser.yandex.com/instaserp/translate"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36"),
}
MOZHI_FALLBACKS = [
    "https://mozhi.adminforge.de",
    "https://mozhi.pussthecat.org",
]
MAX_TEXT_LENGTH = 5000          # Kotlin MAX_TEXT_LENGTH
MIN_INTERVAL = 0.75             # Kotlin minimumIntervalMillis

# Provider (BCP-47-ish) codes, verbatim from YandexWebLanguageMapper.
_PROVIDER_CODES = {
    "af", "az", "sq", "ar", "hy", "eu", "be", "bg", "ca", "zh", "hr",
    "cs", "da", "nl", "en", "et", "fi", "fr", "gl", "de", "el", "ht",
    "he", "hi", "hu", "is", "id", "it", "ga", "ja", "ka", "ko", "lv",
    "lt", "mk", "ms", "mt", "no", "fa", "pl", "pt", "ro", "ru", "sr",
    "sk", "sl", "es", "sw", "sv", "th", "tr", "uk", "ur", "vi", "cy",
    "yi", "eo", "la", "lo", "kk", "uz", "si", "tg", "te", "km", "mn",
    "kn", "ta", "mr", "bn", "tt",
}

# App vocabulary -> provider code. The app's Hebrew code is "iw" (Google
# table) and Chinese is split zh-CN/zh-TW; Yandex takes "he" and one
# "zh" for both (Kotlin: CHINESE_* -> "zh").
_TO_PROVIDER = {"iw": "he", "zh-CN": "zh", "zh-TW": "zh"}
_FROM_PROVIDER = {"he": "iw", "zh": "zh-CN"}

# App codes this service supports = provider codes translated into the
# app's vocabulary (he->iw, zh->zh-CN/zh-TW; both Chinese variants share
# the single provider "zh").
APP_SUPPORTED = tuple(sorted(
    {_FROM_PROVIDER.get(c, c) for c in _PROVIDER_CODES} | {"zh-TW"}))
# providers.build_adapters() reads SUPPORTED_LANGS for langs().
SUPPORTED_LANGS = APP_SUPPORTED

_last_request_at = [0.0]


def _pace():
    wait = MIN_INTERVAL - (time.monotonic() - _last_request_at[0])
    if wait > 0:
        time.sleep(wait)


def _app_code(value):
    """Resolve an int index or a code to an app language code."""
    if isinstance(value, int):
        try:
            from qtranslate.services.google_translate import SUPPORTED_LANGS
            return SUPPORTED_LANGS[value]
        except Exception:
            return ""
    return value or ""


def _to_provider(code):
    return _TO_PROVIDER.get(code, code)


def _form(text, target):
    return urllib.parse.urlencode({
        "text": text,
        "brandID": "int",
        "statLang": target,
        "targetLang": "auto",
        "locale": target,
        "clid": "2270494",
        "disable": "serp",
        "use_llm_srv": "0",
    })


def _post(url, data):
    req = urllib.request.Request(url, data=data.encode("utf-8"),
                                 headers=HEADERS, method="POST")
    with common.http_open(req) as r:
        return r.read().decode("utf-8", errors="replace")


def _parse(body):
    """Kotlin parseResponse: first array element with non-blank text."""
    try:
        arr = json.loads(body)
    except Exception:
        arr = None
    if isinstance(arr, list):
        for item in arr:
            if isinstance(item, dict) and str(
                    item.get("text") or "").strip():
                return str(item["text"]).strip()
    elif isinstance(arr, dict) and str(arr.get("text") or "").strip():
        return str(arr["text"]).strip()
    return ""


def _via_mozhi(text, target):
    """Kotlin translateViaMozhi: try each fallback instance in order."""
    for base in MOZHI_FALLBACKS:
        try:
            q = urllib.parse.urlencode({
                "engine": "yandex", "from": "auto", "to": target,
                "text": text})
            req = urllib.request.Request(
                base + "/api/translate?" + q,
                headers={"Accept": "application/json",
                         "User-Agent": HEADERS["User-Agent"]})
            with common.http_open(req) as r:
                obj = json.loads(r.read().decode("utf-8", "replace"))
            out = str(obj.get("translated-text") or "").strip()
            if out:
                return out
        except Exception:
            continue
    raise RuntimeError(
        "Yandex Web and its privacy-preserving fallback instances are "
        "unavailable. Try again later.")


def translate(text, sl="auto", tl="en") -> str:
    """Port of YandexWebTranslatorService.translate."""
    text = text or ""
    if len(text) > MAX_TEXT_LENGTH:
        raise RuntimeError(
            "Yandex Web accepts up to %d characters per request."
            % MAX_TEXT_LENGTH)
    tl_code = _app_code(tl)
    if tl_code in ("", "auto", None, -1):
        raise RuntimeError("Yandex Web requires a target language.")
    provider_tl = _to_provider(tl_code)
    if provider_tl not in _PROVIDER_CODES:
        raise RuntimeError(
            "Yandex Web does not support language '%s'." % tl_code)
    sl_code = _app_code(sl)
    if sl_code not in ("", "auto", None, -1):
        # The Kotlin service validates the source against its table too;
        # the endpoint itself always auto-detects, so an unsupported
        # source still translates -- but fail explicitly like the plugin.
        if _to_provider(sl_code) not in _PROVIDER_CODES:
            raise RuntimeError(
                "Yandex Web does not support language '%s'." % sl_code)
    _pace()
    try:
        out = _parse(_post(ENDPOINT, _form(text, provider_tl)))
    except urllib.error.HTTPError as exc:
        # Kotlin retries via Mozhi on ServiceUnavailable-class errors
        # (5xx); 4xx transport errors surface unchanged.
        _last_request_at[0] = time.monotonic()
        if exc.code >= 500:
            return _via_mozhi(text, provider_tl)
        raise RuntimeError(
            "Yandex Web rejected the request (HTTP %d). The unofficial "
            "free endpoint may have changed or may be temporarily "
            "blocking requests." % exc.code)
    except Exception as exc:
        _last_request_at[0] = time.monotonic()
        raise RuntimeError(
            "Yandex Web is unavailable. This unofficial free endpoint "
            "may have changed; try again later.") from exc
    finally:
        _last_request_at[0] = time.monotonic()
    if not out:
        # InvalidResponse-class failure -> Mozhi fallback.
        return _via_mozhi(text, provider_tl)
    return out
