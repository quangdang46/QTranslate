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
import uuid

OCR_HOST = "https://api.ocr.space/parse/image"
_UA = {"User-Agent": "QTranslate-re/1.0"}


def ocr_space(image_bytes: bytes, api_key: str = "helloworld",
              lang: str = "eng", overlay: bool = False) -> dict:
    """Upload image bytes, return parsed JSON (matches native multipart layout)."""
    boundary = "----Boundary{:08X}".format(uuid.uuid4().int & 0xFFFFFFFF)
    parts = []
    fields = {"apikey": api_key, "language": lang,
              "isOverlayRequired": "true" if overlay else "false"}
    for k, v in fields.items():
        parts.append(
            f"------Boundary{boundary.split('----Boundary')[1]}\r\n"
            f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
            .encode())
    parts.append(
        f"------Boundary{boundary.split('----Boundary')[1]}\r\n"
        'Content-Disposition: form-data; name="file"; filename="capture.png"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n".encode()
        + image_bytes + b"\r\n")
    parts.append(f"------Boundary{boundary.split('----Boundary')[1]}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        OCR_HOST, data=body,
        headers={**_UA,
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


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
