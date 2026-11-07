"""MyMemory translate provider -- the .tmp Kotlin plugin's port.

Reference: .tmp/QTranslate/plugins/mymemory-services
(MyMemoryTranslatorService.kt). The free endpoint is
``api.mymemory.translated.net/get`` with ``langpair=SRC|TGT``; ``mt=1``
asks for the machine-translation path. Like the Kotlin service this
provider REQUIRES a concrete source language -- MyMemory has no auto
-- so an ``"auto"`` source is resolved through the app's own detect
chain first and an undetectable source raises (the router then moves
to the next provider, exactly as the Kotlin service's
UnsupportedLanguageError does).

No service id: like an extension-registered provider it joins the
strip and the fallback chain after the native ServicesOrder entries
(registry.router_order's TRANSLATORS-append rule).
"""
from __future__ import annotations

import html
import json
import time
import urllib.parse
import urllib.request

from qtranslate import common
from qtranslate.common import code_from_language

ENDPOINT = "https://api.mymemory.translated.net/get"
MAX_QUERY_BYTES = 500          # Kotlin: Utf8Segmenter.split(text, 500)
MIN_INTERVAL = 0.35            # Kotlin paces requests at 350 ms

# App language code -> MyMemory langpair code. MyMemory takes ISO-ish
# tags but splits Portuguese and Chinese; the app's "pt" is ambiguous,
# so it maps to the Brazilian variant, and Hebrew's app code "iw"
# becomes MyMemory's "he".
_CODE_MAP = {
    "iw": "he",
    "pt": "pt-BR",
}

# The Kotlin plugin's SUPPORTED_LANGUAGES, expressed in the MAPPED
# langpair codes (after _CODE_MAP): "pt" arrives as "pt-BR" and "iw"
# as "he", so the set names what the endpoint actually sees.
SUPPORTED = {
    "en", "ar", "es", "fr", "de", "it", "pt-BR", "ru", "zh-CN",
    "zh-TW", "ja", "ko", "hi", "bn", "id", "ur", "tr", "vi", "nl",
    "el", "he", "pl", "uk", "cs", "sv", "ro", "da", "fi", "bg", "no",
    "sk", "sl", "ca", "sr", "hr", "ms", "th", "fa", "af", "sq", "hy",
    "az", "eu", "be", "bs", "et", "ka", "hu", "is", "ga", "lv", "lt",
    "mk",
}

# providers.build_adapters() reads SUPPORTED_LANGS for langs().
SUPPORTED_LANGS = tuple(sorted(SUPPORTED))

_last_request_at = [0.0]


def _app_langs():
    from qtranslate.services.google_translate import SUPPORTED_LANGS
    return SUPPORTED_LANGS


def _app_code(value):
    """Resolve an int index or a code to an app language code."""
    if isinstance(value, int):
        return code_from_language(value, _app_langs())
    return value


def _source_code(text, sl):
    """A concrete source code, or raise like the Kotlin AUTO error."""
    code = _app_code(sl)
    if code in ("", "auto", None, -1):
        try:
            from qtranslate import registry
            code = registry.detect_language(text) or "auto"
        except Exception:
            code = "auto"
    if code in ("", "auto", None, -1):
        raise RuntimeError(
            "MyMemory requires a source language; automatic detection "
            "is not available.")
    return code


def _paragraph_break(text: str) -> bool:
    """Kotlin containsParagraphBreak: "\\n\\n" or "\\r\\n\\r\\n"."""
    return "\n\n" in text or "\r\n\r\n" in text


def _segments(text: str):
    """Kotlin Utf8Segmenter.split(text, 500).

    Two rules, both byte-exact: a text that fits in 500 UTF-8 bytes AND
    has no paragraph break stays ONE request; otherwise the text is cut
    at code-point boundaries on the byte budget AND flushed right after
    every ``\\n\\n`` paragraph break -- so "First.\\n\\nSecond." is two
    requests even though it fits. Segments concatenate back to the
    input losslessly (the ``\\n\\n`` stays at the end of its segment).
    """
    text = text or ""
    if len(text.encode("utf-8")) <= MAX_QUERY_BYTES \
            and not _paragraph_break(text):
        return [text]
    out, cur, size = [], "", 0
    for ch in text:
        n = len(ch.encode("utf-8"))
        if cur and size + n > MAX_QUERY_BYTES:
            out.append(cur)
            cur, size = "", 0
        cur += ch
        size += n
        if cur.endswith("\n\n"):
            out.append(cur)
            cur, size = "", 0
    if cur:
        out.append(cur)
    return out or [""]


def _pace():
    wait = MIN_INTERVAL - (time.monotonic() - _last_request_at[0])
    if wait > 0:
        time.sleep(wait)


def _translate_segment(text, sl_code, tl_code):
    _pace()
    q = urllib.parse.urlencode(
        {"q": text, "langpair": "%s|%s" % (sl_code, tl_code), "mt": 1})
    req = urllib.request.Request(
        ENDPOINT + "?" + q,
        headers={"User-Agent": "QTranslate/6.10",
                 "Accept": "application/json"})
    with common.http_open(req) as r:
        body = r.read().decode("utf-8", errors="replace")
    _last_request_at[0] = time.monotonic()
    try:
        obj = json.loads(body)
    except Exception:
        obj = {}
    data = obj.get("responseData") or {}
    out = data.get("translatedText") or ""
    status = obj.get("responseStatus") or 0
    if 200 <= status < 300 and out.strip():
        # MyMemory HTML-escapes the translated text (Kotlin unescapes).
        return html.unescape(out)
    details = obj.get("responseDetails") or \
        "The provider did not return a translation."
    if obj.get("quotaFinished") or status == 429:
        raise RuntimeError(
            "MyMemory's free request limit has been reached. Try again "
            "later or choose another service.")
    if status >= 500:
        raise RuntimeError(
            "MyMemory's free endpoint is temporarily unavailable. "
            "Try again later.")
    raise RuntimeError("MyMemory could not translate this text: %s"
                       % details)


def translate(text, sl="auto", tl="en") -> str:
    """Port of MyMemoryTranslatorService.translate."""
    sl_app = _source_code(text, sl)
    sl_code = _CODE_MAP.get(sl_app, sl_app)
    tl_code = _app_code(tl)
    if tl_code in ("", "auto", None, -1):
        raise RuntimeError("MyMemory requires a target language.")
    tl_code = _CODE_MAP.get(tl_code, tl_code)
    if sl_code not in SUPPORTED or tl_code not in SUPPORTED:
        raise RuntimeError(
            "MyMemory does not support this language pair.")
    return "".join(_translate_segment(seg, sl_code, tl_code)
                   for seg in _segments(text or ""))
