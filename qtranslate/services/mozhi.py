"""Mozhi translate provider -- the .tmp Kotlin plugin's port.

Reference: .tmp/QTranslate/plugins/mozhi-services
(MozhiTranslatorService.kt + MozhiPlugin.kt). Mozhi is a community
network of translation instances fronting upstream engines; the port
GETs ``{instance}/api/translate?engine=..&from=..&to=..&text=..``.

Settings mirror the Kotlin plugin's, read from Options.json
``General`` (no dedicated UI yet):

- ``MozhiInstanceUrl``  -- a public instance or a custom URL; the
  ``"Self-hosted"`` sentinel uses ``MozhiCustomInstanceUrl``.
- ``MozhiCustomInstanceUrl`` -- only consulted for Self-hosted.
- ``MozhiEngine``       -- one of Google/DeepL/DuckDuckGo/
  LibreTranslate/MyMemory/Reverso/Yandex (default Google).

Defaults match the Kotlin plugin: instance ``mozhi.adminforge.de``,
engine ``Google``.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from qtranslate import common
from qtranslate.common import code_from_language

PUBLIC_INSTANCES = (
    "https://mozhi.aryak.me",
    "https://translate.projectsegfau.lt",
    "https://translate.nerdvpn.de",
    "https://mozhi.ducks.party",
    "https://mozhi.pussthecat.org",
    "https://mozhi.adminforge.de",
    "https://translate.privacyredirect.com",
    "https://mozhi.canine.tools",
    "https://mzh.dc09.ru",
    "https://mozhi.franklyflawless.org",
)
# adminforge.de (the Kotlin plugin's default) answered HTTP 500 on
# 2026-11; pussthecat.org verified serving /api/translate the same day.
DEFAULT_INSTANCE_URL = "https://mozhi.pussthecat.org"
CUSTOM_INSTANCE = "Self-hosted"
DEFAULT_ENGINE = "Google"
SUPPORTED_ENGINES = {"Google", "DeepL", "DuckDuckGo", "LibreTranslate",
                     "MyMemory", "Reverso", "Yandex"}

_CODE_MAP = {"zh-CN": "zh-CN", "zh-TW": "zh-TW"}


def _settings():
    try:
        from qtranslate import config
        g = (config.load() or {}).get("General", {}) or {}
    except Exception:
        g = {}
    inst = (g.get("MozhiInstanceUrl") or "").strip()
    custom = (g.get("MozhiCustomInstanceUrl") or "").strip()
    if inst == CUSTOM_INSTANCE:
        url = custom or DEFAULT_INSTANCE_URL
    elif inst in PUBLIC_INSTANCES:
        url = inst
    elif inst:
        url = inst                      # unknown value: treat as URL
    else:
        url = DEFAULT_INSTANCE_URL
    engine = (g.get("MozhiEngine") or "").strip() or DEFAULT_ENGINE
    if engine not in SUPPORTED_ENGINES:
        engine = DEFAULT_ENGINE
    return url.rstrip("/"), engine


def _mozhi_code(value):
    """Kotlin toMozhiCode: zh variants keep their tags, rest pass."""
    if isinstance(value, int):
        from qtranslate.services.google_translate import SUPPORTED_LANGS
        value = code_from_language(value, SUPPORTED_LANGS)
    if value in ("", None, -1):
        return "auto"
    return _CODE_MAP.get(value, value)


def translate(text, sl="auto", tl="en") -> str:
    """Port of MozhiTranslatorService.translate (single segment)."""
    url, engine = _settings()
    q = urllib.parse.urlencode({
        "engine": engine.lower(),
        "from": _mozhi_code(sl),
        "to": _mozhi_code(tl),
        "text": text or "",
    })
    req = urllib.request.Request(
        url + "/api/translate?" + q,
        headers={"Accept": "application/json",
                 "User-Agent": "QTranslate/6.10"})
    with common.http_open(req) as r:
        raw = r.read().decode("utf-8", errors="replace")
    try:
        obj = json.loads(raw)
    except Exception:
        obj = {}
    out = obj.get("translated-text") or obj.get("translatedText") or ""
    if not str(out).strip():
        raise RuntimeError(
            "Mozhi's %s engine returned no translation. Try another "
            "engine or instance." % engine)
    return str(out)
