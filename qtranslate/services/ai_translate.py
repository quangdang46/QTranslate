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
    return _chat_content(raw)


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


# ---------------------------------------------------------------------
# The other ai-services roles (.tmp AIPlugin registers six services off
# one AIServiceClient): vision OCR, spell checker, dictionary,
# summarizer, rewriter. The port shares ``_complete`` /
# ``_complete_with_image`` the same way -- one settings block, one
# chat-completions path.
# ---------------------------------------------------------------------

def _complete_with_image(system, user_text, image_bytes, s=None):
    """Port of AIServiceClient.completeWithImage: base64 data-URI image
    part + optional text part in the user turn."""
    import base64
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
    fmt = _image_format(image_bytes)
    mime = "image/" + fmt
    data_uri = "data:%s;base64,%s" % (
        mime, base64.b64encode(image_bytes).decode("ascii"))
    parts = [{"type": "image_url",
              "image_url": {"url": data_uri}}]
    if (user_text or "").strip():
        parts.append({"type": "text", "text": user_text})
    body = json.dumps({
        "model": s["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": parts},
        ],
        "temperature": s["temperature"],
        "max_completion_tokens": s["max_tokens"],
    }).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, headers=headers,
                                 method="POST")
    with common.http_open(req) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return _chat_content(raw)


def _image_format(image_bytes):
    """png/jpeg/webp sniff for the data-URI mime type."""
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    return "png"


def _chat_content(raw):
    """Shared tail of _complete/_complete_with_image: parse the
    chat-completions envelope, surface provider errors, return the
    first choice's text."""
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
    if isinstance(content, list):
        content = "".join(str(p.get("text", ""))
                          for p in content if isinstance(p, dict))
    if not str(content).strip():
        raise RuntimeError(
            "AI service returned an empty response (no choices).")
    return str(content)


def _json_from_model(raw):
    """Strip markdown fences / surrounding prose, parse the JSON object
    the AI services demand (AIDictionaryService.parseDictionaryResponse
    and siblings all do this)."""
    clean = raw.strip()
    for fence in ("```json", "```"):
        if clean.startswith(fence):
            clean = clean[len(fence):]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()
    obj = None
    try:
        obj = json.loads(clean)
    except Exception:
        i, j = clean.find("{"), clean.rfind("}")
        if i >= 0 and j > i:
            try:
                obj = json.loads(clean[i:j + 1])
            except Exception:
                obj = None
    if not isinstance(obj, dict):
        raise RuntimeError(
            "AI service did not return the expected JSON object.")
    return obj


# ocr.space 3-letter codes -> English names for the vision prompt hint
# (AIVisionOcrService.buildLanguageHint uses Locale display names).
_OCR_LANG_NAMES = {
    "eng": "English", "vie": "Vietnamese", "fra": "French",
    "deu": "German", "spa": "Spanish", "ita": "Italian",
    "por": "Portuguese", "rus": "Russian", "jpn": "Japanese",
    "kor": "Korean", "zho": "Chinese", "ara": "Arabic",
    "hin": "Hindi", "tha": "Thai", "nld": "Dutch", "pol": "Polish",
    "tur": "Turkish", "ukr": "Ukrainian", "ces": "Czech",
    "swe": "Swedish", "dan": "Danish", "fin": "Finnish",
    "nor": "Norwegian", "ron": "Romanian", "hun": "Hungarian",
}


def vision_ocr(image_bytes, lang="eng"):
    """Port of AIVisionOcrService.extractText. ``lang`` is the app's
    OCR code; the prompt gets an English hint like upstream. Returns
    ``{"text": ..., "detected_language": ...}``; raises when the AI
    endpoint is unconfigured so callers can fall through."""
    hint = ""
    name = _OCR_LANG_NAMES.get(lang)
    if name:
        hint = ("The image is expected to contain text in %s — use "
                "this as a hint to improve recognition accuracy."
                % name)
    system = (
        "You are a precise OCR engine.\n"
        "Extract ALL text visible in the image exactly as it appears.\n"
        "%s\n"
        "You MUST respond with a single valid JSON object and NOTHING "
        "else. No markdown wrapping.\n\n"
        "Schema:\n"
        '{\n  "text": "full extracted text preserving line breaks '
        'with \\n",\n'
        '  "detected_language": "BCP-47 tag of the primary language '
        'in the image, or null if uncertain"\n}\n\n'
        "Rules:\n"
        "- Preserve the original text layout using line breaks (\\n) "
        "where appropriate.\n"
        "- Do NOT correct spelling errors — extract exactly what is "
        "written.\n"
        "- Do NOT add explanations, translations, or any text not "
        "present in the image.\n"
        "- If no text is found, return {\"text\": \"\", "
        "\"detected_language\": null}.\n"
        "- If the image contains text in multiple languages, set "
        "detected_language to the dominant one." % hint)
    raw = _complete_with_image(system, "Extract all text from this "
                               "image.", image_bytes)
    obj = _json_from_model(raw)
    return {"text": str(obj.get("text") or ""),
            "detected_language": obj.get("detected_language")}


def spell_check(text, lang=""):
    """Port of AISpellCheckerService.check. Returns the same shape the
    app's correction flow consumes (bing_spell/system_spell):
    ``{"correctedText", "corrections": [{original, startIndex,
    endIndex, suggestions, type, message}]}`` with UTF-16 offsets like
    every other backend."""
    if not (text or "").strip():
        return {"correctedText": text or "", "corrections": []}
    if lang and lang != "auto":
        lang_instruction = (
            "The text is written in %s (BCP-47: '%s'). Use grammar "
            "and spelling rules specific to this language."
            % (_display_name(lang), lang))
    else:
        lang_instruction = "Detect the language of the text automatically."
    system = (
        "You are a precise spell-checking and grammar assistant.\n\n"
        "Instruction:\n%s\n\n"
        "Analyze the user's text for spelling, grammar, style, and "
        "punctuation errors.\n"
        "You MUST respond with a single valid JSON object and NOTHING "
        "else. No markdown wrapping.\n\n"
        "Schema:\n"
        "{\n"
        '  "corrected_text": "full text with corrections applied",\n'
        '  "corrections": [\n'
        "    {\n"
        '      "original": "incorrect span",\n'
        '      "corrected": "replacement",\n'
        '      "start_index": 0,\n'
        '      "end_index": 5,\n'
        '      "type": "SPELLING",\n'
        '      "message": "explanation"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Note: If no errors are found, return an empty array for "
        "'corrections' and the original text for 'corrected_text'.\n"
        "IMPORTANT: 'start_index' and 'end_index' must reference the "
        "character offsets in the ORIGINAL input string."
        % lang_instruction)
    raw = _complete(system, text or "")
    obj = _json_from_model(raw)
    n = len(text)
    corrections = []
    for item in obj.get("corrections") or []:
        if not isinstance(item, dict):
            continue
        try:
            start = max(0, min(int(item.get("start_index") or 0), n))
            end = max(start + 1,
                      min(int(item.get("end_index") or start + 1), n))
        except (TypeError, ValueError):
            continue
        t = str(item.get("type") or "SPELLING").upper()
        corrections.append({
            "original": str(item.get("original") or ""),
            "startIndex": start,
            "endIndex": end,
            "suggestions": [str(item.get("corrected") or "")],
            "type": t if t in ("SPELLING", "GRAMMAR", "STYLE",
                               "PUNCTUATION") else "SPELLING",
            "message": item.get("message"),
        })
    return {"correctedText": str(obj.get("corrected_text") or text),
            "corrections": corrections}


def dict_lookup(word, lang="", target=""):
    """Port of AIDictionaryService.lookup. ``lang`` is the dictionary
    source language; the Kotlin prompt names it via Locale display
    name -- ``_display_name`` covers the common codes and falls back
    to the raw tag like upstream's ``ifBlank { tag }``."""
    language_name = _display_name(lang or "en")
    system = (
        "You are a professional dictionary.\n"
        "Look up the word or phrase provided by the user in %s.\n\n"
        "You MUST respond with a single valid JSON object and NOTHING "
        "else. No markdown wrapping.\n\n"
        "Schema:\n"
        "{\n"
        '  "entries": [\n'
        "    {\n"
        '      "word": "canonical/base form of the word",\n'
        '      "part_of_speech": "noun | verb | adjective | adverb | '
        'pronoun | preposition | conjunction | interjection | phrase",\n'
        '      "phonetic": "/fəˈnɛtɪk/ in IPA notation, or null",\n'
        '      "definitions": [\n'
        "        {\n"
        '          "text": "clear definition in %s",\n'
        '          "example": "a natural usage example sentence, or '
        'null"\n'
        "        }\n"
        "      ],\n"
        '      "synonyms": ["synonym1", "synonym2"]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Provide up to 3 entries for distinct senses or parts of "
        "speech.\n"
        "- Each entry should have 1–3 definitions.\n"
        "- Synonyms list may be empty if none apply.\n"
        "- If the word is not found or is not a real word, return "
        "{\"entries\": []}.\n"
        "- Do NOT include antonyms, translations, or any fields not in "
        "the schema." % (language_name, language_name))
    raw = _complete(system, word or "")
    obj = _json_from_model(raw)
    return _dict_entries_html(obj.get("entries") or [])


def _dict_entries_html(entries):
    """Render the AI dictionary JSON into the HTML fragment the
    DICT_EXT contract returns (cards wrap it verbatim)."""
    import html as _h
    if not entries:
        return ""
    out = []
    for e in entries[:3]:
        if not isinstance(e, dict):
            continue
        word = _h.escape(str(e.get("word") or ""))
        pos = _h.escape(str(e.get("part_of_speech") or ""))
        phon = e.get("phonetic")
        head = "<b>%s</b>" % word
        if pos:
            head += " <i>(%s)</i>" % pos
        if phon:
            head += " <span class='qt-phon'>%s</span>" % _h.escape(
                str(phon))
        out.append("<div class='qt-ai-entry'>%s<ul>" % head)
        for d in (e.get("definitions") or [])[:3]:
            if not isinstance(d, dict):
                continue
            txt = _h.escape(str(d.get("text") or ""))
            ex = d.get("example")
            item = "<li>%s" % txt
            if ex:
                item += " <i>— %s</i>" % _h.escape(str(ex))
            out.append(item + "</li>")
        out.append("</ul>")
        syn = [str(x) for x in (e.get("synonyms") or []) if x]
        if syn:
            out.append("<div class='qt-ai-syn'><i>Synonyms:</i> %s</div>"
                       % _h.escape(", ".join(syn[:8])))
        out.append("</div>")
    return "\n".join(out)


def summarize(text, length="MEDIUM"):
    """Port of AISummarizerService.summarize (SummaryLength option:
    SHORT / MEDIUM(default) / LONG)."""
    instruction = {
        "SHORT": "Respond with a single sentence of no more than "
                 "30 words.",
        "LONG": "Respond with a detailed multi-paragraph summary "
                "that preserves important nuance.",
    }.get(str(length or "").upper(),
          "Respond with 2–4 concise sentences that capture the key "
          "points.")
    system = (
        "You are a professional editor. \n\n"
        "TASK:\n"
        "Summarize the text provided by the user. \n"
        "The summary MUST be written in the same language as the "
        "source text itself.\n\n"
        "CONSTRAINTS:\n"
        "- %s\n"
        "- Output ONLY the summarized text.\n"
        "- Do not include any introductory text, labels, quotes, or "
        "conversational filler (e.g., do NOT say \"Here is a "
        "summary\").\n\n"
        "The user's text to be summarized starts after the '---' "
        "delimiter below.\n---" % instruction)
    return _complete(system, text or "").strip().strip('"')


def rewrite(text, style="FORMAL"):
    """Port of AIRewriterService.rewrite (RewriteStyle option:
    FORMAL(default) / CASUAL / CONCISE / DETAILED / SIMPLIFIED)."""
    instruction = {
        "CASUAL": "Rewrite in a natural, conversational tone. Use "
                  "everyday language as if speaking to a friend.",
        "CONCISE": "Rewrite as briefly as possible. Remove all "
                   "filler words, redundancy, and unnecessary detail.",
        "DETAILED": "Rewrite in an expanded, thorough form. Add "
                    "relevant context and elaborate on key points.",
        "SIMPLIFIED": "Rewrite using plain, simple language suitable "
                      "for a general audience. Avoid jargon.",
    }.get(str(style or "").upper(),
          "Rewrite in a formal, professional tone. Use precise "
          "vocabulary and complete sentences. Remove slang and "
          "colloquialisms.")
    system = (
        "You are a professional writing assistant.\n\n"
        "TASK:\n%s\n\n"
        "RULES:\n"
        "1. Respond in the EXACT SAME LANGUAGE as the source text.\n"
        "2. Output ONLY the rewritten text. \n"
        "3. Do NOT include any preamble, labels, or introductory "
        "phrases (e.g., do not say \"Here is the rewritten text\").\n"
        "4. Preserve the original paragraph structure and line "
        "breaks.\n\n"
        "The text to rewrite begins after the '---' delimiter "
        "below.\n---" % instruction)
    return _complete(system, text or "").strip().strip('"')
