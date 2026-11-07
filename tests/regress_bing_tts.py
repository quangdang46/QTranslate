"""regress_bing_tts -- bing-services BingTTSService port.

HTTP stubbed through session._net_open / bing_session; asserts the
SSML shape, form fields, chunking, voice map and audio guard.
"""
import io
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qtranslate import tts  # noqa: E402
from qtranslate import session as S  # noqa: E402


class _Resp:
    def __init__(self, body):
        self._b = body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def main():
    ok = 0

    def check(cond, name):
        nonlocal ok
        assert cond, name
        ok += 1

    # --- voice map ---------------------------------------------------------
    check(tts._bing_voice("vi") == ("vi-VN", "Male", "vi-VN-NamMinhNeural"),
          "vi voice")
    check(tts._bing_voice("iw")[2] == "he-IL-AvriNeural", "iw->he")
    check(tts._bing_voice("zh-CN")[2] == "zh-CN-XiaoxiaoNeural",
          "zh-CN->zh-Hans")
    check(tts._bing_voice("zh-TW")[2] == "zh-CN-XiaoxiaoNeural",
          "zh-TW->zh-Hant")
    check(tts._bing_voice("xx")[0] == "en-US", "unknown->en")
    check(len(tts._BING_VOICES) == 74, "voice table size %d"
          % len(tts._BING_VOICES))

    # --- SSML ---------------------------------------------------------------
    ssml = tts._bing_ssml("a<b>&'\"", "en-US", "Female", "v", "+0.00%")
    check("xml:lang='en-US'" in ssml, "lang attr")
    check("name='v'" in ssml, "voice name")
    check("rate='+0.00%'" in ssml, "rate")
    check("a&lt;b&gt;&amp;&apos;&quot;" in ssml, "escaped text")
    check("<speak version='1.0'" in ssml, "speak root")

    # --- chunking ------------------------------------------------------------
    words = " ".join("w%d" % i for i in range(300))
    cs = tts._bing_chunks(words)
    check(all(len(c) <= 500 for c in cs), "chunk size cap")
    check(" ".join(cs).split() == words.split(), "no word lost")
    check(tts._bing_chunks("") == [] and tts._bing_chunks("   ") == [],
          "empty -> no chunks")
    check(len(tts._bing_chunks("x" * 600)) == 1, "oversize word kept")

    # --- request shape (stubbed transport) -----------------------------------
    seen = []

    class _Opener:
        pass

    orig_session, orig_open = S.bing_session, S._net_open
    S.bing_session = lambda: {
        "IG": "IG123", "token": "TOK", "key": "EXP", "iid": "iid.1",
        "opener": _Opener()}

    def fake_open(req, opener=None, data=None):
        seen.append(req)
        return _Resp(b"ID3" + b"\x00" * 100)

    S._net_open = fake_open
    try:
        data = tts.bing_tts("Hello world", "en")
        check(data.startswith(b"ID3"), "mp3 bytes returned")
        check(len(seen) == 1, "one chunk -> one request")
        req = seen[0]
        check(req.full_url.startswith(tts._BING_TTS_URL), "endpoint")
        check("IG=IG123" in req.full_url and "IID=iid.1" in req.full_url,
              "query params")
        body = urllib.parse.parse_qs(req.data.decode())
        check(body["token"] == ["TOK"] and body["key"] == ["EXP"],
              "token/key form fields")
        check("NamMinhNeural" not in body["ssml"][0]
              and "AriaNeural" in body["ssml"][0], "en voice in ssml")
        check("Hello world" in body["ssml"][0], "text in ssml")
    finally:
        S.bing_session, S._net_open = orig_session, orig_open

    # --- multi-chunk concatenation -------------------------------------------
    seen.clear()
    S.bing_session = lambda: {
        "IG": "IG", "token": "T", "key": "K", "iid": "i",
        "opener": _Opener()}
    S._net_open = fake_open
    try:
        long_text = " ".join("word%d" % i for i in range(400))
        tts.bing_tts(long_text, "vi")
        check(len(seen) >= 2, "long text chunked (%d reqs)" % len(seen))
        check(all(b"NamMinhNeural" in urllib.parse.parse_qs(
            r.data.decode())["ssml"][0].encode() for r in seen),
            "vi voice on every chunk")
    finally:
        S.bing_session, S._net_open = orig_session, orig_open

    # --- non-audio body rejected ----------------------------------------------
    S.bing_session = lambda: {
        "IG": "IG", "token": "T", "key": "K", "iid": "i",
        "opener": _Opener()}
    S._net_open = lambda req, opener=None, data=None: _Resp(b'{"err":1}')
    try:
        try:
            tts.bing_tts("hi", "en")
            check(False, "json body should raise")
        except RuntimeError as e:
            check("non-audio" in str(e), "non-audio rejection")
    finally:
        S.bing_session, S._net_open = orig_session, orig_open

    # --- player chain order ----------------------------------------------------
    src = open(os.path.join(ROOT, "qtranslate", "player.py")).read()
    check('("google", google_tts), ("bing", bing_tts)' in src,
          "google before bing in play_text")
    check(src.index('("google", google_tts)') < src.index(
        '("bing", bing_tts)'), "order")
    check('_speak_darwin' in src.split("for name, fetch")[1],
          "offline fallback still last")

    print("regress_bing_tts: all checks ok (%d assertions)" % ok)


if __name__ == "__main__":
    main()
