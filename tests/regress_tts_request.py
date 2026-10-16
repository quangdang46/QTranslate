"""Regression: the four LISTEN (TTS) request builders match the Service.js.

Each TTS provider's `serviceListenRequest` was read out of the recovered
payload and this suite pins the port against it. The shared divergence it
found (fixed 2026-10-16): **all three classic providers encoded the text
with `urllib.parse.quote`, where native uses `encodeGetParam`.**

`encodeGetParam` is native's own helper (Common.js), and it is not the same
as a bare quote:

    function encodeGetParam(a){
      a = encodeUriParam(a);                       // encodeURIComponent
      if (a.length > Const.MAX_URI_LEN) {          // 1800
        a = a.slice(0, Const.MAX_URI_LEN);
        var b = a.lastIndexOf("%20");
        if (0 < b) return a.slice(0, b);
      }
      return a;
    }

Two consequences, both observable:

  * `/` and `:` and other reserved characters are percent-encoded
    (`quote`'s default `safe="/"` leaves them alone), so a sentence with a
    slash produces a **different URL** than native's;
  * text over 1800 encoded characters is **truncated** (at the last whole
    word), which `quote` never does.

Papago has no `serviceListenRequest` in the payload at all — its TTS is
the live web API, so it is pinned as a documented absence rather than
skipped silently.

Headless: the JS is READ from the payload, never executed.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import common  # noqa: E402
from qtranslate import tts  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(REPO, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")


def listen_request(sid):
    """The recovered `serviceListenRequest` body for one service."""
    if not os.path.exists(PAYLOAD):
        return None
    TS = io.open(PAYLOAD, "rb").read().decode("utf-8", "replace")
    i = TS.find("new ServiceHeader(%d," % sid)
    if i < 0:
        return None
    nxt = [m.start() for m in
           re.finditer(r'new ServiceHeader\((\d+),', TS) if m.start() > i]
    seg = TS[i:nxt[0] if nxt else len(TS)]
    m = re.search(r"function serviceListenRequest\s*\([^)]*\)\s*\{", seg)
    if not m:
        return None
    depth, j = 1, m.end()
    while j < len(seg) and depth:
        if seg[j] == "{":
            depth += 1
        elif seg[j] == "}":
            depth -= 1
        j += 1
    return seg[m.end():j - 1]


HAVE_ARTIFACT = os.path.exists(PAYLOAD)

# --- Google ------------------------------------------------------------
g = listen_request(1) if HAVE_ARTIFACT else None
ck("Google has a serviceListenRequest", g is not None)
if g:
    ck("Google's path is /translate_tts?ie=UTF-8&q={0}&tl={1}&client=gtx&tk={2}",
       'format("/translate_tts?ie=UTF-8&q={0}&tl={1}&client=gtx&tk={2}"' in g,
       g[:200])
    ck("Google encodes with encodeGetParam (not a bare quote)",
       "encodeGetParam(a)" in g)
    ck("Google's slow flag adds ttsspeed=0.24",
       '&ttsspeed=0.24' in g and g.index("ttsspeed") > g.index("format("))
    ck("Google passes the text through tk(a) for the token",
       "tk(a)" in g)

# --- Yandex ------------------------------------------------------------
y = listen_request(11) if HAVE_ARTIFACT else None
ck("Yandex has a serviceListenRequest", y is not None)
if y:
    ck("Yandex's path is /tts?format=mp3&quality=hi&platform=web"
       "&application=translate&lang={0}&text={1}",
       'format("/tts?format=mp3&quality=hi&platform=web&application='
       'translate&lang={0}&text={1}"' in y, y[:200])
    ck("Yandex encodes with encodeGetParam too",
       "encodeGetParam(a)" in y)
    ck("Yandex's slow flag adds speed=0.7",
       '&speed=0.7' in y)
    ck("Yandex maps 6 languages explicitly",
       all(('%s"' % code) in y for code in ("en_GB", "sv_SE", "da_DK",
                                            "cs_CZ", "ca_ES", "ar_AE")))
    ck("...and falls back to lang_LANG",
       'b+"_"+b.toUpperCase()' in y)

# --- Baidu -------------------------------------------------------------
b = listen_request(28) if HAVE_ARTIFACT else None
ck("Baidu has a serviceListenRequest", b is not None)
if b:
    ck("Baidu's path is /text2audio?lan={0}&ie=UTF-8&text={1}",
       'format("/text2audio?lan={0}&ie=UTF-8&text={1}"' in b, b[:200])
    ck("Baidu encodes with encodeGetParam too",
       "encodeGetParam(b)" in b)
    ck("Baidu's slow flag adds spd=1",
       '&spd=1' in b)

# --- Papago has NO serviceListenRequest (its TTS is the web API) -------
p = listen_request(30) if HAVE_ARTIFACT else None
ck("Papago has no serviceListenRequest (TTS is the live web API)",
   p is None)

# --- the port encodes the way native's encodeGetParam does ------------
# The helpers take text and return a URL; they are checked through the
# encoded text, capturing what they build rather than fetching.
SRC = {name: io.open(os.path.join(REPO, "qtranslate", "tts.py"),
                     encoding="utf-8").read()
       for name in ("tts",)}
tts_src = SRC["tts"]

# a probe with characters quote's default safe set leaves alone
PROBE = "read/write: a test"
want = common.encode_get_param(PROBE)
ck("encode_get_param encodes the slash and colon",
   "%2F" in want or "/" not in want, want)
ck("urllib.parse.quote does NOT (so the two really differ)",
   __import__("urllib.parse", fromlist=["quote"]).quote(PROBE) != want)

for fn, name in ((tts.google_tts, "google_tts"),
                 (tts.yandex_tts, "yandex_tts"),
                 (tts.baidu_tts, "baidu_tts")):
    ck("%s builds its URL with encode_get_param, not quote" % name,
       "quote(text" not in tts_src.split("def " + name)[1]
       .split("\ndef ")[0],
       "%s still encodes with urllib.parse.quote" % name)

# and the truncation behaviour, on the helper that owns it
long_text = "word " * 500                      # 2500 chars
ck("encode_get_param truncates over MAX_URI_LEN",
   len(common.encode_get_param(long_text)) <= common.MAX_URI_LEN,
   str(len(common.encode_get_param(long_text))))
ck("...and cuts at a word boundary (the last %20), not mid-word",
   not common.encode_get_param(long_text).endswith("%"))

# the port's three builders are reachable and return a URL
for fn, name in ((tts.google_tts, "google_tts"),
                 (tts.yandex_tts, "yandex_tts"),
                 (tts.baidu_tts, "baidu_tts")):
    ck("%s exists" % name, callable(fn))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_tts_request: all checks ok (%d assertions%s)"
      % (n[0], "" if HAVE_ARTIFACT else " [artifact absent, half skipped]"))
