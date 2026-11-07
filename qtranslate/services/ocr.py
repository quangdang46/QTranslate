"""OCR providers — reversed from QTranslate.exe strings + OcrSpaceProvider.

- OcrSpaceProvider (common::OcrSpaceProvider): POST multipart
  https://api.ocr.space/parse/image (apikey, language, isOverlayRequired)
  with format strings at .rdata (Boundary%08X Content-Disposition, ...).
  API key stored in Options.json > Advanced > OcrApiKey; the public demo
  key "helloworld" works for smoke tests.
"""
import json
import urllib.parse
import urllib.request
from qtranslate import common
import uuid

OCR_HOST = "https://api.ocr.space/parse/image"
_UA = {"User-Agent": "QTranslate-re/1.0"}


def _native_multipart(image_bytes: bytes, api_key: str, lang: str,
                      overlay: bool) -> tuple[bytes, str]:
    """Build the multipart body the way native's format strings do.

    The image's `.rdata` carries the builder verbatim, as three adjacent
    wide strings (all found, offsets recorded in
    `tests/regress_ocr_multipart.py`)::

        ------Boundary%08X\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: application/octet-stream\r\n\r\n
        \r\n------Boundary%08X\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n
        ------Boundary%08X--\r\n

    so the **file part comes first** (with a filename), then one part per
    plain field, then the closing boundary. The port previously emitted
    every field first and the file last -- a body the native client never
    sends. `Content-Type: multipart/form-data; boundary=------Boundary…`
    is the fourth literal, matching the `------Boundary` prefix used
    throughout.
    """
    tag = uuid.uuid4().int & 0xFFFFFFFF
    # The header literal (0x529ef0, verified 2026-10-16 against the aligned
    # offset 1216310) is `boundary=----Boundary%08X` -- FOUR dashes. The
    # part delimiters are `------Boundary%08X` -- SIX. That is 2 header
    # dashes + the 4-dash token, deliberately not equal.
    marker = "----Boundary{:08X}".format(tag)
    delim = "--" + marker
    body = (
        delim + '\r\nContent-Disposition: form-data; name="file"; '
        'filename="capture.png"\r\nContent-Type: application/octet-stream'
        "\r\n\r\n"
    ).encode() + image_bytes + b"\r\n"
    for name, value in (("apikey", api_key), ("language", lang),
                        ("isOverlayRequired",
                         "true" if overlay else "false")):
        body += ("\r\n" + delim + '\r\nContent-Disposition: form-data; '
                 'name="' + name + '"\r\n\r\n' + value + "\r\n").encode()
    body += (delim + "--\r\n").encode()
    return body, marker


def ocr_space(image_bytes: bytes, api_key: str = "helloworld",
              lang: str = "eng", overlay: bool = False) -> dict:
    """Upload image bytes, return parsed JSON (matches native multipart layout)."""
    body, marker = _native_multipart(image_bytes, api_key, lang, overlay)
    req = urllib.request.Request(
        OCR_HOST, data=body,
        headers={**_UA,
                 "Content-Type": "multipart/form-data; boundary=" + marker})
    with common.http_open(req) as r:
        return json.loads(r.read().decode("utf-8"))


# ocr.space's own 3-letter language codes. The native carries them as
# ONE wide string in the image (measured 2026-10-16 around offset
# 1215480):
#
#     ara bul chs cht hrv cze dan dut eng fin fre ger gre hun ita
#     jpn kor nor pol por rus spa swe tur
#
# -- 24 codes, which is what the service accepts. The port's tables are
# Google's 2-letter codes, so the request has to be translated; a
# language the list does not have falls back to "eng", which is what
# native does for a language it lacks.
#
# "vi" and "zh" are the port's own additions (ocr.space does have
# Vietnamese, under "vie"), so a Vietnamese capture still reads; every
# other entry is one of the native's own codes.
OCR_LANGUAGES = {
    "en": "eng", "fr": "fre", "de": "ger", "es": "spa", "ru": "rus",
    "ja": "jpn", "ko": "kor", "zh-CN": "chs", "zh-TW": "cht", "zh": "chs",
    "ar": "ara", "bg": "bul", "hr": "hrv", "cs": "cze", "da": "dan",
    "nl": "dut", "fi": "fin", "el": "gre", "hu": "hun", "it": "ita",
    "no": "nor", "pl": "pol", "pt": "por", "sv": "swe", "tr": "tur",
    "vi": "vie",
}


def ocr_language(code: str) -> str:
    """The ocr.space language code for a Google language code.

    "eng" for a language the service does not have -- native's own
    fallback.
    """
    return OCR_LANGUAGES.get(code, "eng")


def _extension_ocr(image_bytes, lang, api_key):
    """An extension's recogniser, when one registered.

    ``registry.OCR_EXT`` is the live table (``api.register_ocr``). A
    backend that raises falls through to the built-in endpoint.
    """
    try:
        from qtranslate import registry as _RG
    except Exception:
        return None
    table = getattr(_RG, "OCR_EXT", None)
    if not table:
        return None
    for name in sorted(table):
        try:
            out = table[name](image_bytes, lang, api_key)
        except Exception:
            continue
        if isinstance(out, str) and out.strip():
            return out.strip()
    return None


# ``ocr_text``'s ``lang`` argument is an ocr.space 3-letter code
# (OCR_LANGUAGES values: chs/cht/fre/ger/...). The offline backends
# speak different code spaces, so both maps are keyed by the ocr.space
# code. Unmapped codes fall back the same way native does: tesseract
# gets "eng", Vision keeps its own language detection (upstream's
# AUTO -> "" path in MacVisionOcrBackend).

# ocr.space code -> tesseract traineddata name.
_TESS_LANG = {
    "ara": "ara", "bul": "bul", "chs": "chi_sim", "cht": "chi_tra",
    "hrv": "hrv", "cze": "ces", "dan": "dan", "dut": "nld",
    "eng": "eng", "fin": "fin", "fre": "fra", "ger": "deu",
    "gre": "ell", "hun": "hun", "ita": "ita", "jpn": "jpn",
    "kor": "kor", "nor": "nor", "pol": "pol", "por": "por",
    "rus": "rus", "spa": "spa", "swe": "swe", "tur": "tur",
    "vie": "vie",
}

# ocr.space code -> Vision recognitionLanguages tag, for the languages
# VNRecognizeTextRequest supports.
_VISION_LANG = {
    "ara": "ar-SA", "dan": "da-DK", "dut": "nl-NL", "eng": "en-US",
    "fre": "fr-FR", "ger": "de-DE", "ita": "it-IT", "jpn": "ja-JP",
    "kor": "ko-KR", "pol": "pl-PL", "por": "pt-BR", "rus": "ru-RU",
    "spa": "es-ES", "tur": "tr-TR", "vie": "vi-VN",
    "chs": "zh-Hans", "cht": "zh-Hant",
}


def _macos_vision_ocr(image_bytes: bytes, lang: str = "eng") -> str | None:
    """Offline OCR through macOS Vision (the .tmp system-ocr plugin's
    macOS half). Returns the recognized text, or None when Vision is
    unavailable or finds nothing -- callers then fall back to the
    cloud endpoint. Runs entirely on-device: no screenshot leaves the
    machine when this path answers."""
    try:
        import Vision
        from Foundation import NSData
        nsdata = NSData.dataWithBytes_length_(image_bytes,
                                               len(image_bytes))
        handler = Vision.VNImageRequestHandler.alloc() \
            .initWithData_options_(nsdata, {})
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(
            Vision.VNRequestTextRecognitionLevelAccurate)
        req.setUsesLanguageCorrection_(True)
        tag = _VISION_LANG.get((lang or "").lower())
        if tag:
            req.setRecognitionLanguages_([tag])
        ok, _err = handler.performRequests_error_([req], None)
        if not ok:
            return None
        lines = []
        for obs in req.results() or []:
            cands = obs.topCandidates_(1) or []
            if cands:
                lines.append(str(cands[0].string()))
        text = "\n".join(lines).strip()
        return text or None
    except Exception:
        return None


def _tesseract_ocr(image_bytes: bytes, lang: str = "eng") -> str | None:
    """Offline OCR through the tesseract CLI -- the .tmp
    system-services LinuxTesseractBackend (and the Windows fallback
    path) equivalent. Used when the platform's native recognizer is
    absent or finds nothing; returns None when tesseract is not
    installed so the caller falls through to the cloud endpoint."""
    import shutil
    import subprocess
    exe = shutil.which("tesseract")
    if not exe:
        return None
    # ``lang`` is already an ocr.space code here; translate it into
    # tesseract's traineddata namespace (chs->chi_sim, fre->fra, ...).
    tess_lang = _TESS_LANG.get((lang or "").lower(), "eng")
    try:
        proc = subprocess.run(
            [exe, "stdin", "stdout", "-l", tess_lang],
            input=image_bytes, capture_output=True, timeout=30)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.decode("utf-8", "replace").strip()
    return text or None


def _offline_ocr(image_bytes: bytes, lang: str = "eng") -> str | None:
    """Platform offline recognizer chain: macOS Vision first (native,
    best quality), then the tesseract CLI when installed -- the same
    role LinuxTesseractBackend plays upstream. On Linux there is no
    platform-gated recognizer, so tesseract is the whole chain."""
    import sys
    if sys.platform == "darwin":
        out = _macos_vision_ocr(image_bytes, lang)
        if out is not None:
            return out
    return _tesseract_ocr(image_bytes, lang)


# .tmp ServiceRole.OCR selections, reduced to the backends this port
# has: the platform offline engines, the ocr.space cloud endpoint,
# Google Cloud Vision and the AI vision model. "" / unknown = the
# default order below.
_OCR_STAGES = ("vision", "tesseract", "ocrspace", "google-vision", "ai")


def _preferred_ocr():
    try:
        from qtranslate import config as _C
        v = (_C.general_setting("PreferredServices", {}) or {}
             ).get("ocr")
        return v if v in _OCR_STAGES else ""
    except Exception:
        return ""


def _ocr_stage(name, image_bytes, lang, api_key):
    """One OCR backend -> text or None/"" (None = unavailable, "" =
    ran but found nothing -- both let the chain continue)."""
    if name == "vision":
        import sys
        if sys.platform != "darwin":
            return None
        return _macos_vision_ocr(image_bytes, lang)
    if name == "tesseract":
        return _tesseract_ocr(image_bytes, lang)
    if name == "ocrspace":
        try:
            obj = ocr_space(image_bytes, api_key, lang)
            return (obj["ParsedResults"][0]["ParsedText"].strip()
                    or "")
        except Exception:
            return None
    if name == "google-vision":
        # plugins/google-services GoogleOCRService: Cloud Vision
        # TEXT_DETECTION, gated on General.GoogleVisionApiKey like the
        # Kotlin plugin's conditional service registration.
        try:
            from qtranslate.services import google_vision as _GV
            res = _GV.extract_text(image_bytes, lang)
            return res[0] if res else ""
        except Exception:
            return None
    if name == "ai":
        # ai-services AIVisionOcrService port: last in the default
        # order; raises before any network I/O while AI settings are
        # unconfigured, so an unconfigured install costs nothing.
        try:
            from qtranslate.services import ai_translate as _AI
            return (_AI.vision_ocr(image_bytes, lang).get("text") or "")
        except Exception:
            return ""
    return None


def ocr_text(image_bytes: bytes, api_key: str = "helloworld",
             lang: str = "eng") -> str:
    """Convenience: return just the parsed text of the first result.

    Order: extension recognizers, then the platform OFFLINE engine
    (macOS Vision, then tesseract), then the ocr.space cloud endpoint,
    then Google Cloud Vision (when keyed), then the AI vision model
    as a last resort. ``General.PreferredServices.ocr`` promotes one
    stage to the front; an earlier hit skips every later, more
    expensive stage."""
    ext = _extension_ocr(image_bytes, lang, api_key)
    if ext is not None:
        return ext
    pref = _preferred_ocr()
    order = ([pref] if pref else []) + [s for s in _OCR_STAGES
                                      if s != pref]
    for stage in order:
        out = _ocr_stage(stage, image_bytes, lang, api_key)
        if out:
            return out
    return ""


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    # 1x1 white PNG (won't parse text, but validates the endpoint path)
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    print(ocr_text(png))
