#!/usr/bin/env python3
"""Provider API-key paths ported from the .tmp plugin services:

- google-services GoogleTranslatorService: official v2 endpoint first
  when General.GoogleTranslateApiKey is set, unofficial gtx fallback.
- deepl-services DeepLTranslatorService: official api.deepl.com first
  when General.DeeplApiKey is set, free web fallback.
- google-services GoogleOCRService: Vision images:annotate gated on
  General.GoogleVisionApiKey.
"""
import io
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate import common, config  # noqa: E402
from qtranslate.services import (deepl, google_translate,  # noqa: E402
                                 google_vision)


def _resp(payload):
    class R(io.BytesIO):
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return R(json.dumps(payload).encode()
             if not isinstance(payload, (bytes, str))
             else payload.encode() if isinstance(payload, str)
             else payload)


def _capture(payload, seen):
    def fn(req, opener=None):
        seen.append(req)
        return _resp(payload)
    return fn


def _with_cfg(section, key, value):
    """Point config at a temp file carrying one key."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w") as f:
        json.dump({section: {key: value}}, f)
    old = config.DEFAULT_PATH
    config.DEFAULT_PATH = path
    return old, path


def main():
    print("== google official translate ==")
    old, path = _with_cfg("General", "GoogleTranslateApiKey", "K1")
    seen = []
    orig = common.http_open
    common.http_open = _capture(
        {"data": {"translations": [{"translatedText": "Xin chào"}]}},
        seen)
    try:
        out = google_translate.translate("Hello", "en", "vi")
    finally:
        common.http_open = orig
    ck("official result", out == "Xin chào", out)
    ck("official endpoint",
       seen and "translation.googleapis.com" in seen[0].full_url,
       seen[0].full_url if seen else "")
    ck("key in query",
       seen and "key=K1" in seen[0].full_url)
    body = json.loads(seen[0].data.decode())
    ck("body shape", body.get("q") == "Hello"
       and body.get("target") == "vi" and body.get("source") == "en"
       and body.get("format") == "text", str(body))

    # auto source -> no "source" field (the API rejects "auto")
    seen.clear()
    common.http_open = _capture(
        {"data": {"translations": [{"translatedText": "x"}]}}, seen)
    try:
        google_translate.translate("hi", "auto", "vi")
    finally:
        common.http_open = orig
        config.DEFAULT_PATH = old
        os.unlink(path)
    body = json.loads(seen[0].data.decode())
    ck("auto omits source", "source" not in body, str(body))

    print("== google official failure -> unofficial ==")
    old, path = _with_cfg("General", "GoogleTranslateApiKey", "K1")
    calls = []

    def flaky(req, opener=None):
        calls.append(req.full_url)
        if "translation.googleapis.com" in req.full_url:
            raise OSError("official down")
        # unofficial gtx single-sentence payload
        return _resp([[["Xin chào", "Hello", None, None]],
                      None, "en"])
    common.http_open = flaky
    try:
        out = google_translate.translate("Hello", "en", "vi")
    finally:
        common.http_open = orig
        config.DEFAULT_PATH = old
        os.unlink(path)
    ck("fell back to gtx", out == "Xin chào", out)
    ck("tried official first",
       calls and "translation.googleapis.com" in calls[0], str(calls))

    print("== no key -> unofficial only ==")
    seen.clear()
    common.http_open = _capture(
        [[["ok", "hi", None, None]], None, "en"], seen)
    try:
        out = google_translate.translate("hi", "en", "vi")
    finally:
        common.http_open = orig
    ck("gtx used", "translate_a/single" in seen[0].full_url
       and "translation.googleapis.com" not in seen[0].full_url,
       seen[0].full_url)

    print("== deepl official ==")
    old, path = _with_cfg("General", "DeeplApiKey", "DK")
    seen = []
    common.http_open = _capture(
        {"translations": [{"text": "Xin chào", "detected_source_language":
                           "EN"}]}, seen)
    try:
        out = deepl.translate("Hello", "en", "vi")
    finally:
        common.http_open = orig
        config.DEFAULT_PATH = old
        os.unlink(path)
    ck("official result", out == "Xin chào", out)
    ck("official endpoint",
       seen and seen[0].full_url.startswith(
           "https://api.deepl.com/v2/translate?key=DK"),
       seen[0].full_url if seen else "")
    body = json.loads(seen[0].data.decode())
    ck("body", body.get("text") == ["Hello"]
       and body.get("target_lang") == "VI"
       and body.get("source_lang") == "EN", str(body))

    print("== deepl code mapping ==")
    ck("EN target -> EN-US", deepl._official_code("EN") == "EN-US")
    ck("EN source stays EN",
       deepl._official_code("EN", source=True) == "EN")
    ck("ZH -> ZH-HANS", deepl._official_code("ZH") == "ZH-HANS")
    ck("PT source collapses",
       deepl._official_code("PT-BR", source=True) == "PT")
    ck("PT-BR target kept",
       deepl._official_code("PT-BR") == "PT-BR")

    print("== deepl official failure -> web ==")
    old, path = _with_cfg("General", "DeeplApiKey", "BAD")
    calls = []

    def deepl_flaky(req, opener=None):
        calls.append(req.full_url)
        if "api.deepl.com" in req.full_url:
            raise OSError("auth rejected")
        return _resp({"translations": [{"text": "Xin chào",
                                        "detected_source_language":
                                        "EN"}]})
    common.http_open = deepl_flaky
    try:
        out = deepl.translate("Hello", "en", "vi")
    finally:
        common.http_open = orig
        config.DEFAULT_PATH = old
        os.unlink(path)
    ck("web fallback result", out == "Xin chào", out)
    ck("official tried first",
       calls and "api.deepl.com" in calls[0], str(calls))

    print("== google vision OCR ==")
    ck("no key -> None",
       google_vision.extract_text(b"\x89PNG", "eng",
                                  api_key="") is None)
    seen = []
    common.http_open = _capture(
        {"responses": [{"fullTextAnnotation": {
            "text": "Hello world\n",
            "pages": [{"property": {"detectedLanguages": [
                {"languageCode": "en"}]}}]}}]}, seen)
    try:
        res = google_vision.extract_text(b"\x89PNG\r\n\x1a\nxxxx",
                                         "eng", api_key="VK")
    finally:
        common.http_open = orig
    ck("vision result", res == ("Hello world", "en"), str(res))
    ck("vision endpoint",
       seen and seen[0].full_url.startswith(
           "https://vision.googleapis.com/v1/images:annotate?key=VK"),
       seen[0].full_url if seen else "")
    body = json.loads(seen[0].data.decode())
    feat = body["requests"][0]["features"][0]
    ck("TEXT_DETECTION", feat.get("type") == "TEXT_DETECTION")
    ck("language hint",
       body["requests"][0].get("imageContext", {})
       .get("languageHints") == ["en"], str(body["requests"][0]))

    seen.clear()
    common.http_open = _capture({"responses": [{}]}, seen)
    try:
        res = google_vision.extract_text(b"img", "auto", api_key="K")
    finally:
        common.http_open = orig
    ck("no annotation -> ('', None)", res == ("", None), str(res))
    ck("auto -> no imageContext",
       "imageContext" not in json.loads(seen[0].data.decode())
       ["requests"][0], "")

    print()
    if FAIL:
        print("regress_provider_api_keys: %d FAILED: %s"
              % (len(FAIL), FAIL))
        sys.exit(1)
    print("regress_provider_api_keys: all checks ok")


if __name__ == "__main__":
    main()
