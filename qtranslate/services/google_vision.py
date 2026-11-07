"""GoogleOCRService -- port of plugins/google-services.

POST ``vision.googleapis.com/v1/images:annotate?key=<visionApiKey>``
with a TEXT_DETECTION feature (+ languageHints for non-AUTO), then
read ``responses[0].fullTextAnnotation``: ``text`` plus the detected
language from ``pages[0].property.detectedLanguages[0]``.

Registered only when ``General.GoogleVisionApiKey`` is configured --
the Kotlin plugin likewise excludes the OCR service while the secret
is blank.
"""
import base64
import json
import urllib.parse
import urllib.request

from qtranslate import common

ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"


def vision_api_key() -> str:
    try:
        from qtranslate import config as _C
        return str((_C.load() or {}).get("General", {})
                   .get("GoogleVisionApiKey", "") or "")
    except Exception:
        return ""


def _mime(image_bytes: bytes) -> str:
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"


def _lang_hint(lang: str) -> str:
    """ocr.space-style 3-letter or BCP-47 code -> Vision hint (BCP-47)."""
    lang = (lang or "").strip()
    if not lang or lang.lower() in ("auto", "und"):
        return ""
    m = {"eng": "en", "vie": "vi", "fra": "fr", "deu": "de",
         "spa": "es", "ita": "it", "por": "pt", "nld": "nl",
         "pol": "pl", "rus": "ru", "jpn": "ja", "kor": "ko",
         "zho": "zh", "chi": "zh", "ara": "ar", "tha": "th",
         "ind": "id", "msa": "ms", "tur": "tr", "ukr": "uk"}
    return m.get(lang.lower(), lang)


def extract_text(image_bytes: bytes, lang: str = "",
                 api_key: str | None = None):
    """-> (text, detected_language) or None on any failure.

    ``lang`` is the OCR language hint; empty/AUTO sends no hint, like
    the Kotlin ``imageContext`` being null.
    """
    key = api_key if api_key is not None else vision_api_key()
    if not key or not image_bytes:
        return None
    feature = {"type": "TEXT_DETECTION"}
    img_req = {"image": {"content": base64.b64encode(image_bytes)
                         .decode("ascii")},
               "features": [feature]}
    hint = _lang_hint(lang)
    if hint:
        img_req["imageContext"] = {"languageHints": [hint]}
    body = json.dumps({"requests": [img_req]}).encode()
    req = urllib.request.Request(
        ENDPOINT + "?key=" + urllib.parse.quote(key), data=body,
        headers={"Content-Type": "application/json"})
    with common.http_open(req) as r:
        obj = json.loads(r.read().decode("utf-8"))
    responses = obj.get("responses") or []
    if not responses:
        return None
    first = responses[0]
    if first.get("error"):
        return None
    ann = first.get("fullTextAnnotation")
    if not ann:
        return ("", None)
    detected = None
    pages = ann.get("pages") or []
    if pages:
        langs = ((pages[0].get("property") or {})
                 .get("detectedLanguages")) or []
        if langs and langs[0].get("languageCode"):
            detected = _bcp47_to_app(langs[0]["languageCode"])
    return ((ann.get("text") or "").strip(), detected)


def _bcp47_to_app(code: str) -> str:
    """Vision languageCode (e.g. "en", "zh-Hant") -> the app's OCR
    language vocabulary; unknown codes pass through uppercased."""
    c = (code or "").strip()
    if not c:
        return ""
    low = c.lower()
    if low.startswith("zh"):
        return "zh-Hant" if "hant" in low else "zh-Hans"
    return low
