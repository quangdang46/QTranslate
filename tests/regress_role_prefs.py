#!/usr/bin/env python3
"""General.PreferredServices role pinning (.tmp per-role service
selection): OCR stage reorder, TTS backend reorder + "system" bypass,
and the Services-page writer mapping display index -> backend key."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate import config as _C  # noqa: E402
_saved = _C.DEFAULT_PATH
_fd, _tmp = tempfile.mkstemp(suffix=".json")
os.close(_fd)
_C.DEFAULT_PATH = _tmp
_C.save({"General": {"PreferredServices": {"ocr": "ai",
                                           "tts": "bing"}}})

from qtranslate.services import ocr as OCR  # noqa: E402

# ---- OCR: preferred stage runs first, others keep default order --
calls = []


def fake_stage(name, image_bytes, lang, api_key):
    calls.append(name)
    return ""   # nothing found -> chain runs to the end


orig_stage = OCR._ocr_stage
orig_ext = OCR._extension_ocr
OCR._ocr_stage = fake_stage
OCR._extension_ocr = lambda *a, **k: None
try:
    out = OCR.ocr_text(b"img")
    ck("ocr chain completes", out == "")
    ck("ocr preferred first", calls[0] == "ai", repr(calls))
    ck("ocr order preserved",
       calls == ["ai", "vision", "tesseract", "ocrspace",
                 "google-vision"], repr(calls))
finally:
    OCR._ocr_stage = orig_stage
    OCR._extension_ocr = orig_ext

# preferred hit short-circuits the rest
calls.clear()


def hit_stage(name, image_bytes, lang, api_key):
    calls.append(name)
    return "text" if name == "ai" else ""


OCR._ocr_stage = hit_stage
try:
    ck("ocr preferred hit", OCR.ocr_text(b"img") == "text")
    ck("ocr short-circuit", calls == ["ai"], repr(calls))
finally:
    OCR._ocr_stage = orig_stage

# unknown pref -> default order
_C.save({"General": {"PreferredServices": {"ocr": "bogus"}}})
calls.clear()
OCR._ocr_stage = fake_stage
try:
    OCR.ocr_text(b"img")
    ck("ocr bogus pref default",
       calls == ["vision", "tesseract", "ocrspace", "google-vision",
                 "ai"], repr(calls))
finally:
    OCR._ocr_stage = orig_stage
_C.save({"General": {"PreferredServices": {"ocr": "ai",
                                           "tts": "bing"}}})

# ---- TTS: preferred backend first; "system" skips online ----------
from qtranslate import player as PL  # noqa: E402
from qtranslate import tts as TTS  # noqa: E402

order = []
orig_google, orig_bing = TTS.google_tts, TTS.bing_tts
orig_ext_be = PL._extension_backend
orig_play = getattr(PL, "_play_mp3_bytes_darwin", None)
orig_play_linux = getattr(PL, "_play_mp3_bytes_linux", None)
orig_play_win = getattr(PL, "play_mp3_bytes", None)
orig_stop = PL.stop


def g(text, lang, slow=False):
    order.append("google")
    return b"mp3"


def b(text, lang, slow=False):
    order.append("bing")
    return b"mp3"


PL._extension_backend = lambda *a, **k: None
PL.stop = lambda: None
if orig_play is not None:
    PL._play_mp3_bytes_darwin = lambda data, block=True: None
if orig_play_win is not None:
    # Windows/Linux playback shells out to bass.dll etc.; stub it so a
    # missing native lib cannot fall through to the next TTS backend
    PL.play_mp3_bytes = lambda data, block=True: None
if orig_play_linux is not None:
    PL._play_mp3_bytes_linux = lambda data, block=True: "mpv"
TTS.google_tts = g
TTS.bing_tts = b
try:
    order.clear()
    PL.play_text("hi", "en")
    ck("tts bing preferred first", order == ["bing"], repr(order))

    # preferred backend failing falls through to the other
    def bad(text, lang, slow=False):
        order.append("bing")
        raise RuntimeError("down")
    TTS.bing_tts = bad
    order.clear()
    PL.play_text("hi", "en")
    ck("tts fallback after pref fail",
       order == ["bing", "google"], repr(order))
    TTS.bing_tts = b

    # "system" skips both online fetches entirely
    _C.save({"General": {"PreferredServices": {"tts": "system"}}})
    spoke = []
    orig_speak = getattr(PL, "_speak_darwin", None)
    if orig_speak is not None:
        PL._speak_darwin = lambda text, lang="", slow=False: \
            spoke.append(text)
    # Windows "system" goes through system_tts.speak (SAPI SpVoice) --
    # stub it so the test never fires a real voice
    from qtranslate.services import system_tts as _ST
    orig_st = _ST.speak
    _ST.speak = lambda text, lang="", slow=False: \
        spoke.append(text) or True
    order.clear()
    try:
        PL.play_text("hi", "en")
    except Exception:
        pass
    ck("tts system skips online", order == [], repr(order))
    if orig_speak is not None:
        PL._speak_darwin = orig_speak
    _ST.speak = orig_st
finally:
    TTS.google_tts = orig_google
    TTS.bing_tts = orig_bing
    PL._extension_backend = orig_ext_be
    PL.stop = orig_stop
    if orig_play is not None:
        PL._play_mp3_bytes_darwin = orig_play
    if orig_play_win is not None:
        PL.play_mp3_bytes = orig_play_win
    if orig_play_linux is not None:
        PL._play_mp3_bytes_linux = orig_play_linux

# ---- Services page writer: display index -> backend key ----------
from PySide6.QtWidgets import QApplication  # noqa: E402
_qapp = QApplication.instance() or QApplication([])
from qtranslate.qt.options import services as SVC  # noqa: E402

ck("pref rows aligned",
   all(len(r[2]) == len(SVC._PREF_VALUES[r[0]])
       for r in SVC._PREF_ROWS), "row/value length mismatch")


class _FakeCombo:
    def __init__(self, idx):
        self._idx = idx

    def currentIndex(self):
        return self._idx


# index 1 of each row must write the first backend key
for role, row in (("tts", SVC._PREF_ROWS[0]),
                  ("spell", SVC._PREF_ROWS[1]),
                  ("ocr", SVC._PREF_ROWS[2])):
    _C.save({"General": {}})
    SVC._set_preferred(None, role, _FakeCombo(1))
    got = (_C.load().get("General", {})
           .get("PreferredServices", {}).get(role))
    ck("pref %s idx1 -> %s" % (role, SVC._PREF_VALUES[role][1]),
       got == SVC._PREF_VALUES[role][1], repr(got))
# index 0 writes "" (auto)
_C.save({"General": {}})
SVC._set_preferred(None, "tts", _FakeCombo(0))
got = (_C.load().get("General", {})
       .get("PreferredServices", {}).get("tts"))
ck("pref auto writes empty", got == "", repr(got))

_C.DEFAULT_PATH = _saved
try:
    os.unlink(_tmp)
except OSError:
    pass

if FAIL:
    print("\nregress_role_prefs: %d FAILURES" % len(FAIL))
    sys.exit(1)
print("\nregress_role_prefs: all checks ok")
