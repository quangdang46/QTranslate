"""regress_commons_images -- Wikimedia Commons image search port.

All HTTP stubbed through ``common.http_open``: asserts the API params
match the Kotlin WikimediaClient.searchImages request (generator
search, namespace 6, filetype filter, iiurlwidth), formatversion=2
parsing, thumbnail-less pages dropped, extmetadata HTML stripped, and
media-type mapping. Plus an offscreen smoke of the dialog's tile
caption.
"""
import io
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qtranslate.services import commons_images as ci  # noqa: E402


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _stub(payload):
    def fake(req, opener=None):
        return _Resp(payload)
    return fake


def main():
    ok = 0

    def check(cond, name):
        nonlocal ok
        assert cond, name
        ok += 1

    captured = {}

    def capture(req, opener=None):
        captured["url"] = req.full_url
        return _Resp({"query": {"pages": [
            {"title": "File:Test Image.png",
             "imageinfo": [{
                 "thumburl": "https://upload.wikimedia.org/thumb/x.jpg",
                 "url": "https://upload.wikimedia.org/x.png",
                 "descriptionurl": "https://commons.wikimedia.org/wiki/File:Test_Image.png",
                 "extmetadata": {
                     "Artist": {"text": "<a href='//x'>Jane Doe</a>"},
                     "LicenseShortName": {"text": "CC BY-SA 4.0"},
                 }}]},
            {"title": "File:NoThumb.svg",
             "imageinfo": [{"url": "https://upload.wikimedia.org/y.svg"}]},
        ]}})

    from qtranslate import common
    orig = common.http_open
    common.http_open = capture
    try:
        out = ci.search_images("borborygmi")
    finally:
        common.http_open = orig

    # --- request params match WikimediaClient.searchImages ---------------
    q = dict(urllib.parse.parse_qsl(
        urllib.parse.urlparse(captured["url"]).query))
    check(q["action"] == "query", "action=query")
    check(q["format"] == "json" and q["formatversion"] == "2",
          "formatversion=2")
    check(q["generator"] == "search", "generator=search")
    check(q["gsrsearch"] == "borborygmi filetype:bitmap|drawing",
          "gsrsearch filetype BOTH: %r" % q["gsrsearch"])
    check(q["gsrnamespace"] == "6", "File: namespace")
    check(q["gsrlimit"] == "12", "default limit")
    check(q["prop"] == "imageinfo", "prop=imageinfo")
    check(q["iiprop"] == "url|extmetadata", "iiprop")
    check(q["iiurlwidth"] == str(ci.THUMBNAIL_WIDTH), "thumb width 480")

    # --- result shape -----------------------------------------------------
    check(len(out) == 1, "no-thumbnail page dropped")
    r = out[0]
    check(r["title"] == "Test Image", "File: prefix + ext stripped")
    check(r["thumbnail"].endswith("thumb/x.jpg"), "thumburl")
    check(r["url"].endswith("x.png"), "full url")
    check(r["source"].endswith("File:Test_Image.png"), "descriptionurl")
    check(r["attribution"] == "Jane Doe", "Artist markup stripped")
    check(r["license"] == "CC BY-SA 4.0", "license")

    # --- media-type mapping ----------------------------------------------
    common.http_open = capture
    try:
        ci.search_images("cat", media="PHOTOS")
        q2 = dict(urllib.parse.parse_qsl(
            urllib.parse.urlparse(captured["url"]).query))
        check(q2["gsrsearch"] == "cat filetype:bitmap", "PHOTOS->bitmap")
        ci.search_images("cat", media="DIAGRAMS")
        q3 = dict(urllib.parse.parse_qsl(
            urllib.parse.urlparse(captured["url"]).query))
        check(q3["gsrsearch"] == "cat filetype:drawing",
              "DIAGRAMS->drawing")
    finally:
        common.http_open = orig

    # --- guards ------------------------------------------------------------
    check(ci.search_images("") == [], "blank query -> []")
    check(ci.search_images("   ") == [], "whitespace -> []")

    # --- limit clamp --------------------------------------------------------
    common.http_open = capture
    try:
        ci.search_images("x", limit=500)
        q4 = dict(urllib.parse.parse_qsl(
            urllib.parse.urlparse(captured["url"]).query))
        check(q4["gsrlimit"] == "50", "limit clamped to 50")
    finally:
        common.http_open = orig

    # --- error propagates (dialog shows 'Search failed') ------------------
    def boom(req, opener=None):
        raise OSError("offline")
    common.http_open = boom
    try:
        try:
            ci.search_images("x")
            check(False, "error should propagate")
        except OSError:
            check(True, "error propagates")
    finally:
        common.http_open = orig

    # --- offscreen dialog smoke --------------------------------------------
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from qtranslate.qt.image_search import (ImageSearchDialog, _Tile)
        d = ImageSearchDialog(app, term="")
        check(d.term is not None and d.grid is not None,
              "dialog builds offscreen")
        t = _Tile(d.grid_host, {"title": "Test", "thumbnail": "u",
                                "url": "f", "source": "s",
                                "attribution": "A", "license": "CC"})
        check("Test" in t.cap.text() and "CC" in t.cap.text(),
              "tile caption carries title + licence")
        d.deleteLater()
    except Exception as exc:
        check(False, "dialog smoke: %s: %s" % (type(exc).__name__, exc))

    print("regress_commons_images: %d checks ok" % ok)


if __name__ == "__main__":
    main()
