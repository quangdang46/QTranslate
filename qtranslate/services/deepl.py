"""1:1 port of Services/DeepL/Service.js (SERVICE_ID=31).

Covers the whole file: serviceHeader/Host/Link, parseText/splitText,
getSourceLanguage, detect request/response (LMT_split_into_sentences),
translate request/response (LMT_handle_jobs), SupportedLanguages.
Live verified 2026-10-07.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

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
    prepare_source,
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
    -1, -1, -1, -1, -1,
]

_SPLIT_RE = re.compile(r"^\s+|(?:\s*\n)+\s*|[.!?\":;।](?:\s+)|\s+$")
_SENT_END_RE = re.compile(r"[.!?\":;।](?:\s+)")


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


def parse_text(text: str) -> list[dict]:
    """Port of parseText(a): type-1 sentences / type-0 separators."""
    parts: list[dict] = []
    text = limit_source(prepare_source(text))
    pos = 0
    for match in _SPLIT_RE.finditer(text):
        frag = match.group(0)
        sentence_end = bool(_SENT_END_RE.fullmatch(frag))
        if match.start() > pos:
            chunk = text[pos:match.start() + (1 if sentence_end else 0)]
            parts.append({"type": 1, "text": chunk})
            pos += len(chunk)
        parts.append({"type": 0, "text": frag[1:] if sentence_end else frag})
        pos += len(frag) - (1 if sentence_end else 0)
    if pos < len(text):
        parts.append({"type": 1, "text": text[pos:]})
    return parts


def split_text(text: str) -> list[str]:
    """Port of splitText(a): sentence strings sent as jobs."""
    return [
        re.sub(r"\s+", " ", p["text"])
        for p in parse_text(text)
        if p["type"] == 1
    ]


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
    with urllib.request.urlopen(req, timeout=20) as resp:
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


def translate(text: str, sl=1, tl=17) -> str:
    """Port of serviceTranslateRequest/Response (LMT_handle_jobs).

    sl/tl are language indices (1 = auto), like the native which calls
    codeFromLanguage() on them. Plain codes are accepted too.
    """
    sl_code = code_from_language(sl, SUPPORTED_LANGS) \
        if isinstance(sl, int) else sl
    tl_code = code_from_language(tl, SUPPORTED_LANGS) \
        if isinstance(tl, int) else tl
    sentences = split_text(text)
    jobs = [{"kind": "default", "raw_en_sentence": s} for s in sentences]
    count = 1
    for job in jobs:
        count += len(re.findall(r"[i]", job["raw_en_sentence"] or ""))
    now = int(time.time() * 1000)
    preferred = [sl_code if (isinstance(sl, int)
                             and is_language(sl, SUPPORTED_LANGS))
                 else "EN", tl_code]
    payload = {
        "id": 2,
        "jsonrpc": "2.0",
        "method": "LMT_handle_jobs",
        "params": {
            "jobs": jobs,
            "lang": {
                "user_preferred_langs": preferred,
                "source_lang_user_selected": sl_code,
                "target_lang": tl_code,
            },
            "priority": 1,
            "timestamp": now + (count - now % count),
        },
    }
    obj = _post_jsonrpc(payload)
    beams = []
    try:
        for t in obj["result"]["translations"]:
            beams.append(t["beams"][0]["postprocessed_sentence"]
                         if t.get("beams") else "")
    except (KeyError, TypeError, IndexError):
        pass
    out = ""
    queue = list(beams)
    for part in parse_text(text):
        out += part["text"] if part["type"] == 0 \
            else (queue.pop(0) if queue else "")
    return out
