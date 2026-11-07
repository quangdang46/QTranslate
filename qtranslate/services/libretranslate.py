"""LibreTranslate provider -- the .tmp Kotlin plugin's port.

Reference: .tmp/QTranslate/plugins/libretranslate-services
(LibreTranslateService.kt). Self-hosted (or public-instance) engine:
POST ``{instance}/translate`` with ``{q, source, target, api_key}``.
The Kotlin plugin defaults the instance to ``http://localhost:5000``
and reads its URL/key from plugin settings; the port reads the same
two values from ``General.LibreTranslateUrl`` /
``General.LibreTranslateApiKey`` in Options.json (no dedicated UI
yet -- set them by hand or through an extension).

LibreTranslate accepts ``source="auto"`` natively, so -- unlike
MyMemory -- an undetected source is passed through verbatim.
"""
from __future__ import annotations

import json
import urllib.request

from qtranslate import common
from qtranslate.common import code_from_language

DEFAULT_INSTANCE_URL = "http://localhost:5000"
MAX_BATCH = 50                # Kotlin maxBatchSize (single calls only here)

# App code -> LibreTranslate code where they differ.
_CODE_MAP = {
    "zh-CN": "zh",
    "zh-TW": "zt",
    "iw": "he",
}


def _settings():
    try:
        from qtranslate import config
        general = (config.load() or {}).get("General", {}) or {}
    except Exception:
        general = {}
    url = (general.get("LibreTranslateUrl") or "").strip().rstrip("/") \
        or DEFAULT_INSTANCE_URL
    key = (general.get("LibreTranslateApiKey") or "").strip()
    return url, key


def _lt_code(value):
    if isinstance(value, int):
        from qtranslate.services.google_translate import SUPPORTED_LANGS
        value = code_from_language(value, SUPPORTED_LANGS)
    if value in ("", None, -1):
        return "auto"
    return _CODE_MAP.get(value, value)


def translate(text, sl="auto", tl="en") -> str:
    """Port of LibreTranslateService.translate (single segment)."""
    url, key = _settings()
    body = {"q": text or "",
            "source": _lt_code(sl),
            "target": _lt_code(tl)}
    if key:
        body["api_key"] = key
    req = urllib.request.Request(
        url + "/translate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST")
    with common.http_open(req) as r:
        raw = r.read().decode("utf-8", errors="replace")
    try:
        obj = json.loads(raw)
    except Exception:
        obj = {}
    out = obj.get("translatedText")
    if isinstance(out, str) and out:
        return out
    detail = obj.get("error") or obj.get("message") or \
        "LibreTranslate did not return a translation."
    raise RuntimeError("LibreTranslate: %s" % detail)
