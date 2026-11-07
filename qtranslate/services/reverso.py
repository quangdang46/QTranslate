"""Reverso translate provider -- the .tmp Kotlin plugin's port.

Reference: .tmp/QTranslate/plugins/reverso-services
(ReversoTranslatorService.kt + ReversoClient.kt). POSTs JSON to
``https://cps.reverso.net/api2/TranslateText`` with the Chrome
extension's own request shape (``origin=chromeextension``, empty
``accessToken``) -- the free endpoint the Kotlin plugin reverse-
engineered. Direction is ``src-tgt`` in lowercase ISO codes.

Language set is exactly the Kotlin mapper's six (en/fr/de/es/it/ru);
AUTO is rejected like the Kotlin service's UnsupportedLanguageError --
the port resolves "auto" through registry.detect_language first and
raises when nothing concrete comes back, so the router moves on.
"""
from __future__ import annotations

import json
import time
import urllib.request

from qtranslate import common
from qtranslate.common import code_from_language

BASE_URL = "https://cps.reverso.net/api2/"
MIN_INTERVAL = 0.6            # Kotlin paces at 600 ms

# Kotlin ReversoLanguageMapper.languages, as app codes.
SUPPORTED = {"en", "fr", "de", "es", "it", "ru"}
SUPPORTED_LANGS = tuple(sorted(SUPPORTED))

_last_request_at = [0.0]


def _app_code(value):
    if isinstance(value, int):
        from qtranslate.services.google_translate import SUPPORTED_LANGS
        return code_from_language(value, SUPPORTED_LANGS)
    return value


def _source_code(text, sl):
    code = _app_code(sl)
    if code in ("", "auto", None, -1):
        try:
            from qtranslate import registry
            code = registry.detect_language(text) or "auto"
        except Exception:
            code = "auto"
    if code in ("", "auto", None, -1):
        raise RuntimeError(
            "Reverso Translation does not support automatic language "
            "detection.")
    return code


def _lang_code(code):
    """Kotlin: language.tag.substringBefore('-').lowercase()."""
    return str(code).split("-")[0].lower()


def translate(text, sl="auto", tl="en") -> str:
    sl_code = _source_code(text, sl)
    tl_code = _app_code(tl)
    if tl_code in ("", "auto", None, -1):
        raise RuntimeError("Reverso Translation requires a target "
                           "language.")
    if sl_code not in SUPPORTED or tl_code not in SUPPORTED:
        raise RuntimeError(
            "Reverso Translation does not support %s." % tl_code)
    direction = "%s-%s" % (_lang_code(sl_code), _lang_code(tl_code))

    wait = MIN_INTERVAL - (time.monotonic() - _last_request_at[0])
    if wait > 0:
        time.sleep(wait)
    body = json.dumps({
        "source": text or "",
        "direction": direction,
        "deviceId": "0",
        "uiLang": "en",
        "origin": "chromeextension",
        "accessToken": "",
        "appId": "0",
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "TranslateText", data=body,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": "QTranslate/6.10"},
        method="POST")
    with common.http_open(req) as r:
        raw = r.read().decode("utf-8", errors="replace")
    _last_request_at[0] = time.monotonic()
    try:
        obj = json.loads(raw)
    except Exception:
        obj = {}
    if obj.get("error") or not obj.get("success"):
        msg = obj.get("message") or "The service returned no result."
        low = msg.lower()
        if "too many" in low or "rate" in low:
            raise RuntimeError(
                "Reverso's free service is rate-limited. Try again "
                "later or choose another service.")
        raise RuntimeError(
            "Reverso's free service could not complete the request: "
            "%s" % msg)
    out = obj.get("translation") or ""
    if not out.strip():
        raise RuntimeError(
            "Reverso Translation returned no text. The free endpoint "
            "may have changed.")
    # The endpoint currently echoes the source for real requests
    # (verified 2026-11): success=true, translation==source. Returning
    # that verbatim would show the user their own text as the
    # "translation" -- fail instead so the router moves on.
    if (out.strip() == (text or "").strip()
            and len(out.strip()) > 3
            and _lang_code(sl_code) != _lang_code(tl_code)):
        raise RuntimeError(
            "Reverso's free endpoint echoed the source text; it may "
            "have changed.")
    return out
