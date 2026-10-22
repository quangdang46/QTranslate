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


def ocr_text(image_bytes: bytes, api_key: str = "helloworld",
             lang: str = "eng") -> str:
    """Convenience: return just the parsed text of the first result."""
    obj = ocr_space(image_bytes, api_key, lang)
    try:
        return obj["ParsedResults"][0]["ParsedText"].strip()
    except (KeyError, IndexError, TypeError):
        return ""


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    # 1x1 white PNG (won't parse text, but validates the endpoint path)
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    print(ocr_text(png))
