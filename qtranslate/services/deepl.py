"""DeepL service port.

Reversed from: C:/Program Files (x86)/QTranslate/Services/DeepL/Service.js
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

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

_SPLIT_RE = re.compile(r"^\s+|(?:\s*\n)+\s*|[.!?\":;\u0964](?:\s+)|\s+$")
_SENT_END_RE = re.compile(r"[.!?\":;\u0964](?:\s+)")


def parse_text(text: str) -> list[dict]:
    """Port of parseText(a): splits into type-1 sentences / type-0 separators."""
    parts: list[dict] = []
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")[:5000]
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


def _post_jsonrpc(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        HOST + "/jsonrpc",
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect(text: str) -> str:
    """Port of serviceDetectLanguageRequest/Response (LMT_split_into_sentences)."""
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "LMT_split_into_sentences",
        "params": {
            "texts": [text[:5000]],
            "lang": {"lang_user_selected": "auto", "user_preferred_langs": ["EN"]},
        },
    }
    obj = _post_jsonrpc(payload)
    try:
        return obj["result"]["lang"]
    except (KeyError, TypeError):
        return ""


def translate(text: str, sl: str = "auto", tl: str = "EN") -> str:
    """Port of serviceTranslateRequest/Response (LMT_handle_jobs)."""
    sentences = split_text(text)
    jobs = [{"kind": "default", "raw_en_sentence": s} for s in sentences]
    count = 1
    for job in jobs:
        count += (job["raw_en_sentence"] or "").count("i")
    now = int(time.time() * 1000)
    payload = {
        "id": 2,
        "jsonrpc": "2.0",
        "method": "LMT_handle_jobs",
        "params": {
            "jobs": jobs,
            "lang": {
                "user_preferred_langs": [sl if sl != "auto" else "EN", tl],
                "source_lang_user_selected": sl,
                "target_lang": tl,
            },
            "priority": 1,
            "timestamp": now + (count - now % count),
        },
    }
    obj = _post_jsonrpc(payload)
    beams = [
        t["beams"][0]["postprocessed_sentence"]
        for t in obj["result"]["translations"]
        if t.get("beams")
    ]
    out = ""
    queue = list(beams)
    for part in parse_text(text):
        out += part["text"] if part["type"] == 0 else (queue.pop(0) if queue else "")
    return out
