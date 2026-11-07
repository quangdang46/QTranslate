"""Google Lens OCR -- free text recognition, no API key required.

Port of the .tmp ``google-lens-services`` plugin: a from-scratch
protobuf wire encoder/decoder for the Chromium Lens overlay endpoint
(``lensfrontend-pa.googleapis.com/v1/crupload``), the same public
client key Chromium ships, and the same request/response schema
(``LensOverlayServerRequest`` / ``LensOverlayServerResponse``).

The OCR_EXT contract hands the recogniser ``(image_bytes, lang,
api_key)`` where ``lang`` is the ocr.space 3-letter code -- mapped back
to BCP-47 here (``eng`` -> ``en``, ``vie`` -> ``vi`` ...). Image
dimensions come from the PNG/JPEG header when readable, else the
plugin's 1000x1000 default. A blank ``lens.api_key`` setting uses the
bundled Chromium key, exactly like the Kotlin ``resolveApiKey``.
"""

import json
import random
import struct
import urllib.request

_NAME = "google-lens-ocr"
_ENDPOINT = "https://lensfrontend-pa.googleapis.com/v1/crupload"
# Public client key used by Chromium for Lens overlay (lens_features.cc).
_DEFAULT_KEY = "AIzaSyDr2UxVnv_U85AbhhY8XSHSIavUW0DC-sY"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

# ocr.space 3-letter codes -> BCP-47 tags (the common OCR languages).
_LANG_BACK = {
    "eng": "en", "vie": "vi", "fra": "fr", "deu": "de", "spa": "es",
    "ita": "it", "por": "pt", "rus": "ru", "jpn": "ja", "kor": "ko",
    "zho": "zh", "ara": "ar", "hin": "hi", "tha": "th", "nld": "nl",
    "pol": "pl", "tur": "tr", "ukr": "uk", "ces": "cs", "swe": "sv",
    "dan": "da", "fin": "fi", "nor": "no", "ron": "ro", "hun": "hu",
}


# ---------------------------------------------------------------- protobuf
def _varint(value):
    out = bytearray()
    while value & ~0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def _tag(field, wire):
    return _varint((field << 3) | wire)


def _ld(field, payload):
    """Length-delimited field (wire type 2)."""
    return _tag(field, 2) + _varint(len(payload)) + payload


def _vf(field, value):
    """Varint field (wire type 0)."""
    return _tag(field, 0) + _varint(value)


def _fields(data):
    """Parse a protobuf buffer into (field_number, wire_type, value)
    where value is int for varints and bytes for length-delimited."""
    out = []
    i, n = 0, len(data)
    while i < n:
        tag = 0
        shift = 0
        while i < n:
            b = data[i]
            i += 1
            tag |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
            if shift > 35:
                return out
        else:
            break
        num, wire = tag >> 3, tag & 7
        if wire == 0:
            v, shift = 0, 0
            while i < n:
                b = data[i]
                i += 1
                v |= (b & 0x7F) << shift
                if not b & 0x80:
                    break
                shift += 7
                if shift > 70:
                    return out
            else:
                return out
            out.append((num, wire, v))
        elif wire == 2:
            ln, shift = 0, 0
            while i < n:
                b = data[i]
                i += 1
                ln |= (b & 0x7F) << shift
                if not b & 0x80:
                    break
                shift += 7
                if shift > 35:
                    return out
            else:
                return out
            if i + ln > n:
                return out
            out.append((num, wire, data[i:i + ln]))
            i += ln
        elif wire == 1:
            if i + 8 > n:
                return out
            i += 8
        elif wire == 5:
            if i + 4 > n:
                return out
            i += 4
        else:
            return out
    return out


def build_request(image, width, height, language):
    """LensOverlayServerRequest, field-for-field the Kotlin builder."""
    request_id = (_vf(1, random.getrandbits(62) + 1)
                  + _vf(2, 1) + _vf(3, 1))
    locale = (_ld(1, language.encode()) + _ld(2, b"US")
              + _ld(3, b"America/New_York"))
    client_filters = _ld(1, _vf(1, 1))                     # AUTO_FILTER
    rendering = _vf(2, 1)                                  # LENS_OVERLAY
    client_context = (_vf(1, 1) + _vf(2, 1) + _ld(4, locale)
                      + _ld(17, client_filters) + _ld(20, rendering))
    request_context = _ld(3, request_id) + _ld(4, client_context)
    payload = _ld(1, image)
    metadata = _vf(1, width) + _vf(2, height)
    image_data = _ld(1, payload) + _ld(3, metadata)
    objects_request = _ld(1, request_context) + _ld(3, image_data)
    return _ld(1, objects_request)


def parse_response(data):
    """LensOverlayServerResponse -> (text, language_or_None)."""
    lines = []
    lang = None

    def words_of(line_bytes):
        parts = []
        for wnum, wwire, wval in _fields(line_bytes):
            if wnum != 1 or wwire != 2:
                continue
            text, sep = "", " "
            for fnum, fwire, fval in _fields(wval):
                if fwire != 2:
                    continue
                if fnum == 2:
                    text = fval.decode("utf-8", "replace")
                elif fnum == 3:
                    sep = fval.decode("utf-8", "replace")
            if text:
                parts.append(text + sep)
        return "".join(parts).strip()

    for num, wire, val in _fields(data):
        if num != 2 or wire != 2:
            continue
        for onum, owire, oval in _fields(val):       # objects_response
            if onum != 3 or owire != 2:
                continue
            for tnum, twire, tval in _fields(oval):  # text
                if twire != 2:
                    continue
                if tnum == 2:
                    lang = tval.decode("utf-8", "replace").strip() or None
                elif tnum == 1:                     # text_layout
                    for lnum, lwire, lval in _fields(tval):
                        if lnum != 1 or lwire != 2:
                            continue
                        for pnum, pwire, pval in _fields(lval):  # lines
                            if pnum != 2 or pwire != 2:
                                continue
                            text = words_of(pval)
                            if text:
                                lines.append(text)
    return "\n".join(lines), lang


# ------------------------------------------------------------- image header
def _png_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 24:
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    return None


def _jpeg_size(data):
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        ln = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + ln
    return None


def _image_size(data):
    size = _png_size(data) or _jpeg_size(data)
    return size if size else (1000, 1000)


# -------------------------------------------------------------------- lookup
def _bcp47(lang):
    return _LANG_BACK.get((lang or "").lower(), "en")


def _api_key(api):
    override = (api.get_setting("lens.api_key", "") or "").strip()
    return override or _DEFAULT_KEY


def _ocr(image_bytes, lang, api_key, api):
    """fn(image_bytes, lang, api_key) -> recognized text ("" on miss)."""
    if not image_bytes:
        return ""
    width, height = _image_size(image_bytes)
    payload = build_request(image_bytes, width, height, _bcp47(lang))
    req = urllib.request.Request(
        _ENDPOINT, data=payload, method="POST",
        headers={"Content-Type": "application/x-protobuf",
                 "X-Goog-Api-Key": _api_key(api),
                 "User-Agent": _UA,
                 "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    text, _detected = parse_response(body)
    return text.strip()


def register(api):
    api.register_ocr(_NAME, lambda b, l, k: _ocr(b, l, k, api))
