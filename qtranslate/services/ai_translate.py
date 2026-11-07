"""AI Translate provider -- the .tmp ai-services plugin's port.

Reference: .tmp/QTranslate/plugins/ai-services
(AITranslatorService.kt + AIServiceClient.kt + AISettings.kt). Any
OpenAI-compatible ``/chat/completions`` endpoint works: OpenRouter
(default), OpenAI, Mistral, Gemini's OpenAI-compat path, local Ollama
/ LM Studio.

Settings live in Options.json ``General`` (no plugin-settings UI yet):

- ``AiBaseUrl``        default ``https://openrouter.ai/api/v1``
- ``AiApiKey``         bearer token; blank OK for local endpoints
- ``AiModel``          default ``openrouter/free``
- ``AiTemperature``    default 0.3
- ``AiMaxTokens``      default 4096
- ``AiCustomHeaders``  JSON object merged into every request

AUTO source uses the Kotlin two-step: one chat call that must return
``{"translation": ..., "detected_language": ...}``.
"""
from __future__ import annotations

import ipaddress
import json
import re
import urllib.request
from urllib.parse import urlparse

from qtranslate import common

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/free"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 4096
DEFAULT_CUSTOM_HEADERS = (
    '{"HTTP-Referer": "https://github.com/ahatem/QTranslate", '
    '"X-Title": "QTranslate", "X-OpenRouter-Title": "QTranslate"}')

# providers.build_adapters() reads SUPPORTED_LANGS for langs(); the AI
# endpoint takes any language, so the table is empty like Kotlin's
# SupportedLanguages.All.
SUPPORTED_LANGS = ()

_LANG_NAMES = {
    "auto": "Auto-detect", "en": "English", "vi": "Vietnamese",
    "fr": "French", "de": "German", "es": "Spanish", "it": "Italian",
    "pt": "Portuguese", "ru": "Russian", "ja": "Japanese",
    "ko": "Korean", "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)", "ar": "Arabic", "th": "Thai",
}


def _settings():
    try:
        from qtranslate import config
        g = (config.load() or {}).get("General", {}) or {}
    except Exception:
        g = {}
    return {
        "base_url": (g.get("AiBaseUrl") or "").strip()
        or DEFAULT_BASE_URL,
        "api_key": (g.get("AiApiKey") or "").strip(),
        "model": (g.get("AiModel") or "").strip() or DEFAULT_MODEL,
        "temperature": _float(g.get("AiTemperature"),
                               DEFAULT_TEMPERATURE),
        "max_tokens": _int(g.get("AiMaxTokens"), DEFAULT_MAX_TOKENS),
        "custom_headers": (g.get("AiCustomHeaders")
                           or DEFAULT_CUSTOM_HEADERS),
    }


def _float(v, d):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _int(v, d):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _is_local_endpoint(base_url):
    """Kotlin isLocalEndpoint: localhost/.local/RFC1918 counts as local
    (no API key needed)."""
    try:
        host = (urlparse(base_url.strip()).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    if host in ("localhost", "::1") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        pass
    return (host.startswith("127.") or host.startswith("10.")
            or host.startswith("192.168.")
            or bool(re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host)))


def _missing_key_error(s):
    if not s["api_key"] and not _is_local_endpoint(s["base_url"]):
        raise RuntimeError(
            "No API key set for %s. Add one in Options.json "
            "General.AiApiKey, or point AiBaseUrl at a local server "
            "such as Ollama, which needs no key."
            % s["base_url"])


def _display_name(code):
    if code == "auto":
        return "Auto-detect"
    return _LANG_NAMES.get(code, code or "Auto-detect")


def _app_code(value):
    from qtranslate.common import code_from_language
    if isinstance(value, int):
        from qtranslate.services.google_translate import SUPPORTED_LANGS
        return code_from_language(value, SUPPORTED_LANGS)
    return value


def _complete(system, user_content, s=None):
    """Port of AIServiceClient.complete."""
    s = s or _settings()
    _missing_key_error(s)
    endpoint = s["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json",
               "Accept": "application/json"}
    if s["api_key"]:
        headers["Authorization"] = "Bearer " + s["api_key"]
    if s["custom_headers"] and s["custom_headers"].strip():
        try:
            extra = json.loads(s["custom_headers"])
            if isinstance(extra, dict):
                headers.update({str(k): str(v)
                                for k, v in extra.items()})
        except Exception:
            pass
    body = json.dumps({
        "model": s["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": s["temperature"],
        "max_completion_tokens": s["max_tokens"],
        # OpenRouter prefers max_tokens on some models; send both like
        # tolerant clients do? Kotlin sends only maxCompletionTokens.
    }).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, headers=headers,
                                 method="POST")
    with common.http_open(req) as r:
        raw = r.read().decode("utf-8", errors="replace")
    try:
        obj = json.loads(raw)
    except Exception:
        raise RuntimeError("AI service returned a non-JSON response.")
    err = obj.get("error")
    if err:
        msg = err.get("message") if isinstance(err, dict) else str(err)
        low = (msg or "").lower()
        if any(t in low for t in ("api key", "invalid key",
                                  "unauthorized", "authentication")):
            raise RuntimeError("AI service authentication failed: %s"
                               % msg)
        if any(t in low for t in ("rate limit", "quota",
                                  "too many requests")):
            raise RuntimeError("AI service rate limit: %s" % msg)
        raise RuntimeError("AI service error: %s" % (msg or "unknown"))
    choices = obj.get("choices") or []
    if not choices:
        raise RuntimeError(
            "AI service returned an empty response (no choices).")
    content = ((choices[0].get("message") or {}).get("content")) or ""
    if isinstance(content, list):          # some endpoints return parts
        content = "".join(str(p.get("text", ""))
                          for p in content if isinstance(p, dict))
    if not str(content).strip():
        raise RuntimeError(
            "AI service returned an empty response (no choices).")
    return str(content)


def _parse_auto(raw):
    """Port of parseAutoDetectResponse: strip fences, take the JSON
    object, return (translation, detected_language)."""
    clean = raw.strip()
    for fence in ("```json", "```"):
        if clean.startswith(fence):
            clean = clean[len(fence):]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()
    try:
        obj = json.loads(clean)
    except Exception:
        # Model may wrap the JSON in prose; take the outermost braces.
        i, j = clean.find("{"), clean.rfind("}")
        if i >= 0 and j > i:
            try:
                obj = json.loads(clean[i:j + 1])
            except Exception:
                obj = None
        else:
            obj = None
    if not isinstance(obj, dict) or not obj.get("translation"):
        raise RuntimeError(
            "AI service did not return the expected JSON "
            "(translation/detected_language).")
    return str(obj["translation"]).strip(), \
        str(obj.get("detected_language") or "")


def translate(text, sl="auto", tl="en") -> str:
    """Port of AITranslatorService.translate."""
    s = _settings()
    sl_code = _app_code(sl)
    tl_code = _app_code(tl)
    if tl_code in ("", None, -1):
        raise RuntimeError("AI Translate requires a target language.")
    if sl_code in ("", "auto", None, -1):
        # translateWithAutoDetect
        target_name = _display_name(tl_code)
        system = (
            "You are a professional translator.\n"
            "Your task: Detect the source language and translate the "
            "text into %s.\n\n"
            "Strict Rule: You must output ONLY a valid JSON object. "
            "No markdown formatting.\n\n"
            "Schema:\n"
            '{\n  "translation": "translated text here",\n'
            '  "detected_language": "BCP-47 tag of source"\n}\n\n'
            "Preserve formatting, line breaks, and punctuation."
            % target_name)
        raw = _complete(system, text or "", s)
        out, _detected = _parse_auto(raw)
        return out
    # translateDirect
    source = _display_name(sl_code)
    target = _display_name(tl_code)
    system = (
        "You are a professional translator.\n"
        "Translate the user's text from %s to %s.\n"
        "Output ONLY the translated text — no labels, no explanations, "
        "no quotes.\n"
        "Preserve the original formatting and line breaks."
        % (source, target))
    return _complete(system, text or "", s).strip()
