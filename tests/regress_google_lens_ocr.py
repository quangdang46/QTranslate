"""regress_google_lens_ocr -- example extension: protobuf round-trip.

The extension ships no network in tests: build/parse is verified on
synthetic protobuf buffers plus a real PNG size parse.
"""
import importlib.util
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_EXT = os.path.join(ROOT, "examples", "extensions", "google_lens_ocr",
                    "ext.py")


def _load():
    spec = importlib.util.spec_from_file_location("lens_ext", _EXT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m = _load()
    ok = 0

    def check(cond, name):
        nonlocal ok
        assert cond, name
        ok += 1

    # varint/tag/ld primitives
    check(m._varint(0) == b"\x00", "varint zero")
    check(m._varint(300) == b"\xac\x02", "varint 300")
    check(m._tag(3, 2) == b"\x1a", "tag field3 wire2")
    check(m._ld(1, b"hi") == b"\x0a\x02hi", "ld field1")

    # _fields round-trip of a nested message
    inner = m._vf(1, 7) + m._ld(2, b"abc")
    outer = m._ld(5, inner) + m._vf(9, 1)
    fields = m._fields(outer)
    check(len(fields) == 2, "fields count")
    check(fields[0] == (5, 2, inner), "fields nested bytes")
    check(fields[1] == (9, 0, 1), "fields varint")

    # parse_response: words "Hello" "World", sep " " -> lines
    word1 = m._ld(2, b"Hello") + m._ld(3, b" ")
    word2 = m._ld(2, b"World") + m._ld(3, b"\n")
    line = m._ld(1, word1) + m._ld(1, word2)
    para = m._ld(2, line)
    layout = m._ld(1, para)
    text = m._ld(1, layout) + m._ld(2, b"en")
    objresp = m._ld(3, text)
    resp = m._ld(2, objresp)
    out, lang = m.parse_response(resp)
    check(lang == "en", "detected lang")
    check(out == "Hello World", "joined words got %r" % out)

    # multiple paragraphs -> separate lines
    w = m._ld(2, b"x") + m._ld(3, b" ")
    l1 = m._ld(1, w); l2 = m._ld(1, w)
    p1 = m._ld(2, l1); p2 = m._ld(2, l2)
    layout2 = m._ld(1, p1) + m._ld(1, p2)
    text2 = m._ld(1, layout2)
    resp2 = m._ld(2, m._ld(3, text2))
    out2, lang2 = m.parse_response(resp2)
    check(lang2 is None, "no lang field")
    check(out2 == "x\nx", "paragraphs got %r" % out2)

    # corrupt input -> empty result, no raise
    check(m.parse_response(b"\x00\x01\x02") == ("", None)
          or m.parse_response(b"") == ("", None), "corrupt safe")
    check(m.parse_response(b"") == ("", None), "empty safe")

    # image size: real PNG IHDR
    png = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
           + struct.pack(">IIBBBBB", 640, 480, 8, 2, 0, 0, 0))
    check(m._image_size(png) == (640, 480), "png size")
    check(m._image_size(b"garbage") == (1000, 1000), "default size")

    # build_request produces a non-empty protobuf blob
    req = m.build_request(png, 640, 480, "en")
    check(len(req) > 20 and req[0] == 0x0A, "request tag")

    # language mapping: ocr.space 3-letter -> BCP-47
    check(m._bcp47("eng") == "en", "eng->en")
    check(m._bcp47("vie") == "vi", "vie->vi")
    check(m._bcp47("zzz") == "en", "unknown->en")
    check(m._bcp47(None) == "en", "none->en")

    # empty input -> "" without touching network
    check(m._ocr(b"", "eng", "", _FakeApi()) == "", "empty image")

    # api key resolution: setting wins, else bundled key
    check(m._api_key(_FakeApi()) == m._DEFAULT_KEY, "default key")
    check(m._api_key(_FakeApi("k")) == "k", "override key")

    # register() calls register_ocr with our name
    api = _FakeApi()
    m.register(api)
    check("google-lens-ocr" in api.ocr, "registered name")

    print("regress_google_lens_ocr: all checks ok (%d assertions)" % ok)


class _FakeApi:
    def __init__(self, key=None):
        self.ocr = {}
        self._key = key

    def get_setting(self, key, default=None):
        return self._key if self._key is not None else default

    def register_ocr(self, name, fn):
        self.ocr[name] = fn


if __name__ == "__main__":
    main()
